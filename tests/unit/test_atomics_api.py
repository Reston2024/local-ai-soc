"""
Wave 0 TDD stubs for Phase 40 atomics API.
P40-T02: GET /api/atomics catalog endpoint.
P40-T05: POST /api/atomics/validate pass/fail.
All stubs SKIP RED until Plans 02+03 implement the router.
"""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

try:
    from backend.main import create_app
    from backend.services.atomics.atomics_store import AtomicsStore
    from backend.core.auth import verify_token
    from backend.core.rbac import OperatorContext
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

# Validate endpoint requires Plan 03 — skip until POST /api/atomics/validate is implemented
try:
    from backend.api.atomics import router as _atomics_router
    _validate_routes = [r.path for r in _atomics_router.routes if hasattr(r, 'path')]
    _VALIDATE_AVAILABLE = any("/atomics/validate" in p for p in _validate_routes)
except Exception:
    _VALIDATE_AVAILABLE = False


def _make_authed_app(atomics_store, sqlite_conn):
    """Build test app with atomics store injected and auth bypassed."""
    app = create_app()
    app.state.atomics_store = atomics_store
    app.state.sqlite_store = SimpleNamespace(_conn=sqlite_conn)
    _ctx = OperatorContext(operator_id="test-admin", username="test", role="admin")
    app.dependency_overrides[verify_token] = lambda: _ctx
    return TestClient(app, raise_server_exceptions=False)


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Minimal detections table so test_validate_pass setup doesn't crash
    conn.execute(
        """CREATE TABLE IF NOT EXISTS detections (
            id TEXT PRIMARY KEY, rule_id TEXT, rule_name TEXT,
            severity TEXT, created_at TEXT, attack_technique TEXT
        )"""
    )
    conn.commit()
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
    conn = _make_conn()
    store = AtomicsStore(conn)
    store.bulk_insert(SAMPLE_TESTS)
    client = _make_authed_app(store, conn)
    resp = client.get("/api/atomics")
    assert resp.status_code == 200
    body = resp.json()
    assert "techniques" in body
    assert "total_techniques" in body
    assert "total_tests" in body
    assert len(body["techniques"]) >= 1

@pytest.mark.skipif(not _VALIDATE_AVAILABLE, reason="Wave 0 stub — POST /api/atomics/validate not yet implemented (Plan 03)")
def test_validate_pass():
    """POST /api/atomics/validate returns pass when matching detection exists within 5 min."""
    conn = _make_conn()
    store = AtomicsStore(conn)
    store.bulk_insert(SAMPLE_TESTS)
    # Insert a fake detection within the last 5 minutes
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute(
        "INSERT OR IGNORE INTO detections (id, rule_id, rule_name, severity, created_at, attack_technique) "
        "VALUES ('det-001', 'sigma_1', 'Test Rule', 'high', ?, 'T1059.001')",
        (now_iso,)
    )
    conn.commit()
    client = _make_authed_app(store, conn)
    resp = client.post(
        "/api/atomics/validate",
        json={"technique_id": "T1059.001", "test_number": 1},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "pass"
    assert body["detection_id"] == "det-001"

@pytest.mark.skipif(not _VALIDATE_AVAILABLE, reason="Wave 0 stub — POST /api/atomics/validate not yet implemented (Plan 03)")
def test_validate_fail():
    """POST /api/atomics/validate returns fail when no detection in 5-minute window."""
    conn = _make_conn()
    store = AtomicsStore(conn)
    store.bulk_insert(SAMPLE_TESTS)
    client = _make_authed_app(store, conn)
    resp = client.post(
        "/api/atomics/validate",
        json={"technique_id": "T1059.001", "test_number": 1},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "fail"
    assert body["detection_id"] is None
