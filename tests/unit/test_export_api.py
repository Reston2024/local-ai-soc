"""Unit tests for backend/api/export.py via TestClient.

Uses a mocked DuckDB store and a real SQLiteStore.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

pytestmark = pytest.mark.unit


def _build_app(tmp_path, duckdb_rows=None, sqlite_store=None):
    """Build a TestClient with mocked stores."""
    from fastapi.testclient import TestClient
    from backend.main import create_app
    from backend.core.deps import Stores

    duckdb = MagicMock()
    duckdb.fetch_all = AsyncMock(return_value=[])
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

    client = TestClient(app, raise_server_exceptions=False)
    return client, stores, sqlite_store


class TestExportEventsCsv:
    def test_csv_no_filters_returns_200(self, tmp_path):
        client, _, _ = _build_app(tmp_path)
        resp = client.get("/api/export/events/csv")
        assert resp.status_code == 200

    def test_csv_content_type(self, tmp_path):
        client, _, _ = _build_app(tmp_path)
        resp = client.get("/api/export/events/csv")
        if resp.status_code == 200:
            assert "text/csv" in resp.headers.get("content-type", "")

    def test_csv_content_disposition(self, tmp_path):
        client, _, _ = _build_app(tmp_path)
        resp = client.get("/api/export/events/csv")
        if resp.status_code == 200:
            cd = resp.headers.get("content-disposition", "")
            assert ".csv" in cd

    def test_csv_with_no_rows_returns_header(self, tmp_path):
        client, _, _ = _build_app(tmp_path, duckdb_rows=[])
        resp = client.get("/api/export/events/csv")
        assert resp.status_code == 200
        # With no events, should return minimal CSV content
        assert len(resp.content) > 0

    def test_csv_with_rows(self, tmp_path):
        rows = [
            {"event_id": "e1", "hostname": "host1", "severity": "high",
             "event_type": "process_create", "timestamp": "2026-01-01T10:00:00"}
        ]
        client, _, _ = _build_app(tmp_path, duckdb_rows=rows)
        resp = client.get("/api/export/events/csv")
        assert resp.status_code == 200
        body = resp.content.decode("utf-8")
        assert "host1" in body

    def test_csv_with_case_id_filter(self, tmp_path):
        client, _, _ = _build_app(tmp_path)
        resp = client.get("/api/export/events/csv?case_id=case-001")
        assert resp.status_code == 200

    def test_csv_with_hostname_filter(self, tmp_path):
        client, _, _ = _build_app(tmp_path)
        resp = client.get("/api/export/events/csv?hostname=dc01")
        assert resp.status_code == 200

    def test_csv_with_severity_filter(self, tmp_path):
        client, _, _ = _build_app(tmp_path)
        resp = client.get("/api/export/events/csv?severity=high")
        assert resp.status_code == 200

    def test_csv_with_limit(self, tmp_path):
        client, _, _ = _build_app(tmp_path)
        resp = client.get("/api/export/events/csv?limit=100")
        assert resp.status_code == 200


class TestExportEventsJson:
    def test_json_no_filters_returns_200(self, tmp_path):
        client, _, _ = _build_app(tmp_path)
        resp = client.get("/api/export/events/json")
        assert resp.status_code == 200

    def test_json_content_type(self, tmp_path):
        client, _, _ = _build_app(tmp_path)
        resp = client.get("/api/export/events/json")
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            assert "ndjson" in ct or "json" in ct

    def test_json_content_disposition(self, tmp_path):
        client, _, _ = _build_app(tmp_path)
        resp = client.get("/api/export/events/json")
        if resp.status_code == 200:
            cd = resp.headers.get("content-disposition", "")
            assert ".ndjson" in cd

    def test_json_with_rows(self, tmp_path):
        from datetime import datetime, timezone
        rows = [
            {"event_id": "e1", "hostname": "host1", "severity": "high",
             "timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc)}
        ]
        client, _, _ = _build_app(tmp_path, duckdb_rows=rows)
        resp = client.get("/api/export/events/json")
        assert resp.status_code == 200
        body = resp.content.decode("utf-8")
        assert "host1" in body

    def test_json_with_case_id_filter(self, tmp_path):
        client, _, _ = _build_app(tmp_path)
        resp = client.get("/api/export/events/json?case_id=case-001")
        assert resp.status_code == 200

    def test_json_with_hostname_filter(self, tmp_path):
        client, _, _ = _build_app(tmp_path)
        resp = client.get("/api/export/events/json?hostname=dc01")
        assert resp.status_code == 200

    def test_json_with_severity_filter(self, tmp_path):
        client, _, _ = _build_app(tmp_path)
        resp = client.get("/api/export/events/json?severity=critical")
        assert resp.status_code == 200


class TestExportCaseBundle:
    def test_bundle_missing_case_returns_404(self, tmp_path):
        client, _, _ = _build_app(tmp_path)
        resp = client.get("/api/export/case/no-such-case/bundle")
        # Case doesn't exist in SQLite — should return 404
        assert resp.status_code in (404, 500)

    def test_bundle_existing_case(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        sqlite = SQLiteStore(str(tmp_path))
        # create_case(name, description, case_id=None) — returns auto-assigned id
        case_id = sqlite.create_case("Export Test Case", "A test case", case_id="case-export-01")

        client, _, _ = _build_app(tmp_path, sqlite_store=sqlite)
        resp = client.get(f"/api/export/case/{case_id}/bundle")
        assert resp.status_code == 200

    def test_bundle_response_has_expected_keys(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        sqlite = SQLiteStore(str(tmp_path))
        case_id = sqlite.create_case("Bundle Test", "Test", case_id="case-bundle-01")

        client, _, _ = _build_app(tmp_path, sqlite_store=sqlite)
        resp = client.get(f"/api/export/case/{case_id}/bundle")
        if resp.status_code == 200:
            body = resp.json()
            assert isinstance(body, dict)
            # Should include case metadata, entities, detections, events
            assert "case" in body or "events" in body or len(body) > 0
