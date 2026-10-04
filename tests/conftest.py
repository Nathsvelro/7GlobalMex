"""Hub test fixtures: every test gets its own temporary database, content copy, price table and uploads folder.

Run:  .venv/bin/pip install pytest httpx && .venv/bin/python -m pytest tests -q
"""
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

collect_ignore = ["e2e"]  # browser tests live in tests/e2e (another owner)


@pytest.fixture
def env(tmp_path, monkeypatch):
    content = tmp_path / "content"
    content.mkdir()
    shutil.copy(ROOT / "content" / "cards.json", content / "cards.json")
    prices = tmp_path / "prices.json"
    shutil.copy(ROOT / "data" / "prices.json", prices)
    monkeypatch.setenv("CAFETAL_DB", str(tmp_path / "hub.db"))
    monkeypatch.setenv("CAFETAL_CONTENT", str(content))
    monkeypatch.setenv("CAFETAL_PRICES", str(prices))
    monkeypatch.setenv("CAFETAL_UPLOADS", str(tmp_path / "uploads"))
    return tmp_path


@pytest.fixture
def client(env):
    from fastapi.testclient import TestClient
    from hub.main import app
    return TestClient(app)


@pytest.fixture
def conn(env, client):
    """The same SQLite connection the app uses."""
    from hub import main
    return main.conn()


def ymd(days_ago: int = 0) -> str:
    return (date.today() - timedelta(days=days_ago)).strftime("%Y%m%d")


def register(client, name="Test Member", phone="+254700001000", community="Ondera Juu", lat=-0.52, lon=37.32,
             language="en"):
    r = client.post("/api/members", json={"name": name, "phone": phone, "community": community, "lat": lat,
                                          "lon": lon, "language": language, "consent": True,
                                          "consent_by": "Personal de prueba"})
    assert r.status_code == 201, r.text
    return r.json()


def sms(client, phone, body):
    r = client.post("/api/sms/inbound", json={"from": phone, "body": body})
    assert r.status_code == 200, r.text
    return r.json()


def card_ids(result):
    return [r["card_id"] for r in result["replies"]]
