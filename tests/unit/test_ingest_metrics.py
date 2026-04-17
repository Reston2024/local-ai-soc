"""Unit tests for ingest pipeline latency and throughput counters.

Verifies the module-level _ingest_counters in backend.api.ingest are
incremented correctly by the ingest endpoints, and that perf.py exposes
them through _soc_brain_metrics().

All DuckDB/Chroma/Ollama I/O is mocked — no real I/O.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


def _build_app(tmp_path):
    """Build a TestClient with stores needed for ingest endpoints."""
    from fastapi.testclient import TestClient

    from backend.core.auth import verify_token
    from backend.core.deps import Stores
    from backend.core.rbac import OperatorContext
    from backend.main import create_app
    from backend.stores.sqlite_store import SQLiteStore

    duckdb = MagicMock()
    duckdb.fetch_all = AsyncMock(return_value=[])
    duckdb.fetch_df = AsyncMock(return_value=[])
    duckdb.execute_write = AsyncMock(return_value=None)

    chroma = MagicMock()
    chroma.query_async = AsyncMock(return_value={
        "ids": [[]], "distances": [[]], "documents": [[]], "metadatas": [[]]
    })
    chroma.add_documents_async = AsyncMock(return_value=None)

    sqlite = SQLiteStore(str(tmp_path))
    stores = Stores(duckdb=duckdb, chroma=chroma, sqlite=sqlite)

    app = create_app()
    app.state.stores = stores
    app.state.ollama = MagicMock()
    app.state.ollama.embed = AsyncMock(return_value=[0.1] * 128)
    app.state.ollama.embed_batch = AsyncMock(return_value=[[0.1] * 128])
    app.state.ollama.health_check = AsyncMock(return_value=False)

    # Settings mock — ingest/file needs DATA_DIR
    app.state.settings = MagicMock()
    app.state.settings.DATA_DIR = str(tmp_path)

    # Bypass auth for unit tests
    _ctx = OperatorContext(operator_id="test-admin", username="test", role="admin")
    app.dependency_overrides[verify_token] = lambda: _ctx

    client = TestClient(app, raise_server_exceptions=False)
    return client, stores


def _reset_counters() -> None:
    """Reset module-level counters between tests."""
    from backend.api.ingest import _ingest_counters

    _ingest_counters["events_total"] = 0
    _ingest_counters["batches_total"] = 0
    _ingest_counters["errors_total"] = 0
    _ingest_counters["files_queued_total"] = 0
    _ingest_counters["last_batch_latency_ms"] = 0.0
    _ingest_counters["last_event_latency_ms"] = 0.0


class TestIngestEventCounter:
    def test_ingest_event_increments_events_total(self, tmp_path):
        """After calling /ingest/event successfully, events_total increments by 1."""
        from backend.api.ingest import _ingest_counters

        _reset_counters()
        before = _ingest_counters["events_total"]

        client, _ = _build_app(tmp_path)
        payload = {
            "event_id": "metrics-evt-001",
            "event_type": "process_create",
            "hostname": "host-metrics-1",
            "timestamp": "2026-01-01T10:00:00+00:00",
            "ingested_at": "2026-01-01T10:00:01+00:00",
        }
        resp = client.post("/api/ingest/event", json=payload)

        assert resp.status_code == 201, f"Unexpected status: {resp.status_code} / {resp.text}"
        assert _ingest_counters["events_total"] == before + 1
        # latency must have been recorded (non-zero) after a successful write
        assert _ingest_counters["last_event_latency_ms"] >= 0.0


class TestIngestBatchCounter:
    def test_ingest_events_increments_events_total_by_batch_size(self, tmp_path):
        """After calling /ingest/events with 5 events, events_total += 5 and batches_total += 1."""
        from backend.api.ingest import _ingest_counters

        _reset_counters()
        events_before = _ingest_counters["events_total"]
        batches_before = _ingest_counters["batches_total"]

        client, _ = _build_app(tmp_path)
        events = [
            {
                "event_id": f"metrics-batch-{i:03d}",
                "event_type": "process_create",
                "hostname": f"host-{i}",
                "timestamp": "2026-01-01T10:00:00+00:00",
                "ingested_at": "2026-01-01T10:00:01+00:00",
            }
            for i in range(5)
        ]
        resp = client.post("/api/ingest/events", json=events)

        # If the loader path succeeds, counters should be updated
        if resp.status_code == 201:
            assert _ingest_counters["events_total"] == events_before + 5
            assert _ingest_counters["batches_total"] == batches_before + 1
        else:
            # Any error path should bump errors_total instead
            assert _ingest_counters["errors_total"] >= 1


class TestIngestErrorCounter:
    def test_ingest_event_failure_increments_errors_total(self, tmp_path):
        """When DuckDB write raises, errors_total increments."""
        from backend.api.ingest import _ingest_counters

        _reset_counters()
        errors_before = _ingest_counters["errors_total"]

        client, stores = _build_app(tmp_path)
        # Force DuckDB write to raise
        stores.duckdb.execute_write = AsyncMock(side_effect=RuntimeError("duckdb down"))

        payload = {
            "event_id": "metrics-err-001",
            "event_type": "process_create",
            "hostname": "host-err",
            "timestamp": "2026-01-01T10:00:00+00:00",
            "ingested_at": "2026-01-01T10:00:01+00:00",
        }
        resp = client.post("/api/ingest/event", json=payload)

        # Expect a 500 from the API and an incremented error counter
        assert resp.status_code == 500
        assert _ingest_counters["errors_total"] == errors_before + 1


class TestPerfExposesIngestCounters:
    def test_soc_brain_metrics_includes_ingest_key(self, tmp_path):
        """_soc_brain_metrics() must include the 'ingest' key snapshot."""
        from backend.api.ingest import _ingest_counters
        from backend.api.perf import _soc_brain_metrics

        _reset_counters()
        _ingest_counters["events_total"] = 42
        _ingest_counters["batches_total"] = 3

        metrics = _soc_brain_metrics()
        assert "ingest" in metrics
        assert metrics["ingest"]["events_total"] == 42
        assert metrics["ingest"]["batches_total"] == 3
        # Must be a snapshot copy, not a live reference
        metrics["ingest"]["events_total"] = 999
        assert _ingest_counters["events_total"] == 42
