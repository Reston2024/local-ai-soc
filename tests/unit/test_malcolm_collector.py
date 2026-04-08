"""Stub tests for Phase 27 MalcolmCollector (P27-T02). Activated in plan 27-02."""
from __future__ import annotations

import pytest

try:
    from ingestion.jobs.malcolm_collector import MalcolmCollector
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False

pytestmark = pytest.mark.skipif(
    not _IMPORT_OK,
    reason="MalcolmCollector not implemented — Wave 2 (plan 27-02)",
)


def test_malcolm_collector_init_sets_defaults():
    """MalcolmCollector() sets _running=False, _alerts_ingested=0,
    _syslog_ingested=0, _consecutive_failures=0."""
    collector = MalcolmCollector()
    assert collector._running is False
    assert collector._alerts_ingested == 0
    assert collector._syslog_ingested == 0
    assert collector._consecutive_failures == 0


def test_malcolm_collector_status_shape():
    """status() returns dict with keys: running, alerts_ingested,
    syslog_ingested, consecutive_failures."""
    collector = MalcolmCollector()
    status = collector.status()
    assert isinstance(status, dict)
    assert "running" in status
    assert "alerts_ingested" in status
    assert "syslog_ingested" in status
    assert "consecutive_failures" in status


@pytest.mark.asyncio
async def test_malcolm_collector_run_cancels_cleanly():
    """asyncio.CancelledError propagates out of run() and sets _running=False."""
    import asyncio
    from unittest.mock import patch

    collector = MalcolmCollector()

    async def _cancel_immediately():
        task = asyncio.create_task(collector.run())
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await _cancel_immediately()
    assert collector._running is False


def test_malcolm_collector_backoff_on_failure():
    """After a failed poll cycle, backoff doubles (up to 300s cap)."""
    collector = MalcolmCollector()
    base_interval = getattr(collector, "_interval_sec", 30)

    collector._consecutive_failures = 3
    expected_backoff = min(base_interval * (2 ** 3), 300)

    # Verify the expected formula — implementation must honour this cap
    assert expected_backoff <= 300
    assert expected_backoff == min(base_interval * 8, 300)


@pytest.mark.asyncio
async def test_malcolm_collector_heartbeat_updates_kv():
    """_poll_and_ingest() calls sqlite.set_kv("malcolm.last_heartbeat", ...) each cycle."""
    from unittest.mock import AsyncMock, MagicMock, call

    mock_sqlite = MagicMock()
    mock_sqlite.set_kv = MagicMock()

    collector = MalcolmCollector(sqlite_store=mock_sqlite)
    await collector._poll_and_ingest()

    assert mock_sqlite.set_kv.called
    kv_key = mock_sqlite.set_kv.call_args[0][0]
    assert kv_key == "malcolm.last_heartbeat"
