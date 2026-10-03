"""Outbreak rule (PLAN.md section 8) and officer worklist (section 9). Plain rules, not AI.

Outbreak: ROYA reports (confidence >= model threshold) from >= MIN_MEMBERS different members, every pair within
RADIUS_KM, observation date within the last WINDOW_DAYS days -> one alert (at most one per WINDOW_DAYS per area)
and card `alert_roya` queued for every consenting member as `pending_approval`.
"""
import json
import math
from datetime import date, timedelta

from . import cards, db

RADIUS_KM = 5.0
WINDOW_DAYS = 7
MIN_MEMBERS = 3

WORKLIST_DAYS = 30
WEIGHTS = {"ROYA": 3, "DUDA": 2, "OTRO": 2, "CERC": 2, "PHOM": 2, "MINA": 2, "ACAR": 2, "SANO": 0}
# Which report of a farm counts (worklist row and map colour): ROYA > DUDA/OTRO (a person must look) >
# CERC/PHOM/MINA/ACAR > SANO; then higher score, then most recent.
SEVERITY = {"ROYA": 3, "DUDA": 2, "OTRO": 2, "CERC": 1, "PHOM": 1, "MINA": 1, "ACAR": 1, "SANO": 0}
ALERT_BONUS = 2
CODE_NAMES_ES = {"ROYA": "Roya", "MINA": "Minador", "PHOM": "Phoma", "CERC": "Cercospora", "ACAR": "Ácaro rojo",
                 "SANO": "Sano", "OTRO": "No es hoja de café", "DUDA": "Duda (la app no está segura)"}
CODE_TO_LABEL = {"SANO": "sano", "ROYA": "roya", "MINA": "minador", "PHOM": "phoma", "CERC": "cercospora",
                 "ACAR": "acaro_rojo", "OTRO": "otro", "DUDA": None}


def params() -> dict:
    return {
        "outbreak": {"code": "ROYA", "min_members": MIN_MEMBERS, "radius_km": RADIUS_KM, "window_days": WINDOW_DAYS,
                     "min_conf": round(db.model_threshold() * 100), "one_alert_per_area_days": WINDOW_DAYS,
                     "note": "Decisiones de diseño para la demo, no umbrales agronómicos."},
        "worklist": {"days": WORKLIST_DAYS, "weights": WEIGHTS, "alert_bonus": ALERT_BONUS,
                     "formula": "weight x conf/100 (1.0 for DUDA/OTRO) + 2 if inside an active alert area",
                     "severity": SEVERITY,
                     "per_farm": "most serious report in the last 30 days (ROYA > DUDA/OTRO > CERC/PHOM/MINA/ACAR"
                                 " > SANO; then score, then most recent)"},
    }


def base_score(o: dict) -> float:
    """Worklist score of one report without the alert bonus: weight x conf/100 (1.0 for DUDA/OTRO)."""
    factor = 1.0 if o["code"] in ("DUDA", "OTRO") else o["conf"] / 100
    return WEIGHTS.get(o["code"], 0) * factor


def seriousness(o: dict) -> tuple:
    """Sort key: the farm's report with the largest key is its most serious one (worklist and map)."""
    return (SEVERITY.get(o["code"], 0), base_score(o), o["date"], o.get("received_at") or "")


def km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance (haversine), km."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _today() -> date:
    return db.now().date()


def active_alerts(conn) -> list[dict]:
    since = (db.now() - timedelta(days=WINDOW_DAYS)).isoformat(timespec="seconds")
    return db.rows(conn.execute(
        "SELECT * FROM alerts WHERE status = 'active' AND created_at >= ? ORDER BY created_at DESC", (since,)))


def in_alert_area(lat, lon, alerts) -> dict | None:
    if lat is None or lon is None:
        return None
    for a in alerts:
        if km(lat, lon, a["lat"], a["lon"]) <= RADIUS_KM:
            return a
    return None


