"""Build data/intent/examples.csv = hand-written examples + a sample of Amazon MASSIVE 1.1 (es-ES) as 'otro'.

    python3 -m hub.build_intent_examples [--massive /home/user/data_raw/massive/1.1/data/es-ES.jsonl] [--n 300]

MASSIVE (CC BY 4.0, https://github.com/alexa/massive) download:
    https://amazon-massive-nlu-dataset.s3.amazonaws.com/amazon-massive-dataset-1.1.tar.gz
Only the 'train' partition is sampled. MASSIVE intents and utterances that overlap ours (money, prices, coffee,
calls, appointments, help, information requests) are excluded, so 'otro' does not contradict the other intents.
"""
import argparse
import csv
import json
import random
from pathlib import Path

from .intent import normalize

ROOT = Path(__file__).resolve().parent.parent
HAND = ROOT / "data" / "intent" / "handwritten.csv"
OUT = ROOT / "data" / "intent" / "examples.csv"
DEFAULT_MASSIVE = Path("/home/user/data_raw/massive/1.1/data/es-ES.jsonl")

EXCLUDE_INTENTS = {"qa_currency", "qa_stock", "iot_coffee", "weather_query", "takeaway_query", "takeaway_order"}
EXCLUDE_WORDS = ["precio", "cuest", "cuanto", "vale", "pag", "cobr", "kilo", "cafe", "dinero", "dolar", "peso",
                 "ayud", "tecnic", "ingenier", "hoja", "plaga", "roya", "report", "llam", "marca", "cita", "visit",
                 "informaci", "info", "hablar", "venga", "cooperativa", "maiz", "frijol", "mancha", "planta"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--massive", type=Path, default=DEFAULT_MASSIVE)
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()

    rows = list(csv.DictReader(HAND.open(encoding="utf-8")))
    seen = {normalize(r["text"]) for r in rows}

    pool = {}
    for line in args.massive.open(encoding="utf-8"):
        d = json.loads(line)
        if d["partition"] != "train" or d["intent"] in EXCLUDE_INTENTS:
            continue
        norm = normalize(d["utt"])
        if not norm or norm in seen or any(w in norm for w in EXCLUDE_WORDS):
            continue
        pool.setdefault(d["intent"], []).append(d["utt"])
    rng = random.Random(args.seed)
    intents = sorted(pool)
    picked = []
    # Round-robin over MASSIVE intents so 'otro' covers many everyday topics.
    for lst in pool.values():
        rng.shuffle(lst)
    i = 0
    while len(picked) < args.n and any(pool.values()):
        lst = pool[intents[i % len(intents)]]
        if lst:
            utt = lst.pop()
            if normalize(utt) not in seen:
                seen.add(normalize(utt))
                picked.append(utt)
        i += 1
    rows += [{"text": u, "intent": "otro", "lang": "es", "source": "MASSIVE"} for u in picked]

    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["text", "intent", "lang", "source"])
        w.writeheader()
        w.writerows(rows)
    counts = {}
    for r in rows:
        counts[(r["intent"], r["source"])] = counts.get((r["intent"], r["source"]), 0) + 1
    print(f"wrote {OUT} ({len(rows)} rows)")
    for k in sorted(counts):
        print(f"  {k[0]:20s} {k[1]:22s} {counts[k]}")


if __name__ == "__main__":
    main()
