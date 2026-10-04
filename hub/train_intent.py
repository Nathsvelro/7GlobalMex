"""Train the free-text SMS intent classifier and export it to JSON for pure-Python inference (hub/intent.py).

    /home/user/venv-train/bin/python -m hub.train_intent        (needs scikit-learn; see requirements-train.txt)

Model: TfidfVectorizer(analyzer='char_wb', ngram_range=(2,4), sublinear_tf) + LogisticRegression (multinomial,
class_weight='balanced'). Data: data/intent/examples.csv, stratified 80/20 split (seed 42).
C is picked by 5-fold cross-validation on the 80% split. The confidence threshold is picked on out-of-fold
predictions of the 80% split (held out from the model that made them) as the LOWEST threshold at which >= 95% of
auto-answered messages get the right answer; below it a message goes to the officer (the safe default).
The exported model is the one trained on the 80% split, so the reported test numbers describe the shipped model.

Outputs: hub/intent_model.json, reports/intent_eval.json, reports/intent_eval.md
"""
import csv
import json
from datetime import date
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import make_pipeline

from hub.intent import INTENTS, normalize

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "intent" / "examples.csv"
MODEL_OUT = ROOT / "hub" / "intent_model.json"
REPORTS = ROOT / "reports"
SEED = 42
NGRAM = (2, 4)
TARGET_PRECISION = 0.95
GRID_C = [1.0, 3.0, 10.0, 30.0]
THRESHOLDS = [round(x, 2) for x in np.arange(0.30, 0.91, 0.05)]

# Fixed probe messages (not in the data) shown in the report as a sanity check.
PROBES = ["how much are you paying for a kilo of cherry", "bei ya kahawa ni ngapi",
          "my coffee leaves have orange powder", "majani ya kahawa yana unga wa rangi ya machungwa",
          "I want to talk to the extension officer", "asdf qwerty",
          "wat r u paying for maize", "kahawa yangu ina madoa ya kahawia", "nataka kuongea na afisa ugani",
          "how do i send my report code", "msaada tafadhali nifanye aje", "good afternoon", "habari za asubuhi",
          "play some music", "weka muziki"]


def make_model(C):
    return make_pipeline(
        TfidfVectorizer(analyzer="char_wb", ngram_range=NGRAM, preprocessor=normalize, lowercase=False,
                        sublinear_tf=True, min_df=1),
        LogisticRegression(C=C, max_iter=5000, class_weight="balanced"))


def routed(proba, classes, t):
    """Label after the threshold: below it, the message goes to the officer ('other')."""
    idx = proba.argmax(1)
    conf = proba.max(1)
    return np.array([classes[i] if c >= t else "other" for i, c in zip(idx, conf)])


def auto_precision(proba, classes, y, t):
    """Among messages answered automatically (predicted intent != other and conf >= t), share answered right."""
    idx = proba.argmax(1)
    conf = proba.max(1)
    pred = np.array([classes[i] for i in idx])
    mask = (conf >= t) & (pred != "other")
    if mask.sum() == 0:
        return 1.0, 0.0
    return float((pred[mask] == y[mask]).mean()), float(mask.mean())


