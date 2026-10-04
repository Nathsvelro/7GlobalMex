"""Cafetal co-op hub (FastAPI). Start with ./run.sh, or:  uvicorn hub.main:app --host 0.0.0.0 --port 8000

API: PLAN.md section 6. Pages: /hub/*.html (English UI for co-op staff and the extension officer).
"""
import base64
import binascii
import json
import mimetypes
import re
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field, StrictBool

from . import cards, db, intent, outbreak, seed, sms

for ext, typ in {".wasm": "application/wasm", ".mjs": "text/javascript", ".js": "text/javascript",
                 ".webmanifest": "application/manifest+json", ".onnx": "application/octet-stream",
                 ".mp3": "audio/mpeg", ".webm": "audio/webm", ".ogg": "audio/ogg", ".m4a": "audio/mp4",
                 ".json": "application/json", ".svg": "image/svg+xml"}.items():
    mimetypes.add_type(typ, ext)

STATIC = db.HUB_DIR / "static"
LABELS = ["sano", "roya", "minador", "phoma", "cercospora", "acaro_rojo", "otro"]
MAX_PHOTO_BYTES = 2 * 1024 * 1024
MAX_AUDIO_BYTES = 10 * 1024 * 1024
UID_RE = re.compile(r"^M\d{4}-[0-9A-Z]{4}$")

# No /docs, /redoc or /openapi.json: they load Swagger UI / ReDoc from a CDN and would give anyone on the LAN a
# ready-made console for every state-changing endpoint (RESPONSIBLE_AI.md section 5).
app = FastAPI(title="Cafetal hub", version="1.0",
              description="Co-op hub: registry with consent, SMS inbox (SIMULATED gateway), outbreak alerts, "
                          "officer worklist, PRICE, content review. PLAN.md section 6.",
              docs_url=None, redoc_url=None, openapi_url=None)

_local = threading.local()


def conn():
    """One SQLite connection per worker thread and database file (WAL mode; the tests switch files
    through CAFETAL_DB). Writes are serialized by db.Tx."""
    p = str(db.db_path())
    conns = _local.__dict__.setdefault("conns", {})
    if p not in conns:
        conns[p] = db.connect(p)
    return conns[p]


@app.middleware("http")
async def cache_headers(request: Request, call_next):
    resp = await call_next(request)
    path = request.url.path
    # Revalidate the PWA shell, cards and hub pages on every load (the service worker does the offline caching).
    if path.endswith("sw.js") or path.startswith(("/app/", "/content/", "/hub/")) or path == "/":
        resp.headers["Cache-Control"] = "no-cache"
    if path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


class StaticGZip:
    """gzip text-like static files only: the 11 MB onnxruntime .wasm goes over the wire as ~3 MB on the phone's
    first load. Audio, the model and photos are left alone (already compressed), and so are Range requests."""
    SUFFIXES = (".wasm", ".js", ".mjs", ".json", ".css", ".html", ".svg", ".webmanifest", "/")

    def __init__(self, app):
        self.app = app
        self.gzip = GZipMiddleware(app, minimum_size=1024)

    async def __call__(self, scope, receive, send):
        if (scope["type"] == "http" and not scope["path"].startswith("/api/") and scope["path"].endswith(self.SUFFIXES)
                and not any(k == b"range" for k, _ in scope["headers"])):
            return await self.gzip(scope, receive, send)
        return await self.app(scope, receive, send)


app.add_middleware(StaticGZip)


# ---------- pages ----------

@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/app", include_in_schema=False)
def app_redirect():
    return RedirectResponse("/app/")


@app.get("/hub", include_in_schema=False)
def hub_redirect():
    return RedirectResponse("/hub/")


# ---------- health, summary, params ----------

@app.get("/api/health")
def health():
    return {"ok": True, "service": "cafetal-hub", "gateway": "SIMULATED", "public_demo": db.public_demo()}


def _demo_present(c) -> bool:
    return bool(c.execute("SELECT 1 FROM members WHERE demo = 1 LIMIT 1").fetchone())


