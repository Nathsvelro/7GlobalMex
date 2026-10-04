"""iNaturalist field photos: label mapping, Mexico rule, observer split, attribution, download.

  python model/inat_field.py --inat /home/user/data_raw/inat            # manifest + download
  python model/inat_field.py --inat /home/user/data_raw/inat --sheets DIR  # + contact sheets for screening
  python model/inat_field.py --inat /home/user/data_raw/inat --train-npz /home/user/data_proc/cafetal/field_train.npz

Inputs (iNaturalist open-data export, already filtered to the taxa below):
  <inat>/obs_coffee.tsv, <inat>/photos_coffee.tsv
Outputs:
  reports/field_inat_attribution.csv  (one row per photo: license, observer, label, split, rounded location)
  <inat>/photos/<label>/<photo_id>.<ext>  (images stay OUT of the repo: many are CC BY-NC / ND)

Split (decided once, seed 42, by OBSERVER so one person's photos are never in both train and test):
  field_test  = every photo of an observer who has any photo inside the Mexico box (all of them held out),
                plus a random ~30 % of the remaining observers of each disease label;
                American leaf spot (`ojo_de_gallo`, not one of our classes) is always test.
  field_train = the other roya / minador / cercospora photos (used by the v2 experiment only).
  coffea_eval = ~400 Coffea arabica photos from distinct observers (health unknown: never trained on,
                only used to measure how often the app answers a disease).
"""
import argparse
import csv
import math
import os
import random
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ATTRIBUTION = os.path.join(REPO, "reports", "field_inat_attribution.csv")
TAXA = {  # taxon_id -> (taxon name, our label)
    "328339": ("Hemileia vastatrix", "roya"),
    "328342": ("Hemileia", "roya"),
    "1331108": ("Leucoptera coffeella", "minador"),
    "1260640": ("Cercospora coffeicola", "cercospora"),
    "155172": ("Mycena citricolor", "ojo_de_gallo"),  # American leaf spot: NOT a model class -> desired DUDA
    "64342": ("Coffea arabica", "coffea"),  # coffee plant, health unknown
}
TRAIN_LABELS = ("roya", "minador", "cercospora")
URL = "https://inaturalist-open-data.s3.amazonaws.com/photos/{pid}/{size}.{ext}"

# ---------------------------------------------------------------- Mexico rule
MEXICO_BOX = (14.5, 32.7, -118.4, -86.7)  # lat min, lat max, lon min, lon max (crude: includes GT, BZ, HN, US)
# Simplified Mexico outline (lon, lat), ~40 vertices, accurate to roughly 5-15 km at the land borders; the
# sea sides run offshore. US border: Tijuana - Colorado river - Nogales line - El Paso - Rio Grande.
# South: Belize (Rio Hondo, 17.82 N line), Guatemala (90.98 W meridian, Usumacinta, 16.07 N line,
# straight lines to Tacana volcano, Suchiate river).
MEXICO_POLYGON = [
    (-117.12, 32.53), (-114.72, 32.72), (-114.81, 32.49), (-111.07, 31.33), (-108.21, 31.33), (-108.21, 31.78),
    (-106.53, 31.78), (-105.00, 30.68), (-104.40, 29.56), (-103.20, 28.98), (-102.40, 29.80), (-101.40, 29.77),
    (-100.90, 29.36), (-100.50, 28.70), (-99.50, 27.50), (-99.10, 26.50), (-98.27, 26.10), (-97.50, 25.88),
    (-97.14, 25.96), (-86.70, 25.96), (-86.70, 20.20), (-87.40, 18.60), (-87.84, 18.18), (-88.05, 18.40),
    (-88.30, 18.48), (-88.95, 17.95), (-89.15, 17.82), (-90.98, 17.82), (-90.98, 17.25), (-91.43, 17.25),
    (-91.00, 16.85), (-90.53, 16.49), (-90.44, 16.07), (-91.73, 16.07), (-91.99, 15.63), (-92.07, 15.26),
    (-92.11, 15.13), (-92.04, 15.05), (-92.13, 14.96), (-92.15, 14.68), (-92.24, 14.53), (-92.30, 14.30), (-96.50, 15.30), (-100.00, 16.40),
    (-102.20, 17.50), (-104.50, 18.60), (-106.00, 20.40), (-110.00, 22.60), (-112.50, 24.30), (-115.50, 27.70),
    (-116.90, 31.50), (-117.30, 32.50),
]
MEXICO_RULE = ("in_mexico = inside a simplified 52-vertex outline of Mexico (MEXICO_POLYGON in model/inat_field.py; "
               "ray-casting point-in-polygon on the observation's public lat/lon; borders accurate to roughly "
               "5-15 km). in_mexico_box = crude box lat 14.5..32.7, lon -118.4..-86.7 (also contains parts of "
               "Guatemala, Belize, Honduras and the southern US). Held out: every observer with any photo in the box.")


