"""Build data/intent/examples.csv = hand-written examples + a sample of Amazon MASSIVE 1.1 (en-US and sw-KE) as 'other'.

    python3 -m hub.build_intent_examples [--massive-dir /home/user/data_raw/massive/1.1/data] [--n 200]

MASSIVE (CC BY 4.0, https://github.com/alexa/massive) download:
    https://amazon-massive-nlu-dataset.s3.amazonaws.com/amazon-massive-dataset-1.1.tar.gz
Only the 'train' partition is sampled, --n utterances per locale. MASSIVE intents and utterances that overlap ours
(money, prices, coffee, crops, calls, visits, appointments, help, information requests) are excluded, so 'other'
does not contradict the other intents.
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
DEFAULT_MASSIVE = Path("/home/user/data_raw/massive/1.1/data")
LOCALES = {"en-US": "en", "sw-KE": "sw"}   # MASSIVE locale -> our language code

EXCLUDE_INTENTS = {"qa_currency", "qa_stock", "iot_coffee", "weather_query", "takeaway_query", "takeaway_order"}
# Substrings of the normalized utterance (English, then Kiswahili). Over-matching only shrinks the pool.
EXCLUDE_WORDS = [
    "price", "cost", "how much", "pay", "paid", "kilo", "kg", "coffee", "money", "dollar", "shilling", "ksh",
    "cheap", "expensive", "sell", "buy", "market", "help", "officer", "extension", "agronom", "expert", "leaf",
    "leaves", "pest", "insect", "bug", "disease", "sick", "rust", "spot", "report", "call", "phone", "visit",
    "appointment", "meeting", "info", "talk", "speak", "chat", "contact", "coop", "co op", "factory", "maize",
    "corn", "bean", "plant", "tree", "farm", "crop", "cherry", "explain", "instruction", "menu", "how do i",
    "how does",
    "bei", "gharama", "ngapi", "pesa", "shilingi", "lipa", "malipo", "kahawa", "buni", "msaada", "saidia", "afisa",
    "ugani", "jani", "wadudu", "ugonjwa", "kutu", "ripoti", "simu", "piga", "tembelea", "ziara", "ongea",
    "zungumza", "chama", "kiwanda", "mahindi", "maharagwe", "mmea", "mimea", "shamba", "kuuza", "nunua", "soko",
    "mbolea", "dawa", "mkutano", "maelezo", "habari",
]


def sample_locale(path: Path, n: int, seed: int, seen: set) -> list[str]:
    pool = {}
    for line in path.open(encoding="utf-8"):
        d = json.loads(line)
        if d["partition"] != "train" or d["intent"] in EXCLUDE_INTENTS:
            continue
        norm = normalize(d["utt"])
        if not norm or norm in seen or any(w in norm for w in EXCLUDE_WORDS):
            continue
        pool.setdefault(d["intent"], []).append(d["utt"])
    rng = random.Random(seed)
    intents = sorted(pool)
    for k in intents:
        rng.shuffle(pool[k])
    picked = []
    i = 0
    # Round-robin over MASSIVE intents so 'other' covers many everyday topics.
    while len(picked) < n and any(pool.values()):
        lst = pool[intents[i % len(intents)]]
        if lst:
            utt = lst.pop()
            if normalize(utt) not in seen:
                seen.add(normalize(utt))
                picked.append(utt)
        i += 1
    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--massive-dir", type=Path, default=DEFAULT_MASSIVE, help="folder with en-US.jsonl and sw-KE.jsonl")
    ap.add_argument("--n", type=int, default=200, help="MASSIVE utterances per locale")
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()

    rows = list(csv.DictReader(HAND.open(encoding="utf-8")))
    seen = {normalize(r["text"]) for r in rows}
    for locale, lang in LOCALES.items():
        picked = sample_locale(args.massive_dir / f"{locale}.jsonl", args.n, args.seed, seen)
        rows += [{"text": u, "intent": "other", "lang": lang, "source": "MASSIVE"} for u in picked]

    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["text", "intent", "lang", "source"])
        w.writeheader()
        w.writerows(rows)
    counts = {}
    for r in rows:
        k = (r["intent"], r["lang"], r["source"])
        counts[k] = counts.get(k, 0) + 1
    print(f"wrote {OUT} ({len(rows)} rows)")
    for k in sorted(counts):
        print(f"  {k[0]:16s} {k[1]:4s} {k[2]:22s} {counts[k]}")


if __name__ == "__main__":
    main()