@app.get("/api/summary")
def summary():
    c = conn()
    week = (db.now().date() - timedelta(days=6)).isoformat()
    q = lambda sql, *a: c.execute(sql, a).fetchone()[0]
    return {
        "members": q("SELECT COUNT(*) FROM members"),
        "observations_7d": q("SELECT COUNT(*) FROM observations WHERE date >= ?", week),
        "rust_7d": q("SELECT COUNT(*) FROM observations WHERE code = 'RUST' AND date >= ?", week),
        "pending_approval": q("SELECT COUNT(*) FROM messages WHERE status = 'pending_approval'"),
        "active_alerts": len(outbreak.active_alerts(c)),
        "officer_messages_new": q("SELECT COUNT(*) FROM officer_messages WHERE status = 'new'"),
        "worklist": len(outbreak.worklist(c)),
        "labels": q("SELECT COUNT(*) FROM labels"),
        "demo": _demo_present(c),
        "public_demo": db.public_demo(),
        "gateway": "SIMULATED",
        "prices_demo": bool((sms.prices() or {}).get("demo", True)),
    }


@app.get("/api/params")
def params():
    p = outbreak.params()
    m = intent.get_model()
    p["intent"] = {"threshold": m.threshold if m else None, "classes": m.classes if m else [],
                   "keywords": sms.KEYWORDS, "model": "hub/intent_model.json", "report": "reports/intent_eval.md"}
    p["image_model_threshold"] = db.model_threshold()
    return p


# ---------- members ----------

class MemberIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=8, max_length=20)
    community: str = Field(min_length=1, max_length=40)   # SLOT_VALUE_RE: it goes into the alert SMS
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    language: Literal["en", "sw", "kik"] = "en"
    consent: StrictBool   # a JSON true/false only ("yes" or 1 is refused with HTTP 422)
    consent_by: str = Field(min_length=1, max_length=80)
    consent_text_version: str = "v1"


@app.get("/api/members")
def list_members():
    c = conn()
    rows = db.rows(c.execute(
        "SELECT m.*, (SELECT COUNT(*) FROM observations o WHERE o.member_id = m.member_id) AS n_observations"
        " FROM members m ORDER BY member_id"))
    return {"members": rows}


@app.post("/api/members", status_code=201)
def register_member(m: MemberIn):
    if m.consent is not True:
        raise HTTPException(400, "The member's consent is needed to register them (consent=true).")
    if not m.consent_by.strip():
        raise HTTPException(400, "Write who explained the consent.")
    if not m.name.strip():
        raise HTTPException(400, "Write the member's name.")
    phone = sms.normalize_phone(m.phone)
    if not re.fullmatch(r"\+\d{10,15}", phone):
        raise HTTPException(400, "Phone number not valid.")
    if not cards.SLOT_VALUE_RE.match(m.community.strip()):
        # The community name goes into the alert SMS, so it may only use letters, digits and . , / : - ( ) % '
        raise HTTPException(400, "Community name not valid (at most 40 characters; letters, digits and . , - ( ) ' only).")
    c = conn()
    with db.Tx(c):
        if db.member_by_phone(c, phone):
            raise HTTPException(409, "That phone number is already registered.")
        mid = db.next_member_id(c)
        ts = db.now_iso()
        c.execute(
            "INSERT INTO members(member_id, name, phone, community, lat, lon, language, consent, consent_date,"
            " consent_by, consent_text_version, created_at, demo) VALUES (?,?,?,?,?,?,?,1,?,?,?,?,0)",
            (mid, m.name.strip(), phone, m.community.strip(),
             None if m.lat is None else round(m.lat, 3), None if m.lon is None else round(m.lon, 3),
             m.language, ts, m.consent_by.strip(), m.consent_text_version, ts))
    return db.member_by_id(c, mid)


@app.delete("/api/members/{member_id}")
def remove_member(member_id: str):
    if not db.delete_member(conn(), member_id.upper()):
        raise HTTPException(404, "Member not found.")
    return {"ok": True, "deleted": member_id.upper()}


# ---------- SMS ----------

class SmsIn(BaseModel):
    body: str = Field(max_length=1000)
    from_: str | None = Field(default=None, alias="from")
    member_id: str | None = None


@app.post("/api/sms/inbound")
def sms_inbound(m: SmsIn):
    """An SMS arrives at the (SIMULATED) gateway. `member_id` instead of `from` = the phone app's
    SIMULATED send button: the hub uses that member's registered phone."""
    c = conn()
    phone = m.from_
    if not phone and m.member_id:
        member = db.member_by_id(c, m.member_id.strip().upper())
        if not member:
            raise HTTPException(404, "member not found")
        phone = member["phone"]
    if not phone:
        raise HTTPException(400, "'from' or 'member_id' is required")
    return sms.route(c, phone, m.body)


