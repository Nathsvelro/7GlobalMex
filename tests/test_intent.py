"""The pure-Python intent inference (hub/intent.py) must give the same answers as scikit-learn."""
import csv
import json
import math
from pathlib import Path

import pytest

from hub.intent import IntentModel, char_wb_ngrams, normalize

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "reports" / "intent_eval.json"


def test_normalize():
    assert normalize("¿Qué PRECIO tiene el café?") == "que precio tiene el cafe"
    assert normalize("  Año   ñandú ") == "ano nandu"
    assert normalize("k’op  ja'") == "k'op ja'"


def test_char_wb_ngrams():
    assert char_wb_ngrams("ab", 2, 4) == [" a", "ab", "b ", " ab", "ab ", " ab "]


@pytest.mark.skipif(not EVAL.exists(), reason="run hub/train_intent.py first")
def test_json_inference_matches_sklearn_test_predictions():
    """reports/intent_eval.json stores scikit-learn's predictions on the held-out split at training time."""
    model = IntentModel()
    preds = json.loads(EVAL.read_text(encoding="utf-8"))["test_predictions"]
    assert len(preds) > 50
    for p in preds:
        proba = model.predict_proba(p["text"])
        assert max(proba, key=proba.get) == p["pred"], p["text"]
        for c, ref in zip(model.classes, p["proba"]):
            assert math.isclose(proba[c], ref, rel_tol=1e-9, abs_tol=1e-12), (p["text"], c)


def test_json_inference_matches_live_sklearn():
    pytest.importorskip("sklearn")
    import numpy as np
    from sklearn.model_selection import train_test_split
    from hub import train_intent as T

    model = IntentModel()
    rows = list(csv.DictReader(T.DATA.open(encoding="utf-8")))
    X = np.array([r["text"] for r in rows], dtype=object)
    y = np.array([r["intent"] for r in rows])
    tr, te = train_test_split(np.arange(len(rows)), test_size=0.2, stratify=y, random_state=T.SEED)
    sk = T.make_model(model.meta["C"])
    sk.fit(X[tr], y[tr])
    ref = sk.predict_proba(X[te])
    assert list(sk.classes_) == model.classes
    for text, r in zip(X[te], ref):
        p = model.predict_proba(text)
        assert max(p, key=p.get) == sk.classes_[int(r.argmax())]
        assert all(math.isclose(p[c], v, rel_tol=1e-7, abs_tol=1e-9) for c, v in zip(sk.classes_, r))


def test_threshold_is_in_model():
    m = IntentModel()
    assert 0 < m.threshold < 1 and set(m.classes) == {"precio", "reporte", "ayuda", "hablar_con_tecnico", "otro"}
