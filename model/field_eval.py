"""Field evaluation on iNaturalist photos: single view (app v1 rule) vs multicrop, one or more models.

  python model/field_eval.py --data /home/user/data_proc/cafetal --inat /home/user/data_raw/inat \
      --model v1=model/checkpoints/v1/cafetal.onnx --model v2=model/checkpoints/v2/cafetal_fp16_weights.onnx
  python model/field_eval.py --render      # only rewrite reports/field_eval.md from reports/field_eval.json

Writes reports/field_eval.json + reports/field_eval.md (+ reports/field_eval_photos.csv). Every photo is decided
exactly like the app: centre-square crop, resize to 224, blur check on the 128 px view (model/blur.py), threshold
from labels.json, "otro" -> fail-safe (SMS code UNSR, or OTHR for "otro"; internally "DUDA"); multicrop per
model/multicrop.py. Predictions are cached per model file hash (--cache), so a rerun needs the images only for the
blur check.
Inputs: reports/field_inat_attribution.csv + reports/field_inat_screening.csv (model/inat_field.py),
images in <inat>/photos/, JMuBEN/otro test split in <data>/test.npz.
Geographic report subsets (East Africa, Kenya): GEO_RULE below; they never change the split, training or threshold.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys

import numpy as np
from PIL import Image
from sklearn.metrics import f1_score

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blur import BLUR_SIZE, center_square, laplacian_variance, laplacian_variance_array  # noqa: E402
from inat_field import ATTRIBUTION, MEXICO_BOX, image_path, read_attribution  # noqa: E402
from multicrop import SCHEMES, decide_multicrop, decide_single, tiles, views  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENING = os.path.join(REPO, "reports", "field_inat_screening.csv")
DISEASES = ("roya", "minador", "phoma", "cercospora")
ANSWERS = ("sano", "roya", "minador", "phoma", "cercospora", "DUDA")  # "DUDA" = internal name of the fail-safe

# ---------------------------------------------------------------- geography (report subsets only)
# Our users farm in Kirinyaga County, central Kenya. These subsets only describe where the iNaturalist photos come
# from; they never change the split, the training data or the threshold. Input: the observation's public location
# as rounded to 0.1 degree (about 11 km) in reports/field_inat_attribution.csv.
EAST_AFRICA_BOX = (-11.8, 15.0, 28.8, 48.0)  # lat min, lat max, lon min, lon max
# Simplified outline of Kenya (lon, lat), 34 vertices, borders accurate to roughly 10-30 km (the coffee areas are
# far from the borders). Clockwise from the Kenya-Uganda-Tanzania point in Lake Victoria: Uganda (Busia, Malaba,
# Mt Elgon, Karamoja), South Sudan (Ilemi), Ethiopia (Lake Turkana, Moyale), Somalia (Mandera, 41 E line), the
# coast (Kiunga, Lamu, Malindi, Mombasa, Vanga), Tanzania (Lake Jipe, north of Kilimanjaro, Namanga line).
KENYA_POLYGON = [
    (33.92, -1.00), (33.95, 0.10), (34.09, 0.46), (34.27, 0.64), (34.55, 1.12), (34.82, 1.30), (35.02, 1.90),
    (34.90, 2.50), (34.45, 3.60), (33.99, 4.22), (34.39, 4.62), (35.30, 4.95), (35.92, 4.62), (36.04, 4.45),
    (36.85, 4.43), (38.10, 3.60), (39.05, 3.52), (39.85, 3.85), (40.77, 4.27), (41.17, 3.94), (41.90, 3.98),
    (41.00, 2.80), (40.99, -0.85), (41.56, -1.66), (40.90, -2.30), (40.20, -2.85), (40.12, -3.27), (39.68, -4.05),
    (39.20, -4.67), (37.75, -3.65), (37.60, -3.00), (36.79, -2.55), (35.00, -1.60), (34.40, -1.25),
]
GEO_RULE = ("East Africa = Kenya, Uganda, Tanzania, Rwanda, Burundi and Ethiopia, approximated by the box lat "
            "-11.8..15.0, lon 28.8..48.0 (EAST_AFRICA_BOX in model/field_eval.py; it also takes in eastern DR Congo, "
            "South Sudan, Somalia, Eritrea, Djibouti and northern Zambia, Malawi and Mozambique, so every photo inside "
            "it is listed in the report). Kenya = inside a simplified 34-vertex outline of Kenya (KENYA_POLYGON; "
            "ray-casting point-in-polygon; borders accurate to roughly 10-30 km). Both use the observation's public "
            "location as rounded to 0.1 degree (about 11 km) in reports/field_inat_attribution.csv. Report subsets "
            "only: they never change the split, the training data or the threshold.")
SPLIT_BOX_RULE = ("field test = every observer with any disease photo inside the fixed box lat {:.1f}..{:.1f}, lon "
                  "{:.1f}..{:.1f} (Mexico and northern Central America; `in_mexico_box` in the attribution CSV), plus "
                  "a random ~30 % of the other observers of each disease (seed 42, `model/inat_field.py`). The box was "
                  "fixed before any v2 result and is kept unchanged so the test set stays the same; it has no special "
                  "meaning for Kenya.").format(*MEXICO_BOX)
# placed by eye from the coordinates (not computed): the photos that fall inside EAST_AFRICA_BOX
PLACE_BY_EYE = {"92700141": "Kenya, near Nakuru", "631362214": "Kenya, Kiambu County near Limuru",
                "717871095": "Kenya, Taita Hills", "672111499": "Tanzania, Kilimanjaro slopes north of Moshi",
                "710570289": "Tanzania, Zanzibar (Unguja)",
                "621748067": "Lake Kivu shore, most likely Rwanda (positional accuracy 1.9 km; DR Congo is across the lake)"}


def in_polygon(lat, lon, pts):
    inside = False
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def geo_flags(lat, lon):
    """(in_east_africa, in_kenya) from the rounded public location; (False, False) if unknown."""
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False, False
    b = EAST_AFRICA_BOX
    return b[0] <= lat <= b[1] and b[2] <= lon <= b[3], in_polygon(lat, lon, KENYA_POLYGON)


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def session(path):
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.intra_op_num_threads = 4
    return ort.InferenceSession(path, so, providers=["CPUExecutionProvider"])


def run(sess, x, batch=64):
    name = sess.get_inputs()[0].name
    return np.concatenate([sess.run(None, {name: x[i:i + batch].astype(np.float32)})[0]
                           for i in range(0, len(x), batch)])


# ---------------------------------------------------------------- data
def load_rows(inat_dir, attribution=ATTRIBUTION, screening=SCREENING):
    rows = read_attribution(attribution)
    scr = {r["photo_id"]: r for r in csv.DictReader(open(screening))} if os.path.exists(screening) else {}
    photos = os.path.join(inat_dir, "photos")
    for r in rows:
        r["path"] = image_path(photos, r)
        s = scr.get(r["photo_id"])
        r["screened"] = s["visible_leaf_symptom"] if s else ""
        ea, ke = geo_flags(r["lat"], r["lon"])
        r["in_east_africa"], r["in_kenya"] = str(int(ea)), str(int(ke))
    return [r for r in rows if r["path"]]


def square_of(path):
    im = Image.open(path).convert("RGB")
    return center_square(im), laplacian_variance(im)


def predict_photos(sess, squares, size, cache=None):
    """Per photo: probabilities of the full view + every tile of every scheme. Cached by model hash."""
    if cache and os.path.exists(cache):
        z = np.load(cache)
        return {k: z[k] for k in z.files}
    full, tl = [], {s: [] for s in SCHEMES}
    for i in range(0, len(squares), 32):
        chunk = squares[i:i + 32]
        xs = [views(sq, size, "2x2") for sq in chunk]
        x3 = [views(sq, size, "3x3")[1:] for sq in chunk]
        p = run(sess, np.concatenate([np.concatenate([a, b]) for a, b in zip(xs, x3)]))
        p = p.reshape(len(chunk), 1 + 4 + 9, -1)
        full.append(p[:, 0])
        tl["2x2"].append(p[:, 1:5])
        tl["3x3"].append(p[:, 5:])
    out = {"full": np.concatenate(full), "2x2": np.concatenate(tl["2x2"]), "3x3": np.concatenate(tl["3x3"])}
    if cache:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        np.savez(cache, **out)
    return out


def decisions(pred, blur, classes, thr, blur_thr, method):
    """method: 'single' or 'mc:<scheme>:<k>'. Returns arrays (answer, reason)."""
    ans, why = [], []
    for i in range(len(blur)):
        if method == "single":
            a, r = decide_single(pred["full"][i], blur[i], classes, thr, blur_thr)
        else:
            _, scheme, k = method.split(":")
            a, r = decide_multicrop(pred["full"][i], pred[scheme][i], blur[i], classes, thr, blur_thr, int(k))
        ans.append(a)
        why.append(r or "")
    return np.array(ans), np.array(why)


# ---------------------------------------------------------------- tables
def group_stats(ans, why, label):
    """label: our class (roya/minador/cercospora), 'ojo_de_gallo' (desired DUDA) or 'coffea' (health unknown)."""
    n = len(ans)
    counts = {a: int((ans == a).sum()) for a in ANSWERS}
    duda = counts["DUDA"]
    st = {"n": n, "answer_counts": counts,
          "duda_reasons": {r: int(((ans == "DUDA") & (why == r)).sum()) for r in ("blurry", "not_coffee", "low_conf")},
          "DUDA": round(duda / n, 4) if n else None, "DUDA_ci95": wilson(duda, n)}
    if label == "coffea":
        k = int(sum(counts[d] for d in DISEASES))
        st.update(disease_answer=round(k / n, 4), disease_answer_ci95=wilson(k, n),
                  sano_answer=round(counts["sano"] / n, 4))
        return st
    correct = counts.get(label, 0) if label in DISEASES else 0
    wrong = n - duda - correct
    st.update(correct=round(correct / n, 4) if n else None, correct_ci95=wilson(correct, n),
              wrong_accepted=round(wrong / n, 4) if n else None, wrong_accepted_ci95=wilson(wrong, n),
              dangerous_sano=counts["sano"], dangerous_sano_rate=round(counts["sano"] / n, 4) if n else None,
              dangerous_sano_ci95=wilson(counts["sano"], n))
    return st


SCOPES = {"all_photos": None, "field_test": ("field_test", "coffea_eval"), "field_dev": ("field_train",)}


def field_groups(rows, splits=None):
    """Named photo subsets, restricted to the given splits (None = all photos)."""
    def sel(f):
        return np.array([bool(f(r)) and (splits is None or r["split"] in splits) for r in rows])
    g = {}
    for lab in ("roya", "minador", "cercospora", "ojo_de_gallo", "coffea"):
        name = "coffea sample" if lab == "coffea" else lab
        g[name] = (lab, sel(lambda r, lab=lab: r["label"] == lab))
        if lab != "coffea":
            g[f"{name} screened"] = (lab, sel(lambda r, lab=lab: r["label"] == lab and r["screened"] == "yes"))
        # geographic subsets (GEO_RULE); evaluate_model drops empty ones, the report shows them as n = 0
        g[f"{name} East Africa"] = (lab, sel(lambda r, lab=lab: r["label"] == lab and r["in_east_africa"] == "1"))
        g[f"{name} Kenya"] = (lab, sel(lambda r, lab=lab: r["label"] == lab and r["in_kenya"] == "1"))
    return g


def npz_eval(pred, y, blur, classes, thr, blur_thr, method):
    ans, _ = decisions(pred, blur, classes, thr, blur_thr, method)
    otro = classes.index("otro")
    coffee = y != otro
    truth = np.array(classes)[y]
    acc = coffee & (ans != "DUDA")
    sano = classes.index("sano")
    dis = coffee & (y != sano)
    return {"jmuben_macro_f1_argmax": round(float(f1_score(y, pred["full"].argmax(1), average="macro")), 4),
            "jmuben_coffee_correct_accepted": round(float((ans[coffee] == truth[coffee]).mean()), 4),
            "jmuben_coffee_DUDA": round(float((ans[coffee] == "DUDA").mean()), 4),
            "jmuben_coffee_wrong_accepted": round(float((acc & (ans != truth))[coffee].mean()), 4),
            "jmuben_diseased_called_sano": round(float((ans[dis] == "sano").mean()), 4),
            "jmuben_diseased_called_sano_n": int((ans[dis] == "sano").sum()),
            # app-level macro-F1 over the 5 coffee classes (DUDA counts as a miss)
            "jmuben_app_macro_f1": round(float(f1_score(truth[coffee], ans[coffee],
                                                        labels=[c for c in classes if c != "otro"],
                                                        average="macro", zero_division=0)), 4),
            "otro_n": int((~coffee).sum()),
            "otro_rejected": round(float((ans[~coffee] == "DUDA").mean()), 4),
            "otro_rejected_ci95": wilson(int((ans[~coffee] == "DUDA").sum()), int((~coffee).sum())),
            "otro_disease_answer": round(float(np.isin(ans[~coffee], DISEASES).mean()), 4)}


def file_hash(path):
    return hashlib.sha1(open(path, "rb").read()).hexdigest()[:12]


def evaluate_model(model_path, labels, rows, squares, blur, npz, cache_dir, methods):
    classes, size = labels["classes"], labels["input"]["size"]
    thr, blur_thr = labels["threshold"], labels["blur_threshold"]
    sess = session(model_path)
    h = file_hash(model_path)
    pred = predict_photos(sess, squares, size, os.path.join(cache_dir, f"inat_{h}_{len(rows)}.npz") if cache_dir else None)
    out = {"model": os.path.relpath(model_path, REPO), "sha1_12": h, "threshold": thr, "blur_threshold": blur_thr,
           "methods": {}}
    te_pred = None
    if npz is not None:
        cache = os.path.join(cache_dir, f"test_{h}.npz") if cache_dir else None
        te_pred = predict_photos(sess, [Image.fromarray(a) for a in npz["x"]], size, cache)
    per_photo = {}
    for m in methods:
        ans, why = decisions(pred, blur, classes, thr, blur_thr, m)
        per_photo[m] = ans
        res = {scope: {} for scope in SCOPES}
        for scope, splits in SCOPES.items():
            for name, (lab, mask) in field_groups(rows, splits).items():
                if mask.any():
                    res[scope][name] = group_stats(ans[mask], why[mask], lab)
        if te_pred is not None:
            res["jmuben_otro_test"] = npz_eval(te_pred, npz["y"], npz["blur"], classes, thr, blur_thr, m)
        out["methods"][m] = res
    return out, pred, per_photo


def npz_with_blur(path):
    te = np.load(path)
    x = te["x"]
    blur = np.where(np.isnan(te["blur"]), [laplacian_variance_array(np.asarray(Image.fromarray(a).resize(
        (BLUR_SIZE, BLUR_SIZE), Image.BILINEAR))) for a in x], te["blur"])
    return {"x": x, "y": te["y"], "blur": blur}


# ---------------------------------------------------------------- report
def pct(v):
    return "n/a" if v is None else f"{100 * v:.1f}%"


def ci(c):
    return "" if not c or c[0] is None else f" [{100 * c[0]:.0f}-{100 * c[1]:.0f}]"


def field_dangerous(res):
    """diseased field-test photos (roya, minador, cercospora, American leaf spot) accepted as 'sano'."""
    return sum(res["field_test"][g]["answer_counts"]["sano"] for g in ("roya", "minador", "cercospora", "ojo_de_gallo")
               if g in res["field_test"])


def select_scheme(model_path, labels, rows, squares, blur, data, cache_dir, schemes):
    """Pre-registered multicrop choice, made on the baseline model WITHOUT the field test: among schemes whose
    otro rejection on the VALIDATION split is >= 98 %, maximise roya correct on the field-dev photos
    (field_train split, never seen by the baseline), then validation coffee correct-and-accepted, then fewer crops."""
    classes, size = labels["classes"], labels["input"]["size"]
    thr, blur_thr = labels["threshold"], labels["blur_threshold"]
    sess = session(model_path)
    h = file_hash(model_path)
    va = npz_with_blur(os.path.join(data, "val.npz"))
    pv = predict_photos(sess, [Image.fromarray(a) for a in va["x"]], size,
                        os.path.join(cache_dir, f"val_{h}.npz") if cache_dir else None)
    pf = predict_photos(sess, squares, size, os.path.join(cache_dir, f"inat_{h}_{len(rows)}.npz") if cache_dir else None)
    dev = np.array([r["split"] == "field_train" and r["label"] == "roya" for r in rows])
    table = []
    for m in schemes:
        v = npz_eval(pv, va["y"], va["blur"], classes, thr, blur_thr, m)
        ans, _ = decisions(pf, blur, classes, thr, blur_thr, m)
        n_tiles = len(tiles(m.split(":")[1]))
        table.append({"method": m, "val_otro_rejected": v["otro_rejected"],
                      "val_coffee_correct_accepted": v["jmuben_coffee_correct_accepted"],
                      "field_dev_roya_n": int(dev.sum()), "field_dev_roya_correct": round(float((ans[dev] == "roya").mean()), 4),
                      "inferences": 1 + n_tiles})
    ok = [t for t in table if t["val_otro_rejected"] >= 0.98]
    best = max(ok, key=lambda t: (t["field_dev_roya_correct"], t["val_coffee_correct_accepted"], -t["inferences"]))
    return best["method"], table


def ship_rule(base, cand):
    b, c = base, cand
    bt, ct = b["jmuben_otro_test"], c["jmuben_otro_test"]
    checks = {
        "field_roya_correct_gain>=10pts": round(c["field_test"]["roya"]["correct"] - b["field_test"]["roya"]["correct"], 4) >= 0.10,
        "jmuben_macro_f1_drop<=1pt": (bt["jmuben_macro_f1_argmax"] - ct["jmuben_macro_f1_argmax"] <= 0.01 + 1e-9 and
                                     bt["jmuben_app_macro_f1"] - ct["jmuben_app_macro_f1"] <= 0.01 + 1e-9),
        "otro_rejection>=98%": ct["otro_rejected"] >= 0.98,
        "dangerous_not_increased": (field_dangerous(c) <= field_dangerous(b) and
                                    ct["jmuben_diseased_called_sano_n"] <= bt["jmuben_diseased_called_sano_n"]),
        "coffea_disease_rate_rise<=5pts": round(c["field_test"]["coffea sample"]["disease_answer"] -
                                                 b["field_test"]["coffea sample"]["disease_answer"], 4) <= 0.05,
    }
    return {"checks": checks, "passes": all(checks.values())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", action="store_true",
                    help="only rewrite reports/field_eval.md from reports/field_eval.json (+ the threshold test and "
                         "model/ship_decision.json); no images or models needed")
    ap.add_argument("--data")
    ap.add_argument("--inat")
    ap.add_argument("--model", action="append",
                    help="name=path.onnx[:labels.json] (repeatable; the FIRST one is the baseline = shipped v1)")
    ap.add_argument("--schemes", default="mc:2x2:2,mc:2x2:3,mc:3x3:2,mc:3x3:3")
    ap.add_argument("--cache", default=os.path.join(REPO, "model", "checkpoints", "field_cache"))
    ap.add_argument("--out", default=os.path.join(REPO, "reports"))
    args = ap.parse_args()
    if args.render:
        res = json.load(open(os.path.join(args.out, "field_eval.json")))
        with open(os.path.join(args.out, "field_eval.md"), "w") as fh:
            fh.write(render_md(res))
        print("wrote", os.path.join(args.out, "field_eval.md"))
        return
    if not (args.data and args.inat and args.model):
        ap.error("--data, --inat and --model are required (or use --render)")
    rows = load_rows(args.inat)
    sq = [square_of(r["path"]) for r in rows]
    squares, blur = [s for s, _ in sq], np.array([b for _, b in sq])
    npz = npz_with_blur(os.path.join(args.data, "test.npz"))
    specs = []
    for spec in args.model:
        name, rest = spec.split("=", 1)
        mpath, _, lpath = rest.partition(":")
        specs.append((name, mpath, json.load(open(lpath or os.path.join(REPO, "app", "model", "labels.json")))))
    schemes = args.schemes.split(",")
    mc, sel_table = select_scheme(specs[0][1], specs[0][2], rows, squares, blur, args.data, args.cache, schemes)
    print("multicrop scheme (chosen on validation + field-dev, baseline model):", mc)
    res = {"generated_by": "model/field_eval.py", "n_photos": len(rows), "split_rule": SPLIT_BOX_RULE,
           "geo_rule": GEO_RULE,
           "multicrop": {"chosen": mc, "selection": sel_table,
                         "rule": " ".join(select_scheme.__doc__.split(":", 1)[1].split()).rstrip(".")},
           "photos": photo_summary(rows), "models": {}}
    per_photo, geo_cfg = {}, []
    app_labels = json.load(open(os.path.join(REPO, "app", "model", "labels.json")))
    app_sha = file_hash(os.path.join(REPO, "app", "model", app_labels["file"]))
    for name, mpath, labels in specs:
        out, pred, per_photo[name] = evaluate_model(mpath, labels, rows, squares, blur, npz, args.cache,
                                                    ["single"] + schemes)
        out["version"] = labels.get("version")
        res["models"][name] = out
        geo_cfg.append((f"{name}@{labels['threshold']}", pred, labels))
        if out["sha1_12"] == app_sha and app_labels["threshold"] != labels["threshold"]:  # the app's threshold
            geo_cfg.append((f"{name}@{app_labels['threshold']}", pred, dict(labels, threshold=app_labels["threshold"])))
        for m, r in out["methods"].items():
            ft = r["field_test"]
            print(name, m, "roya test correct", pct(ft["roya"]["correct"]), "coffea disease",
                  pct(ft["coffea sample"]["disease_answer"]), "otro rej", pct(r["jmuben_otro_test"]["otro_rejected"]),
                  "jmuben F1", r["jmuben_otro_test"]["jmuben_macro_f1_argmax"], flush=True)
    base_name = specs[0][0]
    base = res["models"][base_name]["methods"]["single"]
    cands = [(base_name, mc)] + [(n, m) for n, _, _ in specs[1:] for m in ("single", mc)]
    decision = {}
    for n, m in cands:
        decision[f"{n}+{m}"] = ship_rule(base, res["models"][n]["methods"][m])
    passing = [(n, m) for n, m in cands if decision[f"{n}+{m}"]["passes"]]
    if passing:
        n, m = max(passing, key=lambda nm: (res["models"][nm[0]]["methods"][nm[1]]["field_test"]["roya"]["correct"],
                                            nm[1] == "single"))
        fired = (f"SHIP {n}+{m}: passes all five conditions vs {base_name} single view"
                 + (" (highest field-test roya correct among passing candidates)" if len(passing) > 1 else ""))
    else:
        n, m = base_name, "single"
        fired = f"KEEP {base_name} single view: no candidate passes all five conditions"
    res["ship_rule"] = {"baseline": f"{base_name}+single", "candidates": decision, "shipped": f"{n}+{m}", "fired": fired}
    print(fired)
    res["geo"] = geo_summary(rows, blur, geo_cfg, args.inat)
    print("East Africa photos:", {k: v["east_africa"] for k, v in res["geo"]["counts"]["all_photos"].items()},
          "Kenya:", {k: v["kenya"] for k, v in res["geo"]["counts"]["all_photos"].items()})
    with open(os.path.join(args.out, "field_eval_photos.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        keys = [(n, m) for n in res["models"] for m in ("single", mc)]
        w.writerow(["photo_id", "label", "split", "screened", "in_east_africa", "in_kenya"] +
                   [f"{n}_{m}" for n, m in keys])
        for i, r in enumerate(rows):
            w.writerow([r["photo_id"], r["label"], r["split"], r["screened"], r["in_east_africa"], r["in_kenya"]] +
                       [per_photo[n][m][i] for n, m in keys])
    with open(os.path.join(args.out, "field_eval.json"), "w") as fh:
        json.dump(res, fh, indent=1)
    with open(os.path.join(args.out, "field_eval.md"), "w") as fh:
        fh.write(render_md(res))
    print("wrote", os.path.join(args.out, "field_eval.md"))


def photo_summary(rows):
    from collections import Counter
    out = {}
    for lab in ("roya", "minador", "cercospora", "ojo_de_gallo", "coffea"):
        rs = [r for r in rows if r["label"] == lab]
        out[lab] = {"photos": len(rs), "observations": len({r["observation_uuid"] for r in rs}),
                    "observers": len({r["observer_id"] for r in rs}),
                    "split": dict(Counter(r["split"] for r in rs)),
                    "screened_yes": sum(r["screened"] == "yes" for r in rs) if lab != "coffea" else None,
                    "in_split_box": sum(r["in_mexico_box"] == "1" for r in rs),
                    "in_east_africa": sum(r["in_east_africa"] == "1" for r in rs),
                    "in_kenya": sum(r["in_kenya"] == "1" for r in rs),
                    "licenses": dict(Counter(r["license"] for r in rs)),
                    "quality_grade": dict(Counter(r["quality_grade"] for r in rs))}
    return out


def geo_summary(rows, blur, configs, inat_dir=None):
    """East Africa / Kenya subsets (GEO_RULE): photo counts per label and split, and every East African photo with
    the app's answer for each (model, threshold) in configs = [(key, predictions, labels), ...]. With inat_dir, also
    the taxa of all observations inside the East Africa box in the metadata export (<inat>/obs_coffee.tsv)."""
    from collections import Counter
    counts = {}
    for scope, splits in SCOPES.items():
        counts[scope] = {}
        for lab in ("roya", "minador", "cercospora", "ojo_de_gallo", "coffea"):
            rs = [r for r in rows if r["label"] == lab and (splits is None or r["split"] in splits)]
            counts[scope][lab] = {"n": len(rs), "east_africa": sum(r["in_east_africa"] == "1" for r in rs),
                                  "kenya": sum(r["in_kenya"] == "1" for r in rs)}
    answers = {}
    for key, pred, lab in configs:
        answers[key] = decisions(pred, blur, lab["classes"], lab["threshold"], lab["blur_threshold"], "single")
    photos = []
    for i, r in enumerate(rows):
        if r["in_east_africa"] != "1":
            continue
        top = {}
        for key, pred, lab in configs:
            k = int(np.argmax(pred["full"][i]))
            top[key] = [lab["classes"][k], round(float(pred["full"][i][k]), 3)]
        photos.append({"photo_id": r["photo_id"], "label": r["label"], "split": r["split"], "lat": r["lat"],
                       "lon": r["lon"], "in_kenya": r["in_kenya"] == "1", "place_by_eye": PLACE_BY_EYE.get(r["photo_id"], ""),
                       "license": r["license"], "quality_grade": r["quality_grade"], "observed_on": r["observed_on"],
                       "inat_url": r["inat_url"], "answers": {key: str(answers[key][0][i]) for key, _, _ in configs},
                       "top1": top})
    dis = [r for r in rows if r["split"] == "field_test" and r["label"] != "coffea"]
    americas = sum(r["lon"] != "" and float(r["lon"]) < -30 for r in dis)  # crude: west of 30 W
    export = None
    obs = os.path.join(inat_dir, "obs_coffee.tsv") if inat_dir else None
    if obs and os.path.exists(obs):
        from inat_field import TAXA
        b = EAST_AFRICA_BOX
        export = Counter()
        for o in csv.DictReader(open(obs), delimiter="\t"):
            try:
                lat, lon = float(o["latitude"]), float(o["longitude"])
            except (TypeError, ValueError):
                continue
            if o["taxon_id"] in TAXA and b[0] <= lat <= b[1] and b[2] <= lon <= b[3]:
                export[TAXA[o["taxon_id"]][0]] += 1
        export = {name: export.get(name, 0) for name, _ in TAXA.values()}
    return {"rule": GEO_RULE, "configs": [key for key, _, _ in configs], "counts": counts, "photos": photos,
            "field_test_disease_americas": americas, "export_box_by_taxon": export,
            "note": "answers decided exactly like the app (single view); 'DUDA' = the fail-safe (SMS code UNSR, or "
                    "OTHR when the top class is otro); place_by_eye is read by eye from the coordinates, not computed"}


# ---------------------------------------------------------------- markdown
ALARMS = os.path.join(REPO, "reports", "field_coffea_v2_alarms.csv")
THRESHOLD_TEST = os.path.join(REPO, "reports", "field_v2_threshold_test.json")
THRESHOLD_SWEEP = os.path.join(REPO, "reports", "field_v2_threshold_sweep.json")
GEO_NAMES = ("East Africa", "Kenya")
WORDS = ("Words used below: **UNSR** = the app's fail-safe answer \"I'm not sure - show the leaf to the extension "
         "officer\" (blurry photo, top-1 probability below the threshold, or top class `otro` = not a coffee leaf; the "
         "observation SMS then carries code UNSR, or OTHR for `otro`). Class names are the model's internal labels: "
         "`sano` healthy, `roya` leaf rust, `minador` leaf miner, `phoma` Phoma leaf spot, `cercospora` brown eye "
         "spot, `otro` not a coffee leaf; `ojo_de_gallo` (a table key) is American leaf spot (*Mycena citricolor*), not a "
         "model class.")
JMUBEN_KENYA = ("The model's main held-out test set **is** Kenyan: JMuBEN, photographed in the Mutira coffee plantation, "
                "Kirinyaga County, with a digital camera and a pathologist's help (Jepkoech et al. 2021, *Data in Brief* "
                "36:107142) - the same county as our users. Its limits: one plantation, one camera, 128 px close-up "
                "crops, many augmented copies of each source photo (we split by near-duplicate group), and very few "
                "distinct healthy photos (`sano`: 2 source groups in test, 7 in train).")


def english(text):
    """Report wording in the app's language: the fail-safe is UNSR / "I'm not sure" (it was called DUDA / "No estoy
    seguro" when these results were produced; the JSON keys keep the old internal name "DUDA"). Applied to text that
    comes from other files too (model/ship_decision.json, model/field_threshold.py)."""
    text = text.replace("\"No estoy seguro\"", "\"I'm not sure\"")
    return re.sub(r"\bDUDA\b", "UNSR", text)


def geo_groups_missing(scope_res):
    """Geographic groups with no photo in this scope (evaluate_model drops empty groups)."""
    return [g for g in GROUP_ORDER if g.endswith(GEO_NAMES) and g not in scope_res]


def ea_count(r, scope, labels=("roya", "minador", "cercospora", "ojo_de_gallo")):
    c = r.get("geo", {}).get("counts", {}).get(scope, {})
    return sum(c[lab]["east_africa"] for lab in labels if lab in c) if c else None


def geo_answer_counts(r, key, label="coffea", splits=("coffea_eval",), kenya=False):
    """(disease answers, n) for the East African (or Kenyan) photos of one label, for one (model, threshold) key."""
    ph = [p for p in r.get("geo", {}).get("photos", []) if p["label"] == label and p["split"] in splits
          and (p["in_kenya"] or not kenya) and key in p["answers"]]
    return sum(p["answers"][key] in DISEASES for p in ph), len(ph)


def localize_tradeoff(text, r):
    """The 'Threshold trade-off' section is rendered by model/field_threshold.py from
    reports/field_v2_threshold_test.json (numbers, rule and decision unchanged). Its rows for the old hold-out region
    (roya in the split box / in Mexico, Coffea in Mexico) are replaced by the East Africa / Kenya subsets of the same
    test photos (GEO_RULE; decided by this script from the same cached predictions)."""
    from field_threshold import ci as ci1, pct as pct1
    keys = r.get("geo", {}).get("configs", [])
    out = []
    for line in text.split("\n"):
        if line.startswith("| roya: correct & accepted, Mexico+Guatemala box"):
            cols = line.count("|") - 2
            n_ea = ea_count(r, "field_test", ("roya",))
            out.append("| roya: correct & accepted, East Africa | " + " | ".join(
                [f"n = {n_ea} (no photos)" if n_ea == 0 else "see field_eval.json"] * cols) + " |")
            continue
        if line.startswith("| roya: correct & accepted, Mexico only"):
            continue
        if line.startswith("| Coffea test sample Mexico"):
            head = text.split("| metric |", 1)[1].split("\n", 1)[0]
            cfgs = [c.strip() for c in head.strip(" |").split("|")]
            for name, kenya in (("East Africa", False), ("Kenya", True)):
                vals = []
                for c in cfgs:
                    if c not in keys:
                        vals.append("n/a")
                        continue
                    k, n = geo_answer_counts(r, c, kenya=kenya)
                    vals.append(f"{pct1(k / n)}{ci1(wilson(k, n))} ({k}/{n})" if n else "n = 0")
                out.append(f"| Coffea test sample {name}: disease answers | " + " | ".join(vals) + " |")
            continue
        out.append(line)
    text = "\n".join(out)
    n_ea = ea_count(r, "field_test", ("roya",))
    text = re.sub(r"proxy for field photos from Kirinyaga, n is small \((\d+) rust photos\)",
                  lambda m: f"proxy for field photos from Kirinyaga, n is small ({m.group(1)} rust photos, "
                            f"{n_ea} from East Africa)", text)
    return text


def conclusions(r):
    models, names = r["models"], list(r["models"])
    base, mc = names[0], r["multicrop"]["chosen"]
    b = models[base]["methods"]["single"]
    ba = b["all_photos"]
    roya = ba["roya"]
    n_ea = ea_count(r, "field_test")
    ea_txt = (f"no field-test disease photo is from East Africa (n = {n_ea})" if n_ea == 0 else
              f"{n_ea} field-test disease photos are from East Africa")
    L = [f"- **{base} does not work on field photos.** Of {roya['n']} iNaturalist roya photos it answered "
         f"{roya['answer_counts']['roya']} correctly; {pct(roya['DUDA'])} got the fail-safe DUDA, almost all because the "
         f"model called the photo \"not a coffee leaf\" (`otro`: {roya['duda_reasons']['not_coffee']} photos). Same on "
         f"photos with a clearly visible symptom ({ba['roya screened']['answer_counts']['roya']} of "
         f"{ba['roya screened']['n']}). It is safe (0 diseased photos called \"sano\") but not useful in the field: it "
         "only recognises close-ups that look like the Kenyan 128 px training crops.",
         f"- **Multicrop alone does not help {base}**: with `{mc}` it still finds "
         f"{models[base]['methods'][mc]['all_photos']['roya']['answer_counts']['roya']} roya photos and adds a few wrong "
         "answers; looking at parts of the photo does not close the domain gap."]
    for n in names[1:]:
        x = models[n]["methods"]["single"]
        f, bt = x["field_test"], b["field_test"]
        jt, bj = x["jmuben_otro_test"], b["jmuben_otro_test"]
        L.append(f"- **{n} (trained with field photos) at its export threshold {models[n]['threshold']} finds rust in field "
                 f"photos**: roya correct & accepted "
                 f"{pct(f['roya']['correct'])}{ci(f['roya']['correct_ci95'])} on the held-out field test (n={f['roya']['n']}, "
                 f"{pct(bt['roya']['correct'])} for {base}); {ea_txt}. Minador {f['minador']['answer_counts']['minador']} "
                 f"of {f['minador']['n']}, cercospora {f['cercospora']['answer_counts']['cercospora']} of "
                 f"{f['cercospora']['n']} ({f['cercospora']['answer_counts']['roya']} called roya). Kenyan test macro-F1 "
                 f"{jt['jmuben_macro_f1_argmax']:.4f} ({base}: {bj['jmuben_macro_f1_argmax']:.4f}); no diseased leaf "
                 "was called \"sano\"." if field_dangerous(x) == 0 and jt["jmuben_diseased_called_sano_n"] == 0 else
                 f"- **{n}**: roya correct {pct(f['roya']['correct'])}{ci(f['roya']['correct_ci95'])} (n={f['roya']['n']}).")
        L.append(f"- **But {n} at {models[n]['threshold']} raises false alarms**: disease answers on the Coffea plant photos "
                 f"{pct(f['coffea sample']['disease_answer'])}{ci(f['coffea sample']['disease_answer_ci95'])} "
                 f"({base}: {pct(bt['coffea sample']['disease_answer'])}); non-coffee test images rejected "
                 f"{pct(jt['otro_rejected'])} ({base}: {pct(bj['otro_rejected'])}); American leaf spot sent to DUDA "
                 f"{pct(f['ojo_de_gallo']['DUDA'])} ({base}: {pct(bt['ojo_de_gallo']['DUDA'])}), "
                 f"{f['ojo_de_gallo']['answer_counts']['roya']} of {f['ojo_de_gallo']['n']} called roya. "
                 f"Multicrop makes both sides bigger ({pct(models[n]['methods'][mc]['field_test']['roya']['correct'])} "
                 f"roya, {pct(models[n]['methods'][mc]['field_test']['coffea sample']['disease_answer'])} Coffea disease answers).")
    if os.path.exists(ALARMS):
        al = list(csv.DictReader(open(ALARMS)))
        no = sum(a["visible_leaf_symptom"] == "no" for a in al)
        L.append(f"- **Why**: in a visual check of the {len(al)} Coffea photos that v2 answers with a disease "
                 f"(`reports/field_coffea_v2_alarms.csv`, one rater, thumbnails), {no} show no visible leaf symptom "
                 "(cherries in a hand, flowers, healthy-looking leaves). The field training photos are all diseased "
                 "and there are no labelled healthy field leaves, so the model partly learned \"field photo of a "
                 "coffee plant\" = roya.")
    blurry = sum(ba[g]["duda_reasons"]["blurry"] for g in ("roya", "minador", "cercospora", "ojo_de_gallo", "coffea sample"))
    L.append(f"- The blur check fired on {blurry} of {r['n_photos']} photos: these are sharp ~500 px photos; it is "
             "meant for shaky phone shots, which this test does not contain.")
    if os.path.exists(SCREENING):
        doubt = [x for x in csv.DictReader(open(SCREENING)) if "label may be wrong" in x["note"]]
        if doubt:
            L.append(f"- Label noise: {len(doubt)} roya-labelled photos (one observation series, split "
                     f"`{doubt[0]['split']}`) look like brown eye spot (Cercospora) to us; we kept the iNaturalist label "
                     "and did not drop them" + (" - so v2 trained on them as roya, which may add to cercospora being "
                                               "called roya." if doubt[0]["split"] == "field_train" else "."))
    tt = json.load(open(THRESHOLD_TEST)) if os.path.exists(THRESHOLD_TEST) else None
    from field_threshold import f2_margin, team_decision
    team = team_decision(tt.get("candidate")) if tt else None
    if team:
        c = tt["evaluations"][tt["candidate"]]
        f, j = c["field_test"], c["jmuben_otro_test"]

        from field_threshold import ci as ci1

        def n_of(g, key="correct"):
            a = f[g]["answer_counts"]
            return (a["DUDA"] if key == "DUDA" else sum(a[d] for d in DISEASES) if key == "disease_answer"
                    else a[g.split(" ")[0]]), f[g]["n"]

        def k(g, key="correct"):
            return "{} of {}".format(*n_of(g, key))

        def rate(g, key="correct", with_ci=False):  # from exact counts (the stored rates are rounded)
            x, n = n_of(g, key)
            return pct(x / n) + (ci1(f[g][key + "_ci95"]) if with_ci else "")
        ke, ne = geo_answer_counts(r, tt["candidate"])
        kk, nk = geo_answer_counts(r, tt["candidate"], kenya=True)
        L.append(f"- **v2 at t = {tt['chosen_t']:.2f} (re-chosen on calibration data; the model the app now ships)**: "
                 f"roya correct & accepted {rate('roya', with_ci=True)} ({k('roya')}), "
                 f"screened {rate('roya screened')} ({k('roya screened')}); "
                 f"minador {k('minador')}, cercospora {k('cercospora')}; American leaf spot sent to DUDA "
                 f"{rate('ojo_de_gallo', 'DUDA')} ({k('ojo_de_gallo', 'DUDA')}); disease answers on the Coffea plant "
                 f"photos {rate('coffea sample', 'disease_answer', True)} ({k('coffea sample', 'disease_answer')}; "
                 f"East Africa {ke} of {ne}, Kenya {kk} of {nk}); "
                 f"non-coffee test images rejected {pct(j['otro_rejected'])}; "
                 f"diseased called \"sano\": {field_dangerous(c)} (field) and {j['jmuben_diseased_called_sano_n']} (JMuBEN). "
                 f"The cost: {pct(j['jmuben_coffee_DUDA'])} of Kenyan test close-ups go to DUDA "
                 f"({pct(tt['evaluations'][tt['baseline']]['jmuben_otro_test']['jmuben_coffee_DUDA'])} for {tt['baseline']}).")
        fb, fc, drop = f2_margin(tt)
        L.append(f"- **Decision**: the pre-registered rule kept `{r['ship_rule']['shipped']}` in the first comparison "
                 f"({r['ship_rule']['fired']}) and says {tt['decision']} for v2 at t = {tt['chosen_t']:.2f}, which misses "
                 f"condition (2) by {drop - 1:.2f} points (app-level macro-F1 {fc:.4f} vs {fb:.4f}). **The team shipped "
                 f"v2 at t = {tt['chosen_t']:.2f} anyway** ({team['date']}), as an explicit, documented exception "
                 f"(see \"Result\"): {team['reason']}")
    else:
        L.append(f"- **Decision**: {r['ship_rule']['fired']}. The app keeps `{r['ship_rule']['shipped']}`: it stays safe "
                 "(DUDA, \"show the leaf to the officer\") rather than giving confident wrong answers.")
    L += [f"- **Kenya**: {ea_txt}, so this proxy says nothing specific about field photos "
          "from Kirinyaga; the only Kenyan evidence is the JMuBEN test split (lab-like close-ups from one plantation "
          "in Kirinyaga; `reports/model_eval.md`). See \"East Africa and Kenya\" below.",
          "- **What would fix it**: labelled photos from Kirinyaga farms, healthy *and* diseased, taken with the app - "
          "exactly what the extension officer's confirmations in the hub (`labels` table) collect - then rerun this "
          "protocol (`model/inat_field.py`, `model/train.py --extra`, `model/field_eval.py`). Healthy field leaves "
          "labelled by a person are the missing piece; we did not label iNaturalist *Coffea* photos as healthy because "
          "their health is unknown."]
    return L


GROUP_ORDER = ["roya", "roya screened", "roya East Africa", "roya Kenya", "minador", "minador screened",
               "minador East Africa", "minador Kenya", "cercospora", "cercospora screened", "cercospora East Africa",
               "cercospora Kenya", "ojo_de_gallo", "ojo_de_gallo screened", "ojo_de_gallo East Africa",
               "ojo_de_gallo Kenya", "coffea sample", "coffea sample East Africa", "coffea sample Kenya"]


def exact_rate(st, group, key):
    """Rate from the exact answer counts (the stored rates are rounded to 4 decimals; re-rounding them can be off by
    0.1 point). key: correct | DUDA | wrong_accepted | disease_answer | sano_answer."""
    a, n = st["answer_counts"], st["n"]
    lab = group.split(" ")[0]
    k = {"correct": a.get(lab, 0) if lab in DISEASES else 0, "DUDA": a["DUDA"],
         "disease_answer": sum(a[d] for d in DISEASES), "sano_answer": a["sano"]}
    k["wrong_accepted"] = n - a["DUDA"] - k["correct"]
    return k[key] / n if n else None


def group_table(scope_res):
    L = ["| group (true label) | n | correct & accepted [95% CI] | wrong but accepted | of which \"sano\" (dangerous) | "
         "UNSR [95% CI] | answers: sano / roya / minador / phoma / cercospora / UNSR |", "|---|---|---|---|---|---|---|"]
    for g in GROUP_ORDER:
        if g not in scope_res:
            continue
        st = scope_res[g]
        a = st["answer_counts"]
        cnt = " / ".join(str(a[k]) for k in ANSWERS)
        r = lambda key: pct(exact_rate(st, g, key))  # noqa: E731
        if g.startswith("coffea"):
            L.append(f"| {g} (health unknown) | {st['n']} | n/a - disease answers: {r('disease_answer')}"
                     f"{ci(st['disease_answer_ci95'])} | n/a | sano answers: {r('sano_answer')} | "
                     f"{r('DUDA')}{ci(st['DUDA_ci95'])} | {cnt} |")
        elif g.startswith("ojo"):
            L.append(f"| {g} (desired: UNSR) | {st['n']} | (no correct class) | {r('wrong_accepted')}"
                     f"{ci(st['wrong_accepted_ci95'])} | {st['dangerous_sano']} | **{r('DUDA')}**{ci(st['DUDA_ci95'])} | {cnt} |")
        else:
            L.append(f"| {g} | {st['n']} | **{r('correct')}**{ci(st['correct_ci95'])} | {r('wrong_accepted')} | "
                     f"{st['dangerous_sano']} | {r('DUDA')}{ci(st['DUDA_ci95'])} | {cnt} |")
    miss = geo_groups_missing(scope_res)
    if miss:
        by = {geo: [g[:-len(geo) - 1] for g in miss if g.endswith(geo)] for geo in GEO_NAMES}
        txt = (f"{', '.join(by['Kenya'])} in East Africa or Kenya" if by["East Africa"] == by["Kenya"] else
               "; ".join(f"{', '.join(v)} in {geo}" for geo, v in by.items() if v))
        L.append(f"| {txt} | 0 | no photos in these subsets | - | - | - | - |")
    return L


def geo_section(r):
    g = r.get("geo")
    if not g:
        return []
    c = g["counts"]
    keys = g["configs"]
    L = ["## East Africa and Kenya (where our users are)", "",
         f"Rule: {g['rule']}", "",
         "| label | photos (all splits) | in East Africa | in Kenya | field test: photos | field test: East Africa | "
         "field test: Kenya |", "|---|---|---|---|---|---|---|"]
    for lab in c["all_photos"]:
        a, t = c["all_photos"][lab], c["field_test"][lab]
        L.append(f"| {lab} | {a['n']} | {a['east_africa']} | {a['kenya']} | {t['n']} | {t['east_africa']} | {t['kenya']} |")
    ex = g.get("export_box_by_taxon")
    if ex:
        L += ["", "In the whole iNaturalist metadata export these photos were drawn from (`obs_coffee.tsv`, filtered to "
              "the six taxa in `model/inat_field.py`; not in the repository), the observations inside the East Africa "
              "box are: " + ", ".join(f"{k} {v}" for k, v in ex.items()) + " (*computed*). So the export holds no "
              "leaf rust, leaf miner, Cercospora or American leaf spot observation from East Africa at all."]
    L += ["", "Every photo inside the East Africa box, with the app's answer per model and threshold (decided exactly "
          "like the app; top-1 class and probability in brackets; \"where\" is read by eye from the coordinates, not "
          "computed):", "",
          "| photo | label | split | where | lat, lon | Kenya polygon | licence | " + " | ".join(keys) + " |",
          "|---|---|---|---|---|---|---|" + "---|" * len(keys)]
    for p in g["photos"]:
        L.append(f"| [{p['photo_id']}]({p['inat_url']}) | {p['label']} | {p['split']} | {p['place_by_eye']} | "
                 f"{p['lat']}, {p['lon']} | {'yes' if p['in_kenya'] else 'no'} | {p['license']} | " + " | ".join(
                     f"{p['answers'][k]} ({p['top1'][k][0]} {p['top1'][k][1]:.3f})" for k in keys) + " |")
    n_ea = ea_count(r, "all_photos")
    L += ["", "Plain words: " + (f"there are no labelled disease photos from East Africa (n = {n_ea}), " if n_ea == 0 else
                                 f"there are only {n_ea} labelled disease photos from East Africa, ")
          + "so the field numbers above do not measure the app on Kenyan field photos. The East African *Coffea* "
          "photos (health unknown) are too few to estimate a false-alarm rate; they are listed so nobody has to trust a "
          "rate computed from a handful of photos. The Kenyan evidence is the JMuBEN test split (Mutira, Kirinyaga), "
          "with the limits listed at the top. Kenyan field photos, labelled by the extension officer, are the next "
          "step (`data/field_test/README.md`).", ""]
    return L


def render_md(r):
    models = r["models"]
    names = list(models)
    base = names[0]
    mc = r["multicrop"]["chosen"]
    ph = r["photos"]
    sr = r["ship_rule"]
    gc = r.get("geo", {}).get("counts", {})
    n_ea_all, n_ea_test = ea_count(r, "all_photos"), ea_count(r, "field_test")
    am = r.get("geo", {}).get("field_test_disease_americas")
    n_dis_test = sum(gc["field_test"][lab]["n"] for lab in ("roya", "minador", "cercospora", "ojo_de_gallo")) if gc else None
    cof = gc.get("field_test", {}).get("coffea", {})
    L = ["# Field evaluation on iNaturalist photos (a proxy for field photos from Kirinyaga, Kenya)", "",
         "Generated by `model/field_eval.py` (all numbers **measured** on the files listed below; 95 % intervals are "
         "Wilson score intervals). Photos: iNaturalist open data, decided exactly like the phone app "
         "(centre-square crop, 224 px, blur check on the 128 px view, threshold from `labels.json`, top class `otro` "
         "-> UNSR).", "", WORDS, "",
         "> **Read this first.** Our users farm in Kirinyaga County, central Kenya. " + JMUBEN_KENYA + " iNaturalist "
         "photos are a second, harder test (other phones and framings, whole plants), but they are **not** from our "
         "users' region: " + (f"none of the {n_dis_test} labelled disease photos in the field test is from East Africa "
                              f"(n = {n_ea_test}; in all splits together: n = {n_ea_all})" if n_ea_test == 0 else
                              f"{n_ea_test} of the {n_dis_test} labelled disease photos in the field test are from East "
                              "Africa")
         + (("; all of them are from the Americas (Latin America, the Caribbean and Hawaii; *computed*: longitude "
             "west of 30 W)" if am == n_dis_test else f"; {am} of them are from the Americas (*computed*: longitude "
             "west of 30 W)") if am is not None else "")
         + (f". Only {cof['east_africa']} of the {cof['n']} *Coffea arabica* plant photos are from East Africa "
            f"({cof['kenya']} from Kenya), too few to measure anything (section \"East Africa and Kenya\")" if cof else "")
         + ". Many photos show severe, textbook infections. Labels are the iNaturalist community identification "
         "(mostly \"research\" or \"needs_id\" grade; 3 disease test photos and 189 *Coffea* photos are \"casual\"), "
         "not an agronomist's diagnosis. Sample sizes are small, so the intervals are wide.", "",
         "## Result", ""]
    tradeoff, tt, team = None, None, []
    if os.path.exists(THRESHOLD_TEST) and os.path.exists(THRESHOLD_SWEEP):  # model/field_threshold.py (v2 recalibration)
        from field_threshold import RULE_ANCHOR, pointer_line, render_tradeoff, result_lines
        tt, sw = json.load(open(THRESHOLD_TEST)), json.load(open(THRESHOLD_SWEEP))
        team = result_lines(tt)  # the human ship decision (model/ship_decision.json), if it names this candidate
        L += team
        L += [(f"Rule outcome, first comparison (each model at its export threshold): **{sr['fired']}.** Rule's choice: "
               f"`{sr['shipped']}`. {RULE_ANCHOR}") if team else f"**{sr['fired']}.** Shipped: `{sr['shipped']}`.", "",
              pointer_line(tt), ""]
        tradeoff = localize_tradeoff(render_tradeoff(tt, sw), r)
    else:
        L += [f"**{sr['fired']}.** Shipped: `{sr['shipped']}`.", ""]
    # comparison table on the held-out field test
    cols = [(base, "single"), (base, mc)] + [(n, m) for n in names[1:] for m in ("single", mc)]
    head = ["metric"] + [f"{n} {'single view' if m == 'single' else m.replace('mc:', 'multicrop ')}" for n, m in cols]
    L += ["### Comparison (held-out field test + Kenyan JMuBEN test split)", "",
          "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]

    def row(label, fn):
        vals = []
        for n, m in cols:
            try:
                vals.append(fn(models[n]["methods"][m]))
            except (KeyError, TypeError):
                vals.append("n/a")
        L.append(f"| {label} | " + " | ".join(vals) + " |")

    ft = lambda g, k="correct": (lambda x: f"{pct(exact_rate(x['field_test'][g], g, k))}{ci(x['field_test'][g][k + '_ci95'])} (n={x['field_test'][g]['n']})")  # noqa: E731

    def ft_geo(g, k="correct"):  # a geographic subset: n = 0 is shown as such
        return lambda x: ft(g, k)(x) if g in x["field_test"] else "n = 0 (no photos)"
    row("roya: correct & accepted, all field-test photos", ft("roya"))
    row("roya: correct & accepted, screened (leaf symptom visible)", ft("roya screened"))
    row("roya: correct & accepted, East Africa", ft_geo("roya East Africa"))
    row("roya: UNSR, all field-test photos", ft("roya", "DUDA"))
    row("minador: correct & accepted", ft("minador"))
    row("cercospora: correct & accepted", ft("cercospora"))
    row("American leaf spot (not a model class): UNSR (desired)", ft("ojo_de_gallo", "DUDA"))
    row("diseased field-test photos accepted as \"sano\" (dangerous)", lambda x: str(field_dangerous(x)))
    row("wrong-but-accepted, all diseased field-test photos", lambda x: str(sum(
        round(x["field_test"][g]["wrong_accepted"] * x["field_test"][g]["n"]) for g in ("roya", "minador", "cercospora", "ojo_de_gallo"))))
    row("Coffea arabica sample: disease answers (health unknown)", ft("coffea sample", "disease_answer"))
    row("Coffea arabica sample, East Africa: disease answers", ft_geo("coffea sample East Africa", "disease_answer"))
    row("Coffea arabica sample, Kenya: disease answers", ft_geo("coffea sample Kenya", "disease_answer"))
    row("JMuBEN test (Kenya) macro-F1 (argmax, 6 classes)", lambda x: f"{x['jmuben_otro_test']['jmuben_macro_f1_argmax']:.4f}")
    row("JMuBEN test (Kenya) app macro-F1 (UNSR = miss, 5 coffee classes)", lambda x: f"{x['jmuben_otro_test']['jmuben_app_macro_f1']:.4f}")
    row("JMuBEN test (Kenya): diseased accepted as \"sano\" (count)", lambda x: str(x["jmuben_otro_test"]["jmuben_diseased_called_sano_n"]))
    row("otro test images rejected (UNSR)", lambda x: f"{pct(x['jmuben_otro_test']['otro_rejected'])}{ci(x['jmuben_otro_test']['otro_rejected_ci95'])} (n={x['jmuben_otro_test']['otro_n']})")
    L += ["", "### Ship rule (decided mechanically)", "",
          "The five conditions come from the task brief; how each is measured (both F1 variants, dangerous errors "
          "counted separately on the two test sets, fp16 export for v2, the multicrop scheme) was fixed before the v2 "
          "field results were computed.", "",
          "Candidate vs `" + sr["baseline"] + "`: (1) field-test roya correct & accepted +10 points or more; (2) JMuBEN "
          "test macro-F1 (argmax and app-level) drops at most 1 point; (3) otro rejection >= 98 %; (4) diseased "
          "leaves accepted as \"sano\" do not increase (field test and JMuBEN test, counted separately); (5) Coffea "
          "disease-answer rate rises at most 5 points. Among passing candidates, the highest field-test roya score "
          "wins (ties: single view, it is simpler).", "",
          "| candidate | (1) roya +10 | (2) F1 | (3) otro | (4) dangerous | (5) Coffea | passes |", "|---|---|---|---|---|---|---|"]
    for k, v in sr["candidates"].items():
        c = v["checks"]
        L.append(f"| {k} | " + " | ".join("yes" if c[x] else "**no**" for x in c) + f" | {'**yes**' if v['passes'] else 'no'} |")
    if tradeoff:
        L += ["", tradeoff.rstrip("\n")]
    L += ["", "## Conclusions (plain words)", ""] + conclusions(r) + [""]
    L += [""] + geo_section(r)
    # v1 on all photos
    L += ["", f"## {base} (the app's model before this test) on ALL photos", "",
          f"`{base}` never saw any of these photos, so every photo counts. Single view ({base}'s app rule):", ""]
    L += group_table(models[base]["methods"]["single"]["all_photos"])
    L += ["", f"Same photos with multicrop `{mc}`:", ""]
    L += group_table(models[base]["methods"][mc]["all_photos"])
    for n in names[1:]:
        for m in ("single", mc):
            L += ["", f"## {n} {'single view' if m == 'single' else 'multicrop ' + m} on the held-out field test", ""]
            L += group_table(models[n]["methods"][m]["field_test"])
    L += ["", f"## {base} on the held-out field test (for direct comparison)", ""]
    L += group_table(models[base]["methods"]["single"]["field_test"])
    # multicrop
    L += ["", "## Multicrop (test-time, no retraining)", "",
          "Views: the full centre square plus a grid of tiles from the same square (`model/multicrop.py`): `2x2` = 4 "
          "tiles of 60 % of the side; `3x3` = 9 tiles of 45 %. Rule: blur check on the full view; a confident full-view "
          "disease answer is kept; otherwise a disease is accepted only if at least k tiles agree on it with "
          "probability >= threshold (and no other disease has as many votes); \"sano\" only ever comes from the full "
          "view; otherwise UNSR.", "",
          f"Scheme chosen **without the field test** ({r['multicrop']['rule']}): **{mc}**.", "",
          "| scheme | inferences per photo | validation otro rejected | validation coffee correct & accepted | "
          "field-dev roya correct (baseline never saw these) |", "|---|---|---|---|---|"]
    for t in r["multicrop"]["selection"]:
        L.append(f"| {t['method']} | {t['inferences']} | {pct(t['val_otro_rejected'])} | "
                 f"{pct(t['val_coffee_correct_accepted'])} | {pct(t['field_dev_roya_correct'])} (n={t['field_dev_roya_n']}) |")
    L += ["", "All schemes, held-out field test (for transparency; only the pre-registered scheme enters the ship rule):", "",
          "| model | method | roya correct | roya screened correct | American leaf spot UNSR | Coffea disease answers | "
          "otro rejected | dangerous (field) |", "|---|---|---|---|---|---|---|---|"]
    for n in names:
        for m, x in models[n]["methods"].items():
            f = x["field_test"]
            L.append(f"| {n} | {m} | {pct(f['roya']['correct'])} | {pct(f['roya screened']['correct'])} | "
                     f"{pct(f['ojo_de_gallo']['DUDA'])} | {pct(f['coffea sample']['disease_answer'])} | "
                     f"{pct(x['jmuben_otro_test']['otro_rejected'])} | {field_dangerous(x)} |")
    # protocol
    L += ["", "## Protocol", "",
          "- **Photos**: iNaturalist open-data export (`inaturalist-open-data` S3 bucket), `medium` size (longest side "
          "about 500 px), CC-licensed only. Per-photo attribution (observer, license, link): "
          "`reports/field_inat_attribution.csv`. Images are **not** in the repository (many are CC BY-NC or ND). "
          "Rebuild: `python model/inat_field.py --inat <dir>`.",
          "- **Labels**: taxon of the observation: *Hemileia vastatrix* and genus *Hemileia* -> roya; *Leucoptera "
          "coffeella* -> minador; *Cercospora coffeicola* -> cercospora; *Mycena citricolor* (American leaf spot, "
          "`ojo_de_gallo` in the tables, not one of our classes) -> the right answer is UNSR; *Coffea arabica* -> coffee plant, health "
          "unknown (never trained on, only used to count disease answers).",
          f"- **Split by observer** (`model/inat_field.py`): {r['split_rule']} American leaf spot is always test, so 1 "
          "American leaf spot test photo shares its observer with a v2 training photo (no other test photo does); the rest is "
          "field-train (used only by the v2 experiment). Coffea: one photo per observer, "
          f"{ph['coffea']['observers']} distinct observers, none of them a field-train observer.",
          f"- **Geography (report subsets only)**: {r['geo_rule']}",
          "- **Screening** (`reports/field_inat_screening.csv`): every disease photo was looked at on contact sheets "
          "(220 px thumbnails) and "
          "marked `yes` if a leaf symptom is clearly visible (leaf or lesion close enough to see), `no` for whole "
          "plants, branches far away, microscope slides, cultures, mushrooms, fruit. One person, no second rater. "
          "v2 trained only on field-train photos marked `yes`.",
          "- **v2 training** (`model/train.py --extra ... --extra-repeat 2`): the v1 recipe (same architecture, data, "
          "augmentation, epochs, best epoch by JMuBEN validation macro-F1) plus 7 views of each screened field-train "
          "photo (centre square + 6 random squares of 60-100 % of the short side), oversampled x2. Exported with "
          "`model/export_onnx.py` (fp16 weights, threshold floor 0.70, blur threshold from validation). Training log "
          "and calibration: `reports/field_v2_training_log.csv`, `reports/field_v2_calibration.json` (best epoch by "
          "JMuBEN validation macro-F1; v1's log is `reports/model_training_log.csv`).", "",
          "| label | photos | observations | observers | field-train / field-test | screened yes | in split box | "
          "East Africa | Kenya | licenses |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for lab, v in ph.items():
        sp = v["split"]
        tr_te = (f"{sp.get('field_train', 0)} / {sp.get('field_test', 0)}" if lab != "coffea" else f"eval only ({sp.get('coffea_eval', 0)})")
        L.append(f"| {lab} | {v['photos']} | {v['observations']} | {v['observers']} | {tr_te} | "
                 f"{'n/a' if v['screened_yes'] is None else v['screened_yes']} | {v['in_split_box']} | "
                 f"{v['in_east_africa']} | {v['in_kenya']} | "
                 + ", ".join(f"{k} {c}" for k, c in sorted(v["licenses"].items())) + " |")
    L += ["", "Models: " + "; ".join(f"`{n}` = `{models[n]['model']}` ({models[n].get('version')}, sha1 "
                                     f"{models[n]['sha1_12']}, threshold {models[n]['threshold']}, blur "
                                     f"{models[n]['blur_threshold']})" for n in names) + "."
          + (f" The app ships the `{tt['candidate'].split('@')[0]}` file as `app/model/cafetal.onnx` with threshold "
             f"{tt['chosen_t']} (team decision, see \"Result\")." if team else ""), ""]
    md = english("\n".join(L) + "\n")
    left = [x for x in md.split("\n") if re.search(r"Chiapas|Tseltal|Guatemala|No estoy|Mexico(?! and northern)", x)]
    if left:
        print("WARNING: old-region wording left in field_eval.md:", *[x[:120] for x in left], sep="\n  ")
    return md


if __name__ == "__main__":
    main()
