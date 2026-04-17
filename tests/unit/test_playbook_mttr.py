"""
Unit tests for the GET /api/playbooks/mttr endpoint.

Validates playbook MTTR (Mean Time To Resolve) instrumentation:
    - Empty database returns null mttr / zero sample_size.
    - Single completed run returns correct duration.
    - Multiple runs across multiple playbooks produces correct per-playbook breakdown.

Uses FastAPI TestClient with a mocked SQLiteStore — no real I/O.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.playbooks import router as playbooks_router

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso(dt: datetime) -> str:
    """Return ISO-8601 string for a datetime (matches utcnow_iso() format)."""
    return dt.isoformat()


def _build_app(rows: list[dict]) -> TestClient:
    """
    Build a FastAPI app with the playbooks router and a mocked SQLite store
    whose ``_conn.execute(...).fetchall()`` returns the supplied rows.

    Rows should be dicts with keys:
        run_id, playbook_id, started_at, completed_at, playbook_name
    """
    app = FastAPI()
    app.include_router(playbooks_router)

    # Mock SQLite conn chain: _conn.execute(sql).fetchall() -> rows
    fetch_cursor = MagicMock()
    # Rows need to behave like sqlite3.Row — dict(row) must produce the fields.
    # MagicMock dict() conversion is awkward, so instead we return objects that
    # dict() can accept: use plain dicts and let the endpoint's `dict(r)` call
    # copy them through dict.__init__.
    fetch_cursor.fetchall.return_value = rows

    conn_mock = MagicMock()
    conn_mock.execute.return_value = fetch_cursor

    sqlite_mock = MagicMock()
    sqlite_mock._conn = conn_mock

    stores_mock = MagicMock()
    stores_mock.sqlite = sqlite_mock

    app.state.stores = stores_mock
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_mttr_empty_database_returns_nulls():
    """With no qualifying rows, endpoint returns nulls + sample_size=0."""
    client = _build_app(rows=[])
    resp = client.get("/api/playbooks/mttr")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["mttr_seconds"] is None
    assert data["p50_seconds"] is None
    assert data["p95_seconds"] is None
    assert data["sample_size"] == 0
    assert data["by_playbook"] == []


def test_mttr_single_completed_run_returns_correct_duration():
    """A single completed run with 300s duration should produce mttr=300.0."""
    started = datetime(2026, 4, 17, 12, 0, 0, tzinfo=timezone.utc)
    completed = started + timedelta(seconds=300)

    rows = [
        {
            "run_id": "run-1",
            "playbook_id": "pb-A",
            "playbook_name": "Phishing Response",
            "started_at": _iso(started),
            "completed_at": _iso(completed),
        }
    ]
    client = _build_app(rows=rows)
    resp = client.get("/api/playbooks/mttr")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["sample_size"] == 1
    assert data["mttr_seconds"] == pytest.approx(300.0)
    assert data["p50_seconds"] == pytest.approx(300.0)
    assert data["p95_seconds"] == pytest.approx(300.0)

    assert len(data["by_playbook"]) == 1
    pb = data["by_playbook"][0]
    assert pb["playbook_id"] == "pb-A"
    assert pb["name"] == "Phishing Response"
    assert pb["mttr_seconds"] == pytest.approx(300.0)
    assert pb["sample_size"] == 1


def test_mttr_multiple_runs_across_playbooks_breakdown():
    """Two playbooks with different durations yield a correct per-playbook breakdown."""
    base = datetime(2026, 4, 17, 10, 0, 0, tzinfo=timezone.utc)

    # Playbook A: two runs — 100s and 300s (mean = 200s)
    # Playbook B: one run — 600s
    rows = [
        {
            "run_id": "r1",
            "playbook_id": "pb-A",
            "playbook_name": "Playbook A",
            "started_at": _iso(base),
            "completed_at": _iso(base + timedelta(seconds=100)),
        },
        {
            "run_id": "r2",
            "playbook_id": "pb-A",
            "playbook_name": "Playbook A",
            "started_at": _iso(base),
            "completed_at": _iso(base + timedelta(seconds=300)),
        },
        {
            "run_id": "r3",
            "playbook_id": "pb-B",
            "playbook_name": "Playbook B",
            "started_at": _iso(base),
            "completed_at": _iso(base + timedelta(seconds=600)),
        },
    ]
    client = _build_app(rows=rows)
    resp = client.get("/api/playbooks/mttr")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Overall: mean(100,300,600) = 333.333...
    assert data["sample_size"] == 3
    assert data["mttr_seconds"] == pytest.approx((100 + 300 + 600) / 3.0)

    # by_playbook list — sorted by playbook_id
    by_pb = {b["playbook_id"]: b for b in data["by_playbook"]}
    assert "pb-A" in by_pb
    assert "pb-B" in by_pb

    assert by_pb["pb-A"]["sample_size"] == 2
    assert by_pb["pb-A"]["mttr_seconds"] == pytest.approx(200.0)
    assert by_pb["pb-A"]["name"] == "Playbook A"

    assert by_pb["pb-B"]["sample_size"] == 1
    assert by_pb["pb-B"]["mttr_seconds"] == pytest.approx(600.0)
    assert by_pb["pb-B"]["name"] == "Playbook B"
