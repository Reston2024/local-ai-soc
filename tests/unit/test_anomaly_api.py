"""
Wave 0 TDD stubs for Phase 42 anomaly API endpoints.
P42-T03: anomaly_score DuckDB column.
P42-T04: GET /api/anomaly list + threshold filter.
P42-T05: GET /api/anomaly/entity profile endpoint.
P42-T06: GET /api/anomaly/trend + synthetic detection creation.

Stubs 1-4 GREEN once backend/api/anomaly.py exists (Plan 42-03).
Stub 5 (test_anomaly_score_in_duckdb) GREEN since Plan 42-02 added the column.
Stub 6 tests synthetic detection via ingest pipeline.
"""
from __future__ import annotations

import asyncio
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Try importing anomaly router — skip API stubs if not yet implemented
# ---------------------------------------------------------------------------
try:
    from backend.api.anomaly import router as anomaly_router
    from backend.core.auth import verify_token
    from backend.core.rbac import OperatorContext
    _API_AVAILABLE = True
except ImportError:
    _API_AVAILABLE = False

_skip_api = pytest.mark.skipif(not _API_AVAILABLE, reason="anomaly API not yet implemented (Plan 42-03)")


def _make_app_with_mock_stores(mock_rows=None):
    """Build a minimal test app with mocked stores and auth bypassed."""
    if mock_rows is None:
        mock_rows = []

    app = FastAPI()
    app.include_router(anomaly_router)

    # Mock DuckDB store returning mock_rows
    mock_duckdb = MagicMock()
    mock_duckdb.fetch_df = AsyncMock(return_value=mock_rows)

    mock_stores = SimpleNamespace(duckdb=mock_duckdb)
    app.state.stores = mock_stores

    # Bypass auth
    _ctx = OperatorContext(operator_id="test-admin", username="test", role="admin")
    app.dependency_overrides[verify_token] = lambda: _ctx

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Stub 1 — GET /api/anomaly returns 200 with correct shape
# ---------------------------------------------------------------------------
@_skip_api
def test_list_anomalies_endpoint_exists():
    """GET /api/anomaly returns 200 with {"anomalies": [...], "total": int}."""
    client = _make_app_with_mock_stores([])
    resp = client.get("/api/anomaly")
    assert resp.status_code == 200
    body = resp.json()
    assert "anomalies" in body
    assert "total" in body
    assert isinstance(body["anomalies"], list)
    assert isinstance(body["total"], int)


# ---------------------------------------------------------------------------
# Stub 2 — GET /api/anomaly?min_score=0.7 filters by score
# ---------------------------------------------------------------------------
@_skip_api
def test_list_anomalies_threshold_filter():
    """GET /api/anomaly?min_score=0.7 returns only events with anomaly_score >= 0.7."""
    rows = [
        {"event_id": "e1", "timestamp": "2026-01-01T00:00:00", "hostname": "host1",
         "process_name": "cmd.exe", "src_ip": "192.168.1.1", "event_type": "process",
         "severity": "high", "anomaly_score": 0.9},
        {"event_id": "e2", "timestamp": "2026-01-01T00:00:01", "hostname": "host1",
         "process_name": "svchost.exe", "src_ip": "192.168.1.2", "event_type": "network",
         "severity": "medium", "anomaly_score": 0.75},
    ]
    client = _make_app_with_mock_stores(rows)
    resp = client.get("/api/anomaly?min_score=0.7")
    assert resp.status_code == 200
    body = resp.json()
    for event in body["anomalies"]:
        assert event.get("anomaly_score", 0.0) >= 0.7


# ---------------------------------------------------------------------------
# Stub 3 — GET /api/anomaly/entity returns entity profile
# ---------------------------------------------------------------------------
@_skip_api
def test_entity_profile_endpoint():
    """GET /api/anomaly/entity?subnet=192.168.1&process=svchost.exe returns profile shape."""
    rows = [
        {"event_id": "e1", "timestamp": "2026-01-01T00:00:00", "anomaly_score": 0.8},
    ]
    client = _make_app_with_mock_stores(rows)
    resp = client.get("/api/anomaly/entity?subnet=192.168.1&process=svchost.exe")
    assert resp.status_code == 200
    body = resp.json()
    assert "entity_key" in body
    assert "event_count" in body
    assert "scores" in body
    assert isinstance(body["event_count"], int)
    assert isinstance(body["scores"], list)


