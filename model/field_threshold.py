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
                        load_rows, npz_eval, npz_with_blur, predict_photos, session, ship_rule, square_of, wilson)
from inat_field import (ATTRIBUTION, URL, _f, image_path, in_box, in_mexico, read_attribution,  # noqa: E402
                        write_attribution)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALIB_ATTRIBUTION = os.path.join(REPO, "reports", "field_calib_attribution.csv")
SWEEP_JSON = os.path.join(REPO, "reports", "field_v2_threshold_sweep.json")
SWEEP_MD = os.path.join(REPO, "reports", "field_v2_threshold_sweep.md")
TEST_JSON = os.path.join(REPO, "reports", "field_v2_threshold_test.json")
FIELD_MD = os.path.join(REPO, "reports", "field_eval.md")
MARK_A, MARK_B = "<!-- threshold-tradeoff:start -->", "<!-- threshold-tradeoff:end -->"
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
    base = evals[f"{rn}@{rl['threshold']}"]
    rule = {k: ship_rule(base, v) for k, v in evals.items() if k != f"{rn}@{rl['threshold']}"}
    cand = f"{name}@{t}" if t is not None else None
    res = {"generated_by": "model/field_threshold.py test", "chosen_t": t, "candidate": cand,
           "baseline": f"{rn}@{rl['threshold']}", "evaluations": evals, "ship_rule": rule,
           "decision": ("SHIP" if cand and rule[cand]["passes"] else "DO NOT SHIP"),
           "note": "single evaluation on the held-out test sets with t fixed beforehand in "
                   "reports/field_v2_threshold_sweep.json; v2@0.7 repeats the earlier result for comparison"}
    with open(TEST_JSON, "w") as fh:
        json.dump(res, fh, indent=1)
    insert_section(render_tradeoff(res, sw))
    print(json.dumps({k: v["checks"] for k, v in rule.items()}, indent=1))
    print("decision:", res["decision"])