@app.get("/api/sms/thread")
def sms_thread(phone: str):
    """What this phone has sent and actually received (pending or rejected broadcasts are not shown)."""
    c = conn()
    p = sms.normalize_phone(phone)
    msgs = db.rows(c.execute(
        "SELECT id, direction, body, card_id, lang, status, created_at, alert_id FROM messages"
        " WHERE phone = ? AND status IN ('received', 'sent_simulated') ORDER BY created_at, id", (p,)))
    for msg in msgs:
        msg.update(cards.sms_length(msg["body"]))
    return {"phone": p, "member": db.member_by_phone(c, p), "messages": msgs, "gateway": "SIMULATED"}


def _card_status(card_id, lang):
    card = cards.get(card_id) if card_id else None
    return (card or {}).get("status", {}).get(lang or cards.DEFAULT_LANG, "unverified") if card else None


@app.get("/api/outbox")
def outbox(status: str | None = None, limit: int = 500):
    c = conn()
    sql = ("SELECT msg.*, m.name, m.community FROM messages msg LEFT JOIN members m ON m.member_id = msg.member_id"
           " WHERE msg.direction = 'out'")
    args = []
    if status:
        sql += " AND msg.status = ?"
        args.append(status)
    sql += " ORDER BY (msg.status = 'pending_approval') DESC, msg.id DESC LIMIT ?"
    args.append(min(limit, 2000))
    msgs = db.rows(c.execute(sql, args))
    for msg in msgs:
        msg["card_status"] = _card_status(msg["card_id"], msg["lang"])
        msg.update(cards.sms_length(msg["body"]))
    return {"messages": msgs, "gateway": "SIMULATED"}


class Decision(BaseModel):
    by: str | None = Field(default=None, max_length=80)


def _decide(msg_id: int, new_status: str, d: Decision | None):
    c = conn()
    with db.Tx(c):
        msg = db.one(c.execute("SELECT * FROM messages WHERE id = ?", (msg_id,)))
        if not msg:
            raise HTTPException(404, "Message not found.")
        if msg["status"] != "pending_approval":
            raise HTTPException(409, f"The message is already '{msg['status']}'.")
        c.execute("UPDATE messages SET status = ?, decided_by = ?, decided_at = ? WHERE id = ?",
                  (new_status, (d.by if d else None) or "co-op staff", db.now_iso(), msg_id))
    return db.one(c.execute("SELECT * FROM messages WHERE id = ?", (msg_id,)))


@app.post("/api/outbox/{msg_id}/approve")
def approve(msg_id: int, d: Decision | None = None):
    """Staff tap: the broadcast goes out (through the SIMULATED gateway)."""
    return _decide(msg_id, "sent_simulated", d)


@app.post("/api/outbox/{msg_id}/reject")
def reject(msg_id: int, d: Decision | None = None):
    return _decide(msg_id, "rejected", d)


# ---------- observations ----------

def _obs_out(o: dict) -> dict:
    o = dict(o)
    o["photo_url"] = f"/api/photos/{o['uid']}" if o.get("photo_path") else None
    o.pop("photo_path", None)
    if o.get("top3"):
        try:
            o["top3"] = json.loads(o["top3"])
        except ValueError:
            pass
    return o


@app.get("/api/observations")
def list_observations(member_id: str | None = None, days: int = 30, limit: int = 500):
    c = conn()
    since = (db.now().date() - timedelta(days=max(days, 1) - 1)).isoformat()
    sql = ("SELECT o.*, m.name, m.community FROM observations o JOIN members m ON m.member_id = o.member_id"
           " WHERE o.date >= ?")
    args = [since]
    if member_id:
        sql += " AND o.member_id = ?"
        args.append(member_id.upper())
    sql += " ORDER BY o.date DESC, o.received_at DESC LIMIT ?"
    args.append(min(limit, 5000))
    return {"observations": [_obs_out(o) for o in db.rows(c.execute(sql, args))]}


def _parse_date(v) -> str:
    s = str(v or "").strip()
    for fmt, n in (("%Y-%m-%d", 10), ("%Y%m%d", 8)):
        try:
            return datetime.strptime(s[:n], fmt).date().isoformat()
        except ValueError:
            continue
    raise HTTPException(400, "date must be YYYY-MM-DD or YYYYMMDD")


