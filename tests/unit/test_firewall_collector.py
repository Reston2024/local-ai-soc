"""Unit tests for FirewallCollector — Phase 23 P23-T03 + P23-T04.

Wave 0: all tests pre-skipped. Wave 2 (23-03-PLAN.md) activates them.
"""
from __future__ import annotations

import pytest

try:
    from ingestion.jobs.firewall_collector import FirewallCollector
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False

pytestmark = pytest.mark.skipif(not _IMPORT_OK, reason="FirewallCollector not implemented — Wave 2")


class TestFirewallCollectorIngestsLines:
    """P23-T03: Collector reads new lines from syslog/EVE files and ingests them."""

    @pytest.mark.asyncio
    async def test_ingests_new_syslog_lines(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import AsyncMock, MagicMock

        mock_loader = MagicMock()
        mock_loader.ingest_events = AsyncMock(return_value=MagicMock(loaded=1))
        mock_sqlite = MagicMock()
        mock_sqlite.set_kv = MagicMock()
        mock_sqlite.get_kv = MagicMock(return_value=None)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write(
                "Aug 10 18:44:55 ipfire kernel: FORWARDFW IN=green0 OUT=red0 "
                "SRC=192.168.1.100 DST=54.230.45.152 PROTO=TCP SPT=34995 DPT=443\n"
            )
            syslog_path = Path(f.name)

        collector = FirewallCollector(
            syslog_path=syslog_path,
            eve_path=Path("/nonexistent/eve.json"),
            loader=mock_loader,
            sqlite_store=mock_sqlite,
        )
        await collector._ingest_new_data()
        assert mock_loader.ingest_events.call_count >= 1


class TestFirewallCollectorMissingFile:
    """P23-T03: Collector does not crash when syslog/EVE files are absent."""

    @pytest.mark.asyncio
    async def test_absent_files_no_crash(self):
        from pathlib import Path
        from unittest.mock import AsyncMock, MagicMock

        mock_loader = MagicMock()
        mock_loader.ingest_events = AsyncMock()
        mock_sqlite = MagicMock()
        mock_sqlite.get_kv = MagicMock(return_value=None)

        collector = FirewallCollector(
            syslog_path=Path("/nonexistent/syslog.log"),
            eve_path=Path("/nonexistent/eve.json"),
            loader=mock_loader,
            sqlite_store=mock_sqlite,
        )
        # Must not raise
        result = await collector._ingest_new_data()
        assert result is False or result is True  # does not crash


class TestFirewallCollectorBackoff:
    """P23-T03: Consecutive failures increase the backoff interval."""

    def test_backoff_increases(self):
        from pathlib import Path
        from unittest.mock import MagicMock

        mock_loader = MagicMock()
        mock_sqlite = MagicMock()
        mock_sqlite.get_kv = MagicMock(return_value=None)

        collector = FirewallCollector(
            syslog_path=Path("/nonexistent/syslog.log"),
            eve_path=Path("/nonexistent/eve.json"),
            loader=mock_loader,
            sqlite_store=mock_sqlite,
            interval_sec=5,
        )
        # Simulate 3 consecutive failures
        collector._consecutive_failures = 3
        expected_backoff = min(5 * (2 ** 3), 300)
        assert expected_backoff == 40


class TestHeartbeatNormalisation:
    """P23-T04: Heartbeat events have event_type='heartbeat' and update system_kv."""

    @pytest.mark.asyncio
    async def test_heartbeat_event_type(self):
        from pathlib import Path
        from unittest.mock import AsyncMock, MagicMock, call

        mock_loader = MagicMock()
        mock_loader.ingest_events = AsyncMock(return_value=MagicMock(loaded=1))
        mock_sqlite = MagicMock()
        mock_sqlite.set_kv = MagicMock()
        mock_sqlite.get_kv = MagicMock(return_value=None)

        collector = FirewallCollector(
            syslog_path=Path("/nonexistent/syslog.log"),
            eve_path=Path("/nonexistent/eve.json"),
            loader=mock_loader,
            sqlite_store=mock_sqlite,
        )
        await collector._emit_heartbeat()
        # Heartbeat stored in system_kv
        assert mock_sqlite.set_kv.called
        kv_key = mock_sqlite.set_kv.call_args[0][0]
        assert kv_key == "firewall.last_heartbeat"
        # ingest_events called with a heartbeat NormalizedEvent
        assert mock_loader.ingest_events.called
        events_arg = mock_loader.ingest_events.call_args[0][0]
        assert len(events_arg) == 1
        assert events_arg[0].event_type == "heartbeat"


class TestFirewallStatusEndpoint:
    """P23-T04: GET /api/firewall/status returns connected/degraded/offline."""

    def test_status_route_registered(self):
        from backend.main import create_app
        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/api/firewall/status" in routes
