"""Registry with consent, member deletion, Wi-Fi sync of records and photos."""
import base64

from conftest import register, sms, ymd

JPEG = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF" + b"\x00" * 200 + b"\xff\xd9"


def data_url(raw):
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode()


def test_registration_requires_consent(client):
    base = {"name": "X", "phone": "+254700009000", "community": "Ondera Juu", "consent_by": "Ann"}
    assert client.post("/api/members", json={**base, "consent": False}).status_code == 400
    assert client.post("/api/members", json=base).status_code == 422             # consent missing
    assert client.post("/api/members", json={**base, "consent": True, "consent_by": ""}).status_code == 422
    assert client.post("/api/members", json={**base, "consent": True, "consent_by": "   "}).status_code == 400
    assert client.post("/api/members", json={**base, "consent": True, "name": "   "}).status_code == 400
    r = client.post("/api/members", json={**base, "consent": True})
    assert r.status_code == 201
    m = r.json()
    assert m["member_id"] == "M0001" and m["consent"] == 1 and m["consent_by"] == "Ann" and m["consent_date"]
    assert m["language"] == "en"
    assert client.post("/api/members", json={**base, "consent": True}).status_code == 409   # same phone
    assert client.post("/api/members", json={**base, "consent": True, "phone": "0700 009 000"}).status_code == 409
    assert register(client, phone="+254700009001")["member_id"] == "M0002"
    m3 = register(client, phone="0712 345 678")                      # Kenyan national format is normalised
    assert m3["phone"] == "+254712345678"
    assert client.post("/api/members", json={**base, "consent": True, "phone": "12345"}).status_code == 422


def test_delete_member_cascades(client, conn, env):
    m = register(client)
    other = register(client, name="Other", phone="+254700001001")
    sms(client, m["phone"], f"CAF1 {m['member_id']} RUST 88 {ymd()} -0.52,37.32 #DEL1")
    sms(client, m["phone"], "i want to talk to the officer")
    sms(client, other["phone"], "PRICE")
    client.post("/api/observations/sync", json={"obs_id": "DEL1", "member_id": m["member_id"], "code": "RUST",
                                                "conf": 88, "date": ymd(), "photo": data_url(JPEG)})
    uid = f"{m['member_id']}-DEL1"
    client.post(f"/api/worklist/{uid}/action", json={"action": "confirmed"})
    assert (env / "uploads" / f"{uid}.jpg").exists()
    assert client.delete(f"/api/members/{m['member_id']}").status_code == 200
    for table, col in [("observations", "member_id"), ("messages", "member_id"), ("officer_messages", "member_id")]:
        assert conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} = ?", (m["member_id"],)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM messages WHERE phone = ?", (m["phone"],)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM labels WHERE obs_uid = ?", (uid,)).fetchone()[0] == 0
    assert not (env / "uploads" / f"{uid}.jpg").exists()
    assert conn.execute("SELECT COUNT(*) FROM messages WHERE phone = ?", (other["phone"],)).fetchone()[0] == 2
    assert client.delete(f"/api/members/{m['member_id']}").status_code == 404


def test_member_ids_of_deleted_members_are_never_reused(client):
    register(client)
    last = register(client, name="Last", phone="+254700001001")["member_id"]
    assert client.delete(f"/api/members/{last}").status_code == 200
    new = register(client, name="New", phone="+254700001002")["member_id"]
    assert new != last and int(new[1:]) == int(last[1:]) + 1
    # The deleted member's phone may still send codes under the old id: they must not land on anyone.
    sync = client.post("/api/observations/sync", json={"records": [
        {"obs_id": "OLD1", "member_id": last, "code": "RUST", "conf": 90, "date": ymd()}]}).json()
    assert sync["results"][0]["ok"] is False and sync["results"][0]["status"] == 404


def test_sync_merges_photo_with_sms_observation(client, conn):
    m = register(client)
    sms(client, m["phone"], f"CAF1 {m['member_id']} RUST 87 {ymd()} -0.52,37.32 #K3F9")
    r = client.post("/api/observations/sync", json={
        "obs_id": "K3F9", "member_id": m["member_id"], "code": "RUST", "conf": 87, "date": ymd(), "lat": -0.5183,
        "lon": 37.3222, "created_at": "2026-10-03T10:00:00", "model_version": "cafetal-img-v2",
        "top3": [["roya", 0.87], ["sano", 0.08], ["minador", 0.03]], "photo": data_url(JPEG)})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "obs_uid": f"{m['member_id']}-K3F9", "created": False, "merged": True,
                        "photo": True, "alert_created": None}
    rows = conn.execute("SELECT source, photo_path, model_version, raw_sms FROM observations").fetchall()
    assert len(rows) == 1
    assert rows[0]["source"] == "sms+sync" and rows[0]["photo_path"] and rows[0]["raw_sms"].startswith("CAF1")
    p = client.get(f"/api/photos/{m['member_id']}-K3F9")
    assert p.status_code == 200 and p.headers["content-type"] == "image/jpeg" and p.content == JPEG
    farms = client.get("/api/worklist").json()["farms"]
    assert farms[0]["photo_url"] == f"/api/photos/{m['member_id']}-K3F9"


def test_sync_new_record_then_sms_merges(client, conn):
    m = register(client)
    r = client.post("/api/observations/sync", json={"records": [
        {"obs_id": "S001", "member_id": m["member_id"], "code": "HLTH", "conf": 0.93, "date": ymd()}]})
    assert r.json()["results"][0]["created"] is True
    assert conn.execute("SELECT conf, source FROM observations").fetchone()[:] == (93, "sync")
    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0      # sync sends no SMS
    sms(client, m["phone"], f"CAF1 {m['member_id']} HLTH 93 {ymd()} -0.52,37.32 #S001")
    assert conn.execute("SELECT COUNT(*), source FROM observations").fetchone()[:] == (1, "sms+sync")


def test_sync_validation(client):
    m = register(client)
    rec = {"obs_id": "V001", "member_id": m["member_id"], "code": "RUST", "conf": 80, "date": ymd()}
    assert client.post("/api/observations/sync", json={**rec, "member_id": "M9999"}).status_code == 404
    assert client.post("/api/observations/sync", json={**rec, "code": "XXXX"}).status_code == 400
    assert client.post("/api/observations/sync", json={**rec, "code": "ROYA"}).status_code == 400   # old Spanish code
    assert client.post("/api/observations/sync", json={**rec, "photo": "data:image/png;base64,AAAA"}).status_code == 400
    assert client.post("/api/observations/sync", json={**rec, "photo": data_url(b"notajpeg" * 20)}).status_code == 400
    big = JPEG[:4] + b"\x00" * (2 * 1024 * 1024)
    assert client.post("/api/observations/sync", json={**rec, "photo": data_url(big)}).status_code == 413
    assert client.get("/api/photos/..%2Fhub.db").status_code == 404
    # batch: the bad record is reported, the good one is stored (the phone app sends {"records": [...]})
    r = client.post("/api/observations/sync", json={"records": [{**rec, "member_id": "M9999"}, rec]})
    assert r.status_code == 200
    res = r.json()["results"]
    assert res[0]["ok"] is False and res[0]["status"] == 404 and res[1]["ok"] is True and res[1]["created"]