def _decode_photo(data_url: str) -> bytes:
    m = re.match(r"^data:image/jpe?g;base64,(.+)$", data_url.strip(), re.DOTALL)
    if not m:
        raise HTTPException(400, "photo must be a JPEG data URL (data:image/jpeg;base64,...)")
    if len(m[1]) > MAX_PHOTO_BYTES * 4 // 3 + 16:
        raise HTTPException(413, "photo larger than 2 MB")
    try:
        raw = base64.b64decode(m[1], validate=False)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "photo is not valid base64")
    if len(raw) > MAX_PHOTO_BYTES:
        raise HTTPException(413, "photo larger than 2 MB")
    if raw[:3] != b"\xff\xd8\xff":
        raise HTTPException(400, "photo is not a JPEG")
    return raw


@app.post("/api/observations/sync")
async def sync_observation(request: Request):
    """Wi-Fi sync from the phone: the full record (+ optional photo as a JPEG data URL, <= 2 MB).
    Merges with the same observation if it already arrived by SMS. Accepts one record or {"records": [...]}."""
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(400, "body must be JSON")
    if isinstance(payload, dict) and isinstance(payload.get("records"), list):
        # Batch: one bad record (e.g. member not registered here) must not block the others.
        results = []
        for r in payload["records"]:
            try:
                results.append(_sync_one(r))
            except HTTPException as e:
                results.append({"ok": False, "obs_id": r.get("obs_id") if isinstance(r, dict) else None,
                                "status": e.status_code, "error": e.detail})
        return {"results": results}
    return _sync_one(payload)


def _sync_one(r: dict) -> dict:
    if not isinstance(r, dict):
        raise HTTPException(400, "record must be an object")
    c = conn()
    member_id = str(r.get("member_id") or "").upper()
    obs_id = str(r.get("obs_id") or "").upper().lstrip("#")
    code = str(r.get("code") or "").upper()
    if not re.fullmatch(r"M\d{4}", member_id) or not re.fullmatch(r"[0-9A-Z]{4}", obs_id):
        raise HTTPException(400, "member_id (M####) and obs_id (4 base36 chars) are required")
    if code not in sms.CODES:
        raise HTTPException(400, f"code must be one of {sms.CODES}")
    if not db.member_by_id(c, member_id):
        raise HTTPException(404, "member not found")
    conf = r.get("conf", 0)
    try:
        conf = float(conf)
    except (TypeError, ValueError):
        raise HTTPException(400, "conf must be a number")
    if isinstance(r.get("conf"), float) and conf <= 1.0:
        conf *= 100  # probability 0-1 -> percent
    conf = int(round(min(max(conf, 0), 100)))
    lat, lon = r.get("lat"), r.get("lon")
    try:
        lat = None if lat in (None, "", "-") else round(float(lat), 2)
        lon = None if lon in (None, "", "-") else round(float(lon), 2)
    except (TypeError, ValueError):
        raise HTTPException(400, "lat/lon must be numbers")
    rec = {"member_id": member_id, "obs_id": obs_id, "code": code, "conf": conf, "date": _parse_date(r.get("date")),
           "lat": lat, "lon": lon, "model_version": r.get("model_version"),
           "top3": r.get("top3") or r.get("probs") or r.get("probabilities"),
           "created_at": r.get("created_at")}
    photo = r.get("photo") or r.get("photo_data_url") or r.get("image")
    raw = _decode_photo(photo) if photo else None
    uid = f"{member_id}-{obs_id}"
    alert = None
    with db.Tx(c):
        row, created = sms.save_observation(c, rec, "sync")
        if raw is not None:
            db.uploads_dir().mkdir(parents=True, exist_ok=True)
            (db.uploads_dir() / f"{uid}.jpg").write_bytes(raw)
            c.execute("UPDATE observations SET photo_path = ? WHERE uid = ?", (f"{uid}.jpg", uid))
        if created:
            alert = outbreak.check(c, row)
    return {"ok": True, "obs_uid": uid, "created": created, "merged": not created, "photo": raw is not None,
            "alert_created": alert["id"] if alert else None}


@app.get("/api/photos/{uid}")
def photo(uid: str):
    """Synced photos are served only through the hub API (never from a public static folder)."""
    if not UID_RE.match(uid):
        raise HTTPException(404)
    row = db.one(conn().execute("SELECT photo_path FROM observations WHERE uid = ?", (uid,)))
    if not row or not row["photo_path"]:
        raise HTTPException(404)
    p = db.uploads_dir() / row["photo_path"]
    if not p.is_file():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})


# ---------- worklist, alerts, map ----------

@app.get("/api/worklist")
def get_worklist():
    c = conn()
    return {"farms": outbreak.worklist(c), "params": outbreak.params()["worklist"],
            "note": "You decide whom to visit. The list only ranks reports; it is not a diagnosis."}


