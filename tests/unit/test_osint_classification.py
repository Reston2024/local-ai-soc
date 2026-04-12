"""
TDD tests for Phase 41 OSINT classification extension.
P41-T06: extended ip-api geo fields (proxy/hosting/mobile)
P41-T07: ipapi.is parsing
P41-T03: ipsum tier lookup
P41-T04: Tor exit check
P41-T05: osint_cache schema migration
P41-T02: ipsum parser
"""
from __future__ import annotations
import pytest
import sqlite3
from unittest.mock import AsyncMock, patch, MagicMock

pytestmark = pytest.mark.unit

# Guard: skip osint tests if classification methods not yet added
try:
    from backend.services.osint import OsintService
    # Check for new classification methods
    _has_ipapi_is = hasattr(OsintService, '_ipapi_is')
    _has_ipsum = hasattr(OsintService, '_ipsum_check')
    _OSINT_CLASSIFY_AVAILABLE = _has_ipapi_is and _has_ipsum
except ImportError:
    _OSINT_CLASSIFY_AVAILABLE = False

# Guard: check sqlite_store has classification columns
try:
    from backend.stores.sqlite_store import SQLiteStore
    _SQLITE_AVAILABLE = True
except ImportError:
    _SQLITE_AVAILABLE = False

# Guard: check ipsum parser function (local helper in osint.py)
try:
    from backend.services.osint import _parse_ipsum_line_local
    _IPSUM_PARSER_AVAILABLE = True
except ImportError:
    _IPSUM_PARSER_AVAILABLE = False


# ---------------------------------------------------------------------------
# SQLiteStore schema migration tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _SQLITE_AVAILABLE, reason="SQLiteStore not available")
def test_osint_cache_schema_migration():
    """osint_cache table gains 5 classification columns after SQLiteStore init."""
    store = SQLiteStore(":memory:")
    # Verify all 5 classification columns exist on osint_cache
    cursor = store._conn.execute("PRAGMA table_info(osint_cache)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "ip_type" in columns, "ip_type column missing from osint_cache"
    assert "ipsum_tier" in columns, "ipsum_tier column missing from osint_cache"
    assert "is_tor" in columns, "is_tor column missing from osint_cache"
    assert "is_proxy" in columns, "is_proxy column missing from osint_cache"
    assert "is_datacenter" in columns, "is_datacenter column missing from osint_cache"


@pytest.mark.skipif(not _SQLITE_AVAILABLE, reason="SQLiteStore not available")
def test_ipsum_blocklist_table_created():
    """ipsum_blocklist table is created by SQLiteStore.__init__()."""
    store = SQLiteStore(":memory:")
    cursor = store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ipsum_blocklist'"
    )
    assert cursor.fetchone() is not None, "ipsum_blocklist table not created"


@pytest.mark.skipif(not _SQLITE_AVAILABLE, reason="SQLiteStore not available")
def test_tor_exit_nodes_table_created():
    """tor_exit_nodes table is created by SQLiteStore.__init__()."""
    store = SQLiteStore(":memory:")
    cursor = store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tor_exit_nodes'"
    )
    assert cursor.fetchone() is not None, "tor_exit_nodes table not created"


@pytest.mark.skipif(not _SQLITE_AVAILABLE, reason="SQLiteStore not available")
def test_ipsum_tier_lookup():
    """get_ipsum_tier() returns tier int for known IPs, None for unknown."""
    store = SQLiteStore(":memory:")
    # Insert a test entry directly
    store._conn.execute(
        "INSERT INTO ipsum_blocklist (ip, tier, fetched_date) VALUES (?, ?, ?)",
        ("1.2.3.4", 5, "2026-04-12"),
    )
    store._conn.commit()
    assert store.get_ipsum_tier("1.2.3.4") == 5
    assert store.get_ipsum_tier("9.9.9.9") is None


@pytest.mark.skipif(not _SQLITE_AVAILABLE, reason="SQLiteStore not available")
def test_tor_exit_check():
    """get_tor_exit() returns truthy for known Tor exit IPs, None otherwise."""
    store = SQLiteStore(":memory:")
    store._conn.execute(
        "INSERT INTO tor_exit_nodes (ip, fetched_date) VALUES (?, ?)",
        ("5.5.5.5", "2026-04-12"),
    )
    store._conn.commit()
    assert store.get_tor_exit("5.5.5.5") is not None
    assert store.get_tor_exit("1.1.1.1") is None


@pytest.mark.skipif(not _SQLITE_AVAILABLE, reason="SQLiteStore not available")
def test_bulk_insert_ipsum():
    """bulk_insert_ipsum() inserts entries and handles empty list gracefully."""
    store = SQLiteStore(":memory:")
    entries = [
        ("1.1.1.1", 3, "2026-04-12"),
        ("2.2.2.2", 7, "2026-04-12"),
    ]
    store.bulk_insert_ipsum(entries)
    assert store.get_ipsum_tier("1.1.1.1") == 3
    assert store.get_ipsum_tier("2.2.2.2") == 7
    # Empty list should not crash
    store.bulk_insert_ipsum([])


