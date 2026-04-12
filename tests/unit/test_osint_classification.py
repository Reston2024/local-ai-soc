"""
Wave 0 TDD stubs for Phase 41 OSINT classification extension.
P41-T06: extended ip-api geo fields (proxy/hosting/mobile)
P41-T07: ipapi.is parsing
P41-T03: ipsum tier lookup
P41-T04: Tor exit check
P41-T05: osint_cache schema migration
P41-T02: ipsum parser
All stubs SKIP RED until Plan 03 implements the classification methods.
"""
from __future__ import annotations
import pytest
import sqlite3

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

# Guard: check ipsum parser function
try:
    from backend.api.map import parse_ipsum_line
    _IPSUM_PARSER_AVAILABLE = True
except ImportError:
    _IPSUM_PARSER_AVAILABLE = False


def test_geo_ipapi_extended_fields():
    """_geo_ipapi() result includes proxy, hosting, mobile fields."""
    pytest.skip("stub — Plan 03 adds proxy/hosting/mobile to _geo_ipapi()")


def test_ipapi_is_parse():
    """_ipapi_is() returns dict with is_datacenter, is_tor, is_proxy, is_vpn, asn_type."""
    pytest.skip("stub — Plan 03 implements _ipapi_is()")


@pytest.mark.skipif(not _SQLITE_AVAILABLE, reason="SQLiteStore not available")
def test_ipsum_tier_lookup():
    """get_ipsum_tier() returns tier int for known IPs, None for unknown."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS ipsum_blocklist "
        "(ip TEXT PRIMARY KEY, tier INTEGER NOT NULL, fetched_date TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO ipsum_blocklist VALUES ('1.2.3.4', 5, '2026-04-12')")
    conn.commit()
    # Stub: Plan 03 adds get_ipsum_tier() to SQLiteStore
    pytest.skip("stub — Plan 03 implements get_ipsum_tier() on SQLiteStore")


@pytest.mark.skipif(not _SQLITE_AVAILABLE, reason="SQLiteStore not available")
def test_tor_exit_check():
    """get_tor_exit() returns truthy for known Tor exit IPs, None otherwise."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS tor_exit_nodes "
        "(ip TEXT PRIMARY KEY, fetched_date TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO tor_exit_nodes VALUES ('5.5.5.5', '2026-04-12')")
    conn.commit()
    # Stub: Plan 03 adds get_tor_exit() to SQLiteStore
    pytest.skip("stub — Plan 03 implements get_tor_exit() on SQLiteStore")


@pytest.mark.skipif(not _SQLITE_AVAILABLE, reason="SQLiteStore not available")
def test_osint_cache_schema_migration():
    """osint_cache table gains 5 classification columns after SQLiteStore init."""
    # Stub: Plan 03 adds idempotent ALTER TABLE in sqlite_store.py __init__
    pytest.skip("stub — Plan 03 adds classification columns to osint_cache via ALTER TABLE")


@pytest.mark.skipif(not _IPSUM_PARSER_AVAILABLE, reason="parse_ipsum_line not yet implemented")
def test_ipsum_parser():
    """ipsum.txt data lines parse to (ip, tier) tuples; comment lines are skipped."""
    from backend.api.map import parse_ipsum_line
    assert parse_ipsum_line("1.2.3.4\t3") == ("1.2.3.4", 3)
    assert parse_ipsum_line("# this is a comment") is None
    assert parse_ipsum_line("5.6.7.8\t1") == ("5.6.7.8", 1)
