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


def template_regex(template: str) -> re.Pattern:
    parts = re.split(r"(\{\w+\})", template)
    return re.compile("".join("(?P<%s>.+?)" % p[1:-1] if re.fullmatch(r"\{\w+\}", p) else re.escape(p)
                              for p in parts) + r"\Z", re.DOTALL)


def test_every_outbound_message_is_a_card_template(client, conn):
    client.post("/api/demo/reset")
    tz = register(client, name="Tseltal", phone="+529670007000", language="tzh")
    en = register(client, name="English", phone="+529670007001", language="en")
    for body in ["PRECIO", "q precio tiene el cafe", "mi cafe tiene manchas amarillas", "como funciona", "hola",
                 "kiero hablar con el ingeniero", "CAF1 M0123 ROYA 87 20200101 16.91,-92.11 #BAD1", "PRICE", "HELP"]:
        sms(client, "+529670000123", body)
        sms(client, tz["phone"], body)
        sms(client, en["phone"], body)
    sms(client, "+529990000003", "hola")
    sms(client, "+529670000123", f"CAF1 M0123 ROYA 96 {ymd()} 16.91,-92.11 #K3F9")   # triggers the alert
    out = [dict(r) for r in conn.execute("SELECT * FROM messages WHERE direction = 'out'")]
    assert len(out) > 40 and any(m["card_id"] == "alert_roya" for m in out)
    assert {m["lang"] for m in out} == {"es", "tzh", "en"}
    assert any(m["card_id"] == "alert_roya" and m["lang"] == "en" for m in out)
    for m in out:
        card = cards.get(m["card_id"])
        assert card is not None, m
        match = template_regex(card[m["lang"]]).match(m["body"])
        assert match, (m["card_id"], m["lang"], m["body"])
        for name, value in match.groupdict().items():
            assert name in card["slots"] and cards.SLOT_VALUE_RE.match(value), (name, value)
        info = cards.sms_length(m["body"])
        assert info["segments"] == 1, (m["card_id"], m["lang"], info)


def test_cards_complete_in_every_language():
    """content/cards.json passes scripts/make_audio.py --check (ids, slots, one GSM-7 SMS per language) and has
    English everywhere: text, UNVERIFIED status, reviewed_by entry, audio file for every spoken card."""
    import importlib.util
    from conftest import ROOT
    spec = importlib.util.spec_from_file_location("make_audio", ROOT / "scripts" / "make_audio.py")
    make_audio = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(make_audio)
    doc = json.loads((ROOT / "content" / "cards.json").read_text(encoding="utf-8"))
    assert make_audio.check(doc) == []
    assert doc["languages"] == {"es": "Español", "tzh": "Bats'il k'op (Tseltal)", "en": "English"}
    by_id = {c["id"]: c for c in doc["cards"]}
    assert by_id["diag_duda"]["en"] == "I'm not sure — show the leaf to the extension officer."
    assert by_id["ui_play_en"]["en"] == "Listen in English" and by_id["ui_play_en"]["es"] == "Escuchar en inglés"
    for c in doc["cards"]:
        assert c["en"].strip() and c["status"]["en"] in ("unverified", "verified"), c["id"]
        assert "en" in c["reviewed_by"], c["id"]
        assert set(re.findall(r"\{(\w+)\}", c["en"])) == set(re.findall(r"\{(\w+)\}", c["es"])), c["id"]
        if c["type"] in ("sms", "alert"):
            assert c["en"].isascii() and c["audio"] == {}, c["id"]
        else:
            assert c["audio"]["en"] == f"audio/en/{c['id']}.mp3", c["id"]
            assert (ROOT / "content" / c["audio"]["en"]).stat().st_size > 1000, c["id"]
            src = c["audio_source"]["en"]
            assert src == "synthetic:piper-en-us-lessac-medium" or src.startswith("native:"), c["id"]


def test_render_rejects_free_text_in_slots(env):
    with pytest.raises(cards.CardError):
        cards.render("alert_roya", "es", comunidad="Ondera {x}", n_reportes="3")
    with pytest.raises(cards.CardError):
        cards.render("alert_roya", "es", comunidad="Ondera Alto")          # slot left empty
    with pytest.raises(cards.CardError):
        cards.render("sms_ayuda", "es", fuente="x")                        # undeclared slot
    text, lang = cards.render("alert_roya", "es", comunidad="Ondera Alto", n_reportes="3")
    assert "Ondera Alto" in text and "3" in text and lang == "es"


def test_sms_length():
    assert cards.sms_length("a" * 160) == {"length": 160, "encoding": "GSM-7", "segments": 1}
    assert cards.sms_length("a" * 161)["segments"] == 2
    assert cards.sms_length("€")["length"] == 2
    assert cards.sms_length("á" * 70) == {"length": 70, "encoding": "UCS-2", "segments": 1}


