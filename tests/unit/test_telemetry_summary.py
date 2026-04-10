"""
Wave 0 test stubs for Phase 35 telemetry summary endpoint.
P35-T05 — GET /api/telemetry/summary returns 24h telemetry rollup.

Uses FastAPI TestClient with mocked stores — no real disk I/O.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Try importing the telemetry router — skip if endpoint not yet implemented
# ---------------------------------------------------------------------------
try:
    from backend.api import telemetry as telemetry_api  # noqa: F401
    _TELEMETRY_API_AVAILABLE = True
except ImportError:
    _TELEMETRY_API_AVAILABLE = False


def _build_telemetry_app(
    type_rows=None,
    ioc_rows=None,
    det_count=0,
    asset_count=0,
    top_rows=None,
):
    """Build a minimal FastAPI app with telemetry router for testing."""
    from fastapi.testclient import TestClient

    from backend.core.auth import verify_token
    from backend.core.rbac import OperatorContext
    from backend.main import create_app

    app = create_app()

    # --- Mock DuckDB store ---
    duck_mock = AsyncMock()
    # fetch_all returns different data depending on which query runs
    # We map calls by call order: first call = event_type_counts, second = ioc
    duck_fetch_returns = [
        type_rows if type_rows is not None else [],
        ioc_rows if ioc_rows is not None else [[0]],
    ]
    duck_mock.fetch_all = AsyncMock(side_effect=duck_fetch_returns)

    # --- Mock SQLite store ---
    sqlite_mock = MagicMock()
    conn_mock = MagicMock()
    sqlite_mock._conn = conn_mock

    # Chained cursor returns for three execute calls:
    # 1. SELECT COUNT(*) FROM detections
    # 2. SELECT COUNT(*) FROM assets
    # 3. SELECT rule_name, severity, COUNT(*) FROM detections
    det_cursor = MagicMock()
    det_cursor.fetchone.return_value = [det_count]
    asset_cursor = MagicMock()
    asset_cursor.fetchone.return_value = [asset_count]
    top_cursor = MagicMock()
    top_cursor.fetchall.return_value = top_rows if top_rows is not None else []

    conn_mock.execute.side_effect = [det_cursor, asset_cursor, top_cursor]

    stores_mock = MagicMock()
    stores_mock.duckdb = duck_mock
    stores_mock.sqlite = sqlite_mock
    app.state.stores = stores_mock

    # Auth bypass
    _ctx = OperatorContext(operator_id="test-admin", username="test", role="admin")
    app.dependency_overrides[verify_token] = lambda: _ctx

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Test 1: Response contains required top-level keys with correct types
# ---------------------------------------------------------------------------

def test_telemetry_summary_response_shape():
    """Response must contain all required keys with correct Python types."""
    client = _build_telemetry_app(
        type_rows=[["alert", 5], ["dns", 2]],
        ioc_rows=[[3]],
        det_count=10,
        asset_count=4,
        top_rows=[["Mimikatz Use", "high", 3]],
    )
    resp = client.get("/api/telemetry/summary")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    data = resp.json()
    # Required keys
    assert "event_type_counts" in data
    assert "total_events" in data
    assert "total_detections" in data
    assert "ioc_matches" in data
    assert "assets_count" in data
    assert "top_rules" in data

    # Types
    assert isinstance(data["event_type_counts"], dict)
    assert isinstance(data["total_events"], int)
    assert isinstance(data["total_detections"], int)
    assert isinstance(data["ioc_matches"], int)
    assert isinstance(data["assets_count"], int)
    assert isinstance(data["top_rules"], list)


# ---------------------------------------------------------------------------
# Test 2: event_type_counts maps event_type strings to integer counts
# ---------------------------------------------------------------------------

def test_telemetry_summary_event_type_counts():
    """event_type_counts must be a dict mapping event_type strings to int counts."""
    client = _build_telemetry_app(
        type_rows=[["alert", 100], ["dns", 50], ["http", 25]],
        ioc_rows=[[0]],
        det_count=0,
        asset_count=0,
        top_rows=[],
    )
    resp = client.get("/api/telemetry/summary")
    assert resp.status_code == 200

    data = resp.json()
    counts = data["event_type_counts"]
    assert counts.get("alert") == 100
    assert counts.get("dns") == 50
    assert counts.get("http") == 25
    # total_events should sum counts
    assert data["total_events"] == 175


# ---------------------------------------------------------------------------
# Test 3: top_rules items have required fields (rule_name, severity, count)
# ---------------------------------------------------------------------------

def test_telemetry_summary_top_rules_shape():
    """Each item in top_rules must have rule_name (str), severity (str), count (int)."""
    client = _build_telemetry_app(
        type_rows=[],
        ioc_rows=[[0]],
        det_count=5,
        asset_count=1,
        top_rows=[
            ["Lateral Movement Detected", "critical", 7],
            ["Brute Force Attempt", "high", 3],
        ],
    )
    resp = client.get("/api/telemetry/summary")
    assert resp.status_code == 200

    top_rules = resp.json()["top_rules"]
    assert len(top_rules) == 2

    for rule in top_rules:
        assert "rule_name" in rule
        assert "severity" in rule
        assert "count" in rule
        assert isinstance(rule["rule_name"], str)
        assert isinstance(rule["severity"], str)
        assert isinstance(rule["count"], int)

    assert top_rules[0]["rule_name"] == "Lateral Movement Detected"
    assert top_rules[0]["severity"] == "critical"
    assert top_rules[0]["count"] == 7


# ---------------------------------------------------------------------------
# Test 4: Endpoint returns 200 when DuckDB and SQLite return empty (no events)
# ---------------------------------------------------------------------------

def test_telemetry_summary_empty_stores():
    """Endpoint must return HTTP 200 with zeroed values when stores are empty."""
    client = _build_telemetry_app(
        type_rows=[],
        ioc_rows=[[0]],
        det_count=0,
        asset_count=0,
        top_rows=[],
    )
    resp = client.get("/api/telemetry/summary")
    assert resp.status_code == 200

    data = resp.json()
    assert data["event_type_counts"] == {}
    assert data["total_events"] == 0
    assert data["total_detections"] == 0
    assert data["ioc_matches"] == 0
    assert data["assets_count"] == 0
    assert data["top_rules"] == []
