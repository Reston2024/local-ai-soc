"""
Wave 0 test stubs for Phase 33 IocStore.
P33-T04 (SQLite CRUD), P33-T08 (confidence decay).

Uses in-memory SQLite — no disk I/O.
"""

from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Try importing IocStore — skip individual tests if not available
# ---------------------------------------------------------------------------
try:
    from backend.services.intel.ioc_store import IocStore
    _IOCSTORE_AVAILABLE = True
except ImportError:
    _IOCSTORE_AVAILABLE = False

# Also need the SQLiteStore DDL to set up in-memory DB
try:
    from backend.stores.sqlite_store import _DDL as _SQLITE_DDL
    _DDL_AVAILABLE = True
except ImportError:
    _DDL_AVAILABLE = False


def _make_in_memory_conn() -> sqlite3.Connection:
    """Create in-memory SQLite connection with full schema."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if _DDL_AVAILABLE:
        conn.executescript(_SQLITE_DDL)
        conn.commit()
    return conn


# ---------------------------------------------------------------------------
# test_upsert_ioc_new
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _IOCSTORE_AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_upsert_ioc_new():
    """upsert_ioc() inserts new IOC and returns True."""
    conn = _make_in_memory_conn()
    store = IocStore(conn)

    is_new = store.upsert_ioc(
        value="10.0.0.1",
        ioc_type="ip",
        confidence=50,
        first_seen="2024-01-01T00:00:00Z",
        last_seen="2024-01-01T00:00:00Z",
        malware_family="Emotet",
        actor_tag="ta505",
        feed_source="feodo",
        extra_json=None,
    )

    assert is_new is True

    # Verify row in DB
    cursor = conn.execute("SELECT ioc_value, ioc_type, confidence FROM ioc_store WHERE ioc_value='10.0.0.1'")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "10.0.0.1"
    assert row[1] == "ip"
    assert row[2] == 50


# ---------------------------------------------------------------------------
# test_check_ioc_match_hit
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _IOCSTORE_AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_check_ioc_match_hit():
    """check_ioc_match() returns (True, confidence, actor_tag) for known-bad IP."""
    conn = _make_in_memory_conn()
    store = IocStore(conn)

    store.upsert_ioc(
        value="1.2.3.4",
        ioc_type="ip",
        confidence=75,
        first_seen="2024-01-01T00:00:00Z",
        last_seen="2024-01-01T00:00:00Z",
        malware_family="Emotet",
        actor_tag="ta505",
        feed_source="feodo",
        extra_json=None,
    )

    matched, confidence, actor_tag = store.check_ioc_match(src_ip="1.2.3.4", dst_ip=None)
    assert matched is True
    assert confidence == 75
    assert actor_tag == "ta505"


# ---------------------------------------------------------------------------
# test_check_ioc_match_miss
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _IOCSTORE_AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_check_ioc_match_miss():
    """check_ioc_match() returns (False, 0, None) for clean IPs."""
    conn = _make_in_memory_conn()
    store = IocStore(conn)

    matched, confidence, actor_tag = store.check_ioc_match(src_ip="8.8.8.8", dst_ip="1.1.1.1")
    assert matched is False
    assert confidence == 0
    assert actor_tag is None


# ---------------------------------------------------------------------------
# test_confidence_decay
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _IOCSTORE_AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_confidence_decay():
    """decay_confidence() reduces confidence and floor is 0."""
    conn = _make_in_memory_conn()
    store = IocStore(conn)

    # Insert with confidence=5 — decay should not go below 0
    store.upsert_ioc(
        value="2.2.2.2",
        ioc_type="ip",
        confidence=5,
        first_seen="2024-01-01T00:00:00Z",
        last_seen="2024-01-01T00:00:00Z",
        malware_family=None,
        actor_tag=None,
        feed_source="feodo",
        extra_json=None,
    )

    # Insert with confidence=50 — decay should reduce it
    store.upsert_ioc(
        value="3.3.3.3",
        ioc_type="ip",
        confidence=50,
        first_seen="2024-01-01T00:00:00Z",
        last_seen="2024-01-01T00:00:00Z",
        malware_family=None,
        actor_tag=None,
        feed_source="feodo",
        extra_json=None,
    )

    store.decay_confidence()

    cursor = conn.execute("SELECT ioc_value, confidence FROM ioc_store ORDER BY ioc_value")
    rows = {row[0]: row[1] for row in cursor.fetchall()}

    # Floor: 5 - 1 = 4 (or any decay, but not below 0)
    assert rows["2.2.2.2"] >= 0
    # Decayed: 50 - 1 = 49 (decay reduces)
    assert rows["3.3.3.3"] < 50
    assert rows["3.3.3.3"] >= 0
