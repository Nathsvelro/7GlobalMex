"""Field evaluation on iNaturalist photos: single view (app v1 rule) vs multicrop, one or more models.

  python model/field_eval.py --data /home/user/data_proc/cafetal --inat /home/user/data_raw/inat \
      --model v1=model/checkpoints/v1/cafetal.onnx --model v2=model/checkpoints/v2/cafetal_fp16_weights.onnx

Writes reports/field_eval.json + reports/field_eval.md. Every photo is decided exactly like the app:
centre-square crop, resize to 224, blur check on the 128 px view (model/blur.py), threshold from
labels.json, "otro" -> DUDA; multicrop per model/multicrop.py.
Inputs: reports/field_inat_attribution.csv + reports/field_inat_screening.csv (model/inat_field.py),
images in <inat>/photos/, JMuBEN/otro test split in <data>/test.npz.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from sklearn.metrics import f1_score

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blur import BLUR_SIZE, center_square, laplacian_variance, laplacian_variance_array  # noqa: E402
from inat_field import ATTRIBUTION, MEXICO_RULE, image_path, read_attribution  # noqa: E402
from multicrop import SCHEMES, decide_multicrop, decide_single, tiles, views  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENING = os.path.join(REPO, "reports", "field_inat_screening.csv")
DISEASES = ("roya", "minador", "phoma", "cercospora")
ANSWERS = ("sano", "roya", "minador", "phoma", "cercospora", "DUDA")


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
    for lab in ("roya", "minador", "cercospora", "ojo_de_gallo"):
        g[f"{lab}"] = (lab, sel(lambda r, lab=lab: r["label"] == lab))
        g[f"{lab} screened"] = (lab, sel(lambda r, lab=lab: r["label"] == lab and r["screened"] == "yes"))
        if lab == "roya":
            g["roya Mexico+GT box"] = (lab, sel(lambda r: r["label"] == "roya" and r["in_mexico_box"] == "1"))
            g["roya Mexico"] = (lab, sel(lambda r: r["label"] == "roya" and r["in_mexico"] == "1"))
    g["minador Mexico"] = ("minador", sel(lambda r: r["label"] == "minador" and r["in_mexico"] == "1"))
    g["coffea sample"] = ("coffea", sel(lambda r: r["label"] == "coffea"))
    g["coffea sample Mexico"] = ("coffea", sel(lambda r: r["label"] == "coffea" and r["in_mexico"] == "1"))
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
    """diseased field-test photos (roya, minador, cercospora, ojo de gallo) accepted as 'sano'."""
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
    res = {"generated_by": "model/field_eval.py", "n_photos": len(rows), "mexico_rule": MEXICO_RULE,
           "multicrop": {"chosen": mc, "selection": sel_table,
                         "rule": " ".join(select_scheme.__doc__.split(":", 1)[1].split()).rstrip(".")},
           "photos": photo_summary(rows), "models": {}}
    per_photo = {}
    for name, mpath, labels in specs:
        out, _, per_photo[name] = evaluate_model(mpath, labels, rows, squares, blur, npz, args.cache, ["single"] + schemes)
        out["version"] = labels.get("version")
        res["models"][name] = out
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
    with open(os.path.join(args.out, "field_eval_photos.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        keys = [(n, m) for n in res["models"] for m in ("single", mc)]
        w.writerow(["photo_id", "label", "split", "screened", "in_mexico"] + [f"{n}_{m}" for n, m in keys])
        for i, r in enumerate(rows):
            w.writerow([r["photo_id"], r["label"], r["split"], r["screened"], r["in_mexico"]] +
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
                    "in_mexico": sum(r["in_mexico"] == "1" for r in rs),
                    "in_mexico_box": sum(r["in_mexico_box"] == "1" for r in rs),
                    "licenses": dict(Counter(r["license"] for r in rs)),
                    "quality_grade": dict(Counter(r["quality_grade"] for r in rs))}
    return out


# ---------------------------------------------------------------- markdown
ALARMS = os.path.join(REPO, "reports", "field_coffea_v2_alarms.csv")
THRESHOLD_TEST = os.path.join(REPO, "reports", "field_v2_threshold_test.json")
THRESHOLD_SWEEP = os.path.join(REPO, "reports", "field_v2_threshold_sweep.json")


def conclusions(r):
    models, names = r["models"], list(r["models"])
    base, mc = names[0], r["multicrop"]["chosen"]
    b = models[base]["methods"]["single"]
    ba = b["all_photos"]
    roya = ba["roya"]
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
        L.append(f"- **{n} (trained with field photos) finds rust in field photos**: roya correct & accepted "
                 f"{pct(f['roya']['correct'])}{ci(f['roya']['correct_ci95'])} on the held-out field test (n={f['roya']['n']}, "
                 f"{pct(bt['roya']['correct'])} for {base}); Mexico+Guatemala box {pct(f['roya Mexico+GT box']['correct'])} "
                 f"(n={f['roya Mexico+GT box']['n']}); Mexico only {f['roya Mexico']['answer_counts']['roya']} of "
                 f"{f['roya Mexico']['n']}. Minador {f['minador']['answer_counts']['minador']} of {f['minador']['n']}, "
                 f"cercospora {f['cercospora']['answer_counts']['cercospora']} of {f['cercospora']['n']} "
                 f"({f['cercospora']['answer_counts']['roya']} called roya). Kenyan test macro-F1 "
                 f"{jt['jmuben_macro_f1_argmax']:.4f} ({base}: {bj['jmuben_macro_f1_argmax']:.4f}); no diseased leaf "
                 "was called \"sano\"." if field_dangerous(x) == 0 and jt["jmuben_diseased_called_sano_n"] == 0 else
                 f"- **{n}**: roya correct {pct(f['roya']['correct'])}{ci(f['roya']['correct_ci95'])} (n={f['roya']['n']}).")
        L.append(f"- **But {n} raises false alarms**: disease answers on the Coffea plant photos "
                 f"{pct(f['coffea sample']['disease_answer'])}{ci(f['coffea sample']['disease_answer_ci95'])} "
                 f"({base}: {pct(bt['coffea sample']['disease_answer'])}); non-coffee test images rejected "
                 f"{pct(jt['otro_rejected'])} ({base}: {pct(bj['otro_rejected'])}); ojo de gallo sent to DUDA "
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
        L.append(f"- **v2 at t = {tt['chosen_t']:.2f} (re-chosen on calibration data; the model the app now ships)**: "
                 f"roya correct & accepted {rate('roya', with_ci=True)} ({k('roya')}), "
                 f"screened {rate('roya screened')} ({k('roya screened')}), Mexico+Guatemala box "
                 f"{rate('roya Mexico+GT box')} ({k('roya Mexico+GT box')}), Mexico only {k('roya Mexico')}; "
                 f"minador {k('minador')}, cercospora {k('cercospora')}; ojo de gallo sent to DUDA "
                 f"{rate('ojo_de_gallo', 'DUDA')} ({k('ojo_de_gallo', 'DUDA')}); disease answers on the Coffea plant "
                 f"photos {rate('coffea sample', 'disease_answer', True)} ({k('coffea sample', 'disease_answer')}); "
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
    L += [
          "- **What would fix it**: labelled photos from Chiapas, healthy *and* diseased, taken with the app - exactly "
          "what the officer's confirmations in the hub (`labels` table) collect - then rerun this protocol "
          "(`model/inat_field.py`, `model/train.py --extra`, `model/field_eval.py`). Healthy field leaves labelled by "
          "a person are the missing piece; we did not label iNaturalist *Coffea* photos as healthy because their "
          "health is unknown."]
    return L


GROUP_ORDER = ["roya", "roya screened", "roya Mexico+GT box", "roya Mexico", "minador", "minador screened",
               "minador Mexico", "cercospora", "cercospora screened", "ojo_de_gallo", "ojo_de_gallo screened",
               "coffea sample", "coffea sample Mexico"]


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
         "DUDA [95% CI] | answers: sano / roya / minador / phoma / cercospora / DUDA |", "|---|---|---|---|---|---|---|"]
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
            L.append(f"| {g} (desired: DUDA) | {st['n']} | (no correct class) | {r('wrong_accepted')}"
                     f"{ci(st['wrong_accepted_ci95'])} | {st['dangerous_sano']} | **{r('DUDA')}**{ci(st['DUDA_ci95'])} | {cnt} |")
        else:
            L.append(f"| {g} | {st['n']} | **{r('correct')}**{ci(st['correct_ci95'])} | {r('wrong_accepted')} | "
                     f"{st['dangerous_sano']} | {r('DUDA')}{ci(st['DUDA_ci95'])} | {cnt} |")
    return L


def render_md(r):
    models = r["models"]
    names = list(models)
    base = names[0]
    mc = r["multicrop"]["chosen"]
    ph = r["photos"]
    sr = r["ship_rule"]
    L = ["# Field evaluation on iNaturalist photos (proxy for Chiapas field photos)", "",
         "Generated by `model/field_eval.py` (all numbers **measured** on the files listed below; 95 % intervals are "
         "Wilson score intervals). Photos: iNaturalist open data, decided exactly like the phone app "
         "(centre-square crop, 224 px, blur check on the 128 px view, threshold from `labels.json`, `otro` -> DUDA).", "",
         "> **Read this first.** iNaturalist photos are a *proxy* for Chiapas field photos, not a substitute: most are "
         "from other countries (only " + str(ph["roya"]["in_mexico"]) + " roya photos are inside Mexico), taken with "
         "many different cameras and framings, and many show severe, textbook infections. Labels are the iNaturalist "
         "community identification (\"research\" or \"needs_id\" grade), not an agronomist's diagnosis. Sample sizes "
         "are small, so the intervals are wide.", "",
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
        tradeoff = render_tradeoff(tt, sw)
    else:
        L += [f"**{sr['fired']}.** Shipped: `{sr['shipped']}`.", ""]
    # comparison table on the held-out field test
    cols = [(base, "single"), (base, mc)] + [(n, m) for n in names[1:] for m in ("single", mc)]
    head = ["metric"] + [f"{n} {'single view' if m == 'single' else m.replace('mc:', 'multicrop ')}" for n, m in cols]
    L += ["### Comparison (held-out field test + Kenyan test split)", "",
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
    row("roya: correct & accepted, all field-test photos", ft("roya"))
    row("roya: correct & accepted, screened (leaf symptom visible)", ft("roya screened"))
    row("roya: correct & accepted, Mexico+Guatemala box", ft("roya Mexico+GT box"))
    row("roya: correct & accepted, Mexico only", ft("roya Mexico"))
    row("roya: DUDA, all field-test photos", ft("roya", "DUDA"))
    row("minador: correct & accepted", ft("minador"))
    row("cercospora: correct & accepted", ft("cercospora"))
    row("ojo de gallo (not a model class): DUDA (desired)", ft("ojo_de_gallo", "DUDA"))
    row("diseased field-test photos accepted as \"sano\" (dangerous)", lambda x: str(field_dangerous(x)))
    row("wrong-but-accepted, all diseased field-test photos", lambda x: str(sum(
        round(x["field_test"][g]["wrong_accepted"] * x["field_test"][g]["n"]) for g in ("roya", "minador", "cercospora", "ojo_de_gallo"))))
    row("Coffea arabica sample: disease answers (health unknown)", ft("coffea sample", "disease_answer"))
    row("JMuBEN test macro-F1 (argmax, 6 classes)", lambda x: f"{x['jmuben_otro_test']['jmuben_macro_f1_argmax']:.4f}")
    row("JMuBEN test app macro-F1 (DUDA = miss, 5 coffee classes)", lambda x: f"{x['jmuben_otro_test']['jmuben_app_macro_f1']:.4f}")
    row("JMuBEN test: diseased accepted as \"sano\" (count)", lambda x: str(x["jmuben_otro_test"]["jmuben_diseased_called_sano_n"]))
    row("otro test images rejected (DUDA)", lambda x: f"{pct(x['jmuben_otro_test']['otro_rejected'])}{ci(x['jmuben_otro_test']['otro_rejected_ci95'])} (n={x['jmuben_otro_test']['otro_n']})")
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
          "view; otherwise DUDA.", "",
          f"Scheme chosen **without the field test** ({r['multicrop']['rule']}): **{mc}**.", "",
          "| scheme | inferences per photo | validation otro rejected | validation coffee correct & accepted | "
          "field-dev roya correct (baseline never saw these) |", "|---|---|---|---|---|"]
    for t in r["multicrop"]["selection"]:
        L.append(f"| {t['method']} | {t['inferences']} | {pct(t['val_otro_rejected'])} | "
                 f"{pct(t['val_coffee_correct_accepted'])} | {pct(t['field_dev_roya_correct'])} (n={t['field_dev_roya_n']}) |")
    L += ["", "All schemes, held-out field test (for transparency; only the pre-registered scheme enters the ship rule):", "",
          "| model | method | roya correct | roya screened correct | ojo de gallo DUDA | Coffea disease answers | "
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
          "coffeella* -> minador; *Cercospora coffeicola* -> cercospora; *Mycena citricolor* (ojo de gallo / American "
          "leaf spot, not one of our classes) -> the right answer is DUDA; *Coffea arabica* -> coffee plant, health "
          "unknown (never trained on, only used to count disease answers).",
          f"- **Mexico rule**: {r['mexico_rule']}",
          "- **Split by observer** (seed 42, `model/inat_field.py`): field test = every observer with a photo in the box "
          "+ a random ~30 % of the other observers of each disease; ojo de gallo is always test; the rest is field-train "
          f"(used only by the v2 experiment). Coffea: one photo per observer, {ph['coffea']['observers']} distinct "
          "observers, none of them a field-train observer.",
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
          "| label | photos | observations | observers | field-train / field-test | screened yes | in Mexico | in box | licenses |",
          "|---|---|---|---|---|---|---|---|---|"]
    for lab, v in ph.items():
        sp = v["split"]
        tr_te = (f"{sp.get('field_train', 0)} / {sp.get('field_test', 0)}" if lab != "coffea" else f"eval only ({sp.get('coffea_eval', 0)})")
        L.append(f"| {lab} | {v['photos']} | {v['observations']} | {v['observers']} | {tr_te} | "
                 f"{'n/a' if v['screened_yes'] is None else v['screened_yes']} | {v['in_mexico']} | {v['in_mexico_box']} | "
                 + ", ".join(f"{k} {c}" for k, c in sorted(v["licenses"].items())) + " |")
    L += ["", "Models: " + "; ".join(f"`{n}` = `{models[n]['model']}` ({models[n].get('version')}, sha1 "
                                     f"{models[n]['sha1_12']}, threshold {models[n]['threshold']}, blur "
                                     f"{models[n]['blur_threshold']})" for n in names) + "."
          + (f" The app ships the `{tt['candidate'].split('@')[0]}` file as `app/model/cafetal.onnx` with threshold "
             f"{tt['chosen_t']} (team decision, see \"Result\")." if team else ""), ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
