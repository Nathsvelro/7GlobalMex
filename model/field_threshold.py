"""Constrained confidence-threshold recalibration for the field model (v2), then ONE test evaluation.

Why: v2 (model/field_eval.py) found rust in field photos but failed the ship rule on false alarms; its
threshold (0.70) came from Kenyan validation data with no false-alarm constraint. Here the threshold is
chosen on CALIBRATION data that shares no photo and no observer with any test set, then the unchanged ship
rule is applied once on the held-out test sets.

  # 1. new Coffea arabica calibration sample (observers not in any field test/train set) + download
  python model/field_threshold.py sample --inat /home/user/data_raw/inat
  # 2. sweep on calibration data only, choose t -> reports/field_v2_threshold_sweep.{json,md}
  python model/field_threshold.py sweep --data /home/user/data_proc/cafetal --inat /home/user/data_raw/inat \
      --model v2=model/checkpoints/v2/app/cafetal.onnx:model/checkpoints/v2/app/labels.json \
      --ref v1=model/checkpoints/v1/cafetal.onnx:model/checkpoints/v1/labels.json
  # 3. single test evaluation at the chosen t + ship rule -> reports/field_v2_threshold_test.json and a
  #    "Threshold trade-off" section in reports/field_eval.md
  python model/field_threshold.py test --data /home/user/data_proc/cafetal --inat /home/user/data_raw/inat \
      --model v2=... --ref v1=...
  # 4. only after a human ship decision naming this candidate (model/ship_decision.json): copy the model into
  #    app/model/ and write app/model/labels.json with the calibrated threshold
  python model/field_threshold.py install --model v2=model/checkpoints/v2/app/cafetal.onnx:model/checkpoints/v2/app/labels.json

Calibration sets (never used to choose anything in the test sets):
  coffea   reports/field_calib_attribution.csv: one photo (first of the observation) per observer, observers
           that do not appear in reports/field_inat_attribution.csv at all (so not in the 399-photo Coffea test
           sample, nor among the field-test or field-train disease observers). Images in <inat>/photos_calib/.
  otro     the VALIDATION split "otro" images (<data>/val.npz), not the test split.
  recall   (a) field_train disease photos screened "no" (not used to train v2, not in the field test) and
           (b) JMuBEN validation images. Both are weak: (a) are photos where the symptom is NOT clearly visible
           and share observers with v2's training photos; (b) are Kenyan close-ups. Recall is reported, not
           used to choose t (the lowest feasible t is also the one with the highest recall).
Decision: the app's exact rule (blur check, top-1 >= t, "otro" -> DUDA; multicrop per model/multicrop.py).
"""
import argparse
import csv
import json
import os
import random
import sys
from collections import Counter

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from field_eval import (DISEASES, SCREENING, decisions, evaluate_model, field_dangerous, file_hash,  # noqa: E402
                        load_rows, npz_with_blur, predict_photos, session, ship_rule, square_of, wilson)
from inat_field import (ATTRIBUTION, URL, _f, image_path, in_box, in_mexico, read_attribution,  # noqa: E402
                        write_attribution)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALIB_ATTRIBUTION = os.path.join(REPO, "reports", "field_calib_attribution.csv")
SWEEP_JSON = os.path.join(REPO, "reports", "field_v2_threshold_sweep.json")
SWEEP_MD = os.path.join(REPO, "reports", "field_v2_threshold_sweep.md")
TEST_JSON = os.path.join(REPO, "reports", "field_v2_threshold_test.json")
FIELD_MD = os.path.join(REPO, "reports", "field_eval.md")
MARK_A, MARK_B = "<!-- threshold-tradeoff:start -->", "<!-- threshold-tradeoff:end -->"
SHIP_DECISION = os.path.join(REPO, "model", "ship_decision.json")
MAX_COFFEA_ALARM, MIN_OTRO_REJECT = 0.05, 0.98
GRID = [round(0.70 + 0.005 * i, 3) for i in range(60)]  # 0.700 ... 0.995
MC = "mc:2x2:2"


# ---------------------------------------------------------------- 1. Coffea calibration sample
def build_calib_sample(inat_dir, photos_dir, n=400, seed=2026, threads=8):
    used = {r["observer_id"] for r in read_attribution(ATTRIBUTION)}
    obs = {r["observation_uuid"]: r for r in csv.DictReader(open(os.path.join(inat_dir, "obs_coffee.tsv")),
                                                            delimiter="\t")}
    by_obs = {}
    for p in csv.DictReader(open(os.path.join(inat_dir, "photos_coffee.tsv")), delimiter="\t"):
        o = obs.get(p["observation_uuid"])
        if o is None or o["taxon_id"] != "64342" or int(p["position"]) != 0 or p["observer_id"] in used:
            continue
        lat, lon = _f(o["latitude"]), _f(o["longitude"])
        by_obs.setdefault(p["observer_id"], []).append({
            "photo_id": p["photo_id"], "observation_uuid": p["observation_uuid"], "observer_id": p["observer_id"],
            "license": p["license"], "taxon_name": "Coffea arabica", "label": "coffea", "split": "coffea_calib",
            "quality_grade": o["quality_grade"], "observed_on": o["observed_on"],
            "lat": "" if lat is None else f"{lat:.1f}", "lon": "" if lon is None else f"{lon:.1f}",
            "in_mexico_box": int(in_box(lat, lon)), "in_mexico": int(in_mexico(lat, lon)),
            "ext": p["extension"].lower(), "inat_url": f"https://www.inaturalist.org/photos/{p['photo_id']}"})
    rng = random.Random(seed)
    order = sorted(by_obs, key=int)
    rng.shuffle(order)
    picks = [rng.choice(sorted(by_obs[ob], key=lambda r: int(r["photo_id"]))) for ob in order]
    print(f"candidate observers (not in any field set): {len(order)}; excluded observers: {len(used)}")
    import urllib.request
    from concurrent.futures import ThreadPoolExecutor
    d = os.path.join(photos_dir, "coffea")
    os.makedirs(d, exist_ok=True)

    def one(r):
        dst = os.path.join(d, f"{r['photo_id']}.{r['ext']}")
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            return True
        try:
            with urllib.request.urlopen(URL.format(pid=r["photo_id"], size="medium", ext=r["ext"]), timeout=60) as resp:
                data = resp.read()
            Image.open(__import__("io").BytesIO(data)).verify()
            with open(dst + ".part", "wb") as fh:
                fh.write(data)
            os.replace(dst + ".part", dst)
            return True
        except Exception as e:  # noqa: BLE001
            print("download failed", r["photo_id"], e, file=sys.stderr)
            return False

    chosen, i = [], 0
    with ThreadPoolExecutor(threads) as ex:
        while len(chosen) < n and i < len(picks):  # top up in the fixed random order if a download fails
            batch = picks[i:i + (n - len(chosen))]
            i += len(batch)
            chosen += [r for r, ok in zip(batch, ex.map(one, batch)) if ok]
    chosen.sort(key=lambda r: int(r["photo_id"]))
    write_attribution(chosen, CALIB_ATTRIBUTION)
    print("calibration Coffea photos:", len(chosen), "quality:", dict(Counter(r["quality_grade"] for r in chosen)),
          "licenses:", dict(Counter(r["license"] for r in chosen)),
          "in Mexico:", sum(r["in_mexico"] for r in chosen))
    return chosen


