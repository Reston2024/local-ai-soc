"""
Wave 0 TDD stubs for Phase 40 atomics API.
P40-T02: GET /api/atomics catalog endpoint.
P40-T05: POST /api/atomics/validate pass/fail.
All stubs SKIP RED until Plans 02+03 implement the router.
"""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

try:
    from backend.main import create_app
    from backend.services.atomics.atomics_store import AtomicsStore
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

SAMPLE_TESTS = [
    {
        "technique_id": "T1059.001", "display_name": "Command and Scripting: PowerShell",
        "test_number": 1, "test_name": "Mimikatz", "auto_generated_guid": "abc",
        "description": "Desc.", "supported_platforms": '["windows"]',
        "executor_name": "command_prompt", "elevation_required": 0,
        "command": "cmd /c echo #{var}", "cleanup_command": "", "prereq_command": "",
        "input_arguments": "{}",
    },
]

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — atomics router not yet implemented")
def test_get_atomics_returns_200():
    """GET /api/atomics returns 200 with techniques list + totals."""
    app = create_app()
    conn = _make_conn()
    store = AtomicsStore(conn)
    store.bulk_insert(SAMPLE_TESTS)
    app.state.atomics_store = store
    # Also set sqlite_store._conn so detections query works
    app.state.sqlite_store._conn = conn
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/atomics", headers={"Authorization": "Bearer test"})
    assert resp.status_code == 200
    body = resp.json()
    assert "techniques" in body
    assert "total_techniques" in body
    assert "total_tests" in body
    assert len(body["techniques"]) >= 1

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — atomics router not yet implemented")
def test_validate_pass():
    """POST /api/atomics/validate returns pass when matching detection exists within 5 min."""
    app = create_app()
    conn = _make_conn()
    store = AtomicsStore(conn)
    store.bulk_insert(SAMPLE_TESTS)
    app.state.atomics_store = store
    # Insert a fake detection within the last 5 minutes
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute(
        "INSERT OR IGNORE INTO detections (id, rule_id, rule_name, severity, created_at, attack_technique) "
        "VALUES ('det-001', 'sigma_1', 'Test Rule', 'high', ?, 'T1059.001')",
        (now_iso,)
    )
    conn.commit()
    app.state.sqlite_store._conn = conn
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/api/atomics/validate",
        json={"technique_id": "T1059.001", "test_number": 1},
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "pass"
    assert body["detection_id"] == "det-001"

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — atomics router not yet implemented")
def test_validate_fail():
    """POST /api/atomics/validate returns fail when no detection in 5-minute window."""
    app = create_app()
    conn = _make_conn()
    store = AtomicsStore(conn)
    store.bulk_insert(SAMPLE_TESTS)
    app.state.atomics_store = store
    app.state.sqlite_store._conn = conn
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/api/atomics/validate",
        json={"technique_id": "T1059.001", "test_number": 1},
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "fail"
    assert body["detection_id"] is None
