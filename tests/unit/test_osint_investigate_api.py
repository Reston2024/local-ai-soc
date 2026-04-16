"""Unit tests for POST /api/osint/investigate and related endpoints (Plan 51-03)."""
from __future__ import annotations
import json
import pytest
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

_API_AVAILABLE = False
_client_fixture = None
try:
    from backend.main import create_app
    from backend.services.osint_investigation_store import OsintInvestigationStore
    from backend.core.auth import verify_token
    _API_AVAILABLE = True
except ImportError:
    pass

pytestmark = pytest.mark.skipif(not _API_AVAILABLE, reason="OSINT investigate routes not available")


def _make_mock_stores():
    """Build minimal mock Stores for lifespan-free testing."""
    from unittest.mock import AsyncMock, MagicMock
    stores = MagicMock()
    stores.duckdb = MagicMock()
    stores.duckdb.fetch_all = AsyncMock(return_value=[[1]])
    stores.chroma = MagicMock()
    stores.chroma.list_collections_async = AsyncMock(return_value=[])
    stores.chroma.mode = "local"
    stores.sqlite = MagicMock()
    stores.sqlite.health_check = MagicMock(return_value={"user_version": 1})
    stores.sqlite._conn = MagicMock()
    stores.sqlite._conn.execute = MagicMock(
        return_value=MagicMock(fetchone=MagicMock(return_value=(0,)))
    )
    return stores