# ---------------------------------------------------------------- 2. sweep
def parse_model(spec):
    name, rest = spec.split("=", 1)
    mpath, _, lpath = rest.partition(":")
    return name, mpath, json.load(open(lpath or os.path.join(REPO, "app", "model", "labels.json")))


def calib_data(data, inat_dir, photos_calib):
    """Returns dict of calibration sets: PIL squares + blur (photos) or arrays (npz)."""
    rows = read_attribution(CALIB_ATTRIBUTION)
    for r in rows:
        r["path"] = image_path(photos_calib, r)
    rows = [r for r in rows if r["path"]]
    scr = {r["photo_id"]: r["visible_leaf_symptom"] for r in csv.DictReader(open(SCREENING))}
    test_ids = {r["photo_id"] for r in read_attribution(ATTRIBUTION) if r["split"] in ("field_test", "coffea_eval")}
    pos = [r for r in load_rows(inat_dir) if r["split"] == "field_train" and scr.get(r["photo_id"]) == "no"]
    assert not ({r["photo_id"] for r in rows + pos} & test_ids), "calibration overlaps a test set"
    test_obs = {r["observer_id"] for r in read_attribution(ATTRIBUTION) if r["split"] in ("field_test", "coffea_eval")}
    assert not ({r["observer_id"] for r in rows} & test_obs), "Coffea calibration observer in a test set"
    va = npz_with_blur(os.path.join(data, "val.npz"))
    out = {}
    for key, rs in (("coffea", rows), ("field_pos", pos)):
        sq = [square_of(r["path"]) for r in rs]
        out[key] = {"rows": rs, "squares": [s for s, _ in sq], "blur": np.array([b for _, b in sq])}
    out["val"] = {"squares": [Image.fromarray(a) for a in va["x"]], "y": va["y"], "blur": va["blur"]}
    return out


def predict_all(model_path, labels, cal, cache_dir):
    sess = session(model_path)
    h = file_hash(model_path)
    size = labels["input"]["size"]
    return {k: predict_photos(sess, v["squares"], size,
                              os.path.join(cache_dir, f"calib_{k}_{h}_{len(v['squares'])}.npz") if cache_dir else None)
            for k, v in cal.items()}


def sweep_rows(pred, cal, labels, method):
    classes, blur_thr = labels["classes"], labels["blur_threshold"]
    otro, roya = classes.index("otro"), classes.index("roya")
    yv = cal["val"]["y"]
    pos_lab = np.array([r["label"] for r in cal["field_pos"]["rows"]])
    out = []
    for t in GRID:
        a_c, _ = decisions(pred["coffea"], cal["coffea"]["blur"], classes, t, blur_thr, method)
        a_v, _ = decisions(pred["val"], cal["val"]["blur"], classes, t, blur_thr, method)
        a_p, _ = decisions(pred["field_pos"], cal["field_pos"]["blur"], classes, t, blur_thr, method)
        n_c, k_c = len(a_c), int(np.isin(a_c, DISEASES).sum())
        ov = a_v[yv == otro]
        n_o, k_o = len(ov), int((ov == "DUDA").sum())
        coffee = yv != otro
        truth = np.array(classes)[yv]
        fr = pos_lab == "roya"
        fd = np.isin(pos_lab, DISEASES)
        out.append({
            "t": t,
            "coffea_alarm": round(k_c / n_c, 4), "coffea_alarm_k": k_c, "coffea_n": n_c, "coffea_alarm_ci95": wilson(k_c, n_c),
            "otro_rejected": round(k_o / n_o, 4), "otro_rejected_k": k_o, "otro_n": n_o, "otro_rejected_ci95": wilson(k_o, n_o),
            "field_pos_roya_correct": round(float((a_p[fr] == "roya").mean()), 4), "field_pos_roya_n": int(fr.sum()),
            "field_pos_roya_correct_ci95": wilson(int((a_p[fr] == "roya").sum()), int(fr.sum())),
            "field_pos_any_disease_correct": round(float((a_p[fd] == pos_lab[fd]).mean()), 4), "field_pos_n": int(fd.sum()),
            "field_pos_called_sano": int((a_p[fd] == "sano").sum()),
            "val_roya_correct": round(float((a_v[yv == roya] == "roya").mean()), 4), "val_roya_n": int((yv == roya).sum()),
            "val_coffee_correct": round(float((a_v[coffee] == truth[coffee]).mean()), 4),
            "val_diseased_called_sano": int((a_v[coffee & (yv != classes.index("sano"))] == "sano").sum()),
            "feasible": k_c / n_c <= MAX_COFFEA_ALARM + 1e-12 and k_o / n_o >= MIN_OTRO_REJECT - 1e-12})
    return out


