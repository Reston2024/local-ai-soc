"""
Wave 0 test stubs for Phase 33 IOC matching.
P33-T06 (at-ingest matching), P33-T07 (retroactive scan), P33-T14 (NormalizedEvent fields).

Tests reference not-yet-implemented code and are marked skip where needed.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Try importing dependencies
# ---------------------------------------------------------------------------
try:
    from backend.services.intel.ioc_store import IocStore
    _IOCSTORE_AVAILABLE = True
except ImportError:
    _IOCSTORE_AVAILABLE = False

try:
    from backend.stores.sqlite_store import _DDL as _SQLITE_DDL
    _DDL_AVAILABLE = True
except ImportError:
    _DDL_AVAILABLE = False

# _apply_ioc_matching is implemented in Plan 02 (ingestion/loader.py)
try:
    from ingestion.loader import _apply_ioc_matching
    _APPLY_IOC_AVAILABLE = True
except (ImportError, AttributeError):
    _APPLY_IOC_AVAILABLE = False

# retroactive_ioc_scan is implemented in Plan 02 (ingestion/loader.py)
try:
    from ingestion.loader import retroactive_ioc_scan
    _RETRO_SCAN_AVAILABLE = True
except (ImportError, AttributeError):
    _RETRO_SCAN_AVAILABLE = False


def _make_in_memory_ioc_store() -> "IocStore":
    """Helper: in-memory SQLite + IocStore."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if _DDL_AVAILABLE:
        conn.executescript(_SQLITE_DDL)
        conn.commit()
    return IocStore(conn)


# ---------------------------------------------------------------------------
# test_at_ingest_match — seed store, call _apply_ioc_matching
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not _IOCSTORE_AVAILABLE or not _APPLY_IOC_AVAILABLE,
    reason="Wave 0 stub — implementation in Plan 02 Task 2"
)
def test_at_ingest_match():
    """_apply_ioc_matching sets ioc_matched=True when src_ip is in ioc_store."""
    from backend.models.event import NormalizedEvent
    from datetime import datetime, timezone

    ioc_store = _make_in_memory_ioc_store()
    ioc_store.upsert_ioc(
        value="10.0.0.1",
        ioc_type="ip",
        confidence=80,
        first_seen="2024-01-01T00:00:00Z",
        last_seen="2024-01-01T00:00:00Z",
        malware_family="Emotet",
        actor_tag="ta505",
        feed_source="feodo",
        extra_json=None,
    )

    event = NormalizedEvent(
        event_id="test-001",
        timestamp=datetime.now(tz=timezone.utc),
        ingested_at=datetime.now(tz=timezone.utc),
        src_ip="10.0.0.1",
    )

    _apply_ioc_matching(event, ioc_store)

    assert event.ioc_matched is True
    assert event.ioc_confidence > 0


# ---------------------------------------------------------------------------
# test_at_ingest_no_match
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not _IOCSTORE_AVAILABLE or not _APPLY_IOC_AVAILABLE,
    reason="Wave 0 stub — implementation in Plan 02 Task 2"
)
def test_at_ingest_no_match():
    """_apply_ioc_matching leaves ioc_matched=False when src_ip not in ioc_store."""
    from backend.models.event import NormalizedEvent
    from datetime import datetime, timezone

    ioc_store = _make_in_memory_ioc_store()

    event = NormalizedEvent(
        event_id="test-002",
        timestamp=datetime.now(tz=timezone.utc),
        ingested_at=datetime.now(tz=timezone.utc),
        src_ip="8.8.8.8",
    )

    _apply_ioc_matching(event, ioc_store)

    assert event.ioc_matched is False


# ---------------------------------------------------------------------------
# test_retroactive_scan
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not _IOCSTORE_AVAILABLE or not _RETRO_SCAN_AVAILABLE,
    reason="Wave 0 stub — implementation in Plan 02 Task 2"
)
@pytest.mark.asyncio
async def test_retroactive_scan():
    """retroactive_ioc_scan calls execute_write for each matching event."""
    from datetime import datetime, timezone

    ioc_store = _make_in_memory_ioc_store()
    ioc_store.upsert_ioc(
        value="10.0.0.1",
        ioc_type="ip",
        confidence=80,
        first_seen="2024-01-01T00:00:00Z",
        last_seen="2024-01-01T00:00:00Z",
        malware_family="Emotet",
        actor_tag="ta505",
        feed_source="feodo",
        extra_json=None,
    )

    mock_duckdb = MagicMock()
    mock_duckdb.fetch_all = AsyncMock(return_value=[
        ("evt-001", "10.0.0.1", None),
        ("evt-002", "10.0.0.1", None),
    ])
    mock_duckdb.execute_write = AsyncMock(return_value=None)

    await retroactive_ioc_scan(
        ioc_value="10.0.0.1",
        ioc_type="ip",
        bare_ip=None,
        confidence=80,
        ioc_store=ioc_store,
        duckdb_store=mock_duckdb,
    )

    # execute_write called for each matching event
    assert mock_duckdb.execute_write.call_count >= 2


# ---------------------------------------------------------------------------
# test_normalized_event_fields
# ---------------------------------------------------------------------------

def test_normalized_event_fields():
    """NormalizedEvent accepts ioc_matched, ioc_confidence, ioc_actor_tag fields."""
    from backend.models.event import NormalizedEvent
    from datetime import datetime, timezone

    event = NormalizedEvent(
        event_id="test-003",
        timestamp=datetime.now(tz=timezone.utc),
        ingested_at=datetime.now(tz=timezone.utc),
        ioc_matched=True,
        ioc_confidence=50,
        ioc_actor_tag="emotet",
    )

    assert event.ioc_matched is True
    assert event.ioc_confidence == 50
    assert event.ioc_actor_tag == "emotet"
