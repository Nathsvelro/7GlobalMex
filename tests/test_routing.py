"""SMS routing (PLAN.md section 7)."""
import json

from conftest import card_ids, register, sms, ymd


def test_unregistered_sender_gets_only_registration_card(client, conn):
    r = sms(client, "+254799000001", "PRICE")
    assert card_ids(r) == ["sms_no_registrado"]
    assert r["replies"][0]["lang"] == "en"                       # unknown sender: English
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM officer_messages").fetchone()[0] == 0


def test_price_keyword_variants(client, env):
    register(client)
    prices = json.loads((env / "prices.json").read_text())
    coffee = next(i for i in prices["items"] if i["id"] == "coffee_cherry")
    for body in ["PRICE", "price", "Prices", "Price?", " price. ", "PRÍCE", "BEI", "bei!", "Bei."]:
        r = sms(client, "+254700001000", body)
        assert card_ids(r) == ["sms_precio"], body
        rep = r["replies"][0]
        assert prices["sms_fuente"] in rep["body"] and prices["sms_fecha"] in rep["body"]
        assert f"{coffee['price']:.2f}" in rep["body"] and "KES" in rep["body"]
        assert "{" not in rep["body"]
        assert rep["length"] <= 160 and rep["segments"] == 1, rep


def test_price_without_price_table(client, monkeypatch, env):
    monkeypatch.setenv("CAFETAL_PRICES", str(env / "missing.json"))
    register(client)
    assert card_ids(sms(client, "+254700001000", "PRICE")) == ["sms_precio_sin_datos"]
    assert card_ids(sms(client, "+254700001000", "BEI")) == ["sms_precio_sin_datos"]


def test_intents_route_to_the_right_card(client, conn):
    register(client)
    cases = {
        "how much is cherry today": "sms_precio",
        "bei ya mahindi leo": "sms_precio",
        "my leaves have yellow spots": "sms_reporte_instrucciones",
        "majani yana madoa ya njano": "sms_reporte_instrucciones",
        "how does this work": "sms_ayuda",
        "HELP": "sms_ayuda",
        "MSAADA": "sms_ayuda",
        "i want to talk to the officer please": "sms_pasar_tecnico",
        "OFFICER": "sms_pasar_tecnico",
        "Afisa": "sms_pasar_tecnico",
    }
    for body, card in cases.items():
        assert card_ids(sms(client, "+254700001000", body)) == [card], body
    fwd = [r[0] for r in conn.execute("SELECT body FROM officer_messages ORDER BY id")]
    assert fwd == [b for b, c in cases.items() if c in ("sms_reporte_instrucciones", "sms_pasar_tecnico")]


def test_old_spanish_keywords_are_not_keywords(client):
    register(client)
    for body in ["PRECIO", "AYUDA", "TECNICO"]:
        r = sms(client, "+254700001000", body)
        assert next(a for a in r["actions"] if a["type"] == "intent")["method"] == "classifier", body


def test_unknown_text_goes_to_officer(client, conn):
    register(client)
    for body in ["turn on the radio please", "zzqx wvb"]:
        r = sms(client, "+254700001000", body)
        assert card_ids(r) == ["sms_pasar_tecnico"], body
        assert any(a["type"] == "forwarded_to_officer" for a in r["actions"])
    assert conn.execute("SELECT COUNT(*) FROM officer_messages").fetchone()[0] == 2


def test_valid_code_stores_observation_and_dedupes(client, conn):
    m = register(client)
    body = f"CAF1 {m['member_id']} MINR 77 {ymd(1)} -0.52,37.32 #AB12"
    r = sms(client, m["phone"], body)
    assert card_ids(r) == ["sms_obs_recibida"]
    assert r["actions"][0] == {"type": "observation_stored", "obs_uid": f"{m['member_id']}-AB12", "code": "MINR",
                               "conf": 77}
    r2 = sms(client, m["phone"], body)
    assert r2["actions"][0]["type"] == "observation_duplicate"
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 1


def test_dash_location_uses_plot(client, conn):
    m = register(client, lat=-0.525, lon=37.307)
    sms(client, m["phone"], f"CAF1 {m['member_id']} HLTH 90 {ymd()} - #PL01")
    row = conn.execute("SELECT lat, lon, loc_source FROM observations").fetchone()
    assert tuple(row) == (-0.525, 37.307, "plot")


def test_invalid_code_reply(client, conn):
    m = register(client)
    r = sms(client, m["phone"], f"CAF1 {m['member_id']} RUST 87 20261399 -0.52,37.32 #AB12")
    assert card_ids(r) == ["sms_codigo_invalido"]
    r = sms(client, m["phone"], f"CAF1 {m['member_id']} ROYA 87 {ymd()} -0.52,37.32 #AB13")   # old Spanish code
    assert card_ids(r) == ["sms_codigo_invalido"]
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0


