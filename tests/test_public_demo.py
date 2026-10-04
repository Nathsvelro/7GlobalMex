"""Public online DEMO copy (CAFETAL_PUBLIC_DEMO=1, set by render.yaml): the hub says so, content edits answer 403,
and the DEMO itself (reset, SMS) still works."""
import io
import json
import wave

from hub import db
from conftest import card_ids, sms, ymd


def test_public_demo_is_off_by_default(client, monkeypatch):
    monkeypatch.delenv("CAFETAL_PUBLIC_DEMO", raising=False)
    assert client.get("/api/health").json()["public_demo"] is False
    assert client.get("/api/summary").json()["public_demo"] is False
    for value in ("", "0", "false", "FALSE", "No"):
        monkeypatch.setenv("CAFETAL_PUBLIC_DEMO", value)
        assert db.public_demo() is False, value
    monkeypatch.setenv("CAFETAL_PUBLIC_DEMO", "1")
    assert client.get("/api/health").json()["public_demo"] is True
    assert client.get("/api/summary").json()["public_demo"] is True


def test_public_demo_refuses_content_edits(client, env, monkeypatch):
    monkeypatch.setenv("CAFETAL_PUBLIC_DEMO", "1")
    path = env / "content" / "cards.json"

    def card():
        return next(c for c in json.loads(path.read_text(encoding="utf-8"))["cards"] if c["id"] == "diag_roya")

    before = card()
    r = client.post("/api/cards/diag_roya/verify", json={"lang": "en", "reviewer": "Officer Wanjiru (extension)"})
    assert r.status_code == 403 and "public online demo" in r.json()["detail"]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x01" * 8000)
    r = client.post("/api/cards/diag_roya/audio/kik", data={"speaker": "Wambui (native speaker)"},
                    files={"file": ("rec.wav", buf.getvalue(), "audio/wav")})
    assert r.status_code == 403 and "public online demo" in r.json()["detail"]
    assert card() == before
    assert not (env / "content" / "audio").exists()   # no recording was saved


def test_public_demo_keeps_reset_and_sms(client, monkeypatch):
    monkeypatch.setenv("CAFETAL_PUBLIC_DEMO", "1")
    r = client.post("/api/demo/reset")
    assert r.status_code == 200 and r.json()["members"] > 0
    assert card_ids(sms(client, "+254700000123", "PRICE")) == ["sms_precio"]   # Noor, from the DEMO data
    # the phone app's "Send (SIMULATED)" button sends by member id
    r = client.post("/api/sms/inbound",
                    json={"member_id": "M0123", "body": f"CAF1 M0123 RUST 99 {ymd()} -0.52,37.32 #K3F9"})
    assert r.status_code == 200 and card_ids(r.json())[0] == "sms_obs_recibida"