def main():
    rows = list(csv.DictReader(DATA.open(encoding="utf-8")))
    X = np.array([r["text"] for r in rows], dtype=object)
    y = np.array([r["intent"] for r in rows])
    lang = np.array([r["lang"] for r in rows])
    src = np.array([r["source"] for r in rows])
    assert set(y) <= set(INTENTS), set(y) - set(INTENTS)
    idx = np.arange(len(rows))
    tr, te = train_test_split(idx, test_size=0.2, stratify=y, random_state=SEED)

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    cv_scores = {}
    for C in GRID_C:
        pred = cross_val_predict(make_model(C), X[tr], y[tr], cv=skf)
        cv_scores[C] = f1_score(y[tr], pred, average="macro")
    best_c = max(GRID_C, key=lambda c: (round(cv_scores[c], 4), -c))

    oof = cross_val_predict(make_model(best_c), X[tr], y[tr], cv=skf, method="predict_proba")
    classes_sorted = sorted(set(y))  # cross_val_predict uses sorted class order
    sweep = []
    for t in THRESHOLDS:
        p, cov = auto_precision(oof, classes_sorted, y[tr], t)
        f1 = f1_score(y[tr], routed(oof, classes_sorted, t), average="macro")
        sweep.append({"threshold": t, "auto_precision": round(p, 4), "auto_coverage": round(cov, 4),
                      "macro_f1_routed": round(f1, 4)})
    ok = [s for s in sweep if s["auto_precision"] >= TARGET_PRECISION]
    threshold = ok[0]["threshold"] if ok else THRESHOLDS[-1]

    model = make_model(best_c).fit(X[tr], y[tr])
    vec, clf = model.named_steps["tfidfvectorizer"], model.named_steps["logisticregression"]
    classes = list(clf.classes_)
    proba = model.predict_proba(X[te])
    pred_raw = np.array([classes[i] for i in proba.argmax(1)])
    pred_routed = routed(proba, classes, threshold)
    labels = INTENTS
    test_auto_p, test_auto_cov = auto_precision(proba, classes, y[te], threshold)
    on_topic = y[te] != "other"
    on_topic_auto = float((pred_routed[on_topic] == y[te][on_topic]).mean())

    def metrics(pred, mask=None):
        m = np.ones(len(te), bool) if mask is None else mask
        if m.sum() == 0:
            return None
        return {"n": int(m.sum()), "accuracy": round(accuracy_score(y[te][m], pred[m]), 4),
                "macro_f1": round(f1_score(y[te][m], pred[m], average="macro", labels=sorted(set(y[te][m]))), 4)}

    real_mask = src[te] != "MASSIVE"
    report = {
        "date": date.today().isoformat(),
        "data": {"file": "data/intent/examples.csv", "n": len(rows),
                 "per_intent": {c: int((y == c).sum()) for c in labels},
                 "per_language": {g: int((lang == g).sum()) for g in sorted(set(lang))},
                 "per_source": {s: int((src == s).sum()) for s in sorted(set(src))},
                 "n_train": len(tr), "n_test": len(te), "split": f"stratified 80/20, random_state={SEED}"},
        "model": {"vectorizer": f"TF-IDF char_wb {NGRAM}, sublinear_tf, l2", "classifier":
                  "LogisticRegression multinomial, class_weight=balanced", "C": best_c,
                  "cv_macro_f1_by_C": {str(k): round(v, 4) for k, v in cv_scores.items()},
                  "n_features": len(vec.vocabulary_)},
        "threshold": {"value": threshold, "rule": f"lowest t with >= {TARGET_PRECISION:.0%} precision on auto-answered "
                      "messages, out-of-fold predictions on the 80% split", "sweep_oof_train": sweep},
        "test": {
            "argmax": metrics(pred_raw),
            "with_threshold": metrics(pred_routed),
            "with_threshold_english_only": metrics(pred_routed, lang[te] == "en"),
            "with_threshold_swahili_only": metrics(pred_routed, lang[te] == "sw"),
            "with_threshold_kikuyu_only": metrics(pred_routed, lang[te] == "kik"),
            "with_threshold_excluding_massive": metrics(pred_routed, real_mask),
            "auto_answered_precision": round(test_auto_p, 4),
            "auto_answered_share": round(test_auto_cov, 4),
            "on_topic_answered_right": round(on_topic_auto, 4),
            "confusion_with_threshold": {"labels": labels,
                                         "matrix": confusion_matrix(y[te], pred_routed, labels=labels).tolist()},
            "per_class": classification_report(y[te], pred_routed, labels=labels, output_dict=True,
                                               zero_division=0),
        },
        "probes": [],
        "test_predictions": [
            {"text": X[i], "true": y[i], "lang": lang[i], "source": src[i], "pred": pred_raw[k],
             "conf": round(float(proba[k].max()), 6), "proba": [float(v) for v in proba[k]]}
            for k, i in enumerate(te)],
    }
    for text in PROBES:
        p = model.predict_proba(np.array([text], dtype=object))[0]
        report["probes"].append({"text": text, "pred": classes[int(p.argmax())], "conf": round(float(p.max()), 3),
                                 "routed": classes[int(p.argmax())] if p.max() >= threshold else "other"})

    vocab = {k: int(v) for k, v in vec.vocabulary_.items()}
    export = {
        "name": "cafetal-intent-v2",
        "trained": date.today().isoformat(),
        "classes": classes,
        "preprocessing": "hub.intent.normalize: lowercase, strip accents (NFKD), keep [a-z0-9'] and spaces, "
                         "squeeze spaces; then sklearn char_wb n-grams",
        "analyzer": "char_wb",
        "ngram_range": list(NGRAM),
        "sublinear_tf": True,
        "norm": "l2",
        "vocabulary": vocab,
        "idf": [float(v) for v in vec.idf_],
        "coef": [[float(v) for v in row] for row in clf.coef_],
        "intercept": [float(v) for v in clf.intercept_],
        "C": best_c,
        "threshold": threshold,
        "below_threshold": "other (forward to the extension officer)",
        "data": report["data"],
        "test": {k: report["test"][k] for k in ("argmax", "with_threshold")},
    }
    MODEL_OUT.write_text(json.dumps(export, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "intent_eval.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    write_md(report)
    print(json.dumps({"C": best_c, "threshold": threshold, "test": {k: report["test"][k] for k in (
        "argmax", "with_threshold", "with_threshold_english_only", "with_threshold_swahili_only",
        "with_threshold_excluding_massive",
        "auto_answered_precision", "auto_answered_share", "on_topic_answered_right")}, "model_bytes": MODEL_OUT.stat().st_size}, indent=1))


def write_md(r):
    t = r["test"]
    cm = t["confusion_with_threshold"]
    lines = [
        "# Intent classifier evaluation (free-text SMS)", "",
        f"Date: {r['date']}. Produced by `hub/train_intent.py`; raw numbers in `reports/intent_eval.json`.", "",
        "## Data", "",
        f"- `{r['data']['file']}`: {r['data']['n']} messages. Per intent: "
        + ", ".join(f"{k} {v}" for k, v in r["data"]["per_intent"].items()) + ". Per language: "
        + ", ".join(f"{k} {v}" for k, v in r["data"]["per_language"].items()) + ".",
        "- Sources: " + ", ".join(f"{k} {v}" for k, v in r["data"]["per_source"].items())
        + ". `team` = written by the build team (which includes AI agents) in Kenyan SMS style: English and "
          "Kiswahili with sheng, typos, no diacritics; none of it was checked by a native Kiswahili speaker or "
          "taken from real members. `ai-draft-unverified` = a few Gikuyu drafts nobody has checked; `MASSIVE` = "
          "Amazon MASSIVE 1.1 en-US and sw-KE utterances (CC BY 4.0) used only as 'other' (off-topic) examples, "
          "after removing intents/words that overlap ours.",
        f"- Split: {r['data']['split']} -> {r['data']['n_train']} train / {r['data']['n_test']} test.", "",
        "## Model", "",
        f"- {r['model']['vectorizer']} + {r['model']['classifier']}, C={r['model']['C']} "
        f"(5-fold CV macro-F1 by C: {r['model']['cv_macro_f1_by_C']}). {r['model']['n_features']} n-gram features.",
        f"- Confidence threshold **{r['threshold']['value']}** ({r['threshold']['rule']}). Below it the hub replies "
        "`sms_pasar_tecnico` and forwards the message to the officer.",
        "- Exported to `hub/intent_model.json`; `hub/intent.py` runs it in pure Python (a test checks it matches "
        "scikit-learn on the test split).", "",
        "## Results on the held-out 20% split", "",
        "| | n | accuracy | macro-F1 |", "|---|---|---|---|",
    ]
    for k, name in [("argmax", "argmax (no threshold)"), ("with_threshold", "with threshold (as deployed)"),
                    ("with_threshold_english_only", "with threshold, English only"),
                    ("with_threshold_swahili_only", "with threshold, Kiswahili only"),
                    ("with_threshold_kikuyu_only", "with threshold, Gikuyu only (too few to mean anything)"),
                    ("with_threshold_excluding_massive", "with threshold, excluding MASSIVE")]:
        m = t[k]
        if m:
            lines.append(f"| {name} | {m['n']} | {m['accuracy']:.3f} | {m['macro_f1']:.3f} |")
    lines += ["",
              f"Auto-answered share: {t['auto_answered_share']:.1%} of test messages; precision of those answers: "
              f"{t['auto_answered_precision']:.1%}. On-topic test messages (true intent is not 'other') answered "
              f"with the right card automatically: {t['on_topic_answered_right']:.1%}; the rest go to the officer.", "",
              "Confusion matrix (with threshold; rows = true, columns = predicted):", "",
              "| true \\ pred | " + " | ".join(cm["labels"]) + " |",
              "|---|" + "---|" * len(cm["labels"])]
    for lab, row in zip(cm["labels"], cm["matrix"]):
        lines.append(f"| {lab} | " + " | ".join(str(v) for v in row) + " |")
    lines += ["", "Threshold sweep (out-of-fold, 80% split):", "",
              "| threshold | auto precision | auto share | macro-F1 (routed) |", "|---|---|---|---|"]
    for s in r["threshold"]["sweep_oof_train"]:
        lines.append(f"| {s['threshold']:.2f} | {s['auto_precision']:.3f} | {s['auto_coverage']:.3f} | "
                     f"{s['macro_f1_routed']:.3f} |")
    lines += ["", "Probe messages (not in the data):", "", "| message | predicted | conf | routed |", "|---|---|---|---|"]
    for p in r["probes"]:
        lines.append(f"| {p['text']} | {p['pred']} | {p['conf']:.2f} | {p['routed']} |")
    errors = [p for p in r["test_predictions"] if p["pred"] != p["true"]]
    lines += ["", f"Test errors before threshold ({len(errors)}):", ""]
    for p in errors:
        lines.append(f"- \"{p['text']}\" — true {p['true']}, predicted {p['pred']} ({p['conf']:.2f})")
    lines += ["", "## Limits", "",
              "- Small, team-written data: the test split comes from the same writers, so real member SMS will "
              "score lower. Collect real (consented) messages and relabel.",
              "- The Kiswahili and sheng examples were not checked by a native speaker; real messages will use "
              "words and spellings we did not think of.",
              "- The Gikuyu examples are unverified AI drafts and too few to measure; Gikuyu free text will mostly "
              "fall below the threshold and go to the officer (safe, not smart).",
              "- MASSIVE is US English and Kenyan Kiswahili smart-speaker commands; it only teaches what is off-topic.",
              "- PRICE/PRICES, HELP and OFFICER (English) and BEI, MSAADA and AFISA (Kiswahili) are also matched as "
              "exact keywords before the classifier runs.", ""]
    (REPORTS / "intent_eval.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
