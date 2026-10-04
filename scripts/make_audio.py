#!/usr/bin/env python3
"""Render the spoken version of every card in content/cards.json.

For each card of type ui / diagnosis / advice and each language:
  * audio_source[lang] starting with "native" -> keep the recorded file (never overwritten);
  * otherwise synthesise with Piper (offline TTS) -> WAV -> ffmpeg -> MP3 (mono, 22050 Hz)
    at content/audio/<lang>/<card_id>.mp3, and set audio / audio_source in cards.json.
SMS and alert cards are text messages: they get "audio": {} and "audio_source": {}.

Idempotent: content/audio/manifest.json stores a hash of what was spoken for each file,
so unchanged cards are skipped. WAVs are written to a temp folder and deleted.

Usage:
  python3 scripts/make_audio.py            # render what changed
  python3 scripts/make_audio.py --check    # only validate cards.json (ids, slots, SMS length)
  python3 scripts/make_audio.py --force    # re-render all synthetic audio
  python3 scripts/make_audio.py --only diag_roya --lang kik

Voices (one per language):
  en   English Piper voice (en-us-lessac-medium), phonemes with its own espeak voice (en-us).
       audio_source "synthetic:piper-en-us-lessac-medium".
  sw   PROVISIONAL: a Piper voice trained on another language (default: the English voice en-us-lessac-medium)
       fed Kiswahili phonemes from espeak-ng "sw" (the voice config is copied with "espeak": {"voice": "sw"}),
       length_scale 1.25. audio_source "synthetic-provisional:piper-<voice>-espeak-sw".
       The Spanish voice (es-mls_10246-low) was tried too and came out slow and choppy (see content/README.md).
  kik  PROVISIONAL: the same voice and espeak "sw" phonemes reading the Gikuyu text respelled for the voice
       (i-tilde -> e, u-tilde -> o: in Gikuyu spelling i-tilde is [e] and u-tilde is [o]).
       audio_source "synthetic-provisional:piper-<voice>-espeak-sw-reading-gikuyu".
  No Piper voice for Kiswahili or Gikuyu exists in this build environment; sw and kik audio is a stop-gap
  until native speakers record the cards (hub content page).
  Audio whose audio_source starts with "native" is a person's recording and is never overwritten.

Environment:
  PIPER_BIN        default /home/user/tools/piper/piper
  PIPER_VOICE_EN   English voice (en); default: first .onnx in /home/user/tools/voice-en/
  PIPER_VOICE_SW   voice used for sw and kik; default: the English voice (PIPER_VOICE_EN, else the first .onnx in
                   /home/user/tools/voice-en/). Set it to /home/user/tools/voice-es/es-mls_10246-low.onnx to compare.
  PIPER_ESPEAK_SW  espeak-ng voice for sw and kik (default sw)
  AUDIO_BITRATE    default 24k (keeps all audio small; the source voices are 16 kHz)
"""
import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content")
CARDS = os.path.join(CONTENT, "cards.json")
MANIFEST = os.path.join(CONTENT, "audio", "manifest.json")

AUDIO_TYPES = ("ui", "diagnosis", "advice")
TEXT_ONLY_TYPES = ("sms", "alert")
MAIN_LANG = "en"
# Piper settings. noise_w 0.4 gives steadier timing than the default 0.8.
PIPER_ARGS = ["--noise_w", "0.4", "--sentence_silence", "0.3"]
# The English voice speaks fast (~200+ words/min); length_scale 1.4 gives ~170 words/min.
# Read with Kiswahili phonemes it speaks about 5-6 vowel groups per second (computed estimate); 1.25 slows that to
# roughly 4-5, easier to follow for a voice with a foreign accent.
LANG_ARGS = {"en": ["--length_scale", "1.4"], "sw": ["--length_scale", "1.25"], "kik": ["--length_scale", "1.25"]}
# Squeeze long pauses the low-quality voice sometimes inserts; trim leading silence.
FFMPEG_FILTER = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05:"
                 "stop_periods=-1:stop_duration=0.35:stop_threshold=-45dB:stop_silence=0.3")

