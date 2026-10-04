"""Every outbound SMS is a cards.json template with only its slots filled; content review endpoints; static files."""
import io
import json
import mimetypes
import re
import shutil
import wave

import pytest

from hub import cards
from conftest import register, sms, ymd

LANGS = ["en", "sw", "kik"]


def template_regex(template: str) -> re.Pattern:
    parts = re.split(r"(\{\w+\})", template)
    return re.compile("".join("(?P<%s>.+?)" % p[1:-1] if re.fullmatch(r"\{\w+\}", p) else re.escape(p)
                              for p in parts) + r"\Z", re.DOTALL)


def test_every_outbound_message_is_a_card_template(client, conn):
    client.post("/api/demo/reset")
    sw = register(client, name="Kiswahili", phone="+254700007000", language="sw")
    kik = register(client, name="Gikuyu", phone="+254700007001", language="kik")
    for body in ["PRICE", "BEI", "how much is cherry today", "my leaves have yellow spots", "how does this work",
                 "hello", "i want to talk to the officer", "CAF1 M0123 RUST 87 20200101 -0.52,37.32 #BAD1", "HELP",
                 "MSAADA", "OFFICER", "AFISA", "majani yana madoa ya njano"]:
        sms(client, "+254700000123", body)
        sms(client, sw["phone"], body)
        sms(client, kik["phone"], body)
    sms(client, "+254799000003", "hello")
    sms(client, "+254700000123", f"CAF1 M0123 RUST 99 {ymd()} -0.52,37.32 #K3F9")   # triggers the alert
    out = [dict(r) for r in conn.execute("SELECT * FROM messages WHERE direction = 'out'")]
    assert len(out) > 40 and any(m["card_id"] == "alert_roya" for m in out)
    assert {m["lang"] for m in out} == set(LANGS)
    for lang in LANGS:
        assert any(m["card_id"] == "alert_roya" and m["lang"] == lang for m in out), lang
    for m in out:
        card = cards.get(m["card_id"])
        assert card is not None, m
        match = template_regex(card[m["lang"]]).match(m["body"])
        assert match, (m["card_id"], m["lang"], m["body"])
        for name, value in match.groupdict().items():
            assert name in card["slots"] and cards.SLOT_VALUE_RE.match(value), (name, value)
        info = cards.sms_length(m["body"])
        assert info["encoding"] == "GSM-7" and info["segments"] == 1, (m["card_id"], m["lang"], info)


def test_cards_complete_in_every_language():
    """content/cards.json passes scripts/make_audio.py --check (ids, slots, one GSM-7 SMS per language) and has
    English, Kiswahili and Gikuyu everywhere: text, status, reviewed_by entry, audio file for every spoken card.
    No Spanish or Tseltal is left."""
    import importlib.util
    from conftest import ROOT
    spec = importlib.util.spec_from_file_location("make_audio", ROOT / "scripts" / "make_audio.py")
    make_audio = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(make_audio)
    doc = json.loads((ROOT / "content" / "cards.json").read_text(encoding="utf-8"))
    assert make_audio.check(doc) == []
    assert doc["languages"] == {"en": "English", "sw": "Kiswahili", "kik": "Gĩkũyũ"}
    by_id = {c["id"]: c for c in doc["cards"]}
    assert by_id["diag_duda"]["en"] == "I'm not sure — show the leaf to the extension officer."
    assert by_id["ui_play_en"]["en"] == "Listen in English"
    assert {"ui_play_sw", "ui_play_kik"} <= set(by_id) and not {"ui_play_es", "ui_play_tzh"} & set(by_id)
    for c in doc["cards"]:
        for field in ("status", "reviewed_by", "audio", "audio_source"):
            assert not {"es", "tzh"} & set(c.get(field) or {}), (c["id"], field)
        assert "es" not in c and "tzh" not in c, c["id"]
        for lang in LANGS:
            assert c[lang].strip() and c["status"][lang] in ("unverified", "verified"), (c["id"], lang)
            assert lang in c["reviewed_by"], (c["id"], lang)
            assert set(re.findall(r"\{(\w+)\}", c[lang])) == set(re.findall(r"\{(\w+)\}", c["en"])), (c["id"], lang)
            if c["type"] in ("sms", "alert"):
                assert c[lang].isascii() and c["audio"] == {}, (c["id"], lang)
            else:
                assert c["audio"][lang] == f"audio/{lang}/{c['id']}.mp3", (c["id"], lang)
                assert (ROOT / "content" / c["audio"][lang]).stat().st_size > 1000, (c["id"], lang)
                src = c["audio_source"][lang]
                expected = "synthetic:piper-en-us-lessac-medium" if lang == "en" else "synthetic-provisional:"
                assert src.startswith(expected) or src.startswith("native:"), (c["id"], lang, src)