@pytest.mark.skipif(not _SQLITE_AVAILABLE, reason="SQLiteStore not available")
def test_bulk_insert_tor_exits():
    """bulk_insert_tor_exits() inserts IPs and clears stale entries."""
    store = SQLiteStore(":memory:")
    store.bulk_insert_tor_exits(["10.0.0.1", "10.0.0.2"], "2026-04-12")
    assert store.get_tor_exit("10.0.0.1") is not None
    assert store.get_tor_exit("10.0.0.2") is not None
    assert store.get_tor_exit("99.99.99.99") is None


@pytest.mark.skipif(not _SQLITE_AVAILABLE, reason="SQLiteStore not available")
def test_set_classification_cache():
    """set_classification_cache() updates classification columns on osint_cache row."""
    store = SQLiteStore(":memory:")
    # Insert a cache row first
    store._conn.execute(
        "INSERT INTO osint_cache (ip, result_json, fetched_at, expires_at) VALUES (?, ?, ?, ?)",
        ("8.8.8.8", '{}', "2026-04-12T00:00:00Z", "2026-04-13T00:00:00Z"),
    )
    store._conn.commit()
    store.set_classification_cache(
        ip="8.8.8.8",
        ip_type="datacenter",
        ipsum_tier=2,
        is_tor=False,
        is_proxy=True,
        is_datacenter=True,
    )
    row = store._conn.execute(
        "SELECT ip_type, ipsum_tier, is_tor, is_proxy, is_datacenter FROM osint_cache WHERE ip=?",
        ("8.8.8.8",),
    ).fetchone()
    assert row is not None
    assert row[0] == "datacenter"
    assert row[1] == 2
    assert row[2] == 0   # is_tor=False stored as 0
    assert row[3] == 1   # is_proxy=True stored as 1
    assert row[4] == 1   # is_datacenter=True stored as 1


# ---------------------------------------------------------------------------
# ipsum parser (module-level helper in osint.py)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _IPSUM_PARSER_AVAILABLE, reason="_parse_ipsum_line_local not yet added to osint.py")
def test_ipsum_parser():
    """ipsum.txt data lines parse to (ip, tier) tuples; comment lines are skipped."""
    from backend.services.osint import _parse_ipsum_line_local
    assert _parse_ipsum_line_local("1.2.3.4\t3") == ("1.2.3.4", 3)
    assert _parse_ipsum_line_local("# this is a comment") is None
    assert _parse_ipsum_line_local("5.6.7.8\t1") == ("5.6.7.8", 1)
    assert _parse_ipsum_line_local("") is None
    assert _parse_ipsum_line_local("no_tab_here") is None


# ---------------------------------------------------------------------------
# OsintService extended geo fields
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _OSINT_CLASSIFY_AVAILABLE, reason="OsintService classification methods not yet implemented")
@pytest.mark.asyncio
async def test_geo_ipapi_extended_fields():
    """_geo_ipapi() result includes proxy, hosting, mobile boolean fields."""
    mock_store = MagicMock()
    svc = OsintService(mock_store)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "country": "United States",
        "countryCode": "US",
        "city": "New York",
        "lat": 40.7128,
        "lon": -74.0060,
        "as": "AS15169 Google LLC",
        "org": "Google LLC",
        "proxy": True,
        "hosting": False,
        "mobile": False,
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await svc._geo_ipapi("8.8.8.8")

    assert result is not None
    assert "proxy" in result, "proxy field missing from _geo_ipapi result"
    assert "hosting" in result, "hosting field missing from _geo_ipapi result"
    assert "mobile" in result, "mobile field missing from _geo_ipapi result"
    assert result["proxy"] is True
    assert result["hosting"] is False
    assert result["mobile"] is False


# ---------------------------------------------------------------------------
# OsintService._ipapi_is() parsing
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _OSINT_CLASSIFY_AVAILABLE, reason="OsintService classification methods not yet implemented")
@pytest.mark.asyncio
async def test_ipapi_is_parse():
    """_ipapi_is() returns dict with is_datacenter, is_tor, is_proxy, is_vpn, asn_type."""
    mock_store = MagicMock()
    svc = OsintService(mock_store)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "is_datacenter": True,
        "is_tor": False,
        "is_proxy": False,
        "is_vpn": False,
        "asn": {"type": "hosting"},
        "company": {"type": "hosting"},
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await svc._ipapi_is("8.8.8.8")

    assert result is not None
    assert "is_datacenter" in result
    assert "is_tor" in result
    assert "is_proxy" in result
    assert "is_vpn" in result
    assert "asn_type" in result
    assert result["is_datacenter"] is True
    assert result["asn_type"] == "hosting"


@pytest.mark.skipif(not _OSINT_CLASSIFY_AVAILABLE, reason="OsintService classification methods not yet implemented")
@pytest.mark.asyncio
async def test_ipapi_is_quota_guard():
    """_ipapi_is() returns None when daily quota (900) is reached."""
    import backend.services.osint as osint_module
    mock_store = MagicMock()
    svc = OsintService(mock_store)

    # Force counter to limit
    import datetime
    osint_module._ipapiis_calls_today = 900
    osint_module._ipapiis_last_reset = datetime.date.today().isoformat()

    result = await svc._ipapi_is("8.8.8.8")
    assert result is None, "Expected None when quota guard is triggered"

    # Reset for other tests
    osint_module._ipapiis_calls_today = 0