# Ids every part of the system relies on (PLAN.md section 11).
REQUIRED_IDS = """
ui_app_name ui_choose_language ui_consent_title ui_consent_text ui_consent_accept ui_consent_decline
ui_member_id_prompt ui_pin_optional ui_pin_prompt ui_continue ui_take_photo ui_photo_tip_underside
ui_analyzing ui_confidence ui_play_kik ui_play_sw ui_play_en ui_send_sms ui_simulate_send ui_saved ui_history
ui_settings ui_delete_all ui_delete_confirm ui_sync_photos ui_synced ui_back ui_unverified ui_demo
ui_simulated ui_offline_ready ui_limits_note ui_language ui_pending_sms ui_sent ui_no_records
diag_sano diag_roya diag_minador diag_phoma diag_cercospora diag_acaro_rojo diag_duda
advice_roya advice_minador advice_phoma advice_cercospora advice_sano advice_acaro_rojo
advice_call_officer limits_yield
sms_obs_recibida sms_codigo_invalido sms_no_registrado sms_precio sms_precio_sin_datos
sms_reporte_instrucciones sms_ayuda sms_pasar_tecnico alert_roya
""".split()
REQUIRED_SLOTS = {
    "sms_precio": {"precio_cafe", "unidad_cafe", "precio_maiz", "precio_frijol", "fuente", "fecha"},
    "alert_roya": {"comunidad", "n_reportes"},
}
DUDA = {"en": "I'm not sure — show the leaf to the extension officer."}
# Fields of a card that are not language texts; any other key must be a language from "languages".
CARD_FIELDS = {"id", "type", "slots", "audio", "audio_source", "source", "status", "reviewed_by"}

# Long slot values used to check that every SMS fits in one message (KES, Kirinyaga). The community name has the
# 40 characters registration allows (hub/main.py, hub/cards.py SLOT_VALUE_RE); the report count has 3 digits.
SAMPLE_SLOTS = {
    "precio_cafe": "157.40", "unidad_cafe": "KES/kg cherry", "precio_maiz": "105.50",
    "precio_frijol": "180.00", "fecha": "2026-09-30", "comunidad": "Ondera Kilima Upper Ward, by the factory",
    "n_reportes": "120",
}
assert len(SAMPLE_SLOTS["comunidad"]) == 40
# GSM 03.38 basic alphabet (one SMS = 160 of these). Anything else forces UCS-2 (70 chars).
GSM7 = set("@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
           "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà")
GSM7_EXT = set("^{}\\[~]|€")  # count as 2 characters


def gsm7_length(text):
    """Return the GSM-7 length of text, or None if a character is outside GSM-7."""
    n = 0
    for ch in text:
        if ch in GSM7:
            n += 1
        elif ch in GSM7_EXT:
            n += 2
        else:
            return None
    return n


def load_prices_fuente():
    """Source string the hub puts in {fuente}: data/prices.json 'sms_fuente' if present."""
    try:
        with open(os.path.join(ROOT, "data", "prices.json"), encoding="utf-8") as f:
            return json.load(f).get("sms_fuente") or "DEMO county 25/26, KAMIS"
    except (OSError, ValueError):
        return "DEMO county 25/26, KAMIS"