def choose(rows):
    ok = [r for r in rows if r["feasible"]]
    return ok[0]["t"] if ok else None


def first_t(rows, cond):
    return next((r["t"] for r in rows if cond(r)), None)


def cmd_sweep(args):
    cal = calib_data(args.data, args.inat, args.photos_calib)
    name, mpath, labels = parse_model(args.model)
    pred = predict_all(mpath, labels, cal, args.cache)
    res = {"generated_by": "model/field_threshold.py sweep", "model": {"name": name, "path": os.path.relpath(mpath, REPO),
           "sha1_12": file_hash(mpath), "version": labels.get("version"), "shipped_threshold": labels["threshold"],
           "blur_threshold": labels["blur_threshold"]},
           "rule": f"lowest t in [0.700, 0.995] (step 0.005) with Coffea disease-answer rate <= {MAX_COFFEA_ALARM:.1%} "
                   f"AND otro rejection >= {MIN_OTRO_REJECT:.1%}, both on calibration data only",
           "calibration_sets": {
               "coffea": f"{len(cal['coffea']['rows'])} iNaturalist Coffea arabica photos (taxon 64342), one per observer, "
                         "observers absent from reports/field_inat_attribution.csv (no overlap with the 399-photo Coffea "
                         "test sample or any disease observer); reports/field_calib_attribution.csv",
               "otro": f"{int((cal['val']['y'] == labels['classes'].index('otro')).sum())} validation-split otro images "
                       "(PlantDoc other crops + Imagenette), not the test split",
               "field_pos": f"{len(cal['field_pos']['rows'])} field_train disease photos screened 'no' (symptom not clearly "
                            "visible; never used to train v2; not in the field test; SAME observers as v2 training photos): "
                            + ", ".join(f"{k} {v}" for k, v in sorted(Counter(r['label'] for r in cal['field_pos']['rows']).items())),
               "jmuben_val": "JMuBEN validation split (Kenyan close-ups), 300 per coffee class"},
           "recall_note": "No clean field data is left for recall: every screened-yes field photo is either v2 training or "
                          "field test. Recall on calibration is therefore NOT a field estimate; it is shown only to see "
                          "the direction of the trade-off. The rule does not use it.",
           "methods": {}}
    for m in ("single", MC):
        rows = sweep_rows(pred, cal, labels, m)
        res["methods"][m] = {"chosen_t": choose(rows),
                             "first_t_coffea_ok": first_t(rows, lambda r: r["coffea_alarm"] <= MAX_COFFEA_ALARM + 1e-12),
                             "first_t_otro_ok": first_t(rows, lambda r: r["otro_rejected"] >= MIN_OTRO_REJECT - 1e-12),
                             "sweep": rows}
        print(m, "chosen t:", res["methods"][m]["chosen_t"])
    if args.ref:
        rn, rp, rl = parse_model(args.ref)
        rpred = predict_all(rp, rl, cal, args.cache)
        rrow = next(r for r in sweep_rows(rpred, cal, rl, "single") if r["t"] == rl["threshold"])
        res["reference"] = {"name": rn, "version": rl.get("version"), "threshold": rl["threshold"], "row": rrow}
    res["chosen"] = {"method": "single", "t": res["methods"]["single"]["chosen_t"],
                     "why_single": "the phone app (app/infer.js) runs single view only; multicrop is swept for "
                                   "information and is not a ship candidate"}
    with open(SWEEP_JSON, "w") as fh:
        json.dump(res, fh, indent=1)
    with open(SWEEP_MD, "w") as fh:
        fh.write(render_sweep_md(res))
    print("wrote", SWEEP_JSON, SWEEP_MD)


def pct(v, d=1):
    return "n/a" if v is None else f"{100 * v:.{d}f}%"


def ci(c):
    return "" if not c or c[0] is None else f" [{100 * c[0]:.1f}-{100 * c[1]:.1f}]"


def render_sweep_md(res):
    s = res["methods"]["single"]
    L = ["# v2 confidence threshold: constrained sweep on calibration data", "",
         "Generated by `model/field_threshold.py sweep`. **Calibration data only** - no test photo or test observer "
         "was used to choose the threshold (checked by assertions in the script).", "",
         f"Model: `{res['model']['path']}` ({res['model']['version']}, sha1 {res['model']['sha1_12']}, blur threshold "
         f"{res['model']['blur_threshold']}). Decision = the app's rule (blur check, top-1 >= t, `otro` -> DUDA).", "",
         f"**Rule (fixed before the sweep):** {res['rule']}.", "",
         f"**Chosen: t = {s['chosen_t']}** (single view, what the app runs)." if s["chosen_t"] is not None else
         "**No t in [0.700, 0.995] satisfies both constraints.**", "",
         "## Calibration sets", ""]
    L += [f"- **{k}**: {v}" for k, v in res["calibration_sets"].items()]
    L += [f"- **Recall**: {res['recall_note']}", ""]
    if "reference" in res:
        r = res["reference"]["row"]
        L += [f"Reference, {res['reference']['name']} ({res['reference']['version']}) at its shipped t = "
              f"{res['reference']['threshold']}: Coffea disease answers {pct(r['coffea_alarm'])} ({r['coffea_alarm_k']}/"
              f"{r['coffea_n']}), otro rejected {pct(r['otro_rejected'])} ({r['otro_rejected_k']}/{r['otro_n']}), "
              f"field calib roya correct {pct(r['field_pos_roya_correct'])} (n={r['field_pos_roya_n']}), JMuBEN val roya "
              f"correct {pct(r['val_roya_correct'])}.", ""]
    for m, x in res["methods"].items():
        L += [f"## Sweep: v2 {'single view' if m == 'single' else 'multicrop ' + m}"
              + ("" if m == "single" else " (information only, not in the app)"), "",
              f"Lowest feasible t: **{x['chosen_t']}**. The Coffea constraint alone is met from t = "
              f"{x['first_t_coffea_ok']}, the otro constraint alone from t = {x['first_t_otro_ok']}"
              + (" (otro rejection is the binding constraint)." if (x["first_t_otro_ok"] or 9) > (x["first_t_coffea_ok"] or 9)
                 else " (Coffea is the binding constraint)."), "",
              "| t | Coffea disease answers [95% CI] (n) | otro rejected [95% CI] (n) | field calib roya correct (n) | "
              "field calib any disease correct (n) | JMuBEN val roya correct | JMuBEN val coffee correct | diseased -> sano (field calib / val) | feasible |",
              "|---|---|---|---|---|---|---|---|---|"]
        for r in x["sweep"]:
            L.append(f"| {r['t']:.3f} | {pct(r['coffea_alarm'])}{ci(r['coffea_alarm_ci95'])} ({r['coffea_alarm_k']}/{r['coffea_n']}) | "
                     f"{pct(r['otro_rejected'])}{ci(r['otro_rejected_ci95'])} ({r['otro_rejected_k']}/{r['otro_n']}) | "
                     f"{pct(r['field_pos_roya_correct'])} ({r['field_pos_roya_n']}) | {pct(r['field_pos_any_disease_correct'])} "
                     f"({r['field_pos_n']}) | {pct(r['val_roya_correct'])} | {pct(r['val_coffee_correct'])} | "
                     f"{r['field_pos_called_sano']} / {r['val_diseased_called_sano']} | "
                     f"{'**yes**' if r['t'] == x['chosen_t'] else ('yes' if r['feasible'] else 'no')} |")
        L.append("")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- team decision (human, not computed)
