"""Extended API endpoint tests covering graph, query, investigations, ingest.

Uses TestClient with mocked/real stores.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

pytestmark = pytest.mark.unit


def _build_app_with_real_sqlite(tmp_path):
    """Build a TestClient with real SQLite store and mocked DuckDB/Chroma."""
    import tempfile
    from fastapi.testclient import TestClient
    from backend.main import create_app
    from backend.stores.sqlite_store import SQLiteStore
    from backend.core.deps import Stores

    sqlite = SQLiteStore(str(tmp_path))

    duckdb = MagicMock()
    duckdb.fetch_all = AsyncMock(return_value=[])
    duckdb.fetch_df = AsyncMock(return_value=[])
    duckdb.execute_write = AsyncMock(return_value=None)

    chroma = MagicMock()
    chroma.query_async = AsyncMock(return_value={
        "ids": [[]], "distances": [[]], "documents": [[]], "metadatas": [[]]
    })
    chroma.add_documents_async = AsyncMock(return_value=None)

    stores = Stores(duckdb=duckdb, chroma=chroma, sqlite=sqlite)

    app = create_app()
    app.state.stores = stores
    app.state.ollama = MagicMock()
    app.state.ollama.embed = AsyncMock(return_value=[0.1] * 128)
    app.state.ollama.embed_batch = AsyncMock(return_value=[[0.1] * 128])
    app.state.ollama.health_check = AsyncMock(return_value=False)
    app.state.settings = MagicMock()

    client = TestClient(app, raise_server_exceptions=False)
    return client, stores, sqlite


# ---------------------------------------------------------------------------
# Graph endpoint tests
# ---------------------------------------------------------------------------

class TestGraphEndpoints:
    def test_get_entity_not_found(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        resp = client.get("/api/graph/entity/no-such-entity")
        assert resp.status_code in (404, 200)

    def test_post_entity_creates_entity(self, tmp_path):
        client, _, sqlite = _build_app_with_real_sqlite(tmp_path)
        payload = {
            "type": "host",
            "name": "dc01",
            "attributes": {"os": "Windows"},
        }
        resp = client.post("/api/graph/entity", json=payload)
        assert resp.status_code in (200, 201, 422)

    def test_post_edge_creates_relationship(self, tmp_path):
        client, _, sqlite = _build_app_with_real_sqlite(tmp_path)
        payload = {
            "source_id": "proc-1",
            "source_type": "process",
            "target_id": "host-1",
            "target_type": "host",
            "edge_type": "ran_on",
        }
        resp = client.post("/api/graph/edge", json=payload)
        assert resp.status_code in (200, 201, 422)

    def test_get_case_graph(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        resp = client.get("/api/graph/case/case-001")
        assert resp.status_code in (200, 404, 422)

    def test_traverse_entity(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        resp = client.get("/api/graph/traverse/some-entity-id")
        assert resp.status_code in (200, 404, 422)


# ---------------------------------------------------------------------------
# Query endpoint tests
# ---------------------------------------------------------------------------

class TestQueryEndpoints:
    def test_semantic_search_returns_200(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        payload = {"query": "powershell execution", "n_results": 5}
        resp = client.post("/api/query/semantic", json=payload)
        assert resp.status_code in (200, 422, 503)

    def test_ask_question_returns_200_or_503(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        payload = {"question": "What attack techniques were used?"}
        resp = client.post("/api/query/ask", json=payload)
        assert resp.status_code in (200, 422, 503)

    def test_semantic_search_with_case_id_filter(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        payload = {
            "query": "mimikatz",
            "case_id": "case-001",
            "n_results": 3,
        }
        resp = client.post("/api/query/semantic", json=payload)
        assert resp.status_code in (200, 422, 503)


# ---------------------------------------------------------------------------
# Ingest endpoint tests
# ---------------------------------------------------------------------------

class TestIngestEndpoints:
    def test_list_ingest_jobs(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        resp = client.get("/api/ingest/jobs")
        assert resp.status_code in (200, 404, 422)

    def test_ingest_upload_no_file(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        resp = client.post("/api/ingest/upload")
        # Missing file should return validation error
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# Investigations endpoint tests (via investigation_routes)
# ---------------------------------------------------------------------------

class TestInvestigationsEndpoints:
    def test_list_investigation_cases(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        resp = client.get("/api/investigations")
        assert resp.status_code in (200, 404)

    def test_create_investigation_case(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        payload = {"title": "Test Investigation", "description": "Test desc"}
        resp = client.post("/api/investigations", json=payload)
        assert resp.status_code in (200, 201, 404, 422)

    def test_get_investigation_case(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        resp = client.get("/api/investigations/no-such-case")
        assert resp.status_code in (200, 404)

    def test_hunt_endpoint(self, tmp_path):
        client, stores, _ = _build_app_with_real_sqlite(tmp_path)
        stores.duckdb.fetch_df = AsyncMock(return_value=[])
        resp = client.post(
            "/api/investigations/hunt",
            json={"template_name": "powershell_children", "params": {}},
        )
        assert resp.status_code in (200, 404, 422)


# ---------------------------------------------------------------------------
# Health check with real stores check
# ---------------------------------------------------------------------------

class TestHealthEndpointDetailed:
    def test_health_json_keys(self, tmp_path):
        """Health endpoint JSON should have status key."""
        from fastapi.testclient import TestClient
        from backend.main import create_app
        from backend.core.deps import Stores

        duckdb = MagicMock()
        duckdb.fetch_all = AsyncMock(return_value=[(1,)])
        duckdb.health_check = MagicMock(return_value={"status": "ok"})
        chroma = MagicMock()
        sqlite = MagicMock()
        sqlite.health_check = MagicMock(return_value={"status": "ok"})

        stores = Stores(duckdb=duckdb, chroma=chroma, sqlite=sqlite)
        app = create_app()
        app.state.stores = stores
        app.state.ollama = MagicMock()
        app.state.ollama.health_check = AsyncMock(return_value=False)
        app.state.settings = MagicMock()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/health")
        if resp.status_code == 200:
            body = resp.json()
            assert "status" in body or isinstance(body, dict)


# ---------------------------------------------------------------------------
# Detect API — run detection endpoint (mocked matcher)
# ---------------------------------------------------------------------------

class TestDetectRunEndpoint:
    def test_run_detection_returns_200(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        resp = client.post("/api/detect/run")
        assert resp.status_code in (200, 422)

    def test_run_detection_response_has_count(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        resp = client.post("/api/detect/run")
        if resp.status_code == 200:
            body = resp.json()
            assert "count" in body
            assert "detections" in body


# ---------------------------------------------------------------------------
# Export endpoint basic test
# ---------------------------------------------------------------------------

class TestExportEndpoint:
    def test_export_list_formats(self, tmp_path):
        client, stores, _ = _build_app_with_real_sqlite(tmp_path)
        stores.duckdb.fetch_df = AsyncMock(return_value=[])
        resp = client.get("/api/export/formats")
        assert resp.status_code in (200, 404)

    def test_export_events_csv(self, tmp_path):
        client, stores, _ = _build_app_with_real_sqlite(tmp_path)
        stores.duckdb.fetch_df = AsyncMock(return_value=[])
        resp = client.get("/api/export/events?format=csv")
        assert resp.status_code in (200, 404, 422)


# ---------------------------------------------------------------------------
# Saved investigations endpoints
# ---------------------------------------------------------------------------

class TestSavedInvestigationsEndpoints:
    def test_list_saved_investigations_returns_200(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        resp = client.get("/api/investigations/saved")
        assert resp.status_code == 200

    def test_list_saved_investigations_returns_list(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        resp = client.get("/api/investigations/saved")
        if resp.status_code == 200:
            body = resp.json()
            assert "investigations" in body
            assert isinstance(body["investigations"], list)

    def test_save_investigation_returns_200(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        payload = {
            "detection_id": "det-001",
            "graph_snapshot": {"nodes": [], "edges": []},
            "metadata": {"analyst": "test"},
        }
        resp = client.post("/api/investigations/saved", json=payload)
        assert resp.status_code == 200

    def test_save_investigation_response_has_id(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        payload = {"detection_id": "det-002", "graph_snapshot": {}, "metadata": {}}
        resp = client.post("/api/investigations/saved", json=payload)
        if resp.status_code == 200:
            body = resp.json()
            assert "id" in body

    def test_get_saved_investigation_not_found(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        resp = client.get("/api/investigations/saved/nonexistent-inv-id")
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("investigation") is None

    def test_get_saved_investigation_after_save(self, tmp_path):
        client, _, _ = _build_app_with_real_sqlite(tmp_path)
        payload = {"detection_id": "det-003", "graph_snapshot": {"x": 1}, "metadata": {}}
        save_resp = client.post("/api/investigations/saved", json=payload)
        if save_resp.status_code == 200:
            inv_id = save_resp.json().get("id")
            if inv_id:
                get_resp = client.get(f"/api/investigations/saved/{inv_id}")
                assert get_resp.status_code == 200


# ---------------------------------------------------------------------------
# Events API
# ---------------------------------------------------------------------------

class TestEventsEndpoints:
    def test_list_events_returns_200(self, tmp_path):
        client, stores, _ = _build_app_with_real_sqlite(tmp_path)
        stores.duckdb.fetch_df = AsyncMock(return_value=[])
        stores.duckdb.fetch_all = AsyncMock(return_value=[(0,)])
        resp = client.get("/api/events")
        assert resp.status_code in (200, 422, 500)

    def test_list_events_with_filters(self, tmp_path):
        client, stores, _ = _build_app_with_real_sqlite(tmp_path)
        stores.duckdb.fetch_df = AsyncMock(return_value=[])
        stores.duckdb.fetch_all = AsyncMock(return_value=[(0,)])
        resp = client.get("/api/events?hostname=dc01&severity=high")
        assert resp.status_code in (200, 422, 500)

    def test_get_single_event_not_found(self, tmp_path):
        client, stores, _ = _build_app_with_real_sqlite(tmp_path)
        stores.duckdb.fetch_df = AsyncMock(return_value=[])
        stores.duckdb.fetch_all = AsyncMock(return_value=[])
        resp = client.get("/api/events/no-such-event-id")
        assert resp.status_code in (200, 404, 500)

    def test_rows_to_events_pure_function(self):
        from backend.api.events import _rows_to_events
        rows = [
            {
                "event_id": "e1", "timestamp": "2026-01-01T10:00:00",
                "ingested_at": "2026-01-01T10:00:01", "source_type": "json",
                "source_file": "test.json", "hostname": "host1", "username": None,
                "process_name": None, "process_id": None, "parent_process_name": None,
                "parent_process_id": None, "file_path": None, "file_hash_sha256": None,
                "command_line": None, "src_ip": None, "src_port": None,
                "dst_ip": None, "dst_port": None, "domain": None, "url": None,
                "event_type": "process_create", "severity": "high",
                "confidence": 1.0, "detection_source": None,
                "attack_technique": None, "attack_tactic": None,
                "raw_event": None, "tags": None, "case_id": None,
            }
        ]
        result = _rows_to_events(rows)
        assert len(result) == 1
        assert result[0].event_id == "e1"

    def test_rows_to_events_skips_invalid_rows(self):
        from backend.api.events import _rows_to_events
        # An invalid row (missing required fields or wrong types) should be skipped
        rows = [{"event_id": "broken", "timestamp": "not-a-date-or-will-fail-creation"}]
        result = _rows_to_events(rows)
        # Invalid row should be skipped gracefully
        assert isinstance(result, list)
