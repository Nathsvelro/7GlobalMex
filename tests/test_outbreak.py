"""Outbreak rule (PLAN.md section 8) and staff approval of broadcasts."""
from conftest import register, sms, ymd

# Three plots in Ondera Alto, every pair < 5 km apart (about 1.5-3 km).
NEAR = [(16.91, -92.11), (16.92, -92.12), (16.90, -92.10)]


def three_members(client, locs=NEAR, extra=0):
    ms = [register(client, name=f"Socio {i}", phone=f"+52967000200{i}", lat=lat, lon=lon)
          for i, (lat, lon) in enumerate(locs)]
    for j in range(extra):
        ms.append(register(client, name=f"Lejano {j}", phone=f"+52967000300{j}", community="Ondera Río",
                           lat=16.97, lon=-92.20, language="tzh"))
    return ms


# Reports count only at conf >= the image-model threshold in app/model/labels.json (0.90 -> 90); the app itself
# only sends ROYA with conf >= that threshold.
def roya(client, m, loc, days_ago=0, conf=92, obs="R001"):
    return sms(client, m["phone"], f"CAF1 {m['member_id']} ROYA {conf} {ymd(days_ago)} {loc[0]},{loc[1]} #{obs}")


def alert_actions(r):
    return [a for a in r["actions"] if a["type"] == "alert_created"]


def test_third_nearby_roya_in_7_days_triggers_alert(client, conn):
    ms = three_members(client, extra=2)
    assert not alert_actions(roya(client, ms[0], NEAR[0], days_ago=5, obs="A001"))
    assert not alert_actions(roya(client, ms[1], NEAR[1], days_ago=2, obs="A002"))
    r = roya(client, ms[2], NEAR[2], days_ago=0, obs="A003")
    a = alert_actions(r)
    assert len(a) == 1 and a[0]["n_reports"] == 3
    # one alert_roya per consenting member (5), all waiting for staff approval
    out = client.get("/api/outbox", params={"status": "pending_approval"}).json()["messages"]
    assert len(out) == 5 and {m["card_id"] for m in out} == {"alert_roya"}
    alerts = client.get("/api/alerts").json()
    assert alerts["alerts"][0]["active"] and alerts["alerts"][0]["community"] == "Ondera Alto"
    assert alerts["params"]["radius_km"] == 5.0 and alerts["params"]["min_members"] == 3


def test_broadcast_waits_for_approval(client):
    ms = three_members(client)
    for i in range(3):
        roya(client, ms[i], NEAR[i], obs=f"B00{i}")
    phone = ms[0]["phone"]
    thread = lambda: [m for m in client.get("/api/sms/thread", params={"phone": phone}).json()["messages"]
                      if m["alert_id"]]
    assert thread() == []                                   # not delivered yet
    pending = client.get("/api/outbox", params={"status": "pending_approval"}).json()["messages"]
    mine = next(m for m in pending if m["phone"] == phone)
    other = next(m for m in pending if m["phone"] != phone)
    assert client.post(f"/api/outbox/{mine['id']}/approve", json={"by": "Ana (staff)"}).status_code == 200
    assert len(thread()) == 1 and thread()[0]["status"] == "sent_simulated"
    assert client.post(f"/api/outbox/{mine['id']}/approve").status_code == 409   # only once
    assert client.post(f"/api/outbox/{other['id']}/reject").json()["status"] == "rejected"
    assert client.post("/api/outbox/99999/approve").status_code == 404


def test_far_reports_do_not_trigger(client):
    far = [(16.91, -92.11), (16.97, -92.20), (16.87, -92.04)]   # 8-12 km apart
    ms = three_members(client, locs=far)
    results = [roya(client, ms[i], far[i], obs=f"C00{i}") for i in range(3)]
    assert not any(alert_actions(r) for r in results)


def test_old_reports_do_not_trigger(client):
    ms = three_members(client)
    roya(client, ms[0], NEAR[0], days_ago=9, obs="D001")
    roya(client, ms[1], NEAR[1], days_ago=8, obs="D002")
    assert not alert_actions(roya(client, ms[2], NEAR[2], obs="D003"))


def test_low_confidence_does_not_count(client):
    ms = three_members(client)
    roya(client, ms[0], NEAR[0], conf=89, obs="E001")   # just below the 90 threshold
    roya(client, ms[1], NEAR[1], obs="E002")
    assert not alert_actions(roya(client, ms[2], NEAR[2], obs="E003"))


def test_same_member_three_times_does_not_trigger(client):
    ms = three_members(client)
    results = [roya(client, ms[0], NEAR[0], days_ago=d, obs=f"F00{d}") for d in range(3)]
    assert not any(alert_actions(r) for r in results)


def test_every_pair_must_be_within_radius(client):
    # B is in the middle; A and C are each ~4.4 km from B but ~8.9 km from each other.
    locs = [(16.87, -92.11), (16.91, -92.11), (16.95, -92.11)]
    ms = three_members(client, locs=locs)
    roya(client, ms[0], locs[0], obs="G001")
    roya(client, ms[2], locs[2], obs="G002")
    assert not alert_actions(roya(client, ms[1], locs[1], obs="G003"))


def test_cluster_found_when_nearest_report_does_not_fit(client):
    # Along one meridian (0.009 deg lat ~ 1 km): new report at 0 km, others at +2, -3.5 and -4 km. The +2 km
    # report is nearest but 5.5-6 km from both western ones; new + the two western ones are a valid cluster.
    lat0, lon = 16.91, -92.11
    locs = {"east": (lat0 + 0.018, lon), "west1": (lat0 - 0.0315, lon), "west2": (lat0 - 0.036, lon),
            "new": (lat0, lon)}
    ms = {k: register(client, name=f"Socio {k}", phone=f"+52967000400{i}", lat=lt, lon=ln)
          for i, (k, (lt, ln)) in enumerate(locs.items())}
    for i, k in enumerate(["east", "west1", "west2"]):
        assert not alert_actions(roya(client, ms[k], locs[k], obs=f"J00{i}"))
    a = alert_actions(roya(client, ms["new"], locs["new"], obs="J009"))
    assert len(a) == 1 and a[0]["n_reports"] == 3
    alert = client.get("/api/alerts").json()["alerts"][0]
    assert set(alert["member_ids"]) == {ms[k]["member_id"] for k in ("new", "west1", "west2")}
    assert alert["lat"] < lat0          # centred on the western cluster, not pulled east


def test_one_alert_per_area_per_week(client):
    ms = three_members(client)
    for i in range(3):
        roya(client, ms[i], NEAR[i], obs=f"H00{i}")
    m4 = register(client, name="Cuarta", phone="+529670002009", lat=16.91, lon=-92.12)
    assert not alert_actions(roya(client, m4, (16.91, -92.12), obs="H009"))
    assert len(client.get("/api/alerts").json()["alerts"]) == 1


def test_demo_story_noor_is_the_third_report(client):
    """With the DEMO seed, Noor's ROYA code triggers the alert (two neighbours reported in the last 7 days)."""
    assert client.post("/api/demo/reset").status_code == 200
    assert client.get("/api/alerts").json()["alerts"] == []
    r = sms(client, "+529670000123", f"CAF1 M0123 ROYA 96 {ymd()} 16.91,-92.11 #K3F9")
    a = alert_actions(r)
    assert len(a) == 1 and a[0]["n_reports"] == 3
    assert a[0]["queued_pending_approval"] == 24
    top = client.get("/api/worklist").json()["farms"][0]
    assert top["member_id"] == "M0123" and top["in_alert"] and "zona de alerta" in top["reason"]