def test_render_rejects_free_text_in_slots(env):
    with pytest.raises(cards.CardError):
        cards.render("alert_roya", "en", comunidad="Ondera {x}", n_reportes="3")
    with pytest.raises(cards.CardError):
        cards.render("alert_roya", "en", comunidad="Ondera Juu")          # slot left empty
    with pytest.raises(cards.CardError):
        cards.render("sms_ayuda", "en", fuente="x")                       # undeclared slot
    text, lang = cards.render("alert_roya", "en", comunidad="Ondera Juu", n_reportes="3")
    assert "Ondera Juu" in text and "3" in text and lang == "en"
    text, lang = cards.render("alert_roya", "kik", comunidad="Ondera Juu", n_reportes="3")
    assert "Ondera Juu" in text and lang == "kik"
    assert cards.render("sms_ayuda")[1] == "en"                                # English is the default


def test_sms_length():
    assert cards.sms_length("a" * 160) == {"length": 160, "encoding": "GSM-7", "segments": 1}
    assert cards.sms_length("a" * 161)["segments"] == 2
    assert cards.sms_length("€")["length"] == 2
    assert cards.sms_length("ĩ" * 70) == {"length": 70, "encoding": "UCS-2", "segments": 1}


def test_verify_card(client, env):
    assert client.post("/api/cards/diag_roya/verify", json={"lang": "en", "reviewer": ""}).status_code == 400
    r = client.post("/api/cards/diag_roya/verify", json={"lang": "en", "reviewer": "Officer Wanjiru (extension)"})
    assert r.status_code == 200 and r.json()["status"]["en"] == "verified"
    saved = json.loads((env / "content" / "cards.json").read_text())
    card = next(c for c in saved["cards"] if c["id"] == "diag_roya")
    assert card["status"] == {"en": "verified", "sw": "unverified", "kik": "unverified"}
    assert card["reviewed_by"]["en"].startswith("Officer Wanjiru (extension) (")
    r = client.post("/api/cards/diag_roya/verify", json={"lang": "en", "verified": False})
    assert r.json()["status"]["en"] == "unverified" and r.json()["reviewed_by"]["en"] is None
    assert client.post("/api/cards/nope/verify", json={"lang": "en", "reviewer": "x"}).status_code == 404
    assert client.post("/api/cards/diag_roya/verify", json={"lang": "xx", "reviewer": "x"}).status_code == 400
    assert client.post("/api/cards/diag_roya/verify", json={"lang": "es", "reviewer": "x"}).status_code == 400
    r = client.post("/api/cards/diag_roya/verify", json={"lang": "kik", "reviewer": "Gikuyu speaker (DEMO)"})
    assert r.status_code == 200 and r.json()["status"] == {"en": "unverified", "sw": "unverified", "kik": "verified"}
    assert r.json()["reviewed_by"]["kik"].startswith("Gikuyu speaker (DEMO) (")


def test_upload_native_audio(client, env):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x01" * 8000)
    r = client.post("/api/cards/diag_roya/audio/kik", data={"speaker": "Wambui (native speaker)"},
                    files={"file": ("rec.wav", buf.getvalue(), "audio/wav")})
    assert r.status_code == 200, r.text
    j = r.json()
    ext = "mp3" if shutil.which("ffmpeg") else "wav"
    assert j["path"] == f"audio/kik/diag_roya.{ext}"
    assert (env / "content" / "audio" / "kik" / f"diag_roya.{ext}").stat().st_size > 100
    card = cards.get("diag_roya")
    assert card["audio_source"]["kik"] == "native:Wambui (native speaker)" and card["status"]["kik"] == "unverified"
    assert client.post("/api/cards/diag_roya/audio/kik", data={"speaker": "x"},
                       files={"file": ("a.txt", b"x" * 200, "text/plain")}).status_code == 400
    for lang in ("fr", "es", "tzh"):
        assert client.post(f"/api/cards/diag_roya/audio/{lang}", data={"speaker": "x"},
                           files={"file": ("a.wav", buf.getvalue(), "audio/wav")}).status_code == 400, lang
    r = client.post("/api/cards/diag_roya/audio/sw", data={"speaker": "Achieng (Kiswahili speaker)"},
                    files={"file": ("rec.wav", buf.getvalue(), "audio/wav")})
    assert r.status_code == 200 and r.json()["path"] == f"audio/sw/diag_roya.{ext}"
    card = cards.get("diag_roya")
    assert card["audio_source"]["sw"] == "native:Achieng (Kiswahili speaker)" and card["status"]["sw"] == "unverified"
    assert card["audio_source"]["kik"] == "native:Wambui (native speaker)"


