"""SMS routing (PLAN.md section 7)."""
import json

from conftest import card_ids, register, sms, ymd


def test_unregistered_sender_gets_only_registration_card(client, conn):
    r = sms(client, "+529990000001", "PRECIO")
    assert card_ids(r) == ["sms_no_registrado"]
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM officer_messages").fetchone()[0] == 0


def test_precio_keyword_variants(client, env):
    register(client)
    prices = json.loads((env / "prices.json").read_text())
    for body in ["PRECIO", "precio", "Precios", "¿Precio?", " precio. ", "PRÉCIO"]:
        r = sms(client, "+529670001000", body)
        assert card_ids(r) == ["sms_precio"], body
        rep = r["replies"][0]
        assert prices["sms_fuente"] in rep["body"] and prices["sms_fecha"] in rep["body"]
        assert "{" not in rep["body"]
        assert rep["length"] <= 160 and rep["segments"] == 1, rep


def test_precio_without_price_table(client, monkeypatch, env):
    monkeypatch.setenv("CAFETAL_PRICES", str(env / "missing.json"))
    register(client)
    assert card_ids(sms(client, "+529670001000", "PRECIO")) == ["sms_precio_sin_datos"]


def test_intents_route_to_the_right_card(client, conn):
    register(client)
    cases = {
        "q precio tiene el cafe": "sms_precio",
        "cuanto pagan x kilo": "sms_precio",
        "mi cafe tiene manchas amarillas": "sms_reporte_instrucciones",
        "como funciona esto": "sms_ayuda",
        "AYUDA": "sms_ayuda",
        "kiero hablar con el ingeniero": "sms_pasar_tecnico",
        "TECNICO": "sms_pasar_tecnico",
    }
    for body, card in cases.items():
        assert card_ids(sms(client, "+529670001000", body)) == [card], body
    fwd = [r[0] for r in conn.execute("SELECT body FROM officer_messages ORDER BY id")]
    assert fwd == ["kiero hablar con el ingeniero", "TECNICO"]


def test_unknown_text_goes_to_officer(client, conn):
    register(client)
    for body in ["pon la radio por favor", "zzqx wvb"]:
        r = sms(client, "+529670001000", body)
        assert card_ids(r) == ["sms_pasar_tecnico"], body
        assert any(a["type"] == "forwarded_to_officer" for a in r["actions"])
    assert conn.execute("SELECT COUNT(*) FROM officer_messages").fetchone()[0] == 2


def test_valid_code_stores_observation_and_dedupes(client, conn):
    m = register(client)
    body = f"CAF1 {m['member_id']} MINA 77 {ymd(1)} 16.91,-92.11 #AB12"
    r = sms(client, m["phone"], body)
    assert card_ids(r) == ["sms_obs_recibida"]
    assert r["actions"][0] == {"type": "observation_stored", "obs_uid": f"{m['member_id']}-AB12", "code": "MINA",
                               "conf": 77}
    r2 = sms(client, m["phone"], body)
    assert r2["actions"][0]["type"] == "observation_duplicate"
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 1


def test_dash_location_uses_plot(client, conn):
    m = register(client, lat=16.905, lon=-92.123)
    sms(client, m["phone"], f"CAF1 {m['member_id']} SANO 90 {ymd()} - #PL01")
    row = conn.execute("SELECT lat, lon, loc_source FROM observations").fetchone()
    assert tuple(row) == (16.905, -92.123, "plot")


def test_invalid_code_reply(client, conn):
    m = register(client)
    r = sms(client, m["phone"], f"CAF1 {m['member_id']} ROYA 87 20261399 16.91,-92.11 #AB12")
    assert card_ids(r) == ["sms_codigo_invalido"]
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0


def test_code_for_another_member_from_registered_phone_is_rejected(client, conn):
    a = register(client, phone="+529670001000")
    b = register(client, name="Otra", phone="+529670001001")
    r = sms(client, a["phone"], f"CAF1 {b['member_id']} ROYA 87 {ymd()} 16.91,-92.11 #AB12")
    assert card_ids(r) == ["sms_codigo_invalido"]
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0


def test_code_from_family_phone_is_accepted_for_existing_member(client, conn):
    m = register(client)
    r = sms(client, "+529990000002", f"CAF1 {m['member_id']} ROYA 87 {ymd()} 16.91,-92.11 #FAM1")
    assert card_ids(r) == ["sms_obs_recibida"]
    r = sms(client, "+529990000002", f"CAF1 M9999 ROYA 87 {ymd()} 16.91,-92.11 #FAM2")
    assert card_ids(r) == ["sms_no_registrado"]
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 1


def test_simulated_send_by_member_id(client):
    m = register(client)
    r = client.post("/api/sms/inbound", json={"member_id": m["member_id"], "body": "PRECIO"})
    assert r.status_code == 200 and card_ids(r.json()) == ["sms_precio"]
    assert r.json()["replies"][0]["to"] == m["phone"]
    assert client.post("/api/sms/inbound", json={"member_id": "M9999", "body": "PRECIO"}).status_code == 404
    assert client.post("/api/sms/inbound", json={"body": "PRECIO"}).status_code == 400


def test_reply_in_member_language(client):
    m = register(client, language="tzh")
    from hub import cards
    r = sms(client, m["phone"], "AYUDA")
    assert r["replies"][0]["lang"] == "tzh" and r["replies"][0]["body"] == cards.get("sms_ayuda")["tzh"]


def test_thread_shows_conversation(client):
    m = register(client)
    sms(client, m["phone"], "PRECIO")
    t = client.get("/api/sms/thread", params={"phone": m["phone"]}).json()
    assert [x["direction"] for x in t["messages"]] == ["in", "out"]
    assert t["member"]["member_id"] == m["member_id"]
