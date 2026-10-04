"""Free-text SMS intent classifier: pure-Python inference from hub/intent_model.json (no sklearn at run time).

The model is a char n-gram TF-IDF ('char_wb', like scikit-learn) + multinomial logistic regression, trained by
hub/train_intent.py. `normalize()` is shared with the trainer so both see exactly the same text.
"""
import json
import math
import re
import unicodedata
from pathlib import Path

MODEL_PATH = Path(__file__).resolve().parent / "intent_model.json"
INTENTS = ["price", "report", "help", "talk_to_officer", "other"]

_NON_WORD = re.compile(r"[^a-z0-9' ]+")
_SPACES = re.compile(r"\s\s+")


def normalize(text: str) -> str:
    """Lowercase, drop accents (Gikuyu i/u with tilde -> i/u, as members type them on a basic phone), keep
    letters/digits/apostrophe (I'm, don't), squeeze spaces."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("’", "'").replace("`", "'")
    text = _NON_WORD.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def char_wb_ngrams(text: str, min_n: int, max_n: int) -> list[str]:
    """Same n-grams as sklearn's TfidfVectorizer(analyzer='char_wb') on already-normalized text."""
    out = []
    for w in re.sub(r"\s\s+", " ", text).split():
        w = " " + w + " "
        w_len = len(w)
        for n in range(min_n, max_n + 1):
            offset = 0
            out.append(w[offset:offset + n])
            while offset + n < w_len:
                offset += 1
                out.append(w[offset:offset + n])
            if offset == 0:  # short word: counted once
                break
    return out


class IntentModel:
    def __init__(self, path: Path = MODEL_PATH):
        m = json.loads(Path(path).read_text(encoding="utf-8"))
        self.meta = m
        self.classes = m["classes"]
        self.vocab = m["vocabulary"]          # n-gram -> column
        self.idf = m["idf"]
        self.coef = m["coef"]                 # [n_classes][n_features]
        self.intercept = m["intercept"]
        self.threshold = float(m["threshold"])
        self.min_n, self.max_n = m["ngram_range"]
        self.sublinear_tf = bool(m.get("sublinear_tf", False))

    def features(self, text: str) -> dict[int, float]:
        counts: dict[int, float] = {}
        for g in char_wb_ngrams(normalize(text), self.min_n, self.max_n):
            j = self.vocab.get(g)
            if j is not None:
                counts[j] = counts.get(j, 0.0) + 1.0
        vec = {}
        for j, tf in counts.items():
            if self.sublinear_tf:
                tf = 1.0 + math.log(tf)
            vec[j] = tf * self.idf[j]
        norm = math.sqrt(sum(v * v for v in vec.values()))
        if norm > 0:
            vec = {j: v / norm for j, v in vec.items()}
        return vec

    def predict_proba(self, text: str) -> dict[str, float]:
        x = self.features(text)
        scores = [b + sum(w[j] * v for j, v in x.items()) for w, b in zip(self.coef, self.intercept)]
        mx = max(scores)
        exps = [math.exp(s - mx) for s in scores]
        z = sum(exps)
        return {c: e / z for c, e in zip(self.classes, exps)}

    def classify(self, text: str) -> dict:
        """{"intent", "conf", "accepted"}; accepted=False means below threshold (route to the officer)."""
        p = self.predict_proba(text)
        best = max(p, key=p.get)
        return {"intent": best, "conf": round(p[best], 4), "accepted": p[best] >= self.threshold,
                "threshold": self.threshold}


_model = None


def get_model() -> IntentModel | None:
    global _model
    if _model is None and MODEL_PATH.exists():
        _model = IntentModel()
    return _model


def classify(text: str) -> dict:
    m = get_model()
    if m is None:  # no trained model: everything goes to the officer (safe default)
        return {"intent": "other", "conf": 0.0, "accepted": False, "threshold": None}
    return m.classify(text)
