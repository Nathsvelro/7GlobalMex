#!/usr/bin/env python3
"""Set VERSION in app/sw.js to a short hash of every file the service worker precaches.

    python3 scripts/bump_sw_version.py           # rewrite the VERSION line if a precached file changed
    python3 scripts/bump_sw_version.py --check   # exit 1 if VERSION is out of date (nothing written)

Hashed: the SHELL list in sw.js, config.json, model/labels.json, the model file it names, content/cards.json,
every audio file listed in cards.json, and sw.js itself (with the VERSION line blanked). A new VERSION makes
phones download a fresh copy and delete the old cache. run.sh calls this before starting the hub; sw.js stays a
plain static file, so the app also works from any static host (run this script before uploading).
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
SW = APP / "sw.js"
VERSION_RE = re.compile(r"^const VERSION = '[^']*';$", re.M)


def precached(sw_text: str) -> list[Path]:
    shell = re.search(r"const SHELL = \[(.*?)\];", sw_text, re.S)
    if not shell:
        sys.exit("SHELL list not found in app/sw.js")
    files = [APP / u for u in re.findall(r"'([^']+)'", shell.group(1)) if u != "./"]  # './' is index.html
    files += [APP / "config.json", APP / "model" / "labels.json"]
    labels = json.loads((APP / "model" / "labels.json").read_text(encoding="utf-8"))
    files.append(APP / "model" / labels.get("file", "cafetal.onnx"))
    cards_path = ROOT / "content" / "cards.json"
    files.append(cards_path)
    cards = json.loads(cards_path.read_text(encoding="utf-8"))
    for card in cards["cards"]:
        files += [ROOT / "content" / p for p in (card.get("audio") or {}).values() if p]
    return sorted(set(files))


def compute(sw_text: str) -> str:
    h = hashlib.sha256(VERSION_RE.sub("const VERSION = '';", sw_text).encode())
    for f in precached(sw_text):
        h.update(str(f.relative_to(ROOT)).encode() + b"\0")
        h.update(f.read_bytes() if f.is_file() else b"<missing>")  # the SW tolerates missing audio
        h.update(b"\0")
    return "cafetal-" + h.hexdigest()[:10]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="only report whether VERSION is current")
    args = ap.parse_args()
    text = SW.read_text(encoding="utf-8")
    if not VERSION_RE.search(text):
        sys.exit("VERSION line not found in app/sw.js")
    version = compute(text)
    new = VERSION_RE.sub(f"const VERSION = '{version}';", text)
    if new == text:
        print(f"app/sw.js VERSION is current: {version}")
    elif args.check:
        print(f"app/sw.js VERSION is out of date; run scripts/bump_sw_version.py (want {version})")
        sys.exit(1)
    else:
        SW.write_text(new, encoding="utf-8")
        print(f"app/sw.js VERSION -> {version}")


if __name__ == "__main__":
    main()