def in_box(lat, lon):
    return lat is not None and MEXICO_BOX[0] <= lat <= MEXICO_BOX[1] and MEXICO_BOX[2] <= lon <= MEXICO_BOX[3]


def in_mexico(lat, lon):
    if lat is None:
        return False
    inside, pts = False, MEXICO_POLYGON
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- manifest
def build_manifest(inat_dir, n_coffea=400, test_frac=0.3, seed=42):
    obs = {r["observation_uuid"]: r for r in csv.DictReader(open(os.path.join(inat_dir, "obs_coffee.tsv")),
                                                            delimiter="\t")}
    photos = list(csv.DictReader(open(os.path.join(inat_dir, "photos_coffee.tsv")), delimiter="\t"))
    rows = []
    for p in photos:
        o = obs[p["observation_uuid"]]
        if o["taxon_id"] not in TAXA:
            continue
        lat, lon = _f(o["latitude"]), _f(o["longitude"])
        name, label = TAXA[o["taxon_id"]]
        rows.append({"photo_id": p["photo_id"], "observation_uuid": p["observation_uuid"],
                     "observer_id": p["observer_id"], "license": p["license"], "taxon_name": name, "label": label,
                     "quality_grade": o["quality_grade"], "observed_on": o["observed_on"],
                     "lat": "" if lat is None else f"{lat:.1f}", "lon": "" if lon is None else f"{lon:.1f}",
                     "in_mexico_box": int(in_box(lat, lon)), "in_mexico": int(in_mexico(lat, lon)),
                     "ext": p["extension"].lower(), "position": int(p["position"]),
                     "inat_url": f"https://www.inaturalist.org/photos/{p['photo_id']}"})
    rng = random.Random(seed)
    disease = [r for r in rows if r["label"] != "coffea"]
    # observers with any photo in the box: all their disease photos are test
    test_obs = {r["observer_id"] for r in disease if r["in_mexico_box"]}
    for lab in TRAIN_LABELS:
        cand = sorted({r["observer_id"] for r in disease if r["label"] == lab} - test_obs, key=int)
        already = len({r["observer_id"] for r in disease if r["label"] == lab} & test_obs)
        rng.shuffle(cand)
        k = max(0, math.ceil(test_frac * (len(cand) + already)) - already)  # ~30 % of the label's observers
        test_obs |= set(cand[:k])
    for r in disease:
        r["split"] = "field_test" if (r["observer_id"] in test_obs or r["label"] == "ojo_de_gallo") else "field_train"
    train_obs = {r["observer_id"] for r in disease if r["split"] == "field_train"}
    # coffea: one photo (the observation's first) per observer, distinct observers, none from field_train observers
    first = [r for r in rows if r["label"] == "coffea" and r["position"] == 0 and r["observer_id"] not in train_obs]
    by_obs = {}
    for r in sorted(first, key=lambda r: int(r["photo_id"])):
        by_obs.setdefault(r["observer_id"], []).append(r)
    chosen_obs = sorted(by_obs, key=int)
    rng.shuffle(chosen_obs)
    coffea = []
    for ob in chosen_obs[:n_coffea]:
        r = rng.choice(by_obs[ob])
        r["split"] = "coffea_eval"
        coffea.append(r)
    out = disease + coffea
    out.sort(key=lambda r: (r["label"], r["split"], int(r["photo_id"])))
    return out


def write_attribution(rows, path=ATTRIBUTION):
    cols = ["photo_id", "observation_uuid", "observer_id", "license", "taxon_name", "label", "split",
            "quality_grade", "observed_on", "lat", "lon", "in_mexico_box", "in_mexico", "inat_url"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read_attribution(path=ATTRIBUTION):
    return list(csv.DictReader(open(path, newline="")))


def image_path(photos_dir, row):
    d = os.path.join(photos_dir, row["label"])
    for f in os.listdir(d) if os.path.isdir(d) else []:
        if f.split(".")[0] == row["photo_id"]:
            return os.path.join(d, f)
    return None


# ---------------------------------------------------------------- download
def download(rows, photos_dir, threads=8):
    def one(r):
        d = os.path.join(photos_dir, r["label"])
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, f"{r['photo_id']}.{r['ext']}")
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            return "cached"
        for size in ("medium", "small"):
            try:
                with urllib.request.urlopen(URL.format(pid=r["photo_id"], size=size, ext=r["ext"]), timeout=60) as resp:
                    data = resp.read()
                with open(dst + ".part", "wb") as fh:
                    fh.write(data)
                os.replace(dst + ".part", dst)
                return size
            except Exception as e:  # noqa: BLE001
                err = str(e)
        return "FAILED " + err

    with ThreadPoolExecutor(threads) as ex:
        res = list(ex.map(one, rows))
    from collections import Counter
    print("download:", dict(Counter(x.split(" ")[0] for x in res)))
    return res