def team_decision(candidate, path=SHIP_DECISION):
    """The human ship decision record (model/ship_decision.json) if it is about this candidate, else None."""
    if not candidate or not os.path.exists(path):
        return None
    d = json.load(open(path))
    return d if d.get("shipped", {}).get("candidate_key") == candidate else None


def f2_margin(res):
    """Exact app-level macro-F1 of baseline and candidate on the JMuBEN test split, drop in points."""
    fb = res["evaluations"][res["baseline"]]["jmuben_per_class"]["_app_macro_f1_exact"]
    fc = res["evaluations"][res["candidate"]]["jmuben_per_class"]["_app_macro_f1_exact"]
    return fb, fc, 100 * (fb - fc)


def result_lines(res):
    """Top of the 'Result' section of reports/field_eval.md when the team shipped the recalibrated candidate."""
    d = team_decision(res.get("candidate"))
    if not d:
        return []
    ch = res["ship_rule"][res["candidate"]]["checks"]
    failed = [k for k, v in ch.items() if not v]
    t = res["chosen_t"]
    fb, fc, drop = f2_margin(res)
    ev = res["evaluations"]
    b, c = ev[res["baseline"]], ev[res["candidate"]]
    fa_b, fa_c = b["jmuben_otro_test"]["jmuben_macro_f1_argmax"], c["jmuben_otro_test"]["jmuben_macro_f1_argmax"]
    miss = (f"misses (2) by {drop - 1:.2f} points: the JMuBEN app-level macro-F1 drops {drop:.2f} points "
            f"({fc:.4f} vs {fb:.4f} for {res['baseline']}; limit 1.00), while the argmax macro-F1 passes "
            f"({fa_c:.4f} vs {fa_b:.4f})" if failed == ["jmuben_macro_f1_drop<=1pt"] else
            "fails " + ", ".join(CHECK_NAMES[k] for k in failed))
    rc, rb, n = (c["field_test"]["roya"]["answer_counts"]["roya"], b["field_test"]["roya"]["answer_counts"]["roya"],
                 c["field_test"]["roya"]["n"])
    return [f"**Shipped: `{d['shipped']['model']}` single view at t = {t:.2f} ({d['shipped']['version']}, "
            f"`{d['shipped']['file']}`), by explicit team decision ({d['date']}) - an exception to the pre-registered "
            "ship rule.**", "",
            f"At t = {t:.2f} v2 passes {5 - len(failed)} of the 5 conditions and {miss}. Why the team shipped it anyway: "
            f"{d['reason']} On the held-out field test it finds rust in {rc} of {n} photos ({res['baseline']}: {rb}); "
            f"diseased photos called \"sano\": {field_dangerous(c)} in the field test and "
            f"{c['jmuben_otro_test']['jmuben_diseased_called_sano_n']} in the JMuBEN test ({res['baseline']}: "
            f"{field_dangerous(b)} and {b['jmuben_otro_test']['jmuben_diseased_called_sano_n']}). The rule text and "
            "the mechanical outcomes below are unchanged; the decision record is `model/ship_decision.json`.", ""]