# ---------------------------------------------------------------- validation
def check(doc):
    problems = []
    langs = list(doc.get("languages", {}))
    if MAIN_LANG not in langs:
        problems.append(f"languages must include the main language '{MAIN_LANG}'")
    cards = doc.get("cards", [])
    ids = [c.get("id") for c in cards]
    for rid in REQUIRED_IDS:
        if rid not in ids:
            problems.append(f"missing required card id: {rid}")
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        problems.append(f"duplicate ids: {sorted(dup)}")
    slots_sample = dict(SAMPLE_SLOTS, fuente=load_prices_fuente())
    for c in cards:
        cid = c.get("id")
        for key in ("type", "slots", "audio", "audio_source", "source", "status", "reviewed_by"):
            if key not in c:
                problems.append(f"{cid}: missing field '{key}'")
        if c.get("type") not in AUDIO_TYPES + TEXT_ONLY_TYPES:
            problems.append(f"{cid}: unknown type {c.get('type')!r}")
        # Leftovers of a removed language (text, audio, status or reviewer for a language not in "languages").
        extra = sorted(k for k in c if k not in CARD_FIELDS and k not in langs)
        for key in ("audio", "audio_source", "status", "reviewed_by"):
            extra += [f"{key}.{k}" for k in (c.get(key) or {}) if k not in langs]
        if extra:
            problems.append(f"{cid}: keys for languages not in \"languages\": {extra}")
        for lang in langs:
            text = c.get(lang)
            if not text:
                problems.append(f"{cid}: no text for '{lang}'")
                continue
            used = set(re.findall(r"\{(\w+)\}", text))
            declared = set(c.get("slots", []))
            if used != declared:
                problems.append(f"{cid}/{lang}: slots in text {sorted(used)} != declared {sorted(declared)}")
            if c.get("type") in TEXT_ONLY_TYPES:
                filled = text
                for k, v in slots_sample.items():
                    filled = filled.replace("{" + k + "}", v)
                n = gsm7_length(filled)
                if n is None:
                    bad = sorted({ch for ch in filled if ch not in GSM7 and ch not in GSM7_EXT})
                    problems.append(f"{cid}/{lang}: characters outside GSM-7 {bad} (SMS would drop to 70 chars)")
                elif n > 160:
                    problems.append(f"{cid}/{lang}: {n} chars after filling slots (> 160)")
            if c.get("status", {}).get(lang) not in ("unverified", "verified"):
                problems.append(f"{cid}/{lang}: status must be 'unverified' or 'verified'")
            if lang not in c.get("reviewed_by", {}):
                problems.append(f"{cid}/{lang}: reviewed_by has no '{lang}' entry (null until reviewed)")
        if c.get("type") in TEXT_ONLY_TYPES and c.get("audio"):
            problems.append(f"{cid}: text-only card should have \"audio\": {{}}")
    for cid, need in REQUIRED_SLOTS.items():
        card = next((c for c in cards if c.get("id") == cid), None)
        if card and set(card.get("slots", [])) != need:
            problems.append(f"{cid}: slots must be {sorted(need)}")
    duda = next((c for c in cards if c.get("id") == "diag_duda"), None)
    for lang, want in DUDA.items():
        if duda and lang in langs and duda.get(lang) != want:
            problems.append(f"diag_duda/{lang} must be exactly: {want}")
    return problems


# ---------------------------------------------------------------- text for the TTS
SPOKEN_WORDS = {  # per language; whole words only
    "en": {"SMS": "S M S", "PIN": "pin", "M0123": "M 0 1 2 3", "Gĩkũyũ": "Gikuyu"},
    # sw and kik are read with espeak "sw" phonemes: Swahili letter names and spellings.
    "sw": {"SMS": "es em es", "PIN": "pin", "Wi-Fi": "waifai", "WiFi": "waifai", "app": "ap", "App": "ap",
           "CBD": "si bi di", "M0123": "M 0 1 2 3", "DEMO": "demo"},
}
SPOKEN_WORDS["kik"] = SPOKEN_WORDS["sw"]


def tts_text(text, lang):
    """Turn card text into something the Piper voice reads well (audio only; the
    card text itself is never changed)."""
    t = text
    if lang == "kik":
        # Gikuyu spelling: i-tilde is [e], u-tilde is [o]. espeak "sw" knows neither letter.
        t = t.replace("ĩ", "e").replace("ũ", "o").replace("Ĩ", "E").replace("Ũ", "O")
    if lang != "en":
        # Bilingual labels ("HAIJAHAKIKIWA · UNVERIFIED"): the English word is for readers; the voice says only the
        # word in the card's own language.
        t = re.sub(r"\s*·\s*(UNVERIFIED|SIMULATED)\b", "", t)
    for a, b in SPOKEN_WORDS.get(lang, SPOKEN_WORDS["sw"]).items():
        t = re.sub(r"(?<!\w)" + re.escape(a) + r"(?!\w)", b, t)
    t = re.sub(r"\b([A-Z]{2,})\b", lambda m: m.group(1).lower(), t)  # UNVERIFIED -> unverified (not spelled)
    t = t.replace("—", ", ").replace("–", ", ").replace("…", ".")
    t = re.sub(r"[«»\"“”]", "", t)
    t = re.sub(r"[()]", ", ", t).replace("/", " ")
    if lang in ("sw", "kik"):
        # espeak "sw" turns j into a phoneme neither Piper voice was trained on; "dy" comes out as d + y.
        t = t.replace("j", "dy").replace("J", "Dy")
    t = re.sub(r"\s+([,.;:?!])", r"\1", t)
    t = re.sub(r",(\s*,)+", ",", t)
    t = re.sub(r",\s*([.;:?!])", r"\1", t)
    t = re.sub(r",(?=\S)", ", ", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" ,")
    return t


