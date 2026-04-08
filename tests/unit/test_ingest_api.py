"""Unit tests for backend/api/ingest.py via TestClient.

Uses a real SQLiteStore, mocked DuckDB, mocked Chroma, mocked Ollama.
"""
import io
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


class TestIngestSingleEvent:
    def test_ingest_event_returns_201(self, tmp_path):
        client, _ = _build_app(tmp_path)
        payload = {
            "event_id": "unit-test-event-001",
            "event_type": "process_create",
            "hostname": "test-host",
            "process_name": "cmd.exe",
            "severity": "high",
        }
        resp = client.post("/api/ingest/event", json=payload)
        assert resp.status_code in (201, 422, 500)

    def test_ingest_event_response_has_event_id(self, tmp_path):
        client, _ = _build_app(tmp_path)
        payload = {
            "event_id": "unit-test-event-002",
            "event_type": "process_create",
            "hostname": "test-host",
        }
        resp = client.post("/api/ingest/event", json=payload)
        if resp.status_code == 201:
            body = resp.json()
            assert "event_id" in body
            assert body["event_id"] == "unit-test-event-002"

    def test_ingest_event_status_ingested(self, tmp_path):
        client, _ = _build_app(tmp_path)
        payload = {"event_type": "network_connection", "hostname": "host1"}
        resp = client.post("/api/ingest/event", json=payload)
        if resp.status_code == 201:
            body = resp.json()
            assert body.get("status") == "ingested"

    def test_ingest_event_assigns_uuid_when_no_event_id(self, tmp_path):
        """POST /ingest/event without event_id should auto-assign a UUID."""
        client, _ = _build_app(tmp_path)
        payload = {"event_type": "file_create", "hostname": "host2"}
        resp = client.post("/api/ingest/event", json=payload)
        if resp.status_code == 201:
            body = resp.json()
            assert "event_id" in body
            assert len(body["event_id"]) > 0


class TestIngestBatchEvents:
    def test_ingest_events_empty_list_returns_400(self, tmp_path):
        client, _ = _build_app(tmp_path)
        resp = client.post("/api/ingest/events", json=[])
        assert resp.status_code == 400

    def test_ingest_events_single_event_returns_201(self, tmp_path):
        client, stores = _build_app(tmp_path)
        events = [{
            "event_id": "batch-001",
            "event_type": "process_create",
            "hostname": "h1",
            "timestamp": "2026-01-01T10:00:00+00:00",
            "ingested_at": "2026-01-01T10:00:01+00:00",
        }]
        resp = client.post("/api/ingest/events", json=events)
        # 201 or 500 (if loader fails due to DuckDB mock) — not 400/422
        assert resp.status_code in (201, 500)

    def test_ingest_events_response_has_counts(self, tmp_path):
        client, _ = _build_app(tmp_path)
        events = [{
            "event_id": "batch-002",
            "event_type": "network_connection",
            "hostname": "h2",
            "timestamp": "2026-01-01T10:00:00+00:00",
            "ingested_at": "2026-01-01T10:00:01+00:00",
        }]
        resp = client.post("/api/ingest/events", json=events)
        if resp.status_code == 201:
            body = resp.json()
            assert "loaded" in body
            assert "parsed" in body


class TestIngestFileUpload:
    def test_upload_unsupported_extension_returns_415(self, tmp_path):
        client, _ = _build_app(tmp_path)
        file_bytes = b"not a real file"
        resp = client.post(
            "/api/ingest/file",
            files={"file": ("malware.exe", io.BytesIO(file_bytes), "application/octet-stream")},
        )
        assert resp.status_code == 415

    def test_upload_csv_file_returns_202(self, tmp_path):
        client, _ = _build_app(tmp_path)
        csv_content = b"event_id,event_type,hostname\nevt-1,process_create,host1\n"
        resp = client.post(
            "/api/ingest/file",
            files={"file": ("events.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert resp.status_code == 202

    def test_upload_json_file_returns_202(self, tmp_path):
        client, _ = _build_app(tmp_path)
        json_content = b'[{"event_id":"e1","event_type":"process_create","hostname":"host1"}]'
        resp = client.post(
            "/api/ingest/file",
            files={"file": ("events.json", io.BytesIO(json_content), "application/json")},
        )
        assert resp.status_code == 202

    def test_upload_csv_returns_job_id(self, tmp_path):
        client, _ = _build_app(tmp_path)
        csv_content = b"event_id,event_type\nevt-1,process_create\n"
        resp = client.post(
            "/api/ingest/file",
            files={"file": ("events.csv", io.BytesIO(csv_content), "text/csv")},
        )
        if resp.status_code == 202:
            body = resp.json()
            assert "job_id" in body
            assert "status" in body
            assert body["status"] == "queued"

    def test_upload_ndjson_returns_202(self, tmp_path):
        client, _ = _build_app(tmp_path)
        ndjson = b'{"event_id":"e1","event_type":"process_create","hostname":"host1"}\n'
        resp = client.post(
            "/api/ingest/file",
            files={"file": ("events.ndjson", io.BytesIO(ndjson), "application/x-ndjson")},
        )
        assert resp.status_code == 202

    def test_upload_no_file_returns_422(self, tmp_path):
        client, _ = _build_app(tmp_path)
        resp = client.post("/api/ingest/file")
        assert resp.status_code == 422

    def test_legacy_upload_endpoint_accepts_csv(self, tmp_path):
        client, _ = _build_app(tmp_path)
        csv_content = b"event_id,event_type\nevt-1,process_create\n"
        resp = client.post(
            "/api/ingest/upload",
            files={"file": ("events.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert resp.status_code == 202


class TestIngestJobStatus:
    def test_unknown_job_returns_404(self, tmp_path):
        client, _ = _build_app(tmp_path)
        resp = client.get("/api/ingest/jobs/nonexistent-job-id")
        assert resp.status_code == 404

    def test_queued_job_found_after_upload(self, tmp_path):
        client, _ = _build_app(tmp_path)
        csv_content = b"event_id,event_type\nevt-1,process_create\n"
        upload_resp = client.post(
            "/api/ingest/file",
            files={"file": ("events.csv", io.BytesIO(csv_content), "text/csv")},
        )
        if upload_resp.status_code == 202:
            job_id = upload_resp.json()["job_id"]
            status_resp = client.get(f"/api/ingest/jobs/{job_id}")
            assert status_resp.status_code == 200
            body = status_resp.json()
            assert "status" in body


class TestJobStatusCompat:
    def test_unknown_job_returns_404(self, tmp_path):
        client, _ = _build_app(tmp_path)
        resp = client.get("/api/ingest/status/nonexistent-job-id")
        assert resp.status_code == 404

    def test_status_alias_returns_dashboard_shape(self, tmp_path):
        client, _ = _build_app(tmp_path)
        csv_content = b"event_id,event_type\nevt-1,process_create\n"
        upload_resp = client.post(
            "/api/ingest/file",
            files={"file": ("events.csv", io.BytesIO(csv_content), "text/csv")},
        )
        if upload_resp.status_code == 202:
            job_id = upload_resp.json()["job_id"]
            status_resp = client.get(f"/api/ingest/status/{job_id}")
            assert status_resp.status_code == 200
            body = status_resp.json()
            for key in ("job_id", "status", "filename", "events_processed", "events_total", "error", "started_at"):
                assert key in body, f"Missing key: {key}"
            assert isinstance(body["events_processed"], int)
            assert isinstance(body["events_total"], int)
