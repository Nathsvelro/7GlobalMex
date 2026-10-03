"""Evaluate the Cafetal image model and write reports/model_eval.{json,md} + reports/confusion_matrix.png.

  python model/evaluate.py --data /home/user/data_proc/cafetal

The shipped model (cafetal-img-v2 at threshold 0.90) with the previous app model (v1) as a reference column:

  python model/evaluate.py --data /home/user/data_proc/cafetal --inat-field /home/user/data_raw/inat \
      --fp32 model/checkpoints/v2/cafetal_fp32.onnx --calib reports/field_v2_calibration.json \
      --ref v1=model/checkpoints/v1/cafetal.onnx:model/checkpoints/v1/labels.json:reports/model_calibration.json

Every model is decided with ITS OWN threshold from its labels.json (shipped: app/model/labels.json).
(a) held-out TEST split (split by near-duplicate group): fp32 and shipped model; app decision
    (threshold + blur check + "otro" -> DUDA); "otro" rejection.
(b) robustness under phone-like degradations (proxy for the field gap) + fail-safe rate.
(c) data/field_test/<label>/*.jpg - the team's own photos (evaluated automatically when present).
(d) size, single-thread CPU latency (onnxruntime Python), computed 3G download time.
(e) iNatAg-mini coffee photos (whole plants / flowers / cherries, disease unknown): what the app would say.
(g) --inat-field DIR: labelled iNaturalist field photos (model/inat_field.py), held-out field test, app decision
    (single view, plus multicrop if labels.json enables it). Full comparison: model/field_eval.py.
"""
import argparse
import io
import json
import os
import sys
import time

import numpy as np

import onnxruntime as ort
from PIL import Image, ImageEnhance, ImageFilter
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blur import BLUR_SIZE, center_square, laplacian_variance, laplacian_variance_array  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIELD_LABELS = ["sano", "roya", "minador", "phoma", "cercospora", "acaro_rojo", "otro"]  # PLAN.md section 3
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")


def session(path, threads=4):
    so = ort.SessionOptions()
    so.intra_op_num_threads = threads
    so.inter_op_num_threads = 1
    return ort.InferenceSession(path, so, providers=["CPUExecutionProvider"])


def run(sess, x, batch=64):
    name = sess.get_inputs()[0].name
    return np.concatenate([sess.run(None, {name: x[i:i + batch].astype(np.float32)})[0]
                           for i in range(0, len(x), batch)])


def blur_scores(x):
    return np.array([laplacian_variance_array(np.asarray(
        Image.fromarray(a).resize((BLUR_SIZE, BLUR_SIZE), Image.BILINEAR))) for a in x])


def decide(probs, blur, classes, thr, blur_thr):
    """App logic (PLAN.md section 3): returns final label per image, 'DUDA' for the fail-safe."""
    otro = classes.index("otro")
    out = []
    for p, b in zip(probs, blur):
        k = int(p.argmax())
        out.append("DUDA" if (b < blur_thr or p[k] < thr or k == otro) else classes[k])
    return np.array(out)


def metrics(y, probs, classes):
    pred = probs.argmax(1)
    p, r, f, s = precision_recall_fscore_support(y, pred, labels=range(len(classes)), zero_division=0)
    return {"accuracy": round(float((pred == y).mean()), 4),
            "macro_f1": round(float(f1_score(y, pred, average="macro")), 4),
            "per_class": {c: {"precision": round(float(p[i]), 4), "recall": round(float(r[i]), 4),
                              "f1": round(float(f[i]), 4), "support": int(s[i])} for i, c in enumerate(classes)},
            "confusion_matrix": confusion_matrix(y, pred, labels=range(len(classes))).tolist()}


def app_outcomes(y, final, classes):
    """For coffee images: correct & accepted / wrong & accepted / DUDA. For otro: rejected (DUDA)."""
    res = {}
    for k, c in enumerate(classes):
        m = y == k
        if not m.any():
            continue
        f = final[m]
        if c == "otro":
            res[c] = {"n": int(m.sum()), "rejected_to_DUDA": round(float((f == "DUDA").mean()), 4)}
        else:
            res[c] = {"n": int(m.sum()), "correct": round(float((f == c).mean()), 4),
                      "wrong": round(float(((f != c) & (f != "DUDA")).mean()), 4),
                      "DUDA": round(float((f == "DUDA").mean()), 4)}
    coffee = np.array([classes[k] != "otro" for k in y])
    acc_mask = coffee & (final != "DUDA")
    sano = classes.index("sano")
    diseased = coffee & (y != sano)
    res["_summary"] = {
        "coffee_coverage": round(float(acc_mask.sum() / max(coffee.sum(), 1)), 4),
        "coffee_selective_accuracy": round(float((final[acc_mask] == np.array(classes)[y[acc_mask]]).mean()), 4)
        if acc_mask.any() else None,
        "diseased_called_sano": round(float((final[diseased] == "sano").mean()), 4) if diseased.any() else None,
        "diseased_called_sano_n": int((final[diseased] == "sano").sum()),
        # app-level macro-F1 over the coffee classes, DUDA counts as a miss (same as model/field_eval.py)
        "app_macro_f1_coffee": round(float(f1_score(np.array(classes)[y[coffee]], final[coffee],
                                                    labels=[c for c in classes if c != "otro"], average="macro",
                                                    zero_division=0)), 4) if coffee.any() else None,
    }
    return res


# ---------------------------------------------------------------- degradations (on the SxS view)
def jpeg(a, q=25):
    buf = io.BytesIO()
    Image.fromarray(a).save(buf, "JPEG", quality=q)
    return np.asarray(Image.open(buf).convert("RGB"))