class ActionIn(BaseModel):
    action: Literal["visit_scheduled", "confirmed", "not_confirmed"]
    true_label: str | None = None
    note: str | None = Field(default=None, max_length=500)


@app.post("/api/worklist/{obs_uid}/action")
def worklist_action(obs_uid: str, a: ActionIn):
    """Officer decision on one observation. confirmed / not_confirmed with a true label are saved as
    examples for later retraining (table labels). `obs_uid` = <member_id>-<obs_id> (from /api/worklist)."""
    c = conn()
    obs = db.one(c.execute("SELECT * FROM observations WHERE uid = ?", (obs_uid.upper(),)))
    if not obs:
        raise HTTPException(404, "Observation not found.")
    true_label = a.true_label or None
    model_label = outbreak.CODE_TO_LABEL.get(obs["code"])
    if true_label and true_label not in LABELS:
        raise HTTPException(400, f"true_label must be one of {LABELS}")
    if a.action == "confirmed" and not true_label:
        true_label = model_label
    if a.action == "not_confirmed" and true_label and true_label == model_label:
        raise HTTPException(400, "If not confirmed, the true label must differ from the app's result.")
    ts = db.now_iso()
    with db.Tx(c):
        c.execute("INSERT INTO officer_actions(obs_uid, action, true_label, note, created_at) VALUES (?,?,?,?,?)",
                  (obs["uid"], a.action, true_label, a.note, ts))
        saved_label = False
        if a.action in ("confirmed", "not_confirmed") and true_label:
            c.execute("INSERT INTO labels(obs_uid, model_label, true_label, photo_path, created_at)"
                      " VALUES (?,?,?,?,?)", (obs["uid"], model_label, true_label, obs["photo_path"], ts))
            saved_label = True
    return {"ok": True, "obs_uid": obs["uid"], "action": a.action, "true_label": true_label,
            "saved_as_training_example": saved_label}


@app.get("/api/labels")
def list_labels():
    return {"labels": db.rows(conn().execute("SELECT * FROM labels ORDER BY id DESC"))}


def _alerts_out(c):
    active_ids = {a["id"] for a in outbreak.active_alerts(c)}
    out = []
    for a in db.rows(c.execute("SELECT * FROM alerts ORDER BY id DESC")):
        a["member_ids"] = json.loads(a["member_ids"])
        a["obs_uids"] = json.loads(a["obs_uids"])
        a["active"] = a["id"] in active_ids
        a["messages"] = {r["status"]: r["n"] for r in c.execute(
            "SELECT status, COUNT(*) AS n FROM messages WHERE alert_id = ? GROUP BY status", (a["id"],))}
        out.append(a)
    return out


@app.get("/api/alerts")
def alerts():
    c = conn()
    return {"alerts": _alerts_out(c), "params": outbreak.params()["outbreak"]}


@app.get("/api/map")
def map_data():
    c = conn()
    since = (db.now().date() - timedelta(days=outbreak.WORKLIST_DAYS - 1)).isoformat()
    members = db.rows(c.execute("SELECT member_id, name, community, lat, lon, language, demo FROM members"))
    obs = db.rows(c.execute("SELECT uid, member_id, code, conf, date, lat, lon, received_at FROM observations"
                            " WHERE date >= ?", (since,)))
    # Each farm is coloured by its most serious report (same choice as the worklist), so a later UNSR
    # or HLTH does not hide an earlier RUST.
    worst, count = {}, {}
    for o in obs:
        mid = o["member_id"]
        count[mid] = count.get(mid, 0) + 1
        if mid not in worst or outbreak.seriousness(o) > outbreak.seriousness(worst[mid]):
            worst[mid] = o
    for m in members:
        m["worst"] = worst.get(m["member_id"])
        m["reports_30d"] = count.get(m["member_id"], 0)
    return {"members": members, "observations": obs, "alerts": _alerts_out(c), "params": outbreak.params()}


# ---------- prices ----------

@app.get("/api/prices")
def get_prices():
    p = sms.prices()
    if not p:
        return {"available": False}
    return {"available": True, **p, "sms_slots": sms.price_slots()}


# ---------- content review ----------

@app.get("/api/cards")
def get_cards():
    return cards.load()


class VerifyIn(BaseModel):
    lang: str
    reviewer: str | None = Field(default=None, max_length=80)
    verified: bool = True


