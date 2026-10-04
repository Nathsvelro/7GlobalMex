"""content/cards.json access: the ONLY source of text sent to farmers.

`render(card_id, lang, **slots)` returns the card text with its declared slots filled. Slot values must be
numbers, dates, source names or community names (checked by a strict character whitelist), so no free text
can reach a farmer through a slot.
"""
import json
import re
import threading
import unicodedata
from datetime import date

from . import db

_lock = threading.Lock()
_cache = {"mtime": None, "data": None}

# Letters (incl. accented letters such as the Gikuyu i/u with tilde), digits, space and . , / : - ( ) % ' — enough for
# "139.00", "KES/kg cherry", "DEMO county 25/26, KAMIS", "Ondera Juu". No braces, so a value can never inject
# another slot. In SMS cards accented letters are sent without the accent (gsm_safe).
SLOT_VALUE_RE = re.compile(r"^[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñĨŨĩũ .,/:\-()%']{1,40}$")

# GSM 03.38 basic alphabet (1 unit each) and extension table (2 units each).
GSM_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà")
GSM_EXT = set("^{}\\[~]|€\f")


DEFAULT_LANG = "en"   # main language; used when a card has no text in the member's language


class CardError(Exception):
    pass


def cards_file():
    return db.content_dir() / "cards.json"


def load() -> dict:
    """cards.json, re-read when the file changes on disk."""
    path = cards_file()
    mtime = path.stat().st_mtime_ns
    with _lock:
        if _cache["mtime"] != mtime:
            _cache["data"] = json.loads(path.read_text(encoding="utf-8"))
            _cache["mtime"] = mtime
        return _cache["data"]


def get(card_id: str) -> dict | None:
    for c in load()["cards"]:
        if c["id"] == card_id:
            return c
    return None


def languages() -> list[str]:
    return list(load().get("languages", {DEFAULT_LANG: "English"}).keys())


def gsm_safe(value: str) -> str:
    """Replace characters outside the GSM-7 alphabet by their unaccented letter (Kĩrĩnyaga -> Kirinyaga), so one
    accent in a slot value does not turn the SMS into UCS-2 (70 characters per SMS)."""
    out = []
    for ch in value:
        if ch in GSM_BASIC or ch in GSM_EXT:
            out.append(ch)
        else:
            base = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))
            out.append(base if base and all(c in GSM_BASIC for c in base) else "?")
    return "".join(out)


def render(card_id: str, lang: str = DEFAULT_LANG, **slots) -> tuple[str, str]:
    """Return (text, lang_used). Falls back to English if the card has no text in `lang`.
    For SMS cards (type sms/alert) slot values are made GSM-7 safe."""
    card = get(card_id)
    if card is None:
        raise CardError(f"card '{card_id}' is missing from cards.json")
    if not card.get(lang):
        lang = DEFAULT_LANG
    text = card[lang]
    declared = set(card.get("slots") or [])
    for name, value in slots.items():
        if name not in declared:
            raise CardError(f"card '{card_id}' has no slot '{name}'")
        value = str(value)
        if not SLOT_VALUE_RE.match(value):
            raise CardError(f"slot value not allowed for '{name}': {value!r}")
        if card.get("type") in ("sms", "alert"):
            value = gsm_safe(value)
        text = text.replace("{" + name + "}", value)
    left = re.findall(r"\{(\w+)\}", text)
    if left:
        raise CardError(f"card '{card_id}' has unfilled slots: {left}")
    return text, lang


def sms_length(text: str) -> dict:
    """Length in SMS units and number of segments (GSM-7: 160 / 153 per part; otherwise UCS-2: 70 / 67)."""
    if all(ch in GSM_BASIC or ch in GSM_EXT for ch in text):
        units = sum(2 if ch in GSM_EXT else 1 for ch in text)
        single, multi, enc = 160, 153, "GSM-7"
    else:
        units = len(text.encode("utf-16-le")) // 2
        single, multi, enc = 70, 67, "UCS-2"
    segments = 1 if units <= single else -(-units // multi)
    return {"length": units, "encoding": enc, "segments": segments}


def _save(data: dict) -> None:
    path = cards_file()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def set_verified(card_id: str, lang: str, reviewer: str, verified: bool = True) -> dict:
    """Mark one language of a card verified (reviewer name + date) or back to unverified."""
    with _lock:
        data = json.loads(cards_file().read_text(encoding="utf-8"))
        card = next((c for c in data["cards"] if c["id"] == card_id), None)
        if card is None:
            raise KeyError(card_id)
        if lang not in data.get("languages", {}):
            raise ValueError(f"unknown language {lang}")
        card.setdefault("status", {})[lang] = "verified" if verified else "unverified"
        card.setdefault("reviewed_by", {})[lang] = f"{reviewer} ({date.today().isoformat()})" if verified else None
        _save(data)
        _cache["mtime"] = None
        return card


def set_native_audio(card_id: str, lang: str, rel_path: str, speaker: str) -> dict:
    """Point a card at a native-speaker recording. The language goes back to unverified until reviewed."""
    with _lock:
        data = json.loads(cards_file().read_text(encoding="utf-8"))
        card = next((c for c in data["cards"] if c["id"] == card_id), None)
        if card is None:
            raise KeyError(card_id)
        card.setdefault("audio", {})[lang] = rel_path
        card.setdefault("audio_source", {})[lang] = f"native:{speaker}"
        card.setdefault("status", {})[lang] = "unverified"
        card.setdefault("reviewed_by", {})[lang] = None
        _save(data)
        _cache["mtime"] = None
        return card
