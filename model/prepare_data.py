"""Prepare the Cafetal image dataset.

Steps
1. Scan the sources and map their labels to the shared labels (PLAN.md section 3).
2. Group near-duplicates per (source, label): JMuBEN ships every source photo many times
   (flipped / rotated / colour-shifted copies) and burst shots of the same leaf. A random split
   would put copies of the same photo in train and test. We hash a canonical form of each image
   (grayscale + histogram equalisation, 9x9 thumbnail, 72-bit difference hash) under all
   8 flips/90-degree rotations, link pairs whose Hamming distance is <= --hash-threshold and take
   connected components (union-find) as groups.
3. Split 70/15/15 by group, separately for each (source, label) stratum.
4. Subsample: train up to --train-cap images per class, val up to --val-cap, test up to
   --test-cap, picking round-robin across groups (one image per group first) for diversity.
5. Cache the selected images as uint8 arrays (center square crop, resized to --size).

Outputs (in --out): manifest.csv, meta.json, {train,val,test}.npz, extra_inat.npz (optional)
and reports/model_data_split.json in the repo.

Usage (see model/README.md):
  python model/prepare_data.py --jmuben DIR --plantdoc DIR --negatives DIR --inat DIR \
      --out /home/user/data_proc/cafetal
Optional, UNTESTED (datasets not reachable from the build machine):
  --bracol DIR   BRACOL (Esgario et al. 2020, doi:10.17632/yy2k5y8mxg.1)
  --rocole DIR   RoCoLe (Parraga-Alava et al. 2019, doi:10.17632/c5yvn32dzg.2)
"""
import argparse
import csv
import json
import os
import random
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageOps
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blur import center_square, laplacian_variance  # noqa: E402

CLASSES_V1 = ["sano", "roya", "minador", "phoma", "cercospora", "otro"]
JMUBEN_MAP = {"Healthy": "sano", "Leaf_rust": "roya", "Miner": "minador",
              "Phoma": "phoma", "Cerscospora": "cercospora"}
IMG_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def list_images(folder):
    out = []
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(IMG_EXT) and not f.startswith("."):
                out.append(os.path.join(root, f))
    return sorted(out)


# ---------------------------------------------------------------- sources
def scan_jmuben(d):
    rows = []
    for folder, label in JMUBEN_MAP.items():
        for p in list_images(os.path.join(d, folder)):
            rows.append({"path": p, "label": label, "source": "jmuben"})
    return rows


def scan_plantdoc(d):
    # Every PlantDoc class is another crop -> "otro" (hard negatives, incl. rust on apple/corn).
    return [{"path": p, "label": "otro", "source": "plantdoc"} for p in list_images(d)]