def _no_edits_in_public_demo():
    """Anyone with the link can use the public online DEMO copy, so card texts and recordings stay as shipped."""
    if db.public_demo():
        raise HTTPException(403, "Content edits are off in the public online demo. Run the hub on your own computer"
                                 " (./run.sh) to verify cards or upload recordings.")


@app.post("/api/cards/{card_id}/verify")
def verify_card(card_id: str, v: VerifyIn):
    _no_edits_in_public_demo()
    if v.verified and not (v.reviewer or "").strip():
        raise HTTPException(400, "Write the reviewer's name.")
    try:
        card = cards.set_verified(card_id, v.lang, (v.reviewer or "").strip(), v.verified)
    except KeyError:
        raise HTTPException(404, "Card not found.")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return card


AUDIO_EXT = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mpeg": "mp3", "audio/mp3": "mp3", "audio/wav": "wav",
             "audio/x-wav": "wav", "audio/wave": "wav", "audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/aac": "m4a"}


@app.post("/api/cards/{card_id}/audio/{lang}")
async def upload_audio(card_id: str, lang: str, file: UploadFile = File(...), speaker: str = Form(...)):
    """Native-speaker recording for one card. Saved as content/audio/<lang>/<id>.mp3 (ffmpeg) or kept as
    webm/ogg if ffmpeg is missing; audio_source[lang] = 'native:<speaker>' (make_audio.py never overwrites it)."""
    _no_edits_in_public_demo()
    if not re.fullmatch(r"[a-z0-9_]{1,64}", card_id) or not cards.get(card_id):
        raise HTTPException(404, "Card not found.")
    if lang not in cards.languages():
        raise HTTPException(400, "Unknown language.")
    speaker = speaker.strip()
    if not speaker or len(speaker) > 80 or ":" in speaker:
        raise HTTPException(400, "Write the speaker's name (no ':').")
    data = await file.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Recording larger than 10 MB.")
    if len(data) < 100:
        raise HTTPException(400, "Empty recording.")
    ctype = (file.content_type or "").split(";")[0].strip().lower()
    ext = AUDIO_EXT.get(ctype) or Path(file.filename or "").suffix.lstrip(".").lower()
    if ext not in {"webm", "ogg", "mp3", "wav", "m4a"}:
        raise HTTPException(400, "Audio format not recognised (webm, ogg, mp3, wav, m4a).")
    folder = db.content_dir() / "audio" / lang
    folder.mkdir(parents=True, exist_ok=True)
    final_ext = ext
    ffmpeg = shutil.which("ffmpeg")
    if ext != "mp3" and ffmpeg:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / f"in.{ext}"
            src.write_bytes(data)
            dst = Path(tmp) / "out.mp3"
            r = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "22050",
                                "-b:a", "32k", str(dst)], capture_output=True, timeout=120)
            if r.returncode == 0 and dst.exists():
                data, final_ext = dst.read_bytes(), "mp3"
    target = folder / f"{card_id}.{final_ext}"
    target.write_bytes(data)
    rel = f"audio/{lang}/{card_id}.{final_ext}"
    card = cards.set_native_audio(card_id, lang, rel, speaker)
    return {"ok": True, "path": rel, "converted_to_mp3": final_ext == "mp3" and ext != "mp3", "card": card}


# ---------- officer messages ----------

@app.get("/api/officer/messages")
def officer_messages():
    c = conn()
    rows = db.rows(c.execute(
        "SELECT om.*, m.name, m.community FROM officer_messages om LEFT JOIN members m ON m.member_id = om.member_id"
        " ORDER BY om.id DESC LIMIT 500"))
    return {"messages": rows}


@app.post("/api/officer/messages/{msg_id}/read")
def officer_message_read(msg_id: int):
    c = conn()
    with db.Tx(c):
        cur = c.execute("UPDATE officer_messages SET status = 'read' WHERE id = ?", (msg_id,))
    if cur.rowcount == 0:
        raise HTTPException(404)
    return {"ok": True}


# ---------- DEMO ----------

@app.post("/api/demo/reset")
def demo_reset():
    """Wipe the hub database (and synced photos) and load the DEMO data again."""
    c = conn()
    db.wipe(c)
    counts = seed.seed(c)
    return {"ok": True, **counts}


# ---------- static files (mounted last so /api routes win) ----------

app.mount("/app", StaticFiles(directory=db.app_dir(), html=True, check_dir=False), name="app")
app.mount("/content", StaticFiles(directory=db.content_dir(), check_dir=False), name="content")
app.mount("/hub", StaticFiles(directory=STATIC, html=True, check_dir=False), name="hub")