def check(conn, new_obs: dict) -> dict | None:
    """Run the rule around a new observation. Returns the created alert (dict) or None.

    Must be called inside a transaction (db.Tx)."""
    min_conf = round(db.model_threshold() * 100)
    if new_obs["code"] != "ROYA" or new_obs["conf"] < min_conf or new_obs["lat"] is None:
        return None
    today = _today()
    start = (today - timedelta(days=WINDOW_DAYS - 1)).isoformat()   # last 7 days incl. today
    obs_date = date.fromisoformat(new_obs["date"])
    if obs_date < date.fromisoformat(start) or obs_date > today + timedelta(days=1):
        return None
    lat0, lon0 = new_obs["lat"], new_obs["lon"]

    recent = db.rows(conn.execute(
        "SELECT uid, member_id, lat, lon, date, conf FROM observations WHERE code = 'ROYA' AND conf >= ?"
        " AND date >= ? AND lat IS NOT NULL", (min_conf, start)))
    # Nearest report of each other member, within RADIUS_KM of the new one.
    best = {}
    for o in recent:
        if o["member_id"] == new_obs["member_id"]:
            continue
        d = km(lat0, lon0, o["lat"], o["lon"])
        if d <= RADIUS_KM and (o["member_id"] not in best or d < best[o["member_id"]][0]):
            best[o["member_id"]] = (d, o)
    # Greedy cluster: add members (closest first) only if within RADIUS_KM of everyone already in it.
    cluster = [dict(new_obs)]
    for d, o in sorted(best.values(), key=lambda t: t[0]):
        if all(km(o["lat"], o["lon"], c["lat"], c["lon"]) <= RADIUS_KM for c in cluster):
            cluster.append(o)
    if len(cluster) < MIN_MEMBERS:
        return None
    # At most one alert per area per WINDOW_DAYS.
    for a in active_alerts(conn):
        if km(lat0, lon0, a["lat"], a["lon"]) <= RADIUS_KM:
            return None

    clat = round(sum(c["lat"] for c in cluster) / len(cluster), 4)
    clon = round(sum(c["lon"] for c in cluster) / len(cluster), 4)
    member = db.member_by_id(conn, new_obs["member_id"])
    if not member:   # no registered community to name: no alert (farmer text only from cards and registry)
        return None
    community = member["community"]
    member_ids = sorted({c["member_id"] for c in cluster})
    cur = conn.execute(
        "INSERT INTO alerts(created_at, community, lat, lon, n_reports, member_ids, obs_uids, status, demo)"
        " VALUES (?,?,?,?,?,?,?, 'active', 0)",
        (db.now_iso(), community, clat, clon, len(member_ids), json.dumps(member_ids),
         json.dumps([c["uid"] for c in cluster])))
    alert_id = cur.lastrowid
    queued = queue_alert_broadcast(conn, alert_id, community, len(member_ids))
    return {"id": alert_id, "community": community, "lat": clat, "lon": clon, "n_reports": len(member_ids),
            "member_ids": member_ids, "queued": queued}


def queue_alert_broadcast(conn, alert_id: int, community: str, n_reports: int) -> int:
    """Queue card alert_roya for every consenting member. Nothing is sent until staff approve it."""
    n = 0
    for m in db.rows(conn.execute("SELECT * FROM members WHERE consent = 1 ORDER BY member_id")):
        try:
            text, lang = cards.render("alert_roya", m["language"], comunidad=community, n_reportes=str(n_reports))
        except cards.CardError:  # never improvise text; registration validates community names, so rare
            continue
        db.add_message(conn, "out", m["phone"], text, "pending_approval", member_id=m["member_id"],
                       card_id="alert_roya", lang=lang, alert_id=alert_id)
        n += 1
    return n


def _closed_uids(conn) -> dict[str, dict]:
    """Latest officer action per observation."""
    out = {}
    for a in db.rows(conn.execute("SELECT * FROM officer_actions ORDER BY id")):
        out[a["obs_uid"]] = a
    return out


def worklist(conn) -> list[dict]:
    """Farms ranked by score (PLAN.md section 9). Observations closed by the officer (confirmed / not
    confirmed) leave the list; 'visit_scheduled' stays, marked."""
    since = (_today() - timedelta(days=WORKLIST_DAYS - 1)).isoformat()
    alerts = active_alerts(conn)
    actions = _closed_uids(conn)
    obs = db.rows(conn.execute(
        "SELECT o.*, m.name, m.community, m.phone, m.language, m.lat AS plot_lat, m.lon AS plot_lon"
        " FROM observations o JOIN members m ON m.member_id = o.member_id WHERE o.date >= ?", (since,)))
    farms = {}
    for o in obs:
        last = actions.get(o["uid"])
        if last and last["action"] in ("confirmed", "not_confirmed"):
            continue
        f = farms.setdefault(o["member_id"], {"reports_30d": 0, "best": None, "best_base": -1})
        f["reports_30d"] += 1
        if f["best"] is None or seriousness(o) > seriousness(f["best"]):
            f["best"], f["best_base"] = o, base_score(o)
            f["last_action"] = last
    out = []
    for member_id, f in farms.items():
        o = f["best"]
        if f["best_base"] <= 0:
            continue
        lat = o["lat"] if o["lat"] is not None else o["plot_lat"]
        lon = o["lon"] if o["lon"] is not None else o["plot_lon"]
        alert = in_alert_area(lat, lon, alerts)
        score = round(f["best_base"] + (ALERT_BONUS if alert else 0), 2)
        if o["code"] in ("DUDA", "OTRO"):
            reason = [CODE_NAMES_ES[o["code"]]]
        else:
            reason = [f"{CODE_NAMES_ES.get(o['code'], o['code'])} {o['conf']}%"]
        if alert:
            reason.append("zona de alerta")
        if f["reports_30d"] > 1:
            reason.append(f"{f['reports_30d']} reportes en {WORKLIST_DAYS} días")
        if o["photo_path"]:
            reason.append("con foto")
        last = f.get("last_action")
        out.append({
            "member_id": member_id, "name": o["name"], "community": o["community"], "phone": o["phone"],
            "obs_uid": o["uid"], "obs_id": o["obs_id"], "code": o["code"], "conf": o["conf"], "date": o["date"],
            "lat": lat, "lon": lon, "score": score, "reason": " · ".join(reason),
            "in_alert": bool(alert), "alert_id": alert["id"] if alert else None,
            "photo_url": f"/api/photos/{o['uid']}" if o["photo_path"] else None,
            "model_label": CODE_TO_LABEL.get(o["code"]),
            "status": last["action"] if last else None, "demo": o["demo"],
        })
    out.sort(key=lambda r: (-r["score"], _neg_date(r["date"])))  # same score: most recent first
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out


def _neg_date(d: str) -> int:
    return -int(d.replace("-", ""))
