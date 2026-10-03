"""SMS parsing (PLAN.md section 5) and routing (section 7).

Every reply text comes from content/cards.json via cards.render(); slots get only numbers, dates,
source names and community names.
"""
import hashlib
import json
import re
from datetime import date, timedelta

from . import cards, db, intent, outbreak

CODES = ["SANO", "ROYA", "MINA", "PHOM", "CERC", "ACAR", "OTRO", "DUDA"]

# CAF1 <member> <code> <conf> <yyyymmdd> <lat>,<lon>|- [#<obs>]   (case-insensitive, extra spaces allowed)
CODE_RE = re.compile(
    r"^\s*CAF1\s+(?P<member>M\d{4})\s+(?P<code>[A-Z]{4})\s+(?P<conf>\d{1,3})\s+(?P<date>\d{8})\s+"
    r"(?:(?P<lat>[+-]?\d{1,2}(?:\.\d{1,6})?)\s*,\s*(?P<lon>[+-]?\d{1,3}(?:\.\d{1,6})?)|(?P<noloc>-))"
    r"(?:\s+#(?P<obs>[0-9A-Z]{4}))?\s*$",
    re.IGNORECASE)

KEYWORDS = {  # exact one-word messages (after removing accents/punctuation); the cards advertise these
    "precio": "precio", "precios": "precio",
    "ayuda": "ayuda",
    "tecnico": "hablar_con_tecnico",
}
INTENT_CARD = {"precio": "sms_precio", "reporte": "sms_reporte_instrucciones", "ayuda": "sms_ayuda",
               "hablar_con_tecnico": "sms_pasar_tecnico", "otro": "sms_pasar_tecnico"}


class ParseError(ValueError):
    pass


def normalize_phone(phone: str) -> str:
    p = re.sub(r"[^\d+]", "", phone or "")
    digits = p.lstrip("+")
    if not digits:
        return ""
    if p.startswith("+"):
        return "+" + digits
    if len(digits) == 10:          # Mexican national number
        return "+52" + digits
    if digits.startswith("52") and len(digits) == 12:
        return "+" + digits
    return "+" + digits


def parse_code(body: str, today: date | None = None) -> dict:
    """Parse an observation SMS. Raises ParseError with a reason if it is not a valid CAF1 code."""
    m = CODE_RE.match(body or "")
    if not m:
        raise ParseError("format")
    code = m["code"].upper()
    if code not in CODES:
        raise ParseError("code")
    conf = int(m["conf"])
    if conf > 100:
        raise ParseError("conf")
    try:
        d = date(int(m["date"][:4]), int(m["date"][4:6]), int(m["date"][6:8]))
    except ValueError:
        raise ParseError("date")
    today = today or db.now().date()
    if d > today + timedelta(days=2) or d < today - timedelta(days=365):
        raise ParseError("date")
    lat = lon = None
    if not m["noloc"]:
        lat, lon = float(m["lat"]), float(m["lon"])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ParseError("location")
        lat, lon = round(lat, 2), round(lon, 2)   # ~1 km, for privacy
    return {"member_id": m["member"].upper(), "code": code, "conf": conf, "date": d.isoformat(),
            "lat": lat, "lon": lon, "obs_id": m["obs"].upper() if m["obs"] else None}


def _fallback_obs_id(member_id: str, raw: str) -> str:
    """Codes typed without '#obs' get a stable 4-char id from the text, so a repeat is not stored twice."""
    n = int(hashlib.sha1(f"{member_id}|{raw.strip().upper()}".encode()).hexdigest(), 16)
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    s = ""
    for _ in range(4):
        n, r = divmod(n, 36)
        s += chars[r]
    return s


def save_observation(conn, rec: dict, source: str, raw_sms: str | None = None, demo: int = 0) -> tuple[dict, bool]:
    """Insert or merge one observation. Returns (row, created). Call inside db.Tx.

    rec: member_id, obs_id, code, conf, date (YYYY-MM-DD), lat, lon; optional model_version, top3,
    created_at, photo_path. A missing location uses the member's registered plot.
    """
    member = db.member_by_id(conn, rec["member_id"])
    uid = f"{rec['member_id']}-{rec['obs_id']}"
    if rec.get("top3") is not None and not isinstance(rec["top3"], str):
        rec = {**rec, "top3": json.dumps(rec["top3"])}
    existing = db.one(conn.execute("SELECT * FROM observations WHERE uid = ?", (uid,)))
    if existing:
        updates = {}
        if source == "sms" and not existing["raw_sms"]:
            updates["raw_sms"] = raw_sms
        if source != existing["source"] and source not in existing["source"]:
            updates["source"] = "sms+sync"
        for k in ("model_version", "top3", "created_at", "photo_path"):
            if rec.get(k) and not existing.get(k):
                updates[k] = rec[k]
        if updates:
            sets = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE observations SET {sets} WHERE uid = ?", (*updates.values(), uid))
        return db.one(conn.execute("SELECT * FROM observations WHERE uid = ?", (uid,))), False
    lat, lon, loc_source = rec.get("lat"), rec.get("lon"), "report"
    if lat is None or lon is None:
        lat, lon, loc_source = member["lat"], member["lon"], "plot"
    conn.execute(
        "INSERT INTO observations(uid, obs_id, member_id, code, conf, date, lat, lon, loc_source, raw_sms,"
        " received_at, photo_path, source, model_version, top3, created_at, demo)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (uid, rec["obs_id"], rec["member_id"], rec["code"], int(rec["conf"]), rec["date"], lat, lon, loc_source,
         raw_sms, rec.get("received_at") or db.now_iso(), rec.get("photo_path"), source,
         rec.get("model_version"), rec.get("top3"), rec.get("created_at"), demo))
    return db.one(conn.execute("SELECT * FROM observations WHERE uid = ?", (uid,))), True


