"""Unit tests for OsqueryCollector — Phase 8 live telemetry collection.

Tests P8-T01 through P8-T04. Wave 0: all stubs are xfail.
Wave 1 (08-01-PLAN.md) will implement OsqueryCollector and drive these to XPASS.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ingestion.osquery_collector import OsqueryCollector


class TestOsqueryCollectorReadsLines:
    """P8-T01: Collector reads new lines from file and parses them."""

    @pytest.mark.xfail(strict=False, reason="OsqueryCollector.run() not implemented — Wave 1")
    @pytest.mark.asyncio
    async def test_reads_lines(self):
        mock_store = MagicMock()
        mock_store.execute_write = AsyncMock()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            line = json.dumps({
                "name": "processes",
                "hostIdentifier": "test-host",
                "unixTime": 1742205600,
                "action": "added",
                "columns": {"pid": "1234", "name": "powershell.exe", "cmdline": "powershell.exe -nop"},
            })
            f.write(line + "\n")
            log_path = Path(f.name)
        collector = OsqueryCollector(log_path=log_path, duckdb_store=mock_store)
        await collector._ingest_new_lines()
        assert mock_store.execute_write.call_count >= 1
        assert collector.lines_processed >= 1


class TestOsqueryCollectorMissingLog:
    """P8-T02: Collector skips gracefully when log file does not exist."""

    @pytest.mark.xfail(strict=False, reason="OsqueryCollector._ingest_new_lines() not implemented — Wave 1")
    @pytest.mark.asyncio
    async def test_missing_log_graceful(self):
        mock_store = MagicMock()
        mock_store.execute_write = AsyncMock()
        collector = OsqueryCollector(
            log_path=Path("/nonexistent/path/osqueryd.results.log"),
            duckdb_store=mock_store,
        )
        # Must not raise — just return silently
        await collector._ingest_new_lines()
        mock_store.execute_write.assert_not_called()


class TestOsqueryCollectorWriteQueue:
    """P8-T03: Collector writes through DuckDB write queue, not direct connection."""

    @pytest.mark.xfail(strict=False, reason="OsqueryCollector._ingest_new_lines() not implemented — Wave 1")
    @pytest.mark.asyncio
    async def test_uses_write_queue(self):
        mock_store = MagicMock()
        mock_store.execute_write = AsyncMock()
        # Ensure no direct duckdb.connect() usage — only store.execute_write is called
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            line = json.dumps({
                "name": "processes",
                "unixTime": 1742205600,
                "action": "snapshot",
                "snapshot": [{"pid": "42", "name": "cmd.exe"}],
            })
            f.write(line + "\n")
            log_path = Path(f.name)
        collector = OsqueryCollector(log_path=log_path, duckdb_store=mock_store)
        await collector._ingest_new_lines()
        # Writes must go through execute_write (async queue pattern)
        assert mock_store.execute_write.called


class TestOsqueryCollectorDisabled:
    """P8-T04: OSQUERY_ENABLED=False means collector is not started."""

    @pytest.mark.xfail(strict=False, reason="main.py OSQUERY_ENABLED guard not implemented — Wave 1")
    def test_disabled_no_start(self):
        # When OSQUERY_ENABLED is False, OsqueryCollector should not be
        # instantiated in the lifespan. We test the guard logic directly
        # by verifying settings default is False.
        from backend.core.config import Settings
        s = Settings()
        assert hasattr(s, "OSQUERY_ENABLED")
        assert s.OSQUERY_ENABLED is False, "Default must be False so system starts without osquery"
