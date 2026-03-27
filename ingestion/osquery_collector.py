"""
OsqueryCollector — live osquery results log tail-and-ingest loop.

Reads new lines appended to osqueryd.results.log, parses them with
OsqueryParser.parse_result(), and writes events to DuckDB via the
existing write queue pattern.

If osquery runs as Windows SYSTEM service, grant Users:R on log directory:
    icacls "C:\\Program Files\\osquery\\log" /grant Users:R
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ingestion.parsers.osquery_parser import OsqueryParser

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

_INSERT_SQL = """
INSERT OR IGNORE INTO normalized_events (
    event_id, timestamp, ingested_at, source_type, source_file,
    hostname, username, process_name, process_id,
    parent_process_name, parent_process_id,
    file_path, file_hash_sha256, command_line,
    src_ip, src_port, dst_ip, dst_port, domain, url,
    event_type, severity, confidence, detection_source,
    attack_technique, attack_tactic,
    raw_event, tags, case_id
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


class OsqueryCollector:
    """Background asyncio task: tail osqueryd.results.log, parse, ingest."""

    def __init__(self, log_path: Path, duckdb_store, interval_sec: int = 5):
        self._log_path = log_path
        self._store = duckdb_store
        self._interval = interval_sec
        self._offset: int = 0
        self.lines_processed: int = 0
        self._running: bool = False
        self._error: str | None = None
        self._parser = OsqueryParser()

    async def run(self) -> None:
        """Main polling loop. Cancellation propagates via CancelledError."""
        self._running = True
        try:
            while True:
                await asyncio.sleep(self._interval)
                await self._ingest_new_lines()
        except asyncio.CancelledError:
            self._running = False
            raise

    async def _ingest_new_lines(self) -> None:
        """Read new lines from log file and write parsed events to DuckDB."""
        if not self._log_path.exists():
            return
        try:
            new_lines = await asyncio.to_thread(self._read_new_lines)
        except Exception as exc:
            self._error = str(exc)
            log.warning("OsqueryCollector read error: %s", exc)
            return

        for line in new_lines:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                log.debug("Skipping non-JSON line: %r", line[:100])
                continue
            try:
                events = self._parser.parse_result(record, source_file="osquery_live")
                for evt in events:
                    row = self._build_row(evt)
                    await self._store.execute_write(_INSERT_SQL, row)
                self.lines_processed += 1
            except Exception as exc:
                self._error = str(exc)
                log.warning("OsqueryCollector parse/write error: %s", exc)

    def _read_new_lines(self) -> list[str]:
        """Blocking file read — run via asyncio.to_thread."""
        try:
            with self._log_path.open(encoding="utf-8", errors="replace") as fh:
                fh.seek(self._offset)
                data = fh.read()
                self._offset = fh.tell()
            return [ln.strip() for ln in data.splitlines() if ln.strip()]
        except PermissionError as exc:
            self._error = (
                f"PermissionError reading osquery log: {exc}. "
                f"Fix: icacls \"{self._log_path.parent}\" /grant Users:R"
            )
            log.warning(self._error)
            return []

    def _build_row(self, evt) -> list:
        """Build DuckDB row from NormalizedEvent in _EVENT_COLUMNS order."""
        # to_duckdb_row() returns a tuple; execute_write expects list[Any]
        if hasattr(evt, "to_duckdb_row"):
            return list(evt.to_duckdb_row())
        return [
            evt.event_id, evt.timestamp, evt.ingested_at, evt.source_type, evt.source_file,
            evt.hostname, evt.username, evt.process_name, evt.process_id,
            evt.parent_process_name, evt.parent_process_id,
            evt.file_path, evt.file_hash_sha256, evt.command_line,
            evt.src_ip, evt.src_port, evt.dst_ip, evt.dst_port, evt.domain, evt.url,
            evt.event_type, evt.severity, evt.confidence, evt.detection_source,
            evt.attack_technique, evt.attack_tactic,
            evt.raw_event, evt.tags, evt.case_id,
        ]

    def status(self) -> dict:
        """Return current collector state."""
        return {
            "running": self._running,
            "lines_processed": self.lines_processed,
            "error": self._error,
        }
