"""Officer worklist (PLAN.md section 9) and officer actions."""
from conftest import register, sms, ymd


def setup_farms(client):
    a = register(client, name="Roya", phone="+529670004001", lat=16.91, lon=-92.11)
    b = register(client, name="Duda", phone="+529670004002", lat=16.97, lon=-92.20)
    c = register(client, name="Mina", phone="+529670004003", lat=16.87, lon=-92.04)
    d = register(client, name="Sana", phone="+529670004004", lat=16.98, lon=-92.05)
    e = register(client, name="Vieja", phone="+529670004005", lat=16.98, lon=-92.06)
    sms(client, a["phone"], f"CAF1 {a['member_id']} ROYA 90 {ymd(3)} 16.91,-92.11 #W001")
    sms(client, b["phone"], f"CAF1 {b['member_id']} DUDA 41 {ymd(1)} 16.97,-92.20 #W002")
    sms(client, c["phone"], f"CAF1 {c['member_id']} MINA 80 {ymd(2)} 16.87,-92.04 #W003")
    sms(client, d["phone"], f"CAF1 {d['member_id']} SANO 95 {ymd(1)} 16.98,-92.05 #W004")
    sms(client, e["phone"], f"CAF1 {e['member_id']} ROYA 95 {ymd(40)} 16.98,-92.06 #W005")  # older than 30 days
    return a, b, c, d, e


def test_ranking_scores_and_reasons(client):
    a, b, c, d, e = setup_farms(client)
    w = client.get("/api/worklist").json()
    farms = w["farms"]
    assert [f["member_id"] for f in farms] == [a["member_id"], b["member_id"], c["member_id"]]  # SANO and old excluded
    assert [f["score"] for f in farms] == [2.7, 2.0, 1.6]
    assert farms[0]["reason"] == "Roya 90%"
    assert farms[1]["reason"].startswith("Duda")
    assert [f["rank"] for f in farms] == [1, 2, 3]
    assert w["params"]["weights"]["ROYA"] == 3 and "Usted decide" in w["note"]


def test_alert_area_bonus(client):
    ms = [register(client, name=f"S{i}", phone=f"+52967000500{i}", lat=lat, lon=lon)
          for i, (lat, lon) in enumerate([(16.91, -92.11), (16.92, -92.12), (16.90, -92.10)])]
    far = register(client, name="Lejos", phone="+529670005009", lat=16.97, lon=-92.20)
    sms(client, far["phone"], f"CAF1 {far['member_id']} ROYA 95 {ymd()} 16.97,-92.20 #X009")
    for i, m in enumerate(ms):
        sms(client, m["phone"], f"CAF1 {m['member_id']} ROYA 80 {ymd()} {m['lat']:.2f},{m['lon']:.2f} #X00{i}")
    farms = client.get("/api/worklist").json()["farms"]
    assert farms[-1]["member_id"] == far["member_id"] and not farms[-1]["in_alert"]
    assert all(f["in_alert"] and f["score"] == 4.4 and "zona de alerta" in f["reason"] for f in farms[:3])


def test_officer_actions_and_training_labels(client, conn):
    a, b, c, *_ = setup_farms(client)
    uid_a, uid_b, uid_c = (f"{m['member_id']}-W00{i}" for i, m in zip((1, 2, 3), (a, b, c)))
    r = client.post(f"/api/worklist/{uid_a}/action", json={"action": "visit_scheduled"})
    assert r.status_code == 200 and not r.json()["saved_as_training_example"]
    farms = client.get("/api/worklist").json()["farms"]
    assert farms[0]["status"] == "visit_scheduled"                      # stays on the list, marked
    r = client.post(f"/api/worklist/{uid_a}/action", json={"action": "confirmed"})
    assert r.json()["true_label"] == "roya" and r.json()["saved_as_training_example"]
    r = client.post(f"/api/worklist/{uid_b}/action", json={"action": "not_confirmed", "true_label": "phoma",
                                                           "note": "Era phoma"})
    assert r.json()["saved_as_training_example"]
    farms = client.get("/api/worklist").json()["farms"]
    assert [f["member_id"] for f in farms] == [c["member_id"]]          # closed ones left the list
    labels = client.get("/api/labels").json()["labels"]
    assert {(x["obs_uid"], x["model_label"], x["true_label"]) for x in labels} == {
        (uid_a, "roya", "roya"), (uid_b, None, "phoma")}
    assert client.post(f"/api/worklist/{uid_c}/action", json={"action": "confirmed", "true_label": "xx"}).status_code == 400
    assert client.post(f"/api/worklist/{uid_c}/action", json={"action": "not_confirmed",
                                                               "true_label": "minador"}).status_code == 400
    assert client.post(f"/api/worklist/{uid_c}/action", json={"action": "delete"}).status_code == 422
    assert client.post("/api/worklist/M9999-ZZZZ/action", json={"action": "confirmed"}).status_code == 404


def test_map_colours_farm_by_most_serious_report(client):
    """A later DUDA or SANO must not hide an earlier ROYA; map and worklist pick the same report."""
    a = register(client, name="Roya luego duda", phone="+529670006001", lat=16.91, lon=-92.11)
    b = register(client, name="Cerc luego duda", phone="+529670006002", lat=16.97, lon=-92.20)
    c = register(client, name="Mina luego sana", phone="+529670006003", lat=16.87, lon=-92.04)
    d = register(client, name="Roya vieja", phone="+529670006004", lat=16.98, lon=-92.05)
    sms(client, a["phone"], f"CAF1 {a['member_id']} ROYA 75 {ymd(5)} 16.91,-92.11 #Y001")
    sms(client, a["phone"], f"CAF1 {a['member_id']} DUDA 30 {ymd(2)} 16.91,-92.11 #Y002")
    sms(client, a["phone"], f"CAF1 {a['member_id']} SANO 95 {ymd(0)} 16.91,-92.11 #Y003")
    sms(client, b["phone"], f"CAF1 {b['member_id']} CERC 95 {ymd(1)} 16.97,-92.20 #Y004")
    sms(client, b["phone"], f"CAF1 {b['member_id']} DUDA 40 {ymd(4)} 16.97,-92.20 #Y005")
    sms(client, c["phone"], f"CAF1 {c['member_id']} MINA 80 {ymd(3)} 16.87,-92.04 #Y006")
    sms(client, c["phone"], f"CAF1 {c['member_id']} SANO 90 {ymd(1)} 16.87,-92.04 #Y007")
    sms(client, d["phone"], f"CAF1 {d['member_id']} ROYA 95 {ymd(40)} 16.98,-92.05 #Y008")  # older than 30 days
    sms(client, d["phone"], f"CAF1 {d['member_id']} SANO 90 {ymd(1)} 16.98,-92.05 #Y009")
    members = {m["member_id"]: m for m in client.get("/api/map").json()["members"]}
    assert members[a["member_id"]]["worst"]["code"] == "ROYA" and members[a["member_id"]]["reports_30d"] == 3
    assert members[b["member_id"]]["worst"]["code"] == "DUDA"
    assert members[c["member_id"]]["worst"]["code"] == "MINA"
    assert members[d["member_id"]]["worst"]["code"] == "SANO"
    farms = {f["member_id"]: f for f in client.get("/api/worklist").json()["farms"]}
    for m in (a, b, c):
        assert farms[m["member_id"]]["obs_uid"] == members[m["member_id"]]["worst"]["uid"]
    assert d["member_id"] not in farms