DEGRADATIONS = {
    "clean": lambda a: a,
    "jpeg_q25": jpeg,
    "gaussian_blur_r2": lambda a: np.asarray(Image.fromarray(a).filter(ImageFilter.GaussianBlur(2))),
    "gaussian_blur_r4": lambda a: np.asarray(Image.fromarray(a).filter(ImageFilter.GaussianBlur(4))),
    "brightness_x0.6": lambda a: np.asarray(ImageEnhance.Brightness(Image.fromarray(a)).enhance(0.6)),
    "brightness_x1.4": lambda a: np.asarray(ImageEnhance.Brightness(Image.fromarray(a)).enhance(1.4)),
    "rotate_90": lambda a: np.ascontiguousarray(np.rot90(a)),
    "downscale_64": lambda a: np.asarray(Image.fromarray(a).resize((64, 64), Image.BILINEAR)
                                         .resize(a.shape[:2][::-1], Image.BILINEAR)),
}


def load_field(root, size):
    xs, ys, blur, paths = [], [], [], []
    for lab in FIELD_LABELS:
        d = os.path.join(root, lab)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.lower().endswith(IMG_EXT):
                p = os.path.join(d, f)
                im = Image.open(p).convert("RGB")
                xs.append(np.asarray(center_square(im).resize((size, size), Image.BILINEAR), np.uint8))
                blur.append(laplacian_variance(im))
                ys.append(lab)
                paths.append(os.path.relpath(p, REPO))
    return xs, ys, blur, paths


def leaky_sample(manifest, classes, size, per_class=300, seed=0):
    """Unused near-duplicate copies of TRAINING photos (what a naive random split would put in test)."""
    import csv
    import random
    from collections import defaultdict
    rng = random.Random(seed)
    by = defaultdict(lambda: defaultdict(list))
    with open(manifest, newline="") as fh:
        for r in csv.DictReader(fh):
            if r["split"] == "train" and r["selected"] == "0" and r["label"] in classes:
                by[r["label"]][r["group"]].append(r["path"])
    xs, ys = [], []
    for lab, groups in by.items():
        pools = [rng.sample(v, len(v)) for v in groups.values()]
        picked = []
        while len(picked) < per_class and any(pools):
            for pl in pools:
                if pl and len(picked) < per_class:
                    picked.append(pl.pop())
        for pth in picked:
            im = center_square(Image.open(pth).convert("RGB")).resize((size, size), Image.BILINEAR)
            xs.append(np.asarray(im, np.uint8))
            ys.append(classes.index(lab))
    return (np.stack(xs), np.array(ys)) if xs else (None, None)