def summary_rows(ev):
    f, j = ev["field_test"], ev["jmuben_otro_test"]

    def fc(g, k="correct"):
        return f"{pct(f[g][k])}{ci(f[g][k + '_ci95'])} (n={f[g]['n']})"
    return [
        ("roya: correct & accepted, all field-test photos", fc("roya")),
        ("roya: correct & accepted, screened (leaf symptom visible)", fc("roya screened")),
        ("roya: correct & accepted, Mexico+Guatemala box", fc("roya Mexico+GT box")),
        ("roya: correct & accepted, Mexico only", fc("roya Mexico")),
        ("minador: correct & accepted", fc("minador")),
        ("cercospora: correct & accepted", fc("cercospora")),
        ("ojo de gallo: DUDA (desired)", fc("ojo_de_gallo", "DUDA")),
        ("Coffea test sample: disease answers", fc("coffea sample", "disease_answer")),
        ("Coffea test sample Mexico: disease answers", fc("coffea sample Mexico", "disease_answer")),
        ("diseased field-test photos called \"sano\" (dangerous)", str(field_dangerous(ev))),
        ("otro test images rejected", f"{pct(j['otro_rejected'])}{ci(j['otro_rejected_ci95'])} (n={j['otro_n']})"),
        ("JMuBEN test macro-F1 (argmax / app-level)", f"{j['jmuben_macro_f1_argmax']:.4f} / {j['jmuben_app_macro_f1']:.4f}"),
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
    L = [MARK_A, "## Threshold trade-off (v2 recalibrated on calibration data, one test evaluation)", "",
         f"**Decision: {res['decision']} v2 at t = {t}.** " + (
             "It passes all five ship-rule conditions." if res["decision"] == "SHIP" else
             "It fails: " + ", ".join(CHECK_NAMES[k] for k, v in res["ship_rule"][res["candidate"]]["checks"].items()
                                      if not v) + "." if t is not None else "No threshold satisfies the calibration constraints."), "",
         "v2's original threshold (0.70) was set on Kenyan validation images without any false-alarm constraint. We "
         "re-chose it on **calibration data that shares no photo and no observer with any test set** "
         f"(`reports/field_v2_threshold_sweep.md`): {sw['rule']}. Calibration sets: a new sample of "
         f"{row_07['coffea_n']} iNaturalist *Coffea arabica* photos from new observers "
         f"(`reports/field_calib_attribution.csv`) and the {row_07['otro_n']} validation-split `otro` images. "
         "There is no clean field data left for recall (every screened field rust photo is either v2 training or "
         "test), so recall could **not** be calibrated on field data.", "",
         "| t (calibration) | Coffea disease answers | otro rejected | field calib roya correct* | JMuBEN val roya correct |",
         "|---|---|---|---|---|"]
    for r in s["sweep"]:
        if r["t"] in (0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99) or r["t"] == t:
            L.append(f"| {r['t']:.3f}{' (chosen)' if r['t'] == t else ''} | {pct(r['coffea_alarm'])} ({r['coffea_alarm_k']}/{r['coffea_n']}) | "
                     f"{pct(r['otro_rejected'])} ({r['otro_rejected_k']}/{r['otro_n']}) | {pct(r['field_pos_roya_correct'])} "
                     f"(n={r['field_pos_roya_n']}) | {pct(r['val_roya_correct'])} |")
    L += ["", "\\* field_train rust photos screened \"no\" (symptom not clearly visible; not used to train v2; same "
          "observers as v2's training photos) - a weak, biased recall proxy, not used to choose t.", "",
          "**Single evaluation on the held-out test sets** (t fixed beforehand; Wilson 95 % intervals):", "",
          "| metric | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
    tabs = {k: summary_rows(v) for k, v in ev.items()}
    for i, (label, _) in enumerate(tabs[keys[0]]):
        L.append(f"| {label} | " + " | ".join(tabs[k][i][1] for k in keys) + " |")
    L += ["", "Ship rule (unchanged, vs " + res["baseline"] + " single view):", "",
          "| candidate | " + " | ".join(CHECK_NAMES.values()) + " | passes |", "|---|" + "---|" * (len(CHECK_NAMES) + 1)]
    for k, v in res["ship_rule"].items():
        L.append(f"| {k} | " + " | ".join("yes" if v["checks"][c] else "**no**" for c in CHECK_NAMES)
                 + f" | {'**yes**' if v['passes'] else 'no'} |")
    if row_t is not None and t is not None:
        e = ev[res["candidate"]]
        L += ["", f"Calibration vs test at t = {t}: Coffea disease answers {pct(row_t['coffea_alarm'])} (calibration) vs "
              f"{pct(e['field_test']['coffea sample']['disease_answer'])} (test); otro rejected "
              f"{pct(row_t['otro_rejected'])} (validation) vs {pct(e['jmuben_otro_test']['otro_rejected'])} (test)."]
    L += ["", "**What this means for the product** (plain words): the threshold is the dial between \"finds rust in "
          "field photos\" and \"raises false alarms on healthy-looking coffee photos and non-coffee images\". "
          "With only iNaturalist photos (a proxy for Chiapas, small n, community labels) and no labelled healthy "
          "field leaves, the team has to choose explicitly; this table is the evidence for that choice. The fix "
          "that moves both sides at once is labelled Chiapas photos, healthy and diseased (officer confirmations).",
          MARK_B]
    return "\n".join(L) + "\n"


def insert_section(sec, path=FIELD_MD):
    md = open(path).read()
    if MARK_A in md:
        a, b = md.index(MARK_A), md.index(MARK_B) + len(MARK_B) + 1
        md = md[:a] + sec + md[b:]
    else:
        anchor = "## Conclusions (plain words)"
        md = md.replace(anchor, sec + "\n" + anchor, 1) if anchor in md else md + "\n" + sec
    with open(path, "w") as fh:
        fh.write(md)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "sweep", "test"])
    ap.add_argument("--inat", required=True)
    ap.add_argument("--data")
    ap.add_argument("--photos-calib", help="default <inat>/photos_calib")
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--model", help="name=path.onnx:labels.json (the model whose threshold is calibrated)")
    ap.add_argument("--ref", help="name=path.onnx:labels.json (the shipped baseline)")
    ap.add_argument("--cache", default=os.path.join(REPO, "model", "checkpoints", "field_cache"))
    args = ap.parse_args()
    args.photos_calib = args.photos_calib or os.path.join(args.inat, "photos_calib")
    if args.cmd == "sample":
        build_calib_sample(args.inat, args.photos_calib, args.n, args.seed)
    elif args.cmd == "sweep":
        cmd_sweep(args)
    else:
        cmd_test(args)


if __name__ == "__main__":
    main()