@pytest.fixture
def app_with_osint():
    """FastAPI app with OsintInvestigationStore on app.state (in-memory SQLite).
    Uses raise_server_exceptions=False to avoid lifespan DuckDB file-lock errors."""
    app = create_app()
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    # Create required tables
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS osint_investigations (
            id TEXT PRIMARY KEY, target TEXT NOT NULL, target_type TEXT,
            usecase TEXT DEFAULT 'investigate', status TEXT DEFAULT 'RUNNING',
            started_at TEXT NOT NULL, completed_at TEXT,
            result_summary TEXT, error TEXT
        );
        CREATE TABLE IF NOT EXISTS osint_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investigation_id TEXT NOT NULL, event_type TEXT NOT NULL,
            data TEXT NOT NULL, source_module TEXT, confidence REAL DEFAULT 1.0,
            created_at TEXT NOT NULL, misp_hit INTEGER DEFAULT 0,
            misp_event_ids TEXT DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS dnstwist_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investigation_id TEXT NOT NULL, seed_domain TEXT NOT NULL,
            fuzzer TEXT, lookalike_domain TEXT NOT NULL,
            dns_a TEXT, dns_mx TEXT, whois_registrar TEXT,
            whois_created TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ioc_store (
            ioc_value TEXT, ioc_type TEXT, confidence INTEGER,
            feed_source TEXT, actor_tag TEXT, malware_family TEXT,
            ioc_status TEXT DEFAULT 'active', created_at TEXT, updated_at TEXT,
            PRIMARY KEY (ioc_value, ioc_type)
        );
    """)
    store = OsintInvestigationStore(conn)
    app.state.osint_store = store
    # Inject mock stores so lifespan is not needed
    app.state.stores = _make_mock_stores()
    mock_ollama = MagicMock()
    mock_ollama.health_check = AsyncMock(return_value=True)
    app.state.ollama = mock_ollama
    app.state.ioc_store = MagicMock()
    app.state.ioc_store.get_feed_status = MagicMock(return_value=[])
    app.dependency_overrides[verify_token] = lambda: {"sub": "analyst"}
    return app


def test_post_investigate_spiderfoot_unreachable(app_with_osint):
    """POST /api/osint/investigate returns 503 when SpiderFoot not reachable."""
    with patch(
        "backend.services.spiderfoot_client.SpiderFootClient.ping",
        new_callable=AsyncMock, return_value=False
    ):
        c = TestClient(app_with_osint, raise_server_exceptions=False)
        resp = c.post("/api/osint/investigate", json={"target": "1.2.3.4"})
    assert resp.status_code == 503
    assert "SpiderFoot" in resp.json().get("error", "")


def test_post_investigate_returns_job_id(app_with_osint):
    """POST /api/osint/investigate returns 202 + {job_id, status: RUNNING} when SF reachable."""
    with patch("backend.services.spiderfoot_client.SpiderFootClient.ping",
               new_callable=AsyncMock, return_value=True), \
         patch("backend.services.spiderfoot_client.SpiderFootClient.start_scan",
               new_callable=AsyncMock, return_value="sf-scan-abc"), \
         patch("asyncio.create_task"):  # prevent background poller from starting
        c = TestClient(app_with_osint, raise_server_exceptions=False)
        resp = c.post("/api/osint/investigate", json={"target": "1.2.3.4", "usecase": "passive"})
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "RUNNING"


def test_get_investigation_status(app_with_osint):
    """GET /api/osint/investigate/{job_id} returns job status dict."""
    # Pre-insert a job
    job_id = app_with_osint.state.osint_store.create_investigation("example.com", "investigate")
    c = TestClient(app_with_osint, raise_server_exceptions=False)
    resp = c.get(f"/api/osint/investigate/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == job_id
    assert data["target"] == "example.com"
    assert data["status"] == "RUNNING"


def test_get_investigations_list(app_with_osint):
    """GET /api/osint/investigations returns list of investigations."""
    app_with_osint.state.osint_store.create_investigation("1.1.1.1", "passive")
    c = TestClient(app_with_osint, raise_server_exceptions=False)
    resp = c.get("/api/osint/investigations")
    assert resp.status_code == 200
    data = resp.json()
    assert "investigations" in data
    assert len(data["investigations"]) >= 1


def test_post_dnstwist_returns_lookalikes(app_with_osint):
    """POST /api/osint/dnstwist returns {lookalikes, domain}."""
    mock_result = [{"fuzzer": "homoglyph", "domain": "examp1e.com", "dns_a": "1.2.3.4"}]
    with patch("backend.services.dnstwist_service.run_dnstwist",
               new_callable=AsyncMock, return_value=mock_result):
        c = TestClient(app_with_osint, raise_server_exceptions=False)
        resp = c.post("/api/osint/dnstwist", json={"domain": "example.com"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["domain"] == "example.com"
    assert len(data["lookalikes"]) == 1
    assert data["lookalikes"][0]["domain"] == "examp1e.com"


def test_get_investigation_includes_dnstwist_findings(app_with_osint):
    """GET /api/osint/investigate/{job_id} response includes dnstwist_findings key."""
    job_id = app_with_osint.state.osint_store.create_investigation("example.com", "passive")
    # Insert a dnstwist row for the domain
    app_with_osint.state.osint_store.bulk_insert_osint_findings([{
        "investigation_id": job_id, "event_type": "DOMAIN_NAME", "data": "example.com",
        "source_module": "sfp_dns", "confidence": 1.0, "misp_hit": 0, "misp_event_ids": "[]",
    }])
    app_with_osint.state.osint_store.bulk_insert_dnstwist_findings([{
        "investigation_id": job_id, "seed_domain": "example.com",
        "fuzzer": "homoglyph", "lookalike_domain": "examp1e.com",
        "dns_a": "1.2.3.4", "dns_mx": None, "whois_registrar": None, "whois_created": None,
    }])
    c = TestClient(app_with_osint, raise_server_exceptions=False)
    resp = c.get(f"/api/osint/investigate/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "dnstwist_findings" in data
    assert "example.com" in data["dnstwist_findings"]
    assert data["dnstwist_findings"]["example.com"][0]["lookalike_domain"] == "examp1e.com"


def test_get_findings_since_returns_new_rows(app_with_osint):
    """OsintInvestigationStore.get_findings_since() returns only rows with id > last_seen_id."""
    store = app_with_osint.state.osint_store
    job_id = store.create_investigation("example.com", "passive")
    store.bulk_insert_osint_findings([
        {"investigation_id": job_id, "event_type": "IP_ADDRESS", "data": "1.2.3.4",
         "source_module": "sfp_ripe", "confidence": 1.0, "misp_hit": 0, "misp_event_ids": "[]"},
        {"investigation_id": job_id, "event_type": "DOMAIN_NAME", "data": "evil.com",
         "source_module": "sfp_dns", "confidence": 0.9, "misp_hit": 0, "misp_event_ids": "[]"},
    ])
    all_rows = store.get_findings(job_id)
    assert len(all_rows) == 2
    first_id = min(r["id"] for r in all_rows)
    # get_findings_since with cursor at first row should return only the second row
    new_rows = store.get_findings_since(job_id, first_id)
    assert len(new_rows) == 1
    assert new_rows[0]["data"] == "evil.com"
    # with cursor at 0 should return all rows
    all_since = store.get_findings_since(job_id, 0)
    assert len(all_since) == 2


def test_get_investigation_stream_returns_sse_content_type(app_with_osint):
    """GET /api/osint/investigate/{job_id}/stream returns text/event-stream content type."""
    job_id = app_with_osint.state.osint_store.create_investigation("1.2.3.4", "passive")
    # Mark as FINISHED immediately so the generator exits after one iteration
    app_with_osint.state.osint_store.update_investigation_status(job_id, "FINISHED", "2026-01-01T00:00:00Z")
    c = TestClient(app_with_osint, raise_server_exceptions=False)
    resp = c.get(f"/api/osint/investigate/{job_id}/stream", headers={"Accept": "text/event-stream"})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")


def test_spiderfoot_health_in_system_health(app_with_osint):
    """GET /health response includes spiderfoot key."""
    with patch("backend.services.spiderfoot_client.SpiderFootClient.ping",
               new_callable=AsyncMock, return_value=False):
        c = TestClient(app_with_osint, raise_server_exceptions=False)
        resp = c.get("/health")
    # Health endpoint may return 200 or 503 depending on other services
    data = resp.json()
    # spiderfoot is nested inside components
    components = data.get("components", data)
    assert "spiderfoot" in components
