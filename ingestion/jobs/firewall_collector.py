"""
Firewall telemetry collector — tails IPFire syslog and Suricata EVE JSON files.

Mirrors the OsqueryCollector pattern:
- File-tail loop with configurable poll interval
- Exponential backoff on consecutive failures
- Heartbeat events normalised to NormalizedEvent(event_type='heartbeat')
- All events written through IngestionLoader.ingest_events() (not raw execute_write)
- last_heartbeat stored in system_kv via SQLiteStore.set_kv()
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.core.config import settings as _settings
from backend.core.logging import get_logger
from backend.models.event import NormalizedEvent

log = get_logger(__name__)


class FirewallCollector:
    """Background asyncio task: tail IPFire syslog + Suricata EVE JSON files and ingest events."""

    def __init__(
        self,
        syslog_path: Path,
        eve_path: Path,
        loader,
        sqlite_store,
        interval_sec: int = 5,
    ) -> None:
        self._syslog_path = syslog_path
        self._eve_path = eve_path
        self._loader = loader
        self._sqlite = sqlite_store
        self._interval = interval_sec
        self._syslog_offset: int = 0
        self._eve_offset: int = 0
        self._consecutive_failures: int = 0
        self._running: bool = False
        self._syslog_lines_processed: int = 0
        self._eve_lines_processed: int = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_new_lines(path: Path, offset: int) -> tuple[list[str], int]:
        """
        Read new lines from *path* starting at *offset*.

        Called via asyncio.to_thread — synchronous, safe to block.

        Returns:
            (lines, new_offset) — lines is empty list if file absent.
        """
        if not path.exists():
            return [], offset
        with open(path, encoding="utf-8", errors="replace") as fh:
            fh.seek(offset)
            lines = fh.readlines()
            new_offset = fh.tell()
        return lines, new_offset

    async def _ingest_new_data(self) -> bool:
        """
        Read and ingest new syslog and EVE lines, then emit a heartbeat.

        Returns True on success (even if files are empty), False on unexpected error.
        """
        from ingestion.parsers.ipfire_syslog_parser import IPFireSyslogParser
        from ingestion.parsers.suricata_eve_parser import SuricataEveParser

        try:
            # --- Syslog ---
            lines, self._syslog_offset = await asyncio.to_thread(
                self._read_new_lines, self._syslog_path, self._syslog_offset
            )
            syslog_batch: list[NormalizedEvent] = []
            syslog_parser = IPFireSyslogParser()
            for line in lines:
                line = line.rstrip("\n")
                if not line:
                    continue
                event = syslog_parser.parse_line(line)
                if event is not None:
                    syslog_batch.append(event)
            if syslog_batch:
                await self._loader.ingest_events(syslog_batch)
                self._syslog_lines_processed += len(syslog_batch)

            # --- EVE JSON ---
            eve_lines, self._eve_offset = await asyncio.to_thread(
                self._read_new_lines, self._eve_path, self._eve_offset
            )
            eve_batch: list[NormalizedEvent] = []
            eve_parser = SuricataEveParser()
            for line in eve_lines:
                line = line.rstrip("\n")
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    log.debug("FirewallCollector: skipping non-JSON EVE line", line=line[:80])
                    continue
                event = eve_parser.parse_record(record)
                if event is not None:
                    eve_batch.append(event)
            if eve_batch:
                await self._loader.ingest_events(eve_batch)
                self._eve_lines_processed += len(eve_batch)

            # Always emit heartbeat (proves collector loop is alive)
            await self._emit_heartbeat()
            return True

        except Exception as exc:
            log.warning("FirewallCollector ingest error", error=str(exc))
            return False

    async def _emit_heartbeat(self) -> None:
        """Store heartbeat timestamp in system_kv and ingest a heartbeat NormalizedEvent."""
        iso_str = datetime.now(timezone.utc).isoformat()
        await asyncio.to_thread(self._sqlite.set_kv, "firewall.last_heartbeat", iso_str)

        heartbeat_event = NormalizedEvent(
            event_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            ingested_at=datetime.now(timezone.utc),
            source_type="firewall_heartbeat",
            hostname="ipfire",
            event_type="heartbeat",
            severity="info",
            detection_source="firewall_collector",
            raw_event=json.dumps({"type": "heartbeat", "ts": iso_str}),
        )
        await self._loader.ingest_events([heartbeat_event])

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Main polling loop. Cancellation propagates via CancelledError."""
        self._running = True
        backoff = self._interval
        try:
            while True:
                await asyncio.sleep(backoff)
                success = await self._ingest_new_data()
                if success:
                    self._consecutive_failures = 0
                    backoff = self._interval
                else:
                    self._consecutive_failures += 1
                    backoff = min(self._interval * (2 ** self._consecutive_failures), 300)
                    if self._consecutive_failures >= _settings.FIREWALL_CONSECUTIVE_FAILURE_LIMIT:
                        log.warning(
                            "FirewallCollector: consecutive failure limit reached",
                            consecutive_failures=self._consecutive_failures,
                            backoff_seconds=backoff,
                        )
        except asyncio.CancelledError:
            self._running = False
            raise

    def status(self) -> dict:
        """Return current collector status dict."""
        return {
            "running": self._running,
            "syslog_lines_processed": self._syslog_lines_processed,
            "eve_lines_processed": self._eve_lines_processed,
            "consecutive_failures": self._consecutive_failures,
        }