# ---------------------------------------------------------------- synthesis
def find_voice(env, folder):
    voice = os.environ.get(env)
    if voice:
        return voice
    found = sorted(glob.glob(os.path.join(folder, "*.onnx")))
    if not found:
        sys.exit(f"No Piper voice found in {folder}: set {env}=/path/to/voice.onnx")
    return found[0]


def voice_espeak(voice, default):
    """The espeak-ng voice named in the Piper voice's own config (en-us for the English voice)."""
    try:
        with open(voice + ".json", encoding="utf-8") as f:
            return json.load(f).get("espeak", {}).get("voice") or default
    except (OSError, ValueError):
        return default


def voice_name(voice):
    name = os.path.basename(voice)
    return name[:-len(".onnx")] if name.endswith(".onnx") else name


_VOICES = {}


def voice_for(lang):
    """(voice .onnx path, espeak voice, audio_source label) for one language.
    en: the English voice. sw and kik (and any other language): a provisional voice, by default the same English
    Piper voice fed espeak-ng "sw" phonemes."""
    if lang not in _VOICES:
        if lang == "en":
            voice = find_voice("PIPER_VOICE_EN", "/home/user/tools/voice-en")
            _VOICES[lang] = (voice, voice_espeak(voice, "en-us"), f"synthetic:piper-{voice_name(voice)}")
        else:
            voice = os.environ.get("PIPER_VOICE_SW") or find_voice("PIPER_VOICE_EN", "/home/user/tools/voice-en")
            espeak = os.environ.get("PIPER_ESPEAK_SW", "sw")
            label = f"synthetic-provisional:piper-{voice_name(voice)}-espeak-{espeak}"
            if lang == "kik":
                label += "-reading-gikuyu"
            elif lang != "sw":
                label += f"-reading-{lang}"
            _VOICES[lang] = (voice, espeak, label)
    return _VOICES[lang]


