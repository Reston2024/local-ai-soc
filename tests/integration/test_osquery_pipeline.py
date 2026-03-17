"""Integration test: full osquery pipeline round-trip.

P8-T08: Write mock osquery NDJSON lines -> OsqueryCollector._ingest_new_lines()
         -> verify DuckDB execute_write called with INSERT SQL.

Does NOT require a running backend or real osquery daemon.
Uses in-memory mock store to verify write queue usage.

Wave 0: xfail stub. Wave 1 (08-01-PLAN.md) drives this to XPASS.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ingestion.osquery_collector import OsqueryCollector


MOCK_PROCESS_LINE = json.dumps({
    "name": "processes",
    "hostIdentifier": "WORKSTATION-01",
    "calendarTime": "Mon Mar 17 10:00:00 2026 UTC",
    "unixTime": 1742205600,
    "action": "snapshot",
    "snapshot": [
        {"pid": "4821", "name": "powershell.exe", "path": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe", "cmdline": "powershell.exe -nop -w hidden", "parent": "1234"},
        {"pid": "9042", "name": "cmd.exe", "cmdline": "cmd.exe /c whoami", "parent": "4821"},
    ],
})

MOCK_NETWORK_LINE = json.dumps({
    "name": "open_sockets",
    "hostIdentifier": "WORKSTATION-01",
    "unixTime": 1742205660,
    "action": "added",
    "columns": {
        "pid": "4821",
        "local_address": "192.168.1.5",
        "local_port": "49152",
        "remote_address": "10.0.0.1",
        "remote_port": "443",
        "state": "ESTABLISHED",
    },
})


class TestOsqueryPipelineRoundTrip:
    """P8-T08: Mock file -> collector -> DuckDB write queue."""

    @pytest.mark.xfail(strict=False, reason="OsqueryCollector._ingest_new_lines() not implemented — Wave 1")
    @pytest.mark.asyncio
    async def test_mock_lines_ingested_to_duckdb(self):
        """Write 2 mock osquery lines, verify 3 events are enqueued (2 snapshot rows + 1 differential)."""
        mock_store = MagicMock()
        mock_store.execute_write = AsyncMock()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, encoding="utf-8"
        ) as f:
            f.write(MOCK_PROCESS_LINE + "\n")
            f.write(MOCK_NETWORK_LINE + "\n")
            log_path = Path(f.name)

        collector = OsqueryCollector(log_path=log_path, duckdb_store=mock_store)
        # Simulate initial read (offset=0)
        await collector._ingest_new_lines()

        # snapshot with 2 rows + 1 differential row = 3 execute_write calls
        assert mock_store.execute_write.call_count >= 3, (
            f"Expected >= 3 DuckDB write calls for 3 events, got {mock_store.execute_write.call_count}"
        )
        assert collector.lines_processed >= 2