# ---------------------------------------------------------------------------
# Stub 4 — GET /api/anomaly/trend returns time-series scores
# ---------------------------------------------------------------------------
@_skip_api
def test_score_trend_endpoint():
    """GET /api/anomaly/trend?entity_key=... returns list of {timestamp, score} dicts."""
    rows = [
        {"timestamp": "2026-01-01T00:00:00", "anomaly_score": 0.8},
        {"timestamp": "2026-01-01T01:00:00", "anomaly_score": 0.85},
    ]
    client = _make_app_with_mock_stores(rows)
    resp = client.get("/api/anomaly/trend?entity_key=192.168.1__svchost.exe")
    assert resp.status_code == 200
    body = resp.json()
    assert "trend" in body
    assert "entity_key" in body
    assert isinstance(body["trend"], list)
    for item in body["trend"]:
        assert "timestamp" in item
        assert "score" in item


# ---------------------------------------------------------------------------
# Stub 5 — anomaly_score column exists in DuckDB schema after init
# GREEN since Plan 42-02 added anomaly_score to normalized_events
# ---------------------------------------------------------------------------
async def test_anomaly_score_in_duckdb(tmp_path):
    """normalized_events table has anomaly_score FLOAT column after schema init."""
    from backend.stores.duckdb_store import DuckDBStore
    store = DuckDBStore(data_dir=str(tmp_path))
    store.start_write_worker()
    try:
        await store.initialise_schema()
        conn = store.get_read_conn()
        try:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(normalized_events)").fetchall()]
        finally:
            conn.close()
        assert "anomaly_score" in cols, (
            f"anomaly_score column missing from normalized_events; found: {cols}"
        )
    finally:
        await store.close()


# ---------------------------------------------------------------------------
# Stub 6 — high-anomaly event creates a synthetic detection row
# Tests that _apply_anomaly_scoring creates a detection when score exceeds threshold
# ---------------------------------------------------------------------------
@_skip_api
def test_synthetic_detection_created():
    """After _apply_anomaly_scoring with high score, sqlite_store.insert_detection is called."""
    from ingestion.loader import _apply_anomaly_scoring, _extract_features
    from backend.models.event import NormalizedEvent
    from backend.services.anomaly.scorer import AnomalyScorer
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a scorer that always returns a score above threshold
        scorer = AnomalyScorer(model_dir=tmpdir)

        # Mock sqlite_store to capture insert_detection calls
        mock_sqlite = MagicMock()
        mock_sqlite.insert_detection = MagicMock()

        from datetime import datetime, timezone as tz
        # Create a NormalizedEvent that will have anomaly features forcing high score
        event = NormalizedEvent(
            event_id="test-anomaly-001",
            timestamp=datetime.now(tz=tz.utc),
            ingested_at=datetime.now(tz=tz.utc),
            hostname="host1",
            src_ip="192.168.1.100",
            process_name="ransomware.exe",
            severity="high",
            event_type="process",
            source_type="json",
        )

        # Monkeypatch scorer.score_one to return a very high score
        original_score_one = scorer.score_one
        scorer.score_one = lambda features, entity=None: 0.95  # above 0.85 threshold
        scorer.learn_one = MagicMock()
        scorer.save_model = MagicMock()

        result_event = _apply_anomaly_scoring(
            event, scorer,
            sqlite_store=mock_sqlite,
            anomaly_threshold=0.7,
        )

        # Verify anomaly_score was set
        assert result_event.anomaly_score == 0.95

        # Verify insert_detection was called with anomaly- prefix rule_id
        assert mock_sqlite.insert_detection.called, "insert_detection should have been called"
        call_args = mock_sqlite.insert_detection.call_args[0]
        rule_id = call_args[1]  # second positional arg is rule_id
        assert rule_id.startswith("anomaly-"), (
            f"Expected rule_id starting with 'anomaly-', got {rule_id!r}"
        )
        # Score > 0.85 → severity = "high"
        severity = call_args[3]
        assert severity == "high", f"Expected severity 'high' for score 0.95, got {severity!r}"
