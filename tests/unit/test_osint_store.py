"""Wave 0 TDD stubs for OsintInvestigationStore methods (Plan 51-02)."""
import pytest
import sqlite3

_STORE_AVAILABLE = False
try:
    from backend.services.osint_investigation_store import OsintInvestigationStore
    _STORE_AVAILABLE = True
except ImportError:
    pass

_skip = pytest.mark.skipif(not _STORE_AVAILABLE, reason="OsintInvestigationStore not yet implemented")


@pytest.fixture
def mem_store():
    conn = sqlite3.connect(":memory:")
    store = OsintInvestigationStore(conn)
    return store


@_skip
def test_create_investigation_returns_id(mem_store):
    """create_investigation() returns a non-empty string ID."""
    job_id = mem_store.create_investigation("1.2.3.4", "investigate")
    assert isinstance(job_id, str) and len(job_id) > 0


@_skip
def test_get_investigation_returns_row(mem_store):
    """get_investigation() returns dict with id, target, status keys."""
    job_id = mem_store.create_investigation("example.com", "passive")
    row = mem_store.get_investigation(job_id)
    assert row["id"] == job_id
    assert row["target"] == "example.com"
    assert row["status"] == "RUNNING"


@_skip
def test_update_investigation_status(mem_store):
    """update_investigation_status() changes status and sets completed_at."""
    job_id = mem_store.create_investigation("1.2.3.4", "investigate")
    mem_store.update_investigation_status(job_id, "FINISHED", "2026-01-01T00:00:00Z")
    row = mem_store.get_investigation(job_id)
    assert row["status"] == "FINISHED"
    assert row["completed_at"] == "2026-01-01T00:00:00Z"


@_skip
def test_bulk_insert_osint_findings(mem_store):
    """bulk_insert_osint_findings() inserts multiple rows."""
    job_id = mem_store.create_investigation("1.2.3.4", "investigate")
    findings = [
        {"investigation_id": job_id, "event_type": "IP_ADDRESS", "data": "5.6.7.8",
         "source_module": "sfp_ripe", "confidence": 1.0, "misp_hit": 0, "misp_event_ids": "[]"},
        {"investigation_id": job_id, "event_type": "DOMAIN_NAME", "data": "evil.com",
         "source_module": "sfp_dns", "confidence": 0.9, "misp_hit": 0, "misp_event_ids": "[]"},
    ]
    mem_store.bulk_insert_osint_findings(findings)
    rows = mem_store.get_findings(job_id)
    assert len(rows) == 2


@_skip
def test_bulk_query_ioc_cache_returns_matches(mem_store):
    """bulk_query_ioc_cache() queries ioc_store and returns matching values."""
    # Pre-populate ioc_store table
    conn = mem_store._conn
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ioc_store (
            ioc_value TEXT, ioc_type TEXT, confidence INTEGER, feed_source TEXT,
            actor_tag TEXT, malware_family TEXT, ioc_status TEXT,
            created_at TEXT, updated_at TEXT, PRIMARY KEY (ioc_value, ioc_type)
        )
    """)
    conn.execute("INSERT INTO ioc_store VALUES ('evil.com','domain',80,'feodo',NULL,NULL,'active','2026-01-01','2026-01-01')")
    conn.commit()
    hits = mem_store.bulk_query_ioc_cache(["evil.com", "good.com"])
    values = [h["value"] for h in hits]
    assert "evil.com" in values
    assert "good.com" not in values


@_skip
def test_bulk_insert_dnstwist_findings(mem_store):
    """bulk_insert_dnstwist_findings() inserts DNSTwist lookalikes."""
    job_id = mem_store.create_investigation("example.com", "investigate")
    lookalikes = [
        {"investigation_id": job_id, "seed_domain": "example.com",
         "fuzzer": "homoglyph", "lookalike_domain": "examp1e.com",
         "dns_a": "1.2.3.4", "dns_mx": None, "whois_registrar": None,
         "whois_created": None},
    ]
    mem_store.bulk_insert_dnstwist_findings(lookalikes)
    rows = mem_store.get_dnstwist_findings(job_id, "example.com")
    assert len(rows) == 1
    assert rows[0]["lookalike_domain"] == "examp1e.com"


@_skip
def test_list_investigations(mem_store):
    """list_investigations() returns rows sorted by started_at DESC."""
    mem_store.create_investigation("1.1.1.1", "investigate")
    mem_store.create_investigation("2.2.2.2", "passive")
    rows = mem_store.list_investigations()
    assert len(rows) == 2


@_skip
def test_get_findings_since(mem_store):
    """get_findings_since() returns only rows with id > last_seen_id."""
    assert False, "implement in Plan 51-02"