def test_code_for_another_member_from_registered_phone_is_rejected(client, conn):
    a = register(client, phone="+254700001000")
    b = register(client, name="Other", phone="+254700001001")
    r = sms(client, a["phone"], f"CAF1 {b['member_id']} RUST 87 {ymd()} -0.52,37.32 #AB12")
    assert card_ids(r) == ["sms_codigo_invalido"]
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0


def test_code_from_family_phone_is_accepted_for_existing_member(client, conn):
    m = register(client)
    r = sms(client, "+254799000002", f"CAF1 {m['member_id']} RUST 87 {ymd()} -0.52,37.32 #FAM1")
    assert card_ids(r) == ["sms_obs_recibida"]
    r = sms(client, "+254799000002", f"CAF1 M9999 RUST 87 {ymd()} -0.52,37.32 #FAM2")
    assert card_ids(r) == ["sms_no_registrado"]
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 1


def test_simulated_send_by_member_id(client):
    m = register(client)
    r = client.post("/api/sms/inbound", json={"member_id": m["member_id"], "body": "PRICE"})
    assert r.status_code == 200 and card_ids(r.json()) == ["sms_precio"]
    assert r.json()["replies"][0]["to"] == m["phone"]
    assert client.post("/api/sms/inbound", json={"member_id": "M9999", "body": "PRICE"}).status_code == 404
    assert client.post("/api/sms/inbound", json={"body": "PRICE"}).status_code == 400


def test_reply_in_member_language(client):
    from hub import cards
    kik = register(client, language="kik")
    r = sms(client, kik["phone"], "HELP")
    assert r["replies"][0]["lang"] == "kik" and r["replies"][0]["body"] == cards.get("sms_ayuda")["kik"]
    sw = register(client, name="Kiswahili", phone="+254700001001", language="sw")
    r = sms(client, sw["phone"], "MSAADA")
    assert r["replies"][0]["lang"] == "sw" and r["replies"][0]["body"] == cards.get("sms_ayuda")["sw"]


def test_reply_falls_back_to_english(client, env):
    from hub import cards
    m = register(client, language="sw")
    assert m["language"] == "sw"
    cases = {"MSAADA": "sms_ayuda", "HELP": "sms_ayuda", "bei": "sms_precio", "AFISA": "sms_pasar_tecnico"}
    for body, card_id in cases.items():
        rep = sms(client, m["phone"], body)["replies"][0]
        assert rep["card_id"] == card_id and rep["lang"] == "sw", body
        assert rep["encoding"] == "GSM-7" and rep["segments"] == 1, rep
    rep = sms(client, m["phone"], f"CAF1 {m['member_id']} RUST 87 {ymd()} -0.52,37.32 #SW01")["replies"][0]
    assert rep["card_id"] == "sms_obs_recibida" and rep["body"] == cards.get("sms_obs_recibida")["sw"]
    # a card without Kiswahili text falls back to English
    path = env / "content" / "cards.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    del next(c for c in doc["cards"] if c["id"] == "sms_ayuda")["sw"]
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    rep = sms(client, m["phone"], "MSAADA")["replies"][0]
    assert rep["lang"] == "en" and rep["body"] == cards.get("sms_ayuda")["en"]


def test_registration_languages(client):
    for i, lang in enumerate(["en", "sw", "kik"]):
        assert register(client, phone=f"+25470000800{i}", language=lang)["language"] == lang
    base = {"name": "X", "community": "Ondera Juu", "consent": True, "consent_by": "Ann"}
    for i, lang in enumerate(["es", "tzh", "fr"]):
        bad = client.post("/api/members", json={**base, "phone": f"+25470000801{i}", "language": lang})
        assert bad.status_code == 422, lang
    r = client.post("/api/members", json={**base, "phone": "+254700008020"})
    assert r.status_code == 201 and r.json()["language"] == "en"       # English is the default


def test_thread_shows_conversation(client):
    m = register(client)
    sms(client, m["phone"], "PRICE")
    t = client.get("/api/sms/thread", params={"phone": m["phone"]}).json()
    assert [x["direction"] for x in t["messages"]] == ["in", "out"]
    assert t["member"]["member_id"] == m["member_id"]
    # the national format of the same number finds the same thread
    t2 = client.get("/api/sms/thread", params={"phone": "0700 001 000"}).json()
    assert t2["phone"] == m["phone"] and len(t2["messages"]) == 2
