"""SQLite storage for the hub (stdlib sqlite3 only).

Paths can be changed with environment variables (the tests use temporary copies):
  CAFETAL_DB       SQLite file            (default hub/cafetal.db)
  CAFETAL_CONTENT  content folder         (default content/)
  CAFETAL_PRICES   reference price table  (default data/prices.json)
  CAFETAL_UPLOADS  synced photos          (default hub/uploads/, never served as static files)
  CAFETAL_APP      phone PWA folder       (default app/)
"""
import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

HUB_DIR = Path(__file__).resolve().parent
ROOT = HUB_DIR.parent


def db_path() -> Path:
    return Path(os.environ.get("CAFETAL_DB", HUB_DIR / "cafetal.db"))


def content_dir() -> Path:
    return Path(os.environ.get("CAFETAL_CONTENT", ROOT / "content"))


def prices_path() -> Path:
    return Path(os.environ.get("CAFETAL_PRICES", ROOT / "data" / "prices.json"))


def uploads_dir() -> Path:
    return Path(os.environ.get("CAFETAL_UPLOADS", HUB_DIR / "uploads"))


def app_dir() -> Path:
    return Path(os.environ.get("CAFETAL_APP", ROOT / "app"))


def now() -> datetime:
    """Local time of the hub computer, to the second. Tests may monkeypatch this."""
    return datetime.now().replace(microsecond=0)


def now_iso() -> str:
    return now().isoformat(timespec="seconds")


def model_threshold() -> float:
    """Confidence threshold of the image model (app/model/labels.json), default 0.70."""
    try:
        return float(json.loads((app_dir() / "model" / "labels.json").read_text())["threshold"])
    except Exception:
        return 0.70


SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
  member_id TEXT PRIMARY KEY,             -- M + 4 digits
  name TEXT NOT NULL,
  phone TEXT NOT NULL UNIQUE,
  community TEXT NOT NULL,
  lat REAL, lon REAL,                     -- plot location (rounded to 2 decimals)
  language TEXT NOT NULL DEFAULT 'es',    -- es | tzh | en
  consent INTEGER NOT NULL,               -- must be 1
  consent_date TEXT NOT NULL,
  consent_by TEXT NOT NULL,               -- staff member who explained it
  consent_text_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  demo INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS observations (
  uid TEXT PRIMARY KEY,                   -- "<member_id>-<obs_id>" (obs ids are only unique per phone)
  obs_id TEXT NOT NULL,                   -- 4-char base36 id from the phone
  member_id TEXT NOT NULL,
  code TEXT NOT NULL,                     -- SANO ROYA MINA PHOM CERC ACAR OTRO DUDA
  conf INTEGER NOT NULL,                  -- 0-100
  date TEXT NOT NULL,                     -- YYYY-MM-DD (phone local date)
  lat REAL, lon REAL,
  loc_source TEXT,                        -- report | plot
  raw_sms TEXT,
  received_at TEXT NOT NULL,
  photo_path TEXT,                        -- file name inside the uploads folder
  source TEXT NOT NULL,                   -- sms | sync | sms+sync
  model_version TEXT,
  top3 TEXT,                              -- JSON, optional
  created_at TEXT,                        -- phone timestamp, from sync
  demo INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  direction TEXT NOT NULL,                -- in | out
  phone TEXT NOT NULL,
  member_id TEXT,
  body TEXT NOT NULL,
  card_id TEXT,                           -- outbound: the cards.json card the text comes from
  lang TEXT,
  status TEXT NOT NULL,                   -- received | sent_simulated | pending_approval | rejected
  created_at TEXT NOT NULL,
  alert_id INTEGER,
  decided_by TEXT, decided_at TEXT,       -- staff approval / rejection of broadcasts
  demo INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  community TEXT NOT NULL,
  lat REAL NOT NULL, lon REAL NOT NULL,   -- centre of the cluster
  n_reports INTEGER NOT NULL,             -- distinct members
  member_ids TEXT NOT NULL,               -- JSON list
  obs_uids TEXT NOT NULL,                 -- JSON list
  status TEXT NOT NULL,                   -- active | closed
  demo INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS officer_actions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  obs_uid TEXT NOT NULL,
  action TEXT NOT NULL,                   -- visit_scheduled | confirmed | not_confirmed
  true_label TEXT,
  note TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS labels (       -- officer-checked examples for later retraining
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  obs_uid TEXT NOT NULL,
  model_label TEXT,
  true_label TEXT NOT NULL,
  photo_path TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS officer_messages (  -- free-text SMS forwarded to the officer
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  message_id INTEGER,
  member_id TEXT,
  phone TEXT NOT NULL,
  body TEXT NOT NULL,
  intent TEXT,
  conf REAL,
  status TEXT NOT NULL DEFAULT 'new',     -- new | read
  created_at TEXT NOT NULL,
  demo INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS retired_member_ids (  -- ids of deleted members, never given out again; no personal data
  member_id TEXT PRIMARY KEY
);
CREATE INDEX IF NOT EXISTS idx_obs_member ON observations(member_id);
CREATE INDEX IF NOT EXISTS idx_msg_phone ON messages(phone);
"""

TABLES = ["members", "observations", "messages", "alerts", "officer_actions", "labels", "officer_messages"]

_lock = threading.RLock()  # one writer at a time; the hub is a single small process


def connect(path: Path | None = None) -> sqlite3.Connection:
    p = Path(path or db_path())
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p, check_same_thread=False, isolation_level=None)  # autocommit; we use explicit BEGIN
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA)
    return conn


class Tx:
    """`with Tx(conn):` runs a block in one transaction, holding the hub's write lock."""

    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        _lock.acquire()
        self.conn.execute("BEGIN IMMEDIATE")
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        try:
            self.conn.execute("ROLLBACK" if exc_type else "COMMIT")
        finally:
            _lock.release()
        return False


def rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def one(cur) -> dict | None:
    r = cur.fetchone()
    return dict(r) if r else None


def wipe(conn) -> None:
    # retired_member_ids is kept on purpose: phones of deleted members may still hold those ids.
    with Tx(conn):
        for t in TABLES:
            conn.execute(f"DELETE FROM {t}")
        conn.execute("DELETE FROM sqlite_sequence")
    folder = uploads_dir()
    if folder.is_dir():
        for f in folder.glob("*.jpg"):
            f.unlink(missing_ok=True)


def member_by_phone(conn, phone: str) -> dict | None:
    return one(conn.execute("SELECT * FROM members WHERE phone = ?", (phone,)))


def member_by_id(conn, member_id: str) -> dict | None:
    return one(conn.execute("SELECT * FROM members WHERE member_id = ?", (member_id,)))


def next_member_id(conn) -> str:
    """Highest id ever given out + 1. Ids of deleted members are never reused: the deleted person's phone may
    still send reports under the old id, and they must not land on someone else."""
    r = conn.execute("SELECT MAX(CAST(SUBSTR(member_id, 2) AS INTEGER)) FROM"
                     " (SELECT member_id FROM members UNION ALL SELECT member_id FROM retired_member_ids)").fetchone()[0]
    n = (r or 0) + 1
    if n > 9999:
        raise ValueError("member ids exhausted (M9999)")
    return f"M{n:04d}"


def add_message(conn, direction, phone, body, status, member_id=None, card_id=None, lang=None,
                alert_id=None, created_at=None, demo=0) -> int:
    cur = conn.execute(
        "INSERT INTO messages(direction, phone, member_id, body, card_id, lang, status, created_at, alert_id, demo)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (direction, phone, member_id, body, card_id, lang, status, created_at or now_iso(), alert_id, demo))
    return cur.lastrowid


def delete_member(conn, member_id: str) -> bool:
    """Remove a member and everything stored about them (observations, messages, labels, photos)."""
    m = member_by_id(conn, member_id)
    if not m:
        return False
    photos = [r["photo_path"] for r in conn.execute(
        "SELECT photo_path FROM observations WHERE member_id = ? AND photo_path IS NOT NULL", (member_id,))]
    with Tx(conn):
        uids = [r[0] for r in conn.execute("SELECT uid FROM observations WHERE member_id = ?", (member_id,))]
        for uid in uids:
            conn.execute("DELETE FROM officer_actions WHERE obs_uid = ?", (uid,))
            conn.execute("DELETE FROM labels WHERE obs_uid = ?", (uid,))
        conn.execute("DELETE FROM observations WHERE member_id = ?", (member_id,))
        conn.execute("DELETE FROM messages WHERE member_id = ? OR phone = ?", (member_id, m["phone"]))
        conn.execute("DELETE FROM officer_messages WHERE member_id = ? OR phone = ?", (member_id, m["phone"]))
        conn.execute("DELETE FROM members WHERE member_id = ?", (member_id,))
        conn.execute("INSERT OR IGNORE INTO retired_member_ids(member_id) VALUES (?)", (member_id,))
        # Alerts keep only counts; drop the member id from their lists.
        for a in rows(conn.execute("SELECT id, member_ids, obs_uids FROM alerts")):
            mids = [x for x in json.loads(a["member_ids"]) if x != member_id]
            ous = [x for x in json.loads(a["obs_uids"]) if x not in uids]
            conn.execute("UPDATE alerts SET member_ids = ?, obs_uids = ? WHERE id = ?",
                         (json.dumps(mids), json.dumps(ous), a["id"]))
    for p in photos:
        (uploads_dir() / p).unlink(missing_ok=True)
    return True