# ---------------------------------------------------------------- 3. single test evaluation
def cmd_test(args):
    sw = json.load(open(SWEEP_JSON))
    t = sw["chosen"]["t"]
    rows = load_rows(args.inat)
    sq = [square_of(r["path"]) for r in rows]
    squares, blur = [s for s, _ in sq], np.array([b for _, b in sq])
    npz = npz_with_blur(os.path.join(args.data, "test.npz"))
    rn, rp, rl = parse_model(args.ref)
    name, mpath, labels = parse_model(args.model)
    assert file_hash(mpath) == sw["model"]["sha1_12"], "model differs from the one calibrated"
    evals = {}
    for key, path, lab in ((f"{rn}@{rl['threshold']}", rp, rl), (f"{name}@{labels['threshold']}", mpath, labels)) + (
            ((f"{name}@{t}", mpath, dict(labels, threshold=t)),) if t is not None else ()):
        out, _, _ = evaluate_model(path, lab, rows, squares, blur, npz, args.cache, ["single"])
        evals[key] = out["methods"]["single"]
        evals[key]["_meta"] = {"model": out["model"], "sha1_12": out["sha1_12"], "threshold": lab["threshold"],
                               "version": lab.get("version")}
        evals[key]["jmuben_per_class"] = jmuben_per_class(
            os.path.join(args.cache, f"test_{out['sha1_12']}.npz"), npz, lab)
    base = evals[f"{rn}@{rl['threshold']}"]
    rule = {k: ship_rule(base, v) for k, v in evals.items() if k != f"{rn}@{rl['threshold']}"}
    cand = f"{name}@{t}" if t is not None else None
    res = {"generated_by": "model/field_threshold.py test", "chosen_t": t, "candidate": cand,
           "baseline": f"{rn}@{rl['threshold']}", "evaluations": evals, "ship_rule": rule,
           "decision": ("SHIP" if cand and rule[cand]["passes"] else "DO NOT SHIP"),
           "note": "single evaluation on the held-out test sets with t fixed beforehand in "
                   "reports/field_v2_threshold_sweep.json; v2@0.7 repeats the earlier result for comparison",
           "posthoc_validation_f1": posthoc_val_f1(args, (rp, rl), (mpath, labels)),
           "posthoc_note": "computed AFTER the test evaluation, on the JMuBEN VALIDATION split only, to explain the "
                           "result; it does not change t or the decision"}
    with open(TEST_JSON, "w") as fh:
        json.dump(res, fh, indent=1)
    insert_section(render_tradeoff(res, sw), pointer_line(res))
    print(json.dumps({k: v["checks"] for k, v in rule.items()}, indent=1))
    print("decision:", res["decision"])


def count(st, group, key):
    """Exact count behind a group_stats rate (the rates in field_eval are rounded to 4 decimals)."""
    a = st["answer_counts"]
    if key == "DUDA":
        return a["DUDA"]
    if key == "disease_answer":
        return sum(a[d] for d in DISEASES)
    return a.get(group.split(" ")[0], 0)  # correct: answers equal to the group's label


def jmuben_per_class(cache, npz, labels):
    """Per coffee class on the JMuBEN test split: correct & accepted, DUDA (from the cached test predictions)."""
    from sklearn.metrics import f1_score
    z = np.load(cache)
    classes = labels["classes"]
    ans, _ = decisions({k: z[k] for k in z.files}, npz["blur"], classes, labels["threshold"],
                       labels["blur_threshold"], "single")
    truth = np.array(classes)[npz["y"]]
    coffee = truth != "otro"
    out = {c: {"n": int((truth == c).sum()), "correct": round(float((ans[truth == c] == c).mean()), 4),
               "DUDA": round(float((ans[truth == c] == "DUDA").mean()), 4)} for c in classes if c != "otro"}
    out["_app_macro_f1_exact"] = float(f1_score(truth[coffee], ans[coffee], labels=[c for c in classes if c != "otro"],
                                                average="macro", zero_division=0))
    return out


def posthoc_val_f1(args, ref, cand):
    """App-level macro-F1 on JMuBEN VALIDATION: reference at its threshold, candidate over the grid (cached preds)."""
    from sklearn.metrics import f1_score
    va = npz_with_blur(os.path.join(args.data, "val.npz"))

    def f1(path, lab, t):
        z = np.load(os.path.join(args.cache, f"calib_val_{file_hash(path)}_{len(va['y'])}.npz"))
        classes = lab["classes"]
        ans, _ = decisions({k: z[k] for k in z.files}, va["blur"], classes, t, lab["blur_threshold"], "single")
        truth = np.array(classes)[va["y"]]
        cof = truth != "otro"
        return round(float(f1_score(truth[cof], ans[cof], labels=[c for c in classes if c != "otro"],
                                    average="macro", zero_division=0)), 4)
    r = f1(ref[0], ref[1], ref[1]["threshold"])
    rows = [{"t": t, "app_macro_f1": f1(cand[0], cand[1], t)} for t in GRID]
    for x in rows:
        x["drop_vs_ref_pts"] = round(100 * (r - x["app_macro_f1"]), 2)
    ok = [x["t"] for x in rows if x["drop_vs_ref_pts"] <= 1.0 + 1e-9]
    return {"reference_app_macro_f1": r, "rows": rows, "highest_t_with_drop<=1pt": max(ok) if ok else None}


def summary_rows(ev):
    f, j = ev["field_test"], ev["jmuben_otro_test"]

    def fc(g, k="correct"):
        return f"{pct(count(f[g], g, k) / f[g]['n'])}{ci(f[g][k + '_ci95'])} ({count(f[g], g, k)}/{f[g]['n']})"
    wrong = sum(round(f[g]["wrong_accepted"] * f[g]["n"]) for g in ("roya", "minador", "cercospora", "ojo_de_gallo"))
    return [
        ("roya: correct & accepted, all field-test photos", fc("roya")),
        ("roya: correct & accepted, screened (leaf symptom visible)", fc("roya screened")),
        ("roya: correct & accepted, Mexico+Guatemala box", fc("roya Mexico+GT box")),
        ("roya: correct & accepted, Mexico only", fc("roya Mexico")),
        ("minador: correct & accepted", fc("minador")),
        ("cercospora: correct & accepted", fc("cercospora")),
        ("ojo de gallo: DUDA (desired)", fc("ojo_de_gallo", "DUDA")),
        ("wrong-but-accepted, diseased field-test photos (incl. ojo de gallo), count", str(wrong)),
        ("diseased field-test photos called \"sano\" (dangerous)", str(field_dangerous(ev))),
        ("Coffea test sample: disease answers", fc("coffea sample", "disease_answer")),
        ("Coffea test sample Mexico: disease answers", fc("coffea sample Mexico", "disease_answer")),
        ("otro test images rejected", f"{pct(j['otro_rejected'])}{ci(j['otro_rejected_ci95'])} (n={j['otro_n']})"),
        ("JMuBEN test macro-F1, argmax (6 classes)", f"{j['jmuben_macro_f1_argmax']:.4f}"),
        ("JMuBEN test macro-F1, app-level (DUDA = miss, 5 coffee classes)", f"{j['jmuben_app_macro_f1']:.4f}"),
        ("JMuBEN test: coffee close-ups sent to DUDA", pct(j["jmuben_coffee_DUDA"])),
        ("JMuBEN test: diseased called \"sano\"", str(j["jmuben_diseased_called_sano_n"])),
    ]


