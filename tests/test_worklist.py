"""Officer worklist (PLAN.md section 9) and officer actions."""
from conftest import register, sms, ymd


def setup_farms(client):
    a = register(client, name="Rust", phone="+254700004001", lat=-0.52, lon=37.32)
    b = register(client, name="Unsure", phone="+254700004002", lat=-0.46, lon=37.23)
    c = register(client, name="Miner", phone="+254700004003", lat=-0.56, lon=37.39)
    d = register(client, name="Healthy", phone="+254700004004", lat=-0.45, lon=37.38)
    e = register(client, name="Old", phone="+254700004005", lat=-0.45, lon=37.37)
    sms(client, a["phone"], f"CAF1 {a['member_id']} RUST 90 {ymd(3)} -0.52,37.32 #W001")
    sms(client, b["phone"], f"CAF1 {b['member_id']} UNSR 41 {ymd(1)} -0.46,37.23 #W002")
    sms(client, c["phone"], f"CAF1 {c['member_id']} MINR 80 {ymd(2)} -0.56,37.39 #W003")
    sms(client, d["phone"], f"CAF1 {d['member_id']} HLTH 95 {ymd(1)} -0.45,37.38 #W004")
    sms(client, e["phone"], f"CAF1 {e['member_id']} RUST 95 {ymd(40)} -0.45,37.37 #W005")  # older than 30 days
    return a, b, c, d, e


def test_ranking_scores_and_reasons(client):
    a, b, c, d, e = setup_farms(client)
    w = client.get("/api/worklist").json()
    farms = w["farms"]
    assert [f["member_id"] for f in farms] == [a["member_id"], b["member_id"], c["member_id"]]  # HLTH and old excluded
    assert [f["score"] for f in farms] == [2.7, 2.0, 1.6]
    assert farms[0]["reason"] == "Rust 90%"
    assert farms[1]["reason"].startswith("Unsure")
    assert farms[2]["reason"] == "Leaf miner 80%"
    assert [f["code"] for f in farms] == ["RUST", "UNSR", "MINR"]
    assert [f["rank"] for f in farms] == [1, 2, 3]
    assert w["params"]["weights"]["RUST"] == 3 and "You decide" in w["note"]


def test_alert_area_bonus(client):
    ms = [register(client, name=f"S{i}", phone=f"+25470000500{i}", lat=lat, lon=lon)
          for i, (lat, lon) in enumerate([(-0.52, 37.32), (-0.51, 37.31), (-0.53, 37.33)])]
    far = register(client, name="Far", phone="+254700005009", lat=-0.46, lon=37.23)
    sms(client, far["phone"], f"CAF1 {far['member_id']} RUST 95 {ymd()} -0.46,37.23 #X009")
    for i, m in enumerate(ms):
        sms(client, m["phone"], f"CAF1 {m['member_id']} RUST 92 {ymd()} {m['lat']:.2f},{m['lon']:.2f} #X00{i}")
    farms = client.get("/api/worklist").json()["farms"]
    assert farms[-1]["member_id"] == far["member_id"] and not farms[-1]["in_alert"]
    assert all(f["in_alert"] and f["score"] == 4.76 and f["reason"] == "Rust 92% · alert area" for f in farms[:3])


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
                                                           "note": "It was phoma"})
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
    """A later UNSR or HLTH must not hide an earlier RUST; map and worklist pick the same report."""
    a = register(client, name="Rust then unsure", phone="+254700006001", lat=-0.52, lon=37.32)
    b = register(client, name="Cerc then unsure", phone="+254700006002", lat=-0.46, lon=37.23)
    c = register(client, name="Miner then healthy", phone="+254700006003", lat=-0.56, lon=37.39)
    d = register(client, name="Old rust", phone="+254700006004", lat=-0.45, lon=37.38)
    sms(client, a["phone"], f"CAF1 {a['member_id']} RUST 75 {ymd(5)} -0.52,37.32 #Y001")
    sms(client, a["phone"], f"CAF1 {a['member_id']} UNSR 30 {ymd(2)} -0.52,37.32 #Y002")
    sms(client, a["phone"], f"CAF1 {a['member_id']} HLTH 95 {ymd(0)} -0.52,37.32 #Y003")
    sms(client, b["phone"], f"CAF1 {b['member_id']} CERC 95 {ymd(1)} -0.46,37.23 #Y004")
    sms(client, b["phone"], f"CAF1 {b['member_id']} UNSR 40 {ymd(4)} -0.46,37.23 #Y005")
    sms(client, c["phone"], f"CAF1 {c['member_id']} MINR 80 {ymd(3)} -0.56,37.39 #Y006")
    sms(client, c["phone"], f"CAF1 {c['member_id']} HLTH 90 {ymd(1)} -0.56,37.39 #Y007")
    sms(client, d["phone"], f"CAF1 {d['member_id']} RUST 95 {ymd(40)} -0.45,37.38 #Y008")  # older than 30 days
    sms(client, d["phone"], f"CAF1 {d['member_id']} HLTH 90 {ymd(1)} -0.45,37.38 #Y009")
    members = {m["member_id"]: m for m in client.get("/api/map").json()["members"]}
    assert members[a["member_id"]]["worst"]["code"] == "RUST" and members[a["member_id"]]["reports_30d"] == 3
    assert members[b["member_id"]]["worst"]["code"] == "UNSR"
    assert members[c["member_id"]]["worst"]["code"] == "MINR"
    assert members[d["member_id"]]["worst"]["code"] == "HLTH"
    farms = {f["member_id"]: f for f in client.get("/api/worklist").json()["farms"]}
    for m in (a, b, c):
        assert farms[m["member_id"]]["obs_uid"] == members[m["member_id"]]["worst"]["uid"]
    assert d["member_id"] not in farms