def plot_confusion(cms, titles, classes, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, len(cms), figsize=(6.2 * len(cms), 5.4))
    axes = np.atleast_1d(axes)
    for ax, cm, title in zip(axes, cms, titles):
        cm = np.array(cm)
        norm = cm / np.maximum(cm.sum(1, keepdims=True), 1)
        ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
        for i in range(len(classes)):
            for j in range(len(classes)):
                ax.text(j, i, f"{cm[i, j]}\n{norm[i, j]:.0%}", ha="center", va="center", fontsize=8,
                        color="white" if norm[i, j] > 0.6 else "#1f2937")
        ax.set_xticks(range(len(classes)), classes, rotation=35, ha="right")
        ax.set_yticks(range(len(classes)), classes)
        ax.set_xlabel("predicted (argmax, before threshold)")
        ax.set_ylabel("true")
        ax.set_title(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def latency(path, size, n=50):
    s = session(path, threads=1)
    x = np.random.default_rng(0).uniform(0, 255, (1, size, size, 3)).astype(np.float32)
    name = s.get_inputs()[0].name
    for _ in range(5):
        s.run(None, {name: x})
    t = []
    for _ in range(n):
        t0 = time.perf_counter()
        s.run(None, {name: x})
        t.append((time.perf_counter() - t0) * 1000)
    return round(float(np.median(t)), 2)


def file_sha1_12(path):
    import hashlib
    return hashlib.sha1(open(path, "rb").read()).hexdigest()[:12]


def parse_ref(spec):
    """name=model.onnx:labels.json[:calibration.json]"""
    name, rest = spec.split("=", 1)
    parts = rest.split(":")
    labels = json.load(open(parts[1]))
    calib = json.load(open(parts[2])) if len(parts) > 2 and parts[2] else {}
    return name, parts[0], labels, calib


def otro_by_source(te, y, final, probs, otro):
    om = y == otro
    out = {}
    for src in sorted(set(te["source"][om])):
        for view in sorted(set(te["view"][om & (te["source"] == src)])):
            m = om & (te["source"] == src) & (te["view"] == view)
            out[f"{src}/{view}"] = {"n": int(m.sum()), "rejected": round(float((final[m] == "DUDA").mean()), 4),
                                    "argmax_otro": round(float((probs[m].argmax(1) == otro).mean()), 4)}
    return out


def otro_accepted(te, y, final, probs, otro, ref_final=None):
    """The otro test images the app would NOT send to DUDA (false alarms), one row per image view."""
    raw = os.environ.get("DATA_RAW", "/home/user/data_raw")
    out = []
    for i in np.where((y == otro) & (final != "DUDA"))[0]:
        row = {"image": os.path.relpath(str(te["path"][i]), raw), "view": str(te["view"][i]), "answer": str(final[i]),
               "top1": round(float(probs[i].max()), 3)}
        if ref_final is not None:
            row["reference_answer"] = str(ref_final[i])
        out.append(row)
    return out


def robustness_row(pd, bd, y, classes, thr, blur_thr):
    otro = classes.index("otro")
    fd = decide(pd, bd, classes, thr, blur_thr)
    coffee = y != otro
    acc_m = coffee & (fd != "DUDA")
    return {
        "accuracy_argmax": round(float((pd.argmax(1) == y).mean()), 4),
        "macro_f1_argmax": round(float(f1_score(y, pd.argmax(1), average="macro")), 4),
        "coffee_failsafe_rate": round(float((fd[coffee] == "DUDA").mean()), 4),
        "coffee_failsafe_by_blur": round(float((bd[coffee] < blur_thr).mean()), 4),
        "coffee_selective_accuracy": round(float((fd[acc_m] == np.array(classes)[y[acc_m]]).mean()), 4)
        if acc_m.any() else None,
        "coffee_wrong_accepted": round(float(((fd != "DUDA") & (fd != np.array(classes)[y]))[coffee].mean()), 4),
        "otro_rejected": round(float((fd[~coffee] == "DUDA").mean()), 4),
    }


def inatag_eval(sess, ia, crops, classes, thr, blur_thr):
    pi = run(sess, ia["x"])
    fi = decide(pi, ia["blur"], classes, thr, blur_thr)
    vals, cnts = np.unique(fi, return_counts=True)
    zoom = {}
    for key, (xs, bs) in crops.items():
        fz = decide(run(sess, xs), bs, classes, thr, blur_thr)
        zoom[key] = {str(v): int(c) for v, c in zip(*np.unique(fz, return_counts=True))}
    return {"n_images": int(len(fi)), "app_decision_share": {str(v): round(int(c) / len(fi), 4) for v, c in zip(vals, cnts)},
            "argmax_share": {classes[k]: round(float((pi.argmax(1) == k).mean()), 4) for k in range(len(classes))},
            "app_decision_counts_centre_crops": zoom}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", action="store_true",
                    help="only rewrite model_eval.md from model_eval.json (no data or models needed)")
    ap.add_argument("--data")
    ap.add_argument("--fp32", default=os.path.join(REPO, "model", "checkpoints", "cafetal_fp32.onnx"),
                    help="float32 export of the SAME weights as the shipped model (v2: model/checkpoints/v2/cafetal_fp32.onnx)")
    ap.add_argument("--shipped", default=os.path.join(REPO, "app", "model", "cafetal.onnx"))
    ap.add_argument("--labels", default=os.path.join(REPO, "app", "model", "labels.json"))
    ap.add_argument("--calib", default=os.path.join(REPO, "reports", "model_calibration.json"),
                    help="export-time calibration record of the shipped model (model/export_onnx.py --calib-out); "
                         "v2: reports/field_v2_calibration.json")
    ap.add_argument("--ref", help="name=model.onnx:labels.json[:calibration.json] - reference model (e.g. the previous "
                                  "app model), decided with its own threshold and shown next to the shipped model")
    ap.add_argument("--decision", default=os.path.join(REPO, "model", "ship_decision.json"),
                    help="human ship-decision record; shown in the header when it names the shipped model file")
    ap.add_argument("--field", default=os.path.join(REPO, "data", "field_test"))
    ap.add_argument("--out", default=os.path.join(REPO, "reports"))
    ap.add_argument("--inat-field", help="iNaturalist field photo folder from model/inat_field.py (adds section g)")
    ap.add_argument("--cache", default=os.path.join(REPO, "model", "checkpoints", "field_cache"),
                    help="prediction cache for section (g), keyed by model file hash")
    args = ap.parse_args()
    if args.render:
        rep = json.load(open(os.path.join(args.out, "model_eval.json")))
        with open(os.path.join(args.out, "model_eval.md"), "w") as fh:
            fh.write(render_md(rep, rep["model"]["classes"]))
        print("wrote", os.path.join(args.out, "model_eval.md"))
        return
    if not args.data:
        ap.error("--data is required (or use --render)")
    labels = json.load(open(args.labels))
    classes, size = labels["classes"], labels["input"]["size"]
    thr, blur_thr = labels["threshold"], labels["blur_threshold"]
    calib = json.load(open(args.calib))
    split = json.load(open(os.path.join(args.out, "model_data_split.json")))
    shipped_kind = calib.get("shipped", "?")
    sha = file_sha1_12(args.shipped)
    decision = json.load(open(args.decision)) if args.decision and os.path.exists(args.decision) else None
    if decision and decision.get("shipped", {}).get("file_sha1_12") != sha:
        decision = None  # the record is about another model file
    ref = parse_ref(args.ref) if args.ref else None
    rep = {"model": {"version": labels.get("version"), "file": os.path.relpath(args.shipped, REPO), "sha1_12": sha,
                     "classes": classes, "size": size, "threshold": thr, "threshold_note": labels.get("threshold_note"),
                     "blur_threshold": blur_thr, "shipped": shipped_kind,
                     "fp32_file": os.path.relpath(args.fp32, REPO), "calibration_file": os.path.relpath(args.calib, REPO)},
           "ship_decision": decision}
    if ref:
        rname, rpath, rlab, rcalib = ref
        assert rlab["classes"] == classes, "reference model has a different class order"
        rthr, rblur = rlab["threshold"], rlab["blur_threshold"]
        sref = session(rpath)
        rep["reference"] = {"name": rname, "version": rlab.get("version"), "file": os.path.relpath(rpath, REPO),
                            "sha1_12": file_sha1_12(rpath), "threshold": rthr, "blur_threshold": rblur,
                            "note": "the app's previous model, evaluated on the same images, decided with its own threshold"}
    te = np.load(os.path.join(args.data, "test.npz"))
    x, y = te["x"], te["y"]
    s32, ssh = session(args.fp32), session(args.shipped)
    otro = classes.index("otro")

    # ---- (a) test split
    p32, psh = run(s32, x), run(ssh, x)
    blur_orig = np.where(np.isnan(te["blur"]), blur_scores(x), te["blur"])  # crop views: score the crop
    final = decide(psh, blur_orig, classes, thr, blur_thr)
    groups = {c: len({g for g, yy in zip(te["group"], y) if yy == k}) for k, c in enumerate(classes)}
    rep["test"] = {"n_images": int(len(y)), "distinct_groups_per_class": groups,
                   "fp32": metrics(y, p32, classes), "shipped": metrics(y, psh, classes),
                   "app_decision_shipped": app_outcomes(y, final, classes),
                   "otro_rejection_shipped": otro_by_source(te, y, final, psh, otro),
                   "shipped_vs_fp32_top1_agreement": round(float((p32.argmax(1) == psh.argmax(1)).mean()), 4)}
    cms = [rep["test"]["fp32"]["confusion_matrix"], rep["test"]["shipped"]["confusion_matrix"]]
    titles = [f"{labels.get('version')} fp32 - test split (n={len(y)})",
              f"shipped {labels.get('version')} {shipped_kind} - test split (n={len(y)})"]
    if ref:
        pref = run(sref, x)
        fref = decide(pref, blur_orig, classes, rthr, rblur)
        rep["reference"]["test"] = {"argmax": metrics(y, pref, classes), "app_decision": app_outcomes(y, fref, classes),
                                    "otro_rejection": otro_by_source(te, y, fref, pref, otro)}
        rep["reference"]["test"]["otro_accepted"] = otro_accepted(te, y, fref, pref, otro)
        cms.append(rep["reference"]["test"]["argmax"]["confusion_matrix"])
        titles.append(f"reference {rname} ({rlab.get('version')}) - test split (n={len(y)})")
    rep["test"]["otro_accepted_shipped"] = otro_accepted(te, y, final, psh, otro, fref if ref else None)
    plot_confusion(cms, titles, classes, os.path.join(args.out, "confusion_matrix.png"))
    print("test", {k: rep["test"][k]["accuracy"] for k in ("fp32", "shipped")},
          {k: rep["test"][k]["macro_f1"] for k in ("fp32", "shipped")},
          "app F1", rep["test"]["app_decision_shipped"]["_summary"]["app_macro_f1_coffee"],
          "ref app F1", rep["reference"]["test"]["app_decision"]["_summary"]["app_macro_f1_coffee"] if ref else None)

    # ---- (b) robustness (blur check on the degraded SxS view resized to 128)
    rob, rob_ref = {}, {}
    for name, fn in DEGRADATIONS.items():
        xd = np.stack([fn(a) for a in x]).astype(np.uint8)
        bd = blur_scores(xd)
        rob[name] = robustness_row(run(ssh, xd), bd, y, classes, thr, blur_thr)
        if ref:
            rob_ref[name] = robustness_row(run(sref, xd), bd, y, classes, rthr, rblur)
        print("robustness", name, rob[name], flush=True)
    rep["robustness"] = rob
    if ref:
        rep["reference"]["robustness"] = rob_ref

    # ---- (c) field test photos
    fx, fy, fb, fp = load_field(args.field, size)
    if fx:
        pf = run(ssh, np.stack(fx))
        ff = decide(pf, np.array(fb), classes, thr, blur_thr)
        rows = []
        for path, lab, p, f, b in zip(fp, fy, pf, ff, fb):
            k = int(p.argmax())
            ok = (f == lab) if lab in classes and lab != "otro" else (f == "DUDA")
            rows.append({"path": path, "label": lab, "argmax": classes[k], "top1": round(float(p[k]), 3),
                         "blur": round(b, 1), "app_decision": str(f), "correct": bool(ok)})
        per = {}
        for lab in FIELD_LABELS:
            r = [q for q in rows if q["label"] == lab]
            if r:
                per[lab] = {"n": len(r), "app_correct": round(sum(q["correct"] for q in r) / len(r), 4),
                            "DUDA": round(sum(q["app_decision"] == "DUDA" for q in r) / len(r), 4)}
        rep["field_test"] = {"n_images": len(rows), "per_label": per,
                             "app_correct_overall": round(sum(q["correct"] for q in rows) / len(rows), 4),
                             "images": rows,
                             "note": "app_correct: coffee classes must get their own label; acaro_rojo and otro "
                                     "must get DUDA (acaro_rojo is not a model class)"}
    else:
        rep["field_test"] = {"n_images": 0, "note": "0 images - not yet collected (put photos in "
                                                    "data/field_test/<label>/ and rerun)"}

    # ---- (f) leakage check: near-duplicates of training photos
    xl, yl = leaky_sample(os.path.join(args.data, "manifest.csv"), classes, size)
    if xl is not None:
        pl = run(ssh, xl)
        rep["leakage_check"] = {
            "n_images": int(len(yl)),
            "accuracy": round(float((pl.argmax(1) == yl).mean()), 4),
            "macro_f1": round(float(f1_score(yl, pl.argmax(1), average="macro")), 4),
            "note": "unused copies (flips/rotations/colour shifts/burst shots) of TRAINING photos, i.e. what a "
                    "naive random split would have put in the test set. Compare with the group-split test."}
        print("leakage check", rep["leakage_check"])

    # ---- (e) iNatAg-mini coffee photos (unlabeled)
    inat_path = os.path.join(args.data, "extra_inat.npz")
    if os.path.exists(inat_path):
        ia = np.load(inat_path)
        crops = {}
        for frac in (0.5, 0.25, 0.12):  # centre crops: does a closer framing change the answer?
            xs = []
            for pth in ia["path"]:
                im = center_square(Image.open(str(pth)).convert("RGB"))
                c = int(im.size[0] * frac)
                o = (im.size[0] - c) // 2
                xs.append(np.asarray(im.crop((o, o, o + c, o + c)).resize((size, size), Image.BILINEAR), np.uint8))
            xs = np.stack(xs)
            crops[f"centre_{int(frac * 100)}pct"] = (xs, blur_scores(xs))
        rep["inat_coffee_photos"] = dict(inatag_eval(ssh, ia, crops, classes, thr, blur_thr), note=(
            "iNatAg-mini/coffea_arabica (iNaturalist, CC BY-NC 4.0): whole plants, flowers, cherries; disease status "
            "unknown. Not used for training (neither v1 nor v2). Desired behaviour: mostly DUDA."))
        if ref:
            rep["reference"]["inat_coffee_photos"] = inatag_eval(sref, ia, crops, classes, rthr, rblur)

    # ---- (g) iNaturalist field photos (held-out field test)
    if args.inat_field:
        from field_eval import evaluate_model, load_rows, square_of
        rows = load_rows(args.inat_field)
        sq = [square_of(r["path"]) for r in rows]
        squares, blur = [s for s, _ in sq], np.array([b for _, b in sq])
        mcfg = labels.get("inference", {}).get("multicrop")
        methods = ["single"] + ([f"mc:{mcfg['scheme']}:{mcfg['min_votes']}"] if mcfg else [])
        out, _, _ = evaluate_model(args.shipped, labels, rows, squares, blur, None, args.cache, methods)
        rep["inat_field"] = {"n_photos": len(rows), "app_method": methods[-1],
                             "field_test": {m: out["methods"][m]["field_test"] for m in methods},
                             "note": "held-out field test only (observers not used in training, except the observer of 1 ojo de gallo "
                                     "photo); iNaturalist photos "
                                     "are a proxy for Chiapas photos; details, ship rule and v1/v2 comparison in "
                                     "reports/field_eval.md"}
        print("inat field", {m: rep["inat_field"]["field_test"][m]["roya"]["correct"] for m in methods})
        if ref:
            ro, _, _ = evaluate_model(rpath, rlab, rows, squares, blur, None, args.cache, ["single"])
            rep["reference"]["inat_field"] = {"app_method": "single", "field_test": {"single": ro["methods"]["single"]["field_test"]}}

    # ---- (d) size / latency / download
    sizes = {"fp32": os.path.getsize(args.fp32), "shipped": os.path.getsize(args.shipped)}
    lat = {"fp32": latency(args.fp32, size), "shipped": latency(args.shipped, size)}
    web_ck = calib.get("ortweb_node_check", {})
    web = {"fp32": web_ck.get("fp32", {}).get("ms_median"), "shipped": web_ck.get(shipped_kind, {}).get("ms_median")}
    if ref:
        sizes["reference"] = os.path.getsize(rpath)
        lat["reference"] = latency(rpath, size)
        web["reference"] = rcalib.get("ortweb_node_check", {}).get(rcalib.get("shipped"), {}).get("ms_median")
    rep["size_latency"] = {
        "size_bytes": sizes,
        "size_mb": {k: round(v / 1e6, 2) for k, v in sizes.items()},
        "cpu_latency_ms_median_1thread": lat,
        "latency_note": "onnxruntime Python 1.19.2, CPUExecutionProvider, 1 thread, batch 1, median of 50, "
                        "build server x86 CPU (not a phone)",
        "ortweb_node_wasm_ms_median": web,
        "ortweb_note": "onnxruntime-web 1.19.2 WASM backend, 1 thread, Node.js on the build server (not a phone), "
                       "measured at export time (model/export_onnx.py, calibration record)",
        "download_seconds_computed": {
            k: {"3G_384kbps": round(v * 8 / 384e3, 1), "3G_1Mbps": round(v * 8 / 1e6, 1)} for k, v in sizes.items()},
        "download_note": "computed = bytes*8/bitrate, no protocol overhead; throttled-browser measurements are in "
                         "reports/browser_metrics.md (emulated)",
    }
    rep["data_split"] = split
    rep["calibration"] = {k: calib[k] for k in ("threshold", "blur_threshold", "val_macro_f1", "val_accuracy",
                                                "fp32_vs_keras_max_abs_diff", "shipped", "choice_reason",
                                                "candidates") if k in calib}
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "model_eval.json"), "w") as fh:
        json.dump(rep, fh, indent=2)
    with open(os.path.join(args.out, "model_eval.md"), "w") as fh:
        fh.write(render_md(rep, classes))
    print("wrote", os.path.join(args.out, "model_eval.md"))


