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
  python3 scripts/make_audio.py --only diag_roya --lang tzh

Voices (one per language):
  es   Spanish Piper voice, phonemes with espeak-ng es-419
  tzh  the same Spanish voice reading a respelled Tseltal text (provisional, until native recordings)
  en   English Piper voice (en-us-lessac-medium), phonemes with the voice's own espeak voice (en-us)

Environment:
  PIPER_BIN      default /home/user/tools/piper/piper
  PIPER_VOICE    Spanish voice (es, tzh); default: first .onnx in /home/user/tools/voice-es/
  PIPER_VOICE_EN English voice (en); default: first .onnx in /home/user/tools/voice-en/
  PIPER_ESPEAK   espeak-ng voice for es/tzh (default es-419, Latin-American Spanish:
                 "c/z" said as "s", as in Mexico). Not used for English.
  AUDIO_BITRATE  default 24k (keeps all audio small; the source voices are 16-22 kHz)
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
SOURCE_LABEL = {
    "es": "synthetic:piper-es-mls_10246-low",
    "tzh": "synthetic-provisional:piper-es-voice-reading-tseltal",
}  # en: "synthetic:piper-<voice name>", e.g. synthetic:piper-en-us-lessac-medium (see voice_for)
# Piper settings. noise_w 0.4 gives steadier timing than the default 0.8 with this voice.
PIPER_ARGS = ["--noise_w", "0.4", "--sentence_silence", "0.3"]
# The English voice speaks fast (~200+ words/min); length_scale 1.4 gives ~170, about the pace of the Spanish audio.
LANG_ARGS = {"en": ["--length_scale", "1.4"]}
# Squeeze long pauses the low-quality voice sometimes inserts; trim leading silence.
FFMPEG_FILTER = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05:"
                 "stop_periods=-1:stop_duration=0.35:stop_threshold=-45dB:stop_silence=0.3")

# Ids every part of the system relies on (PLAN.md section 11).
REQUIRED_IDS = """
ui_app_name ui_choose_language ui_consent_title ui_consent_text ui_consent_accept ui_consent_decline
ui_member_id_prompt ui_pin_optional ui_pin_prompt ui_continue ui_take_photo ui_photo_tip_underside
ui_analyzing ui_confidence ui_play_tzh ui_play_es ui_play_en ui_send_sms ui_simulate_send ui_saved ui_history
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
DUDA = {"es": "No estoy seguro — muestre la hoja al técnico.",
        "en": "I'm not sure — show the leaf to the extension officer."}

# Worst-case-ish slot values used to check that every SMS fits in one message.
SAMPLE_SLOTS = {
    "precio_cafe": "100.50", "unidad_cafe": "MXN/kg", "precio_maiz": "10.25",
    "precio_frijol": "25.50", "fecha": "2026-09-30", "comunidad": "San Juan Cancuc Centro",
    "n_reportes": "12",
}
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
            return json.load(f).get("sms_fuente") or "SNIIM; ICE NY + Banxico"
    except (OSError, ValueError):
        return "SNIIM; ICE NY + Banxico"


# ---------------------------------------------------------------- validation
def check(doc):
    problems = []
    langs = list(doc.get("languages", {}))
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
SPOKEN_WORDS = {"SMS": "ese eme ese", "PIN": "pin", "Wi-Fi": "wifi", "WiFi": "wifi", "app": "ap"}
SPOKEN_WORDS_EN = {"SMS": "S M S", "PIN": "pin", "M0123": "M 0 1 2 3"}


def tts_text(text, lang):
    """Turn card text into something the Piper voice reads well (audio only; the
    card text itself is never changed)."""
    t = text
    for a, b in (SPOKEN_WORDS_EN if lang == "en" else SPOKEN_WORDS).items():
        t = re.sub(r"(?<!\w)" + re.escape(a) + r"(?!\w)", b, t)
    t = t.replace("PIN", "pin")  # also inside "aPIN" (Tseltal: "your PIN")
    t = re.sub(r"\b([A-ZÁÉÍÓÚÑ]{2,})\b", lambda m: m.group(1).lower(), t)  # DEMO -> demo (not spelled)
    t = t.replace("—", ", ").replace("–", ", ").replace("…", ".")
    t = re.sub(r"[«»\"“”]", "", t)
    t = re.sub(r"[()]", ", ", t).replace("/", " ")
    if lang == "tzh":
        # Rough respelling so a Spanish voice can say Tseltal (provisional audio only):
        t = t.replace("'", "").replace("’", "")       # glottal stop: not in Spanish
        t = t.replace("x", "sh")                       # Tseltal x = "sh"
        t = re.sub(r"(?<![\wáéíóú])j(?=[bcdfgklmnpqrstvwyz])", "", t, flags=re.I)  # initial j+consonant
        t = re.sub(r"(?<![\wáéíóú])ts(?=[aeiouáéíóú])", "s", t, flags=re.I)          # initial ts
    t = re.sub(r"\s+([,.;:?!])", r"\1", t)
    t = re.sub(r",(\s*,)+", ",", t)
    t = re.sub(r",\s*([.;:?!])", r"\1", t)
    t = re.sub(r",(?=\S)", ", ", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" ,")
    return t


# ---------------------------------------------------------------- synthesis
def find_voice(env="PIPER_VOICE", folder="/home/user/tools/voice-es"):
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


_VOICES = {}


def voice_for(lang):
    """(voice .onnx path, espeak voice, audio_source label) for one language. es and tzh share the Spanish
    voice (tzh is provisional); en has its own English voice."""
    key = "en" if lang == "en" else "es"
    if key not in _VOICES:
        if key == "en":
            voice = find_voice("PIPER_VOICE_EN", "/home/user/tools/voice-en")
            name = os.path.basename(voice)
            name = name[:-len(".onnx")] if name.endswith(".onnx") else name
            _VOICES[key] = (voice, voice_espeak(voice, "en-us"), f"synthetic:piper-{name}")
        else:
            _VOICES[key] = (find_voice(), os.environ.get("PIPER_ESPEAK", "es-419"), "synthetic:piper")
    voice, espeak, label = _VOICES[key]
    return voice, espeak, SOURCE_LABEL.get(lang, label)


def piper_config(voice, espeak_voice, tmpdir):
    """Copy the voice config with the chosen espeak voice (es-419 for Spanish: Mexican-style 's')."""
    with open(voice + ".json", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.setdefault("espeak", {})["voice"] = espeak_voice
    path = os.path.join(tmpdir, os.path.basename(voice) + ".json")
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

    manifest.pop("voice", None)
    manifest.pop("espeak_voice", None)
    manifest.setdefault("voices", {}).update(voices_used)
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