def scan_negatives(d, n, seed):
    # Generic non-plant photos (Imagenette). Sample n, stratified over sub-folders.
    files = list_images(d)
    by_dir = defaultdict(list)
    for p in files:
        by_dir[os.path.basename(os.path.dirname(p))].append(p)
    rng = random.Random(seed)
    per = max(1, n // max(1, len(by_dir)))
    rows = []
    for k in sorted(by_dir):
        sel = rng.sample(by_dir[k], min(per, len(by_dir[k])))
        rows += [{"path": p, "label": "otro", "source": "imagenette"} for p in sel]
    return rows


def keyword_label(name):
    """Map a BRACOL/RoCoLe folder or label name to a shared label (None = unknown)."""
    s = name.lower()
    if "health" in s or s in ("sano", "0"):
        return "sano"
    if "spider" in s or "mite" in s or "acaro" in s:
        return "acaro_rojo"
    if "rust" in s or "roya" in s:  # RoCoLe rust_level_1..4 -> roya
        return "roya"
    if "miner" in s or "minador" in s:
        return "minador"
    if "phoma" in s or "brown" in s:
        return "phoma"
    if "cercospora" in s:
        return "cercospora"
    return None


def scan_labeled_folder(d, source):
    """UNTESTED - datasets not reachable from the build machine.

    Accepts either (a) class sub-folders whose names contain a keyword (healthy, rust, miner,
    phoma/brown_leaf_spot, cercospora, red_spider_mite), or (b) a CSV with a file column and a
    label column. BRACOL 'leaf' CSV: column predominant_stress 0=healthy 1=miner 2=rust
    3=phoma 4=cercospora. RoCoLe CSV: column 'Multiclass.Label' (healthy, red_spider_mite,
    rust_level_1..4).
    """
    images = list_images(d)
    by_name = {os.path.basename(p): p for p in images}
    by_stem = {os.path.splitext(os.path.basename(p))[0]: p for p in images}
    bracol_codes = {"0": "sano", "1": "minador", "2": "roya", "3": "phoma", "4": "cercospora"}
    rows, seen = [], set()
    for root, _, files in os.walk(d):
        for f in files:
            if not f.lower().endswith(".csv"):
                continue
            with open(os.path.join(root, f), newline="", encoding="utf-8", errors="ignore") as fh:
                reader = csv.DictReader(fh)
                cols = reader.fieldnames or []
                fcol = next((c for c in cols if c.lower() in ("file", "filename", "id", "image")), None)
                lcol = next((c for c in cols if c.lower() in ("multiclass.label", "predominant_stress",
                                                               "label", "class")), None)
                if not fcol or not lcol:
                    continue
                for r in reader:
                    key = str(r[fcol]).strip()
                    p = by_name.get(key) or by_stem.get(os.path.splitext(key)[0])
                    raw = str(r[lcol]).strip()
                    lab = bracol_codes.get(raw) if lcol == "predominant_stress" else keyword_label(raw)
                    if p and lab and p not in seen:
                        rows.append({"path": p, "label": lab, "source": source})
                        seen.add(p)
    if rows:
        return rows
    for p in images:  # folder-name fallback
        lab = keyword_label(os.path.basename(os.path.dirname(p)))
        if lab:
            rows.append({"path": p, "label": lab, "source": source})
    return rows


# ---------------------------------------------------------------- hashing / grouping
def thumb9(path):
    """Canonical 9x9 thumbnail: center square, grayscale, histogram-equalised (colour/brightness invariant)."""
    try:
        im = center_square(Image.open(path).convert("RGB"))
    except Exception:
        return None
    g = ImageOps.equalize(im.convert("L"))
    return np.asarray(g.resize((9, 9), Image.BOX), np.int16)


def dihedral_dhash_bits(thumbs):
    """(N,9,9) -> (N,8,72) difference-hash bits of the 8 flips/rotations."""
    out = []
    for k in range(4):
        r = np.rot90(thumbs, k, axes=(1, 2))
        for f in (r, r[:, :, ::-1]):
            out.append((f[:, :, 1:] > f[:, :, :-1]).reshape(len(thumbs), -1))
    return np.stack(out, 1)


def group_near_duplicates(bits, threshold, chunk=512):
    """Connected components (union-find) over pairs with min-over-dihedral Hamming <= threshold."""
    n, _, b = bits.shape
    a = bits[:, 0, :].astype(np.float32) * 2 - 1
    v = bits.reshape(n * 8, b).astype(np.float32) * 2 - 1
    rows, cols = [], []
    for s in range(0, n, chunk):
        ham = ((b - a[s:s + chunk] @ v.T) / 2).reshape(-1, n, 8).min(2)  # +-1 dot product -> Hamming
        r, c = np.nonzero(ham <= threshold)
        rows.append((r + s).astype(np.int32))
        cols.append(c.astype(np.int32))
    r, c = np.concatenate(rows), np.concatenate(cols)
    graph = coo_matrix((np.ones(len(r), np.int8), (r, c)), shape=(n, n))
    return connected_components(graph, directed=False)[1]


# ---------------------------------------------------------------- split / select
def split_groups(group_sizes, fracs, rng):
    """Assign groups to splits greedily by image-count deficit; each split gets >=1 group if possible."""
    gids = list(group_sizes)
    rng.shuffle(gids)
    total = sum(group_sizes.values())
    names = list(fracs)
    count = {k: 0 for k in names}
    assign = {}
    # seed val and test with one group each (smallest first, so train keeps the bulk)
    if len(gids) >= 3:
        for k in ("val", "test"):
            g = min((g for g in gids if g not in assign), key=lambda g: group_sizes[g])
            assign[g] = k
            count[k] += group_sizes[g]
    for g in gids:
        if g in assign:
            continue
        k = max(names, key=lambda k: fracs[k] * total - count[k])
        assign[g] = k
        count[k] += group_sizes[g]
    return assign


def round_robin(indices_by_group, cap, rng):
    """Pick up to cap items, one per group per round (groups and members shuffled)."""
    pools = [list(v) for v in indices_by_group.values()]
    for p in pools:
        rng.shuffle(p)
    rng.shuffle(pools)
    out = []
    while len(out) < cap and any(pools):
        for p in pools:
            if p and len(out) < cap:
                out.append(p.pop())
    return out


# ---------------------------------------------------------------- caching
def load_views(args):
    """Return list of (view_name, uint8 SxSx3 array) and blur variance of the main view."""
    path, source, size, seed = args
    try:
        im = Image.open(path).convert("RGB")
    except Exception:
        return None
    sq = center_square(im)
    views = [("full", np.asarray(sq.resize((size, size), Image.BILINEAR), np.uint8))]
    if source == "plantdoc":
        # extra close-up view so "otro" is not just "a whole leaf in the frame"
        rng = random.Random(f"{seed}:{path}")
        w, h = im.size
        s = int(min(w, h) * rng.uniform(0.35, 0.6))
        l, t = rng.randint(0, w - s), rng.randint(0, h - s)
        crop = im.crop((l, t, l + s, t + s)).resize((size, size), Image.BILINEAR)
        views.append(("crop", np.asarray(crop, np.uint8)))
    return views, laplacian_variance(im)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jmuben", required=True, help="AgML arabica_coffee_leaf_disease_classification folder")
    ap.add_argument("--plantdoc", help="AgML plant_doc_classification folder (-> otro)")
    ap.add_argument("--negatives", help="Imagenette folder (non-plant -> otro)")
    ap.add_argument("--n-negatives", type=int, default=700)
    ap.add_argument("--inat", help="iNatAg-mini coffea_arabica folder (EVAL ONLY, unlabeled)")
    ap.add_argument("--bracol", help="BRACOL folder (UNTESTED)")
    ap.add_argument("--rocole", help="RoCoLe folder (UNTESTED)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=int, default=224)
    ap.add_argument("--hash-threshold", type=int, default=8, help="max Hamming distance (of 72 bits)")
    ap.add_argument("--train-cap", type=int, default=1500)
    ap.add_argument("--otro-train-cap", type=int, default=3000)
    ap.add_argument("--val-cap", type=int, default=300)
    ap.add_argument("--test-cap", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    rng = random.Random(args.seed)

    rows = scan_jmuben(args.jmuben)
    if args.plantdoc:
        rows += scan_plantdoc(args.plantdoc)
    if args.negatives:
        rows += scan_negatives(args.negatives, args.n_negatives, args.seed)
    if args.bracol:
        rows += scan_labeled_folder(args.bracol, "bracol")
    if args.rocole:
        rows += scan_labeled_folder(args.rocole, "rocole")
    classes = list(CLASSES_V1)
    if any(r["label"] == "acaro_rojo" for r in rows):
        classes.insert(5, "acaro_rojo")
    print(f"scanned {len(rows)} images", Counter((r['source'], r['label']) for r in rows))

    # --- hashing
    with Pool(4) as pool:
        thumbs = pool.map(thumb9, [r["path"] for r in rows], chunksize=256)
    bad = [i for i, t in enumerate(thumbs) if t is None]
    rows = [r for i, r in enumerate(rows) if thumbs[i] is not None]
    thumbs = np.stack([t for t in thumbs if t is not None])
    bits = dihedral_dhash_bits(thumbs)

    # exact (dihedral-invariant) duplicates across different labels = label noise
    canon = [min(np.packbits(bits[i, k]).tobytes() for k in range(8)) for i in range(len(rows))]
    labels_by_hash = defaultdict(set)
    for r, h in zip(rows, canon):
        labels_by_hash[h].add(r["label"])
    cross = {h for h, s in labels_by_hash.items() if len(s) > 1}
    n_cross = sum(1 for h in canon if h in cross)
    print(f"unreadable: {len(bad)}; images whose exact hash appears under >1 label: {n_cross}")

    strata = defaultdict(list)
    for i, r in enumerate(rows):
        strata[(r["source"], r["label"])].append(i)
    report = {"hash": f"dHash 72-bit on equalised grayscale 9x9, min over 8 flips/rotations, "
                      f"Hamming <= {args.hash_threshold}, union-find",
              "seed": args.seed, "size": args.size, "classes": classes, "strata": {},
              "unreadable_files": len(bad), "cross_label_exact_duplicates": n_cross}
    fracs = {"train": 0.70, "val": 0.15, "test": 0.15}
    for (src, lab), idx in sorted(strata.items()):
        comp = group_near_duplicates(bits[idx], args.hash_threshold)
        exact = group_near_duplicates(bits[idx], 0)
        for j, i in enumerate(idx):
            rows[i]["group"] = f"{src}:{lab}:{comp[j]}"
        sizes = Counter(rows[i]["group"] for i in idx)
        assign = split_groups(sizes, fracs, rng)
        for i in idx:
            rows[i]["split"] = assign[rows[i]["group"]]
        per_split = Counter(rows[i]["split"] for i in idx)
        gps = Counter(assign.values())
        report["strata"][f"{src}/{lab}"] = {
            "images": len(idx), "exact_dup_groups": int(exact.max() + 1), "groups": len(sizes),
            "largest_group": max(sizes.values()), "median_group": int(np.median(list(sizes.values()))),
            "images_per_split": dict(per_split), "groups_per_split": dict(gps)}
        print(f"{src}/{lab}: {len(idx)} images -> {len(sizes)} groups "
              f"(exact {exact.max() + 1}); split images {dict(per_split)} groups {dict(gps)}")

    # --- selection
    caps = {"train": args.train_cap, "val": args.val_cap, "test": args.test_cap}
    for r in rows:
        r["selected"] = 0
    for split in ("train", "val", "test"):
        for lab in classes:
            by_group = defaultdict(list)
            for i, r in enumerate(rows):
                if r["split"] == split and r["label"] == lab:
                    by_group[r["group"]].append(i)
            if not by_group:
                continue
            cap = caps[split]
            if lab == "otro":
                # PlantDoc gives 2 views per photo; split otro budget across sources
                cap = args.otro_train_cap // 2 if split == "train" else cap // 2
            for i in round_robin(by_group, cap, rng):
                rows[i]["selected"] = 1

    # --- cache arrays
    sel = [r for r in rows if r["selected"]]
    with Pool(4) as pool:
        res = pool.map(load_views, [(r["path"], r["source"], args.size, args.seed) for r in sel], chunksize=64)
    data = {s: {"x": [], "y": [], "group": [], "source": [], "view": [], "blur": [], "path": []}
            for s in ("train", "val", "test")}
    for r, out in zip(sel, res):
        if out is None:
            continue
        views, bv = out
        r["blur_var"] = round(bv, 2)
        for vname, arr in views:
            d = data[r["split"]]
            d["x"].append(arr)
            d["y"].append(classes.index(r["label"]))
            d["group"].append(r["group"])
            d["source"].append(r["source"])
            d["view"].append(vname)
            d["blur"].append(bv if vname == "full" else np.nan)
            d["path"].append(r["path"])
    counts = {}
    for s, d in data.items():
        np.savez(os.path.join(args.out, f"{s}.npz"), x=np.stack(d["x"]), y=np.array(d["y"], np.int64),
                 group=np.array(d["group"]), source=np.array(d["source"]), view=np.array(d["view"]),
                 blur=np.array(d["blur"], np.float64), path=np.array(d["path"]))
        counts[s] = {c: int(sum(1 for y in d["y"] if y == k)) for k, c in enumerate(classes)}
        counts[s + "_groups"] = {c: len({g for g, y in zip(d["group"], d["y"]) if y == k})
                                 for k, c in enumerate(classes)}
        print(s, counts[s], "groups", counts[s + "_groups"])
    report["selected"] = counts

    if args.inat:  # eval-only: real phone photos of coffee plants, disease status unknown
        paths = list_images(args.inat)
        xs, bl, ps = [], [], []
        for p in paths:
            out = load_views((p, "inat", args.size, args.seed))
            if out:
                xs.append(out[0][0][1]); bl.append(out[1]); ps.append(p)
        np.savez(os.path.join(args.out, "extra_inat.npz"), x=np.stack(xs), blur=np.array(bl), path=np.array(ps))
        report["extra_inat_images"] = len(xs)

    with open(os.path.join(args.out, "manifest.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["path", "label", "source", "group", "split", "selected", "blur_var"])
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})
    meta = {"classes": classes, "size": args.size, "seed": args.seed}
    with open(os.path.join(args.out, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    os.makedirs(os.path.join(REPO, "reports"), exist_ok=True)
    with open(os.path.join(REPO, "reports", "model_data_split.json"), "w") as fh:
        json.dump(report, fh, indent=2)
    print("done ->", args.out)


if __name__ == "__main__":
    main()