def contact_sheets(rows, photos_dir, out_dir, per_sheet=30, cols=6, cell=220):
    from PIL import Image, ImageDraw
    os.makedirs(out_dir, exist_ok=True)
    by = {}
    for r in rows:
        if r["label"] != "coffea":
            by.setdefault(r["label"], []).append(r)
    for lab, rs in by.items():
        for s in range(0, len(rs), per_sheet):
            chunk = rs[s:s + per_sheet]
            nrow = math.ceil(len(chunk) / cols)
            sheet = Image.new("RGB", (cols * cell, nrow * (cell + 16)), "white")
            dr = ImageDraw.Draw(sheet)
            for i, r in enumerate(chunk):
                p = image_path(photos_dir, r)
                if not p:
                    continue
                im = Image.open(p).convert("RGB")
                im.thumbnail((cell, cell))
                x, y = (i % cols) * cell, (i // cols) * (cell + 16)
                sheet.paste(im, (x + (cell - im.size[0]) // 2, y))
                dr.text((x + 3, y + cell + 2), r["photo_id"], fill="black")
            sheet.save(os.path.join(out_dir, f"{lab}_{s // per_sheet:02d}.jpg"), quality=85)


def make_train_npz(rows, photos_dir, out, classes, screening, size=224, n_crops=6, min_side=0.6, seed=42):
    """Training views of the field_train photos that passed the screening (visible leaf symptom):
    the centre square + n_crops random squares (side 60-100 % of the short side, anywhere in the photo)."""
    import numpy as np
    from PIL import Image
    ok = {r["photo_id"] for r in csv.DictReader(open(screening)) if r["visible_leaf_symptom"] == "yes"}
    rng = random.Random(seed)
    xs, ys, groups, paths = [], [], [], []
    for r in rows:
        if r["split"] != "field_train" or r["label"] not in TRAIN_LABELS or r["photo_id"] not in ok:
            continue
        p = image_path(photos_dir, r)
        im = Image.open(p).convert("RGB")
        w, h = im.size
        s0 = min(w, h)
        boxes = [((w - s0) // 2, (h - s0) // 2, s0)]
        for _ in range(n_crops):
            s = int(s0 * rng.uniform(min_side, 1.0))
            boxes.append((rng.randint(0, w - s), rng.randint(0, h - s), s))
        for x, y, s in boxes:
            xs.append(np.asarray(im.crop((x, y, x + s, y + s)).resize((size, size), Image.BILINEAR), np.uint8))
            ys.append(classes.index(r["label"]))
            groups.append("inat:" + r["observer_id"])
            paths.append(p)
    np.savez(out, x=np.stack(xs), y=np.array(ys, np.int64), group=np.array(groups), path=np.array(paths))
    from collections import Counter
    print("field training views:", len(ys), {classes[k]: v for k, v in Counter(ys).items()},
          "photos:", len(set(paths)), "observers:", len(set(groups)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inat", required=True, help="folder with obs_coffee.tsv and photos_coffee.tsv")
    ap.add_argument("--photos", help="image folder (default <inat>/photos)")
    ap.add_argument("--n-coffea", type=int, default=400)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--sheets", help="write contact sheets of the disease photos to this folder")
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--train-npz", help="write training views of the screened field_train photos to this .npz")
    ap.add_argument("--classes", default="sano,roya,minador,phoma,cercospora,otro", help="model class order")
    args = ap.parse_args()
    photos = args.photos or os.path.join(args.inat, "photos")
    rows = build_manifest(args.inat, args.n_coffea)
    if not args.no_download:
        download(rows, photos, args.threads)
    missing = [r for r in rows if not image_path(photos, r)]
    if missing:
        print("dropping", len(missing), "photos that could not be downloaded:", [r["photo_id"] for r in missing],
              file=sys.stderr)
        rows = [r for r in rows if image_path(photos, r)]
    write_attribution(rows)
    from collections import Counter
    print(Counter((r["label"], r["split"]) for r in rows))
    print("in_mexico:", Counter(r["label"] for r in rows if r["in_mexico"] == 1),
          "in box:", Counter(r["label"] for r in rows if r["in_mexico_box"] == 1))
    if args.sheets:
        contact_sheets(rows, photos, args.sheets)
    if args.train_npz:
        make_train_npz(rows, photos, args.train_npz, args.classes.split(","),
                       os.path.join(REPO, "reports", "field_inat_screening.csv"))


if __name__ == "__main__":
    main()