def test_verify_card(client, env):
    assert client.post("/api/cards/diag_roya/verify", json={"lang": "es", "reviewer": ""}).status_code == 400
    r = client.post("/api/cards/diag_roya/verify", json={"lang": "es", "reviewer": "Ing. Pérez (técnico)"})
    assert r.status_code == 200 and r.json()["status"]["es"] == "verified"
    saved = json.loads((env / "content" / "cards.json").read_text())
    card = next(c for c in saved["cards"] if c["id"] == "diag_roya")
    assert card["status"] == {"es": "verified", "tzh": "unverified", "en": "unverified"}
    assert card["reviewed_by"]["es"].startswith("Ing. Pérez (técnico) (")
    r = client.post("/api/cards/diag_roya/verify", json={"lang": "es", "verified": False})
    assert r.json()["status"]["es"] == "unverified" and r.json()["reviewed_by"]["es"] is None
    assert client.post("/api/cards/nope/verify", json={"lang": "es", "reviewer": "x"}).status_code == 404
    assert client.post("/api/cards/diag_roya/verify", json={"lang": "xx", "reviewer": "x"}).status_code == 400
    r = client.post("/api/cards/diag_roya/verify", json={"lang": "en", "reviewer": "Visiting judge"})
    assert r.status_code == 200 and r.json()["status"] == {"es": "unverified", "tzh": "unverified", "en": "verified"}
    assert r.json()["reviewed_by"]["en"].startswith("Visiting judge (")


def test_upload_native_audio(client, env):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x01" * 8000)
    r = client.post("/api/cards/diag_roya/audio/tzh", data={"speaker": "Juana (hablante nativa)"},
                    files={"file": ("rec.wav", buf.getvalue(), "audio/wav")})
    assert r.status_code == 200, r.text
    j = r.json()
    ext = "mp3" if shutil.which("ffmpeg") else "wav"
    assert j["path"] == f"audio/tzh/diag_roya.{ext}"
    assert (env / "content" / "audio" / "tzh" / f"diag_roya.{ext}").stat().st_size > 100
    card = cards.get("diag_roya")
    assert card["audio_source"]["tzh"] == "native:Juana (hablante nativa)" and card["status"]["tzh"] == "unverified"
    assert client.post("/api/cards/diag_roya/audio/tzh", data={"speaker": "x"},
                       files={"file": ("a.txt", b"x" * 200, "text/plain")}).status_code == 400
    assert client.post("/api/cards/diag_roya/audio/fr", data={"speaker": "x"},
                       files={"file": ("a.wav", buf.getvalue(), "audio/wav")}).status_code == 400
    r = client.post("/api/cards/diag_roya/audio/en", data={"speaker": "Ann (English speaker)"},
                    files={"file": ("rec.wav", buf.getvalue(), "audio/wav")})
    assert r.status_code == 200 and r.json()["path"] == f"audio/en/diag_roya.{ext}"
    card = cards.get("diag_roya")
    assert card["audio_source"]["en"] == "native:Ann (English speaker)" and card["status"]["en"] == "unverified"
    assert card["audio_source"]["tzh"] == "native:Juana (hablante nativa)"


def test_static_and_mime(client):
    import hub.main  # noqa: F401  (registers the MIME types)
    assert mimetypes.guess_type("x.wasm")[0] == "application/wasm"
    assert mimetypes.guess_type("x.mjs")[0] == "text/javascript"
    assert mimetypes.guess_type("x.webmanifest")[0] == "application/manifest+json"
    assert mimetypes.guess_type("x.onnx")[0] == "application/octet-stream"
    assert client.get("/api/health").json()["ok"] is True
    r = client.get("/")
    assert r.status_code == 200 and "Hub de la cooperativa" in r.text
    r = client.get("/hub/style.css")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"
    r = client.get("/app/model/labels.json")
    assert r.status_code == 200 and r.json()["threshold"] > 0
    assert client.get("/app/model/cafetal.onnx").headers["content-type"] == "application/octet-stream"
    assert client.get("/app", follow_redirects=False).status_code in (307, 308)


def test_no_api_docs_pages(client):
    # FastAPI's /docs and /redoc load Swagger UI / ReDoc from a CDN and give a console for every endpoint: off.
    for path in ("/docs", "/redoc", "/openapi.json"):
        r = client.get(path)
        assert r.status_code == 404 and "cdn.jsdelivr" not in r.text, path


def test_accented_community_keeps_alert_in_one_gsm_sms(client):
    ms = [register(client, name=f"R{i}", phone=f"+52967000600{i}", community="Ondera Río", lat=lat, lon=lon)
          for i, (lat, lon) in enumerate([(16.96, -92.21), (16.97, -92.20), (16.96, -92.20)])]
    for i, m in enumerate(ms):
        sms(client, m["phone"], f"CAF1 {m['member_id']} ROYA 92 {ymd()} {m['lat']},{m['lon']} #RI0{i}")
    out = client.get("/api/outbox", params={"status": "pending_approval"}).json()["messages"]
    assert len(out) == 3
    for m in out:
        assert "Ondera Rio" in m["body"] and m["encoding"] == "GSM-7" and m["segments"] == 1, m
    bad = client.post("/api/members", json={"name": "X", "phone": "+529670006099", "community": "Ondera {x}",
                                            "consent": True, "consent_by": "Ana"})
    assert bad.status_code == 400