def pct(v):
    return "n/a" if v is None else f"{100 * v:.1f}%"


def rob_table(rows):
    L = ["| degradation | accuracy (argmax) | macro-F1 | coffee fail-safe | of which blur check | "
         "selective acc. | wrong & accepted | otro rejected |", "|---|---|---|---|---|---|---|---|"]
    for k, v in rows.items():
        L.append(f"| {k} | {pct(v['accuracy_argmax'])} | {v['macro_f1_argmax']:.3f} | {pct(v['coffee_failsafe_rate'])} | "
                 f"{pct(v['coffee_failsafe_by_blur'])} | {pct(v['coffee_selective_accuracy'])} | "
                 f"{pct(v['coffee_wrong_accepted'])} | {pct(v['otro_rejected'])} |")
    return L


def inatag_lines(i):
    return ["App decision share: " + ", ".join(f"{k} {pct(v)}" for k, v in i["app_decision_share"].items()) + ".", "",
            "Same photos cropped to the centre (closer framing), app decision counts: " +
            "; ".join(f"{k}: " + ", ".join(f"{a} {b}" for a, b in v.items())
                      for k, v in i.get("app_decision_counts_centre_crops", {}).items()) + "."]


def render_md(r, classes):
    t, m = r["test"], r["model"]
    ref = r.get("reference")
    tag = f"{m.get('version') or 'shipped'}@{m['threshold']}"
    rtag = f"{ref['name']}@{ref['threshold']}" if ref else None
    a, s = t["app_decision_shipped"], t["app_decision_shipped"]["_summary"]
    ra = ref["test"]["app_decision"] if ref else None
    rs = ra["_summary"] if ref else None
    L = ["# Cafetal image model - evaluation report", "",
         f"Generated by `model/evaluate.py`. Shipped model: **{m.get('version')}** (`{m.get('file', 'app/model/cafetal.onnx')}`, "
         f"{m['shipped']}, sha1 {m.get('sha1_12')}), input {m['size']}x{m['size']}, **threshold {m['threshold']}**"
         + (f" ({m['threshold_note']})" if m.get("threshold_note") else "") + f", blur threshold {m['blur_threshold']}."
         + (f" Reference column: **{ref['name']}** ({ref['version']}, threshold {ref['threshold']}), {ref['note']}."
            if ref else "") + " All numbers below are **measured** unless marked *computed*.", ""]
    d = r.get("ship_decision")
    if d:
        f1s, f1r = s.get("app_macro_f1_coffee"), (rs or {}).get("app_macro_f1_coffee")
        drop = f" it drops {100 * (f1r - f1s):.2f} points ({f1s:.4f} vs {f1r:.4f} for {rtag}, section (a))" \
            if ref and f1s is not None and f1r is not None else ""
        L += [f"> **Shipped by explicit team decision, as an exception to the pre-registered ship rule** ({d['date']}, "
              f"`model/ship_decision.json`). {d['rule_outcome']}: condition {d['exception']};{drop}. "
              f"Why the team shipped it anyway: {d['reason']} Full rule, numbers and decision: `reports/field_eval.md` "
              "(\"Result\", \"Threshold trade-off\").", ""]
    fld = r.get("inat_field")
    fline = ""
    if fld:
        from field_eval import exact_rate
        fr = fld["field_test"][fld["app_method"]]["roya"]
        fline = (f" On held-out iNaturalist field photos of leaf rust (a proxy, section (g)) the shipped model answers "
                 f"{pct(exact_rate(fr, 'roya', 'correct'))} correctly ({fr['answer_counts']['roya']} of {fr['n']})")
        if ref and "inat_field" in ref:
            rr = ref["inat_field"]["field_test"]["single"]["roya"]
            fline += f"; {ref['name']}: {pct(exact_rate(rr, 'roya', 'correct'))} ({rr['answer_counts']['roya']} of {rr['n']})"
        fline += "."
    L += ["> Read this first: the test split comes from the same Kenyan dataset as training (JMuBEN), split by "
          "near-duplicate group. It is NOT a field test. The `sano` class has only "
          f"{t['distinct_groups_per_class'].get('sano')} distinct source photos in test "
          "(and 7 in train) - see 'Data' below. Field accuracy on Chiapas photos is unknown until "
          "`data/field_test/` is filled." + fline, "",
          "## (a) Held-out test split (group split, 70/15/15)", "",
          "| model | threshold | accuracy (argmax) | macro-F1 (argmax, 6 classes) | app-level macro-F1 (5 coffee classes, DUDA = miss) |",
          "|---|---|---|---|---|",
          f"| {m.get('version')} fp32 (same weights, float32) | - | {pct(t['fp32']['accuracy'])} | {t['fp32']['macro_f1']:.4f} | - |",
          f"| **shipped {m.get('version')}** ({m['shipped']}) | {m['threshold']} | {pct(t['shipped']['accuracy'])} | "
          f"{t['shipped']['macro_f1']:.4f} | {s['app_macro_f1_coffee']:.4f} |"]
    if ref:
        L.append(f"| reference {ref['name']} ({ref['version']}) | {ref['threshold']} | {pct(ref['test']['argmax']['accuracy'])} | "
                 f"{ref['test']['argmax']['macro_f1']:.4f} | {rs['app_macro_f1_coffee']:.4f} |")
    ag = t["shipped_vs_fp32_top1_agreement"]
    L += ["", f"Top-1 agreement fp32 vs shipped on test: {100 * ag:.2f}% ({round((1 - ag) * t['n_images'])} of "
          f"{t['n_images']} images differ). The argmax "
          "columns do not depend on the threshold; the app-level column does (a photo sent to DUDA counts as a miss).", "",
          "Per class (shipped model, argmax before threshold):", "",
          "| class | precision | recall | F1 | test images | distinct source groups |", "|---|---|---|---|---|---|"]
    for c in classes:
        pc = t["shipped"]["per_class"][c]
        L.append(f"| {c} | {pct(pc['precision'])} | {pct(pc['recall'])} | {pc['f1']:.3f} | {pc['support']} | "
                 f"{t['distinct_groups_per_class'][c]} |")
    L += ["", "![confusion matrix](confusion_matrix.png)", "",
          "### What the app would do (threshold + blur check; `otro` -> DUDA)", ""]
    if ref:
        L += [f"| true class | {tag} correct | {tag} wrong (accepted) | {tag} DUDA (fail-safe) | {rtag} correct | "
              f"{rtag} wrong (accepted) | {rtag} DUDA |", "|---|---|---|---|---|---|---|"]
    else:
        L += ["| true class | correct | wrong (accepted) | DUDA (fail-safe) |", "|---|---|---|---|"]
    for c in classes:
        if c in a and c != "otro":
            row = f"| {c} | {pct(a[c]['correct'])} | {pct(a[c]['wrong'])} | {pct(a[c]['DUDA'])} |"
            if ref:
                row += f" {pct(ra[c]['correct'])} | {pct(ra[c]['wrong'])} | {pct(ra[c]['DUDA'])} |"
            L.append(row)

    def both(key, fmt=pct):
        return f"**{fmt(s[key])}**" + (f" ({rtag}: {fmt(rs[key])})" if ref else "")
    L += ["", f"- Coffee images answered (coverage): {both('coffee_coverage')}; accuracy of the answered ones "
              f"(selective accuracy): {both('coffee_selective_accuracy')}.",
          f"- Diseased leaves told 'sano' (the dangerous error): {both('diseased_called_sano')}.",
          f"- `otro` test images sent to DUDA: **{pct(a.get('otro', {}).get('rejected_to_DUDA'))}**"
          + (f" ({rtag}: {pct(ra.get('otro', {}).get('rejected_to_DUDA'))})" if ref else "") + ". By source:", ""]
    if ref:
        L += [f"| otro source / view | n | {tag} rejected (DUDA) | {tag} argmax = otro | {rtag} rejected (DUDA) |",
              "|---|---|---|---|---|"]
        for k, v in t["otro_rejection_shipped"].items():
            L.append(f"| {k} | {v['n']} | {pct(v['rejected'])} | {pct(v['argmax_otro'])} | "
                     f"{pct(ref['test']['otro_rejection'][k]['rejected'])} |")
    else:
        L += ["| otro source / view | n | rejected (DUDA) | argmax = otro |", "|---|---|---|---|"]
        for k, v in t["otro_rejection_shipped"].items():
            L.append(f"| {k} | {v['n']} | {pct(v['rejected'])} | {pct(v['argmax_otro'])} |")
    fa = t.get("otro_accepted_shipped")
    if fa is not None:
        n_otro = a.get("otro", {}).get("n")
        journey = any(q["image"].endswith("Apple-Scab-image-02.jpg") for q in fa)
        L += ["", f"False alarms: the {len(fa)} `otro` test image views (of {n_otro}; {len({q['image'] for q in fa})} "
              f"distinct photos, view `crop` = a close-up crop of the same photo) that {tag} does NOT send to DUDA. "
              "Images are not in the repository (PlantDoc / Imagenette terms); paths are under the raw-data folder."
              + (" `Apple-Scab-image-02.jpg` was the PlantDoc image of the journey test (`tests/e2e/journey.mjs`), "
                 "which now uses the first PlantDoc test image the shipped model rejects; that check tests the "
                 "fail-safe path, not the false-alarm rate (that is this table)." if journey else ""), "",
              "| image | view | shipped answer (top-1) |" + (f" {rtag} answer |" if ref else ""),
              "|---|---|---|" + ("---|" if ref else "")]
        for q in fa:
            L.append(f"| {q['image']} | {q['view']} | {q['answer']} ({q['top1']:.3f}) |"
                     + (f" {q.get('reference_answer')} |" if ref else ""))
        if ref and ref["test"].get("otro_accepted") is not None:
            L += ["", f"{rtag} accepts {len(ref['test']['otro_accepted'])}: " + "; ".join(
                f"{q['image']} ({q['view']}) -> {q['answer']} ({q['top1']:.3f})" for q in ref["test"]["otro_accepted"]) + "."]
    L += ["", f"## (b) Robustness to phone-like degradations (test split, shipped model {tag})", "",
          "Proxy for the field gap: the same test images degraded. 'fail-safe' = the app says "
          "\"No estoy seguro\" (DUDA) because of the threshold, the blur check or an `otro` prediction. "
          "Here the blur check runs on the cached 224 px view resized to 128 px (also for 'clean'), so its "
          "rejections are a little higher than in (a), which scores the original files.", ""]
    L += rob_table(r["robustness"])
    if ref and "robustness" in ref:
        L += ["", f"Reference {rtag} on the same degraded images:", ""] + rob_table(ref["robustness"])
    f = r["field_test"]
    L += ["", "## (c) Field test - the team's own photos (`data/field_test/`)", ""]
    if f["n_images"] == 0:
        L.append("**0 images - not yet collected.** Put photos in `data/field_test/<label>/` "
                 "(labels: " + ", ".join(FIELD_LABELS) + ") and rerun `python model/evaluate.py`.")
    else:
        L += [f"{f['n_images']} images, app decision correct: **{pct(f['app_correct_overall'])}** "
              f"({f['note']}).", "", "| label | n | app correct | DUDA |", "|---|---|---|---|"]
        for k, v in f["per_label"].items():
            L.append(f"| {k} | {v['n']} | {pct(v['app_correct'])} | {pct(v['DUDA'])} |")
        L += ["", "| photo | label | argmax | top-1 | blur | app says |", "|---|---|---|---|---|---|"]
        for q in f["images"]:
            L.append(f"| {q['path']} | {q['label']} | {q['argmax']} | {q['top1']} | {q['blur']} | {q['app_decision']} |")
    if "inat_coffee_photos" in r:
        i = r["inat_coffee_photos"]
        L += ["", "## (e) Real phone photos of coffee plants (iNaturalist, unlabeled)", "",
              f"{i['n_images']} photos. {i['note']}", "", f"Shipped {tag}:", ""] + inatag_lines(i)
        if ref and "inat_coffee_photos" in ref:
            L += ["", f"Reference {rtag}:", ""] + inatag_lines(ref["inat_coffee_photos"])
        L += ["", "Meaning: these are mostly whole plants, flowers and cherries, not leaf close-ups; the desired answer "
              "is the fail-safe. Disease answers here are false alarms or real symptoms we cannot check (health is "
              "unknown). Labelled Chiapas photos are needed."]
    if "inat_field" in r:
        from field_eval import group_table
        g = r["inat_field"]
        L += ["", "## (g) Labelled field photos (iNaturalist, held-out field test)", "",
              f"{g['note'][0].upper() + g['note'][1:]}. Decided like the app (`{g['app_method']}`).", ""]
        for meth, res in g["field_test"].items():
            L += [f"Shipped {tag}, app rule `{meth}`:", ""] + group_table(res) + [""]
        if ref and "inat_field" in ref:
            L += [f"Reference {rtag}, app rule `single`:", ""] + group_table(ref["inat_field"]["field_test"]["single"]) + [""]
    if "leakage_check" in r:
        lk = r["leakage_check"]
        L += ["", "## (f) Why we split by group: leakage check", "",
              f"Same shipped model on {lk['n_images']} {lk['note'].rstrip('.')}: accuracy **{pct(lk['accuracy'])}**, "
              f"macro-F1 **{lk['macro_f1']:.3f}** vs. **{pct(t['shipped']['accuracy'])}** / "
              f"**{t['shipped']['macro_f1']:.3f}** on the group-split test."]
    z = r["size_latency"]
    L += ["", "## (d) Size, speed, download", "",
          "| model | size | CPU latency, 1 thread (ORT Python) | onnxruntime-web WASM, 1 thread (Node) | "
          "3G 384 kbps (*computed*) | 1 Mbps (*computed*) |", "|---|---|---|---|---|---|"]
    web = z["ortweb_node_wasm_ms_median"]
    names = {"fp32": f"{m.get('version')} fp32", "shipped": f"shipped {m.get('version')} ({m['shipped']})",
             "reference": f"reference {ref['name']} ({ref['version']})" if ref else "reference"}
    for k in z["size_bytes"]:
        wk = web.get(k)
        L.append(f"| {names[k]} | {z['size_mb'][k]} MB ({z['size_bytes'][k]} B) | {z['cpu_latency_ms_median_1thread'][k]} ms | "
                 f"{'n/a' if wk is None else f'{wk:.1f} ms'} | {z['download_seconds_computed'][k]['3G_384kbps']} s | "
                 f"{z['download_seconds_computed'][k]['3G_1Mbps']} s |")
    L += ["", f"Latency: {z['latency_note']}. Web: {z['ortweb_note']}. Download: {z['download_note']}.", ""]
    c = r["calibration"]
    th = c["threshold"]
    L += [f"## Calibration (validation split, export of {m.get('version')}; record `{m.get('calibration_file', '')}`)", "",
          f"- Shipped: **{c.get('shipped')}** - {c.get('choice_reason')}. "
          f"fp32 ONNX vs Keras max |diff| on 20 images: {c['fp32_vs_keras_max_abs_diff']:.2e}.", "",
          "| candidate | size | val accuracy | val macro-F1 | top-1 agreement with fp32 | runs in onnxruntime-web |",
          "|---|---|---|---|---|---|"]
    for k, v in c.get("candidates", {}).items():
        L.append(f"| {k} | {v['size_bytes'] / 1e6:.2f} MB | {pct(v['val_accuracy'])} | {v['val_macro_f1']:.3f} | "
                 f"{pct(v['top1_agreement_with_fp32'])} | {'yes' if v['ortweb_node'].get('ok') else 'NO'} |")
    L += [""]
    if abs(th["value"] - m["threshold"]) > 1e-9:
        L += [f"- Confidence threshold **shipped: {m['threshold']}** (from `app/model/labels.json`"
              + (f": {m['threshold_note']}" if m.get("threshold_note") else "") + "). It was re-chosen after export "
              "with a false-alarm constraint on separate calibration data (`model/field_threshold.py`: lowest t with "
              "<= 5 % disease answers on 400 new *Coffea* photos and >= 98 % `otro` rejection on validation). "
              f"The export-time value below ({th['value']}) came from Kenyan validation images only and is kept for "
              "the record."]
    L += [f"- Export-time confidence threshold **{th['value']}** (data-driven value {th.get('data_driven_value')}: {th['rule']}; "
          f"policy floor {th.get('policy_floor')}: {th.get('floor_reason', '')}).", "",
          "| threshold | coverage (clean val) | selective accuracy (clean val) | coverage (clean + degraded val) | "
          "selective accuracy (clean + degraded val) |", "|---|---|---|---|---|"]
    for row, row2 in zip(th["curve"], th.get("curve_with_degradations", th["curve"])):
        if abs(row["threshold"] * 20 - round(row["threshold"] * 20)) < 1e-6 or row["threshold"] == th["value"]:
            L.append(f"| {row['threshold']:.2f} | {pct(row['coverage'])} | {pct(row['selective_accuracy'])} | "
                     f"{pct(row2['coverage'])} | {pct(row2['selective_accuracy'])} |")
    b = c["blur_threshold"]
    L += ["", f"- Blur threshold **{b['value']}** ({b['rule']}; algorithm in `model/blur.py`, the app must match).", "",
          "| class | val n | median Laplacian var | 5th pct | real rejected | blurred r3 median | blurred r3 rejected | "
          "blurred r4 rejected |", "|---|---|---|---|---|---|---|---|"]
    for k, v in b["per_class"].items():
        L.append(f"| {k} | {v['n']} | {v['real_median']} | {v['real_p5']} | {pct(v['real_rejected'])} | "
                 f"{v['blur_r3_median']} | {pct(v['blur_r3_rejected'])} | {pct(v['blur_r4_rejected'])} |")
    dsp = r["data_split"]
    L += ["", "## Data: near-duplicate grouping and split", "",
          f"Grouping: {dsp['hash']}. Split 70/15/15 by group within each source/label.", "",
          "| source/label | images | exact-duplicate groups | near-duplicate groups | largest group | "
          "groups train/val/test |", "|---|---|---|---|---|---|"]
    for k, v in dsp["strata"].items():
        g = v["groups_per_split"]
        L.append(f"| {k} | {v['images']} | {v['exact_dup_groups']} | {v['groups']} | {v['largest_group']} | "
                 f"{g.get('train', 0)}/{g.get('val', 0)}/{g.get('test', 0)} |")
    sel = dsp["selected"]
    L += ["", "Images actually used (round-robin over groups, capped): " +
          "; ".join(f"{sp}: " + ", ".join(f"{c} {sel[sp][c]}" for c in classes) for sp in ("train", "val", "test")) + ".",
          "v2 adds field training views of 147 screened iNaturalist photos to train (see `reports/field_eval.md`, "
          "Protocol); validation and test are unchanged." if (m.get("version") or "").endswith("v2") else "", ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