def prices() -> dict | None:
    try:
        return json.loads(db.prices_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def price_slots() -> dict | None:
    """Slots for card sms_precio from data/prices.json, or None if the table is missing/incomplete."""
    p = prices()
    if not p:
        return None
    items = {i.get("id"): i for i in p.get("items", [])}
    try:
        cafe, maiz, frijol = items["cafe_pergamino"], items["maiz"], items["frijol"]
        return {
            "precio_cafe": f"{float(cafe['price']):.2f}", "unidad_cafe": cafe.get("unit", "MXN/kg"),
            "precio_maiz": f"{float(maiz['price']):.2f}", "precio_frijol": f"{float(frijol['price']):.2f}",
            "fuente": p.get("sms_fuente") or cafe.get("source"),
            "fecha": p.get("sms_fecha") or cafe.get("date"),
        }
    except (KeyError, TypeError, ValueError):
        return None


def _reply(conn, phone, member, card_id, out, **slots):
    """Render a card in the member's language and log it as sent (SIMULATED gateway)."""
    lang = member["language"] if member else "es"
    try:
        text, lang = cards.render(card_id, lang, **slots)
    except cards.CardError as e:   # never improvise text: log and send nothing
        out["actions"].append({"type": "card_error", "detail": str(e)})
        return
    mid = db.add_message(conn, "out", phone, text, "sent_simulated",
                         member_id=member["member_id"] if member else None, card_id=card_id, lang=lang)
    out["replies"].append({"id": mid, "to": phone, "body": text, "card_id": card_id, "lang": lang,
                           "status": "sent_simulated", **cards.sms_length(text)})


def _forward_to_officer(conn, member, phone, body, message_id, cls, out):
    conn.execute(
        "INSERT INTO officer_messages(message_id, member_id, phone, body, intent, conf, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (message_id, member["member_id"] if member else None, phone, body, cls.get("intent"), cls.get("conf"),
         db.now_iso()))
    out["actions"].append({"type": "forwarded_to_officer"})


def route(conn, phone: str, body: str) -> dict:
    """Handle one inbound SMS. Returns {"replies": [...], "actions": [...]}."""
    phone = normalize_phone(phone)
    body = (body or "").strip()
    out = {"replies": [], "actions": []}
    with db.Tx(conn):
        member = db.member_by_phone(conn, phone)
        msg_id = db.add_message(conn, "in", phone, body, "received",
                                member_id=member["member_id"] if member else None)
        is_code = bool(re.match(r"^\s*CAF1\b", body, re.IGNORECASE))

        # 1. Unknown sender. Exception: a CAF1 code for a registered member may come from a family phone
        #    (the daughter's smartphone), so it is accepted if the member in the code exists.
        if not member and not is_code:
            _reply(conn, phone, None, "sms_no_registrado", out)
            out["actions"].append({"type": "unregistered_sender"})
            return out

        # 2. Observation code.
        if is_code:
            try:
                rec = parse_code(body)
                code_member = db.member_by_id(conn, rec["member_id"])
                if not code_member:
                    raise ParseError("member")
                if member and member["member_id"] != rec["member_id"]:
                    raise ParseError("member_mismatch")
            except ParseError as e:
                if not member:
                    _reply(conn, phone, None, "sms_no_registrado", out)
                    out["actions"].append({"type": "unregistered_sender", "reason": str(e)})
                else:
                    _reply(conn, phone, member, "sms_codigo_invalido", out)
                    out["actions"].append({"type": "invalid_code", "reason": str(e)})
                return out
            rec["obs_id"] = rec["obs_id"] or _fallback_obs_id(rec["member_id"], body)
            conn.execute("UPDATE messages SET member_id = ? WHERE id = ?", (rec["member_id"], msg_id))
            row, created = save_observation(conn, rec, "sms", raw_sms=body)
            out["actions"].append({"type": "observation_stored" if created else "observation_duplicate",
                                   "obs_uid": row["uid"], "code": row["code"], "conf": row["conf"]})
            _reply(conn, phone, member or code_member, "sms_obs_recibida", out)
            if created:
                alert = outbreak.check(conn, row)
                if alert:
                    out["actions"].append({"type": "alert_created", "alert_id": alert["id"],
                                           "n_reports": alert["n_reports"], "queued_pending_approval": alert["queued"]})
            return out

        # 3. Exact keywords (PRECIO, AYUDA, TECNICO), then 4. the intent classifier.
        norm = intent.normalize(body).replace(" ", "")
        if norm in KEYWORDS:
            cls = {"intent": KEYWORDS[norm], "conf": 1.0, "accepted": True, "method": "keyword"}
        else:
            cls = {**intent.classify(body), "method": "classifier"}
        out["actions"].append({"type": "intent", **cls})
        name = cls["intent"] if cls["accepted"] else "otro"
        if name == "precio":
            slots = price_slots()
            if slots:
                _reply(conn, phone, member, "sms_precio", out, **slots)
            else:
                _reply(conn, phone, member, "sms_precio_sin_datos", out)
        else:
            _reply(conn, phone, member, INTENT_CARD[name], out)
            if name in ("hablar_con_tecnico", "otro"):
                _forward_to_officer(conn, member, phone, body, msg_id, cls, out)
        return out
