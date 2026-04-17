"""Unit tests for the one-click Incident Notebook export endpoint.

Endpoint: GET /api/export/case/{case_id}/notebook

Tests use a real SQLiteStore (in tmp_path) and a mocked DuckDB store.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


def _build_app(tmp_path, duckdb_rows=None, duckdb_count=0, sqlite_store=None):
    """Build a TestClient with mocked DuckDB and a real SQLiteStore."""
    from fastapi.testclient import TestClient

    from backend.core.auth import verify_token
    from backend.core.deps import Stores
    from backend.core.rbac import OperatorContext
    from backend.main import create_app

    duckdb = MagicMock()
    # fetch_all is used for the total-events COUNT(*) — return [(N,)]
    duckdb.fetch_all = AsyncMock(return_value=[(duckdb_count,)])
    # fetch_df is used for the events sample — return list[dict]
    duckdb.fetch_df = AsyncMock(return_value=duckdb_rows if duckdb_rows is not None else [])
    duckdb.execute_write = AsyncMock(return_value=None)

    chroma = MagicMock()
    chroma.query_async = AsyncMock(return_value={
        "ids": [[]], "distances": [[]], "documents": [[]], "metadatas": [[]]
    })

    if sqlite_store is None:
        from backend.stores.sqlite_store import SQLiteStore
        sqlite_store = SQLiteStore(str(tmp_path))

    stores = Stores(duckdb=duckdb, chroma=chroma, sqlite=sqlite_store)

    app = create_app()
    app.state.stores = stores
    app.state.ollama = MagicMock()
    app.state.ollama.embed = AsyncMock(return_value=[0.1] * 128)
    app.state.settings = MagicMock()

    _ctx = OperatorContext(operator_id="test-admin", username="test", role="admin")
    app.dependency_overrides[verify_token] = lambda: _ctx

    client = TestClient(app, raise_server_exceptions=False)
    return client, stores, sqlite_store


class TestIncidentNotebook:
    def test_unknown_case_returns_404(self, tmp_path):
        """Unknown case_id -> 404 with detail == 'Case not found'."""
        client, _, _ = _build_app(tmp_path)
        resp = client.get("/api/export/case/does-not-exist/notebook")
        assert resp.status_code == 404
        body = resp.json()
        assert body.get("detail") == "Case not found"

    def test_case_with_no_playbook_runs(self, tmp_path):
        """Case with no playbook runs -> mttr_seconds is null, playbook_runs empty."""
        from backend.stores.sqlite_store import SQLiteStore
        sqlite = SQLiteStore(str(tmp_path))
        case_id = sqlite.create_case("Notebook Empty", "No runs", case_id="case-nb-empty")

        client, _, _ = _build_app(tmp_path, sqlite_store=sqlite)
        resp = client.get(f"/api/export/case/{case_id}/notebook")
        assert resp.status_code == 200
        body = resp.json()

        assert body["case"]["id"] == case_id
        assert body["playbook_runs"] == []
        assert body["summary"]["total_playbook_runs"] == 0
        assert body["summary"]["playbooks_completed"] == 0
        assert body["summary"]["playbooks_failed"] == 0
        assert body["summary"]["mttr_seconds"] is None
        # Every section present, even when empty
        assert "detections" in body
        assert "events_sample" in body
        assert "graph_entities" in body
        assert "generated_at" in body

    def test_case_with_two_completed_runs_mttr_average(self, tmp_path):
        """Two completed runs (100s and 300s) -> mttr_seconds == 200.0."""
        from backend.stores.sqlite_store import SQLiteStore
        sqlite = SQLiteStore(str(tmp_path))
        case_id = sqlite.create_case("Notebook MTTR", "Two runs", case_id="case-nb-mttr")

        # Insert a playbook so the FK is satisfied (create_playbook handles that).
        pb = sqlite.create_playbook({
            "name": "Test PB",
            "description": "",
            "trigger_conditions": [],
            "steps": [],
        })
        playbook_id = pb["playbook_id"]

        # Run 1: started 10:00:00 -> completed 10:01:40  (100 seconds)
        # Run 2: started 10:10:00 -> completed 10:15:00  (300 seconds)
        # Mean = 200.0
        run1 = sqlite.create_playbook_run({
            "playbook_id": playbook_id,
            "investigation_id": case_id,
        })
        sqlite.update_playbook_run(run1["run_id"], {
            "status": "completed",
            "completed_at": "2026-04-17T10:01:40+00:00",
        })
        # Overwrite started_at to a deterministic value
        sqlite._conn.execute(
            "UPDATE playbook_runs SET started_at = ? WHERE run_id = ?",
            ("2026-04-17T10:00:00+00:00", run1["run_id"]),
        )
        sqlite._conn.commit()

        run2 = sqlite.create_playbook_run({
            "playbook_id": playbook_id,
            "investigation_id": case_id,
        })
        sqlite.update_playbook_run(run2["run_id"], {
            "status": "completed",
            "completed_at": "2026-04-17T10:15:00+00:00",
        })
        sqlite._conn.execute(
            "UPDATE playbook_runs SET started_at = ? WHERE run_id = ?",
            ("2026-04-17T10:10:00+00:00", run2["run_id"]),
        )
        sqlite._conn.commit()

        client, _, _ = _build_app(tmp_path, sqlite_store=sqlite)
        resp = client.get(f"/api/export/case/{case_id}/notebook")
        assert resp.status_code == 200
        body = resp.json()

        assert body["summary"]["total_playbook_runs"] == 2
        assert body["summary"]["playbooks_completed"] == 2
        assert body["summary"]["playbooks_failed"] == 0
        assert body["summary"]["mttr_seconds"] == pytest.approx(200.0)

        # Each run should have duration_seconds computed
        durations = sorted(r["duration_seconds"] for r in body["playbook_runs"])
        assert durations == pytest.approx([100.0, 300.0])