CHECK_NAMES = {"field_roya_correct_gain>=10pts": "(1) field roya correct & accepted +10 pts vs v1",
               "jmuben_macro_f1_drop<=1pt": "(2) JMuBEN test macro-F1 drops <= 1 pt",
               "otro_rejection>=98%": "(3) otro rejection >= 98 %",
               "dangerous_not_increased": "(4) diseased accepted as sano does not increase",
               "coffea_disease_rate_rise<=5pts": "(5) Coffea disease answers rise <= 5 pts vs v1"}


def render_tradeoff(res, sw):
    ev = res["evaluations"]
    keys = list(ev)
    s = sw["methods"]["single"]
    t = res["chosen_t"]
    row_t = next((r for r in s["sweep"] if r["t"] == t), None)
    row_07 = next(r for r in s["sweep"] if r["t"] == 0.7)
    b = ev[res["baseline"]]
    L = [MARK_A, "## Threshold trade-off (v2 recalibrated on calibration data, one test evaluation)", ""]
    if t is None:
        L += ["**No threshold in [0.700, 0.995] satisfies the calibration constraints; v2 is not shipped.**", MARK_B]
        return "\n".join(L) + "\n"
    c = ev[res["candidate"]]
    ch = res["ship_rule"][res["candidate"]]["checks"]
    bj, cj = b["jmuben_otro_test"], c["jmuben_otro_test"]
    bf, cf = b["field_test"], c["field_test"]
    otro_k = round(cj["otro_rejected"] * cj["otro_n"])
    kr_c, kr_b, n_r = cf["roya"]["answer_counts"]["roya"], bf["roya"]["answer_counts"]["roya"], cf["roya"]["n"]
    kc_c = count(cf["coffea sample"], "coffea sample", "disease_answer")
    kc_b = count(bf["coffea sample"], "coffea sample", "disease_answer")
    n_c = cf["coffea sample"]["n"]
    fa_c, fa_b = cj["jmuben_macro_f1_argmax"], bj["jmuben_macro_f1_argmax"]
    fp_c, fp_b = c["jmuben_per_class"]["_app_macro_f1_exact"], b["jmuben_per_class"]["_app_macro_f1_exact"]
    detail = {
        "field_roya_correct_gain>=10pts": f"{pct(kr_c / n_r)}{ci(cf['roya']['correct_ci95'])} ({kr_c}/{n_r}) vs "
                                          f"{pct(kr_b / n_r)}{ci(bf['roya']['correct_ci95'])} ({kr_b}/{n_r}): "
                                          f"{100 * (kr_c - kr_b) / n_r:+.1f} pts",
        "jmuben_macro_f1_drop<=1pt": f"argmax {fa_c:.4f} vs {fa_b:.4f} (change {100 * (fa_c - fa_b):+.2f} pts, passes); "
                                     f"app-level {fp_c:.4f} vs {fp_b:.4f} (change {100 * (fp_c - fp_b):+.2f} pts, "
                                     f"{'passes' if fp_b - fp_c <= 0.01 + 1e-9 else 'limit -1.00'})",
        "otro_rejection>=98%": f"{pct(otro_k / cj['otro_n'])}{ci(cj['otro_rejected_ci95'])} ({otro_k}/{cj['otro_n']}); "
                               f"{otro_margin(otro_k, cj['otro_n'])}",
        "dangerous_not_increased": f"field {field_dangerous(c)} vs {field_dangerous(b)}; JMuBEN "
                                   f"{cj['jmuben_diseased_called_sano_n']} vs {bj['jmuben_diseased_called_sano_n']}",
        "coffea_disease_rate_rise<=5pts": f"{pct(kc_c / n_c)}{ci(cf['coffea sample']['disease_answer_ci95'])} ({kc_c}/{n_c}) "
                                          f"vs {pct(kc_b / n_c)} ({kc_b}/{n_c}): {100 * (kc_c - kc_b) / n_c:+.1f} pts"}
    failed = [k for k, v in ch.items() if not v]
    team = team_decision(res["candidate"])
    L += [f"**{'Rule outcome' if team else 'Decision'}: {res['decision']} v2 at t = {t:.2f}.** " + (
        "It passes all five ship-rule conditions." if not failed else
        f"It passes {5 - len(failed)} of the 5 conditions and fails " + "; ".join(
            f"{CHECK_NAMES[k]}: {detail[k]}" for k in failed) + "." + (
            f" **Team decision ({team['date']}): v2 at t = {t:.2f} is shipped anyway**, as an explicit, documented "
            "exception to the rule (see \"Result\" above and `model/ship_decision.json`)." if team else
            " The app keeps v1.")), "",
          "v2's original threshold (0.70) came from Kenyan validation images with no false-alarm constraint. It was "
          "re-chosen on **calibration data that shares no photo and no observer with any test set** "
          f"(`reports/field_v2_threshold_sweep.md`): {sw['rule']}. Calibration sets: a new random sample of "
          f"{row_07['coffea_n']} iNaturalist *Coffea arabica* photos from observers not used anywhere else "
          f"(`reports/field_calib_attribution.csv`) and the {row_07['otro_n']} validation-split `otro` images. The "
          f"choice (t = {t:.2f}) was committed before the test sets were scored at that threshold. There is no clean "
          "field data left for recall (every screened field rust photo is either v2 training or test), so recall "
          "could **not** be calibrated on field data.", "",
          "Calibration sweep (excerpt; full table in `reports/field_v2_threshold_sweep.md`):", "",
          "| t | Coffea disease answers (calibration) | otro rejected (validation) | field calib roya correct* | JMuBEN val roya correct |",
          "|---|---|---|---|---|"]
    for r in s["sweep"]:
        if r["t"] in (0.7, 0.8, 0.85, 0.9, 0.95, 0.99) or r["t"] == t:
            L.append(f"| {r['t']:.3f}{' (chosen)' if r['t'] == t else ''} | {pct(r['coffea_alarm'])} ({r['coffea_alarm_k']}/{r['coffea_n']}) | "
                     f"{pct(r['otro_rejected'])} ({r['otro_rejected_k']}/{r['otro_n']}) | {pct(r['field_pos_roya_correct'])} "
                     f"(n={r['field_pos_roya_n']}) | {pct(r['val_roya_correct'])} |")
    L += ["", f"The Coffea constraint alone is met from t = {s['first_t_coffea_ok']}; otro rejection is the binding "
          f"constraint (met from t = {s['first_t_otro_ok']})." if s["first_t_otro_ok"] > s["first_t_coffea_ok"] else "",
          "", "\\* field_train rust photos screened \"no\" (symptom not clearly visible; never used to train v2; same "
          "observers as v2's training photos) - a weak, biased recall proxy, not used to choose t.", "",
          "**Single evaluation on the held-out test sets** (t fixed beforehand; decided exactly like the app; Wilson "
          "95 % intervals):", "",
          "| metric | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
    tabs = {k: summary_rows(v) for k, v in ev.items()}
    for i, (label, _) in enumerate(tabs[keys[0]]):
        L.append(f"| {label} | " + " | ".join(tabs[k][i][1] for k in keys) + " |")
    L += ["", f"**Ship rule, unchanged** (candidate vs `{res['baseline']}` single view; (2) is measured with both "
          "F1 variants, as fixed before the first v2 test):", "",
          "| condition | " + " | ".join(res["ship_rule"]) + " |", "|---|" + "---|" * len(res["ship_rule"])]
    for k, name in CHECK_NAMES.items():
        L.append(f"| {name} | " + " | ".join("pass" if v["checks"][k] else "**FAIL**" for v in res["ship_rule"].values()) + " |")
    L.append("| **all five** | " + " | ".join("**pass**" if v["passes"] else "**FAIL**" for v in res["ship_rule"].values()) + " |")
    L += ["", f"Details at t = {t:.2f}:", ""] + [f"- {CHECK_NAMES[k]}: {'pass' if ch[k] else '**FAIL**'} - {detail[k]}" for k in CHECK_NAMES]
    if row_t is not None:
        L += ["", f"Calibration carried over to test: Coffea disease answers {pct(row_t['coffea_alarm'])} "
              f"({row_t['coffea_alarm_k']}/{row_t['coffea_n']}, calibration) vs {pct(kc_c / n_c)} ({kc_c}/{n_c}, test); "
              f"otro rejected {pct(row_t['otro_rejected'])} ({row_t['otro_rejected_k']}/{row_t['otro_n']}, validation) vs "
              f"{pct(otro_k / cj['otro_n'])} ({otro_k}/{cj['otro_n']}, test)."]
    L += ["", "Why (2) moves: a higher threshold sends more Kenyan close-ups to DUDA (argmax F1 does not depend on t; "
          "the app-level F1 counts DUDA as a miss). JMuBEN test, correct & accepted / DUDA per class:", "",
          "| class | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
    for cl in [k for k in c["jmuben_per_class"] if not k.startswith("_")]:
        L.append(f"| {cl} (n={c['jmuben_per_class'][cl]['n']}) | " + " | ".join(
            f"{pct(ev[k]['jmuben_per_class'][cl]['correct'])} / {pct(ev[k]['jmuben_per_class'][cl]['DUDA'])}" for k in keys) + " |")
    ph = res.get("posthoc_validation_f1")
    if ph:
        rv = next(x for x in ph["rows"] if x["t"] == t)
        hi = ph["highest_t_with_drop<=1pt"] or 0
        L += ["", f"Post-hoc check on the JMuBEN **validation** split (computed after the test evaluation; it explains "
              f"the result and changes nothing): v2's app-level macro-F1 at t = {t:.2f} is {rv['app_macro_f1']:.4f} vs "
              f"{ph['reference_app_macro_f1']:.4f} for v1 at 0.70 (drop {rv['drop_vs_ref_pts']:.2f} pts). The highest t "
              f"whose validation drop is <= 1 pt is {hi}; the otro constraint needs t >= {s['first_t_otro_ok']}" + (
                  ", so on calibration data no single threshold satisfies all three: the conflict is in the model, "
                  "not in the threshold." if hi < s["first_t_otro_ok"] else
                  f". So adding condition (2) to the calibration rule would not have changed t; on validation t = "
                  f"{t:.2f} meets it, on the test split it misses by {100 * (fp_b - fp_c) - 1:.2f} pts. Validation and "
                  "test are different JMuBEN source photos, and a handful of close-ups more or less in DUDA decides "
                  "this margin.")]

    def dis(x):
        return sum(x["field_test"]["coffea sample"]["answer_counts"][d] for d in DISEASES)
    safe = field_dangerous(c) == 0 and cj["jmuben_diseased_called_sano_n"] == 0
    head = (f"at t = {t:.2f} v2 finds rust in {cf['roya']['answer_counts']['roya']} of {cf['roya']['n']} held-out field "
            f"photos (v1: {bf['roya']['answer_counts']['roya']}), answers a disease on {dis(c)} of "
            f"{cf['coffea sample']['n']} Coffea plant photos (v1: {dis(b)})"
            + (" and never says \"sano\" to a diseased leaf" if safe else ""))
    if failed and team:
        tail = ("; the price is more \"I'm not sure\" on Kenyan lab close-ups"
                + (", which breaks condition (2) by a small margin" if failed == ["jmuben_macro_f1_drop<=1pt"] else "")
                + f". The pre-registered rule says **do not ship**. **The team shipped v2 at t = {t:.2f} anyway** "
                f"({team['date']}), as an explicit, documented exception taken by people, not by this script, because "
                f"{team['reason']} Any further threshold change would now be chosen with test knowledge and is not "
                "offered here.")
    elif failed:
        tail = ("; the price is more \"I'm not sure\" on Kenyan lab close-ups"
                + (", which breaks condition (2) by a small margin" if failed == ["jmuben_macro_f1_drop<=1pt"] else "")
                + ". The pre-registered rule says **do not ship**. Shipping v2 anyway would be an explicit, documented "
                "exception to that rule, taken by people, not by this script; any further threshold change would now "
                "be chosen with test knowledge and is not offered here.")
    else:
        tail = ". The pre-registered rule says **ship**."
    L += ["", "**Product decision for the team** (plain words): " + head + tail + " Either way: iNaturalist is a "
          f"proxy for Chiapas photos, n is small ({cf['roya']['n']} rust photos, {cf['roya Mexico']['n']} from Mexico), "
          "labels are community identifications, and the real fix is labelled Chiapas photos, healthy and diseased "
          "(officer confirmations in the hub).", MARK_B]
    return "\n".join(L) + "\n"


def otro_margin(k, n):
    need = int(np.ceil(MIN_OTRO_REJECT * n - 1e-9))
    if k == need:
        return f"exactly at the limit ({need} of {n} needed): one more accepted non-coffee image would fail"
    return (f"{k - need} image(s) above the limit ({need} of {n} needed)" if k > need else
            f"{need - k} image(s) short ({need} of {n} needed)")


POINTER = "<!-- threshold-pointer -->"
RULE_ANCHOR = "<!-- rule-outcome -->"  # line in field_eval.md's "Result" after which the pointer goes


def pointer_line(res):
    """One line for the 'Result' paragraph of reports/field_eval.md."""
    t = res["chosen_t"]
    if t is not None and team_decision(res.get("candidate")):
        return (f"Rule outcome, v2 with its threshold re-chosen on calibration data (t = {t:.2f}), evaluated once on the "
                f"same test sets: **{res['decision']}** (see \"Threshold trade-off\" below); shipped anyway by the team "
                f"decision above. {POINTER}")
    return (f"Update - v2 with its threshold re-chosen on calibration data (t = {t:.2f}), evaluated once on the same "
            f"test sets: **{res['decision']}** (see \"Threshold trade-off\" below). {POINTER}" if t is not None else
            f"Update - no v2 threshold satisfies the calibration constraints: **DO NOT SHIP**. {POINTER}")


def insert_section(sec, pointer=None, path=FIELD_MD):
    md = open(path).read()
    if MARK_A in md:
        a, b = md.index(MARK_A), md.index(MARK_B) + len(MARK_B) + 1
        md = md[:a] + sec + md[b:]
    else:
        anchor = "## Conclusions (plain words)"
        md = md.replace(anchor, sec + "\n" + anchor, 1) if anchor in md else md + "\n" + sec
    if pointer:
        lines = md.split("\n")
        lines = [x for x in lines if POINTER not in x]
        i = next((k for k, x in enumerate(lines) if RULE_ANCHOR in x), None)
        if i is None:
            i = next((k for k, x in enumerate(lines) if x.startswith("**") and "Shipped: `" in x), None)
        if i is not None:
            lines[i + 1:i + 1] = ["", pointer]
            while lines[i + 3] == "" and lines[i + 4] == "":  # keep one blank line after the pointer
                del lines[i + 3]
        md = "\n".join(lines)
    with open(path, "w") as fh:
        fh.write(md)


def cmd_install(args):
    """Install the calibrated candidate in the app - only if model/ship_decision.json names it (a human decision)."""
    import shutil
    sw = json.load(open(SWEEP_JSON))
    name, mpath, labels = parse_model(args.model)
    t = sw["chosen"]["t"]
    d = team_decision(f"{name}@{t}")
    if not d:
        sys.exit(f"model/ship_decision.json does not name {name}@{t}: nothing installed")
    h = file_hash(mpath)
    assert h == sw["model"]["sha1_12"] == d["shipped"]["file_sha1_12"], "model differs from the one calibrated/decided"
    app = os.path.join(REPO, "app", "model")
    dst = os.path.join(app, labels["file"])
    shutil.copyfile(mpath, dst)
    out = dict(labels, threshold=t, size_bytes=os.path.getsize(dst),
               threshold_note=f"{t:.2f} chosen on calibration data only; see reports/field_v2_threshold_sweep.md")
    with open(os.path.join(app, "labels.json"), "w") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"installed {os.path.relpath(mpath, REPO)} (sha1 {h}) as {os.path.relpath(dst, REPO)}, threshold {t}; "
          "now run: python3 scripts/bump_sw_version.py")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "sweep", "test", "install"])
    ap.add_argument("--inat", help="required for sample, sweep, test")
    ap.add_argument("--data")
    ap.add_argument("--photos-calib", help="default <inat>/photos_calib")
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--model", help="name=path.onnx:labels.json (the model whose threshold is calibrated)")
    ap.add_argument("--ref", help="name=path.onnx:labels.json (the shipped baseline)")
    ap.add_argument("--cache", default=os.path.join(REPO, "model", "checkpoints", "field_cache"))
    args = ap.parse_args()
    if args.cmd == "install":
        return cmd_install(args)
    if not args.inat:
        ap.error("--inat is required")
    args.photos_calib = args.photos_calib or os.path.join(args.inat, "photos_calib")
    if args.cmd == "sample":
        build_calib_sample(args.inat, args.photos_calib, args.n, args.seed)
    elif args.cmd == "sweep":
        cmd_sweep(args)
    else:
        cmd_test(args)


if __name__ == "__main__":
    main()