def test_static_and_mime(client):
    import hub.main  # noqa: F401  (registers the MIME types)
    assert mimetypes.guess_type("x.wasm")[0] == "application/wasm"
    assert mimetypes.guess_type("x.mjs")[0] == "text/javascript"
    assert mimetypes.guess_type("x.webmanifest")[0] == "application/manifest+json"
    assert mimetypes.guess_type("x.onnx")[0] == "application/octet-stream"
    assert client.get("/api/health").json()["ok"] is True
    r = client.get("/")
    assert r.status_code == 200 and "Co-op hub" in r.text and 'lang="en"' in r.text
    r = client.get("/hub/style.css")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"
    r = client.get("/app/model/labels.json")
    assert r.status_code == 200 and r.json()["threshold"] > 0
    assert client.get("/app/model/cafetal.onnx").headers["content-type"] == "application/octet-stream"
    assert client.get("/app", follow_redirects=False).status_code in (307, 308)


def test_hub_pages_are_english(client):
    """Staff and officer pages: English UI, no Spanish left (Kenya re-localization)."""
    spanish = re.compile(r"\b(socio|socios|técnico|tecnico|bandeja|aviso|avisos|precio|reporte|enviar|guardar|"
                         r"aprobar|rechazar|cargando|idioma|comunidad|parcela|roya|duda)\b", re.IGNORECASE)
    for page in ("index.html", "registro.html", "simulador.html", "bandeja.html", "mapa.html", "tecnico.html",
                 "contenido.html", "common.js"):
        r = client.get(f"/hub/{page}")
        assert r.status_code == 200, page
        # file names, in-page anchors and internal model labels stay as they were (other pages, tests and the
        # model use them; they are never shown as text)
        text = re.sub(r"(registro|simulador|bandeja|mapa|tecnico|contenido)\.html|#(mensajes|etiquetas)|"
                      r"id=\"(mensajes|etiquetas)\"|\[\"(roya|minador|phoma|cercospora|acaro_rojo|sano|otro)\",",
                      "", r.text)
        assert not spanish.findall(text), (page, sorted(set(spanish.findall(text)))[:10])
        if page.endswith(".html"):
            assert '<html lang="en">' in r.text, page


def test_no_api_docs_pages(client):
    # FastAPI's /docs and /redoc load Swagger UI / ReDoc from a CDN and give a console for every endpoint: off.
    for path in ("/docs", "/redoc", "/openapi.json"):
        r = client.get(path)
        assert r.status_code == 404 and "cdn.jsdelivr" not in r.text, path


def test_accented_community_keeps_alert_in_one_gsm_sms(client):
    ms = [register(client, name=f"K{i}", phone=f"+25470000600{i}", community="Ondera Kĩlĩma", lat=lat, lon=lon,
                   language=lang)
          for i, ((lat, lon), lang) in enumerate(zip([(-0.47, 37.22), (-0.46, 37.23), (-0.47, 37.23)], LANGS))]
    for i, m in enumerate(ms):
        sms(client, m["phone"], f"CAF1 {m['member_id']} RUST 92 {ymd()} {m['lat']},{m['lon']} #KI0{i}")
    out = client.get("/api/outbox", params={"status": "pending_approval"}).json()["messages"]
    assert len(out) == 3 and {m["lang"] for m in out} == set(LANGS)
    for m in out:
        assert "Ondera Kilima" in m["body"] and m["encoding"] == "GSM-7" and m["segments"] == 1, m
    bad = client.post("/api/members", json={"name": "X", "phone": "+254700006099", "community": "Ondera {x}",
                                            "consent": True, "consent_by": "Ann"})
    assert bad.status_code == 400