def piper_config(voice, espeak_voice, tmpdir):
    """Copy the voice config with the chosen espeak voice ("sw" to give the English voice Kiswahili phonemes)."""
    with open(voice + ".json", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.setdefault("espeak", {})["voice"] = espeak_voice
    path = os.path.join(tmpdir, f"{os.path.basename(voice)}.{espeak_voice}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    return path


def synthesize(jobs, piper_bin, voice, config, bitrate, tmpdir, piper_args=PIPER_ARGS):
    """jobs: list of (spoken_text, mp3_path). One Piper process for the whole batch."""
    lines = []
    for i, (text, _) in enumerate(jobs):
        lines.append(json.dumps({"text": text, "output_file": os.path.join(tmpdir, f"{i}.wav")},
                                ensure_ascii=False))
    proc = subprocess.run([piper_bin, "-q", "--model", voice, "--config", config, "--json-input"]
                          + list(piper_args), input="\n".join(lines) + "\n", text=True,
                          capture_output=True)
    if proc.returncode != 0:
        sys.exit(f"piper failed: {proc.stderr[-2000:]}")
    for i, (text, mp3) in enumerate(jobs):
        wav = os.path.join(tmpdir, f"{i}.wav")
        if not os.path.exists(wav):
            sys.exit(f"piper produced no audio for: {text!r}")
        os.makedirs(os.path.dirname(mp3), exist_ok=True)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", wav,
                        "-af", FFMPEG_FILTER, "-ac", "1", "-ar", "22050",
                        "-c:a", "libmp3lame", "-b:a", bitrate, mp3], check=True)
        os.remove(wav)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="only validate cards.json")
    ap.add_argument("--force", action="store_true", help="re-render all synthetic audio")
    ap.add_argument("--only", nargs="*", help="card ids to render")
    ap.add_argument("--lang", help="only this language")
    args = ap.parse_args()

    with open(CARDS, encoding="utf-8") as f:
        original = f.read()
    doc = json.loads(original)

    problems = check(doc)
    for p in problems:
        print("PROBLEM:", p)
    if args.check:
        print(f"{len(doc['cards'])} cards checked, {len(problems)} problem(s).")
        sys.exit(1 if problems else 0)

    piper_bin = os.environ.get("PIPER_BIN", "/home/user/tools/piper/piper")
    bitrate = os.environ.get("AUDIO_BITRATE", "24k")
    for tool in (piper_bin, shutil.which("ffmpeg")):
        if not tool or not os.path.exists(tool):
            sys.exit(f"missing tool: {tool or 'ffmpeg'}")

    try:
        with open(MANIFEST, encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError):
        manifest = {}
    files = manifest.setdefault("files", {})

    jobs = {}  # (voice, espeak voice, piper args) -> [(spoken_text, mp3_path, rel, hash)]
    kept_native, skipped, voices_used = 0, 0, {}
    for card in doc["cards"]:
        if card["type"] in TEXT_ONLY_TYPES:
            card["audio"], card["audio_source"] = {}, {}
            continue
        card.setdefault("audio", {})
        card.setdefault("audio_source", {})
        for lang in doc["languages"]:
            if args.lang and lang != args.lang:
                continue
            if args.only and card["id"] not in args.only:
                continue
            rel = card["audio"].get(lang) or f"audio/{lang}/{card['id']}.mp3"
            mp3 = os.path.join(CONTENT, rel)
            if str(card["audio_source"].get(lang, "")).startswith("native"):
                kept_native += 1
                if not os.path.exists(mp3):
                    print(f"WARNING: native recording missing: {rel}")
                continue
            voice, espeak_voice, label = voice_for(lang)
            piper_args = tuple(PIPER_ARGS + LANG_ARGS.get(lang, []))
            voices_used[lang] = f"{os.path.basename(voice)} (espeak {espeak_voice}) {' '.join(piper_args)}"
            spoken = tts_text(card[lang], lang)
            h = hashlib.sha256("|".join([spoken, os.path.basename(voice), espeak_voice,
                                         " ".join(piper_args), FFMPEG_FILTER, bitrate]).encode()).hexdigest()[:16]
            card["audio"][lang] = rel
            card["audio_source"][lang] = label
            if not args.force and files.get(rel, {}).get("hash") == h and os.path.exists(mp3):
                skipped += 1
                continue
            jobs.setdefault((voice, espeak_voice, piper_args), []).append((spoken, mp3, rel, h))

    rendered = sum(len(batch) for batch in jobs.values())
    with tempfile.TemporaryDirectory() as tmp:
        for (voice, espeak_voice, piper_args), batch in jobs.items():  # one Piper voice at a time
            print(f"Synthesising {len(batch)} clip(s) with {os.path.basename(voice)} (espeak {espeak_voice}) ...")
            cfg = piper_config(voice, espeak_voice, tmp)
            for start in range(0, len(batch), 40):
                synthesize([(t, m) for t, m, _, _ in batch[start:start + 40]], piper_bin, voice, cfg, bitrate, tmp,
                           piper_args)
            for spoken, _, rel, h in batch:
                files[rel] = {"hash": h, "spoken_text": spoken}

    # Forget files of languages no longer in cards.json, and files that are gone.
    for rel in list(files):
        parts = rel.split("/")
        if len(parts) < 3 or parts[1] not in doc["languages"] or not os.path.exists(os.path.join(CONTENT, rel)):
            del files[rel]
    manifest.pop("voice", None)
    manifest.pop("espeak_voice", None)
    voices = {k: v for k, v in manifest.get("voices", {}).items() if k in doc["languages"]}
    voices.update(voices_used)
    manifest["voices"] = voices
    manifest["bitrate"] = bitrate
    manifest["note"] = ("Hash of the text actually spoken per file; make_audio.py skips files whose hash "
                        "is unchanged. Native recordings (audio_source 'native...') are never touched.")
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    new = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    if new != original:
        with open(CARDS, "w", encoding="utf-8") as f:
            f.write(new)

    total, count, per_lang = 0, 0, []
    for lang in doc["languages"]:
        paths = glob.glob(os.path.join(CONTENT, "audio", lang, "*.mp3"))
        size = sum(os.path.getsize(p) for p in paths)
        per_lang.append(f"{lang}: {len(paths)} files, {size / 1e6:.2f} MB")
        total += size
        count += len(paths)
    print(f"rendered {rendered}, unchanged {skipped}, native kept {kept_native}; "
          f"{count} MP3 files, {total / 1e6:.2f} MB total ({'; '.join(per_lang)})")


if __name__ == "__main__":
    main()
