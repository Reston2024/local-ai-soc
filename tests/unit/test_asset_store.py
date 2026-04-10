"""
Wave 0 test stubs for Phase 34 AssetStore.
P34-T07 — SQLite CRUD for the assets table, IP classification.

Uses in-memory SQLite — no disk I/O.
"""

from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Try importing AssetStore — skip individual tests if not available
# ---------------------------------------------------------------------------
try:
    from backend.services.attack.asset_store import (
        AssetStore,
        _classify_ip,
        _apply_asset_upsert,
    )
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

# Also need the SQLiteStore DDL to set up in-memory DB
try:
    from backend.stores.sqlite_store import _DDL as _SQLITE_DDL
    _DDL_AVAILABLE = True
except ImportError:
    _DDL_AVAILABLE = False


def _make_conn() -> sqlite3.Connection:
    """Create in-memory SQLite connection with full schema."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if _DDL_AVAILABLE:
        conn.executescript(_SQLITE_DDL)
        conn.commit()
    return conn


# ---------------------------------------------------------------------------
# test_upsert_from_event
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_upsert_from_event():
    """upsert_asset() inserts a record and asset_count() == 1."""
    conn = _make_conn()
    store = AssetStore(conn)

    store.upsert_asset(
        ip="192.168.1.10",
        hostname="ws01",
        tag="internal",
        last_seen="2024-01-01T00:00:00Z",
    )

    assert store.asset_count() == 1


# ---------------------------------------------------------------------------
# test_internal_external_tag
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_internal_external_tag():
    """_classify_ip returns 'internal' for RFC1918/loopback, 'external' for public IPs."""
    assert _classify_ip("192.168.1.1") == "internal"
    assert _classify_ip("10.0.0.1") == "internal"
    assert _classify_ip("172.16.0.1") == "internal"
    assert _classify_ip("127.0.0.1") == "internal"
    assert _classify_ip("8.8.8.8") == "external"
    assert _classify_ip("1.1.1.1") == "external"


# ---------------------------------------------------------------------------
# test_upsert_dedup
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_upsert_dedup():
    """Upserting the same IP twice does not duplicate rows; last_seen is updated."""
    conn = _make_conn()
    store = AssetStore(conn)

    store.upsert_asset(
        ip="192.168.1.10",
        hostname="ws01",
        tag="internal",
        last_seen="2024-01-01T00:00:00Z",
    )
    store.upsert_asset(
        ip="192.168.1.10",
        hostname="ws01-renamed",
        tag="internal",
        last_seen="2024-02-01T00:00:00Z",
    )

    assert store.asset_count() == 1

    asset = store.get_asset("192.168.1.10")
    assert asset is not None
    assert asset["last_seen"] == "2024-02-01T00:00:00Z"


# ---------------------------------------------------------------------------
# test_null_ip_skip
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_null_ip_skip():
    """_apply_asset_upsert silently skips None src_ip and dst_ip; no error, no row inserted."""
    from unittest.mock import MagicMock
    from backend.models.event import NormalizedEvent

    conn = _make_conn()
    store = AssetStore(conn)

    # Create a minimal NormalizedEvent with no IPs
    event = MagicMock(spec=NormalizedEvent)
    event.src_ip = None
    event.dst_ip = None
    event.hostname = None

    # Must not raise
    _apply_asset_upsert(event, store)

    assert store.asset_count() == 0
