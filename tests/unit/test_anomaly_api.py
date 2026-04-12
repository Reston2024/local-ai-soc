"""
Wave 0 TDD stubs for Phase 42 anomaly API endpoints.
P42-T03: anomaly_score DuckDB column.
P42-T04: GET /api/anomaly list + threshold filter.
P42-T05: GET /api/anomaly/entity profile endpoint.
P42-T06: GET /api/anomaly/trend + synthetic detection creation.

Stubs 1-4 and 6 SKIP until backend/api/anomaly.py exists (Plan 42-03).
Stub 5 (test_anomaly_score_in_duckdb) FAILS RED immediately — anomaly_score
column not yet in _ECS_MIGRATION_COLUMNS.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Try importing anomaly router — skip API stubs if not yet implemented
# ---------------------------------------------------------------------------
try:
    from backend.api.anomaly import router as anomaly_router
    _API_AVAILABLE = True
except ImportError:
    _API_AVAILABLE = False

_skip_api = pytest.mark.skipif(not _API_AVAILABLE, reason="anomaly API not yet implemented (Plan 42-03)")


# ---------------------------------------------------------------------------
# Stub 1 — GET /api/anomaly returns 200 with correct shape
# ---------------------------------------------------------------------------
@_skip_api
def test_list_anomalies_endpoint_exists():
    """GET /api/anomaly returns 200 with {"anomalies": [...], "total": int}."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(anomaly_router)
    client = TestClient(app)

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
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(anomaly_router)
    client = TestClient(app)

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
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(anomaly_router)
    client = TestClient(app)

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
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(anomaly_router)
    client = TestClient(app)

    resp = client.get("/api/anomaly/trend?entity_key=192.168.1.subnet:svchost.exe")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    for item in body:
        assert "timestamp" in item
        assert "score" in item


# ---------------------------------------------------------------------------
# Stub 5 — anomaly_score column exists in DuckDB schema after init
# RED immediately — anomaly_score not yet added to _ECS_MIGRATION_COLUMNS
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
# ---------------------------------------------------------------------------
@_skip_api
async def test_synthetic_detection_created():
    """After ingest of high-anomaly event (score > ANOMALY_THRESHOLD),
    detections table gains a row with rule_id matching 'anomaly-*'."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from backend.api.anomaly import router as anomaly_router  # noqa: F811
    app = FastAPI()
    app.include_router(anomaly_router)
    client = TestClient(app)

    # Trigger synthetic detection creation via the anomaly API
    resp = client.post("/api/anomaly/detect", json={
        "event": {"bytes_out": 9999999, "process_name": "ransomware.exe"},
        "entity_key": "192.168.1.subnet:ransomware.exe",
    })
    assert resp.status_code in (200, 201)
    body = resp.json()
    # Synthetic detection must have a rule_id matching the anomaly prefix
    rule_id = body.get("rule_id", "")
    assert rule_id.startswith("anomaly-"), f"Expected rule_id starting with 'anomaly-', got {rule_id!r}"
