"""
OsqueryCollector — live osquery results log tail-and-ingest loop.

Reads new lines appended to osqueryd.results.log, parses them with
OsqueryParser.parse_result(), and writes events to DuckDB via the
existing write queue pattern.

Implementation added in Phase 8 Wave 1 (08-01-PLAN.md).
"""
from __future__ import annotations

from pathlib import Path


class OsqueryCollector:
    """
    Background asyncio task: tail osqueryd.results.log, parse, ingest.
    Stub — full implementation in Wave 1.
    """
    def __init__(self, log_path: Path, duckdb_store, interval_sec: int = 5):
        self._log_path = log_path
        self._store = duckdb_store
        self._interval = interval_sec
        self._offset: int = 0
        self.lines_processed: int = 0
        self._running: bool = False
        self._error: str | None = None

    async def run(self) -> None:
        """Main collection loop. Stub raises NotImplementedError until Wave 1."""
        raise NotImplementedError("OsqueryCollector.run() implemented in Wave 1")

    async def _ingest_new_lines(self) -> None:
        """Read and ingest new lines from the log file. Stub raises NotImplementedError until Wave 1."""
        raise NotImplementedError("OsqueryCollector._ingest_new_lines() implemented in Wave 1")

    def status(self) -> dict:
        """Return current collector state dict."""
        return {
            "running": self._running,
            "lines_processed": self.lines_processed,
            "error": self._error,
        }
