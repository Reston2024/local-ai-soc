"""
osquery JSON output parser.

Handles the standard osquery result log format:
  {
    "name": "query_name",
    "unixTime": 1234567890,
    "columns": { "pid": "1234", "name": "python.exe", ... },
    "action": "added"
  }

Also handles osquery differential / snapshot formats where results may be
nested under a "data" list or similar wrappers.

Used programmatically (no file extension registration) — call parse() with
a path to an osquery results JSON file, or construct events from in-memory
dicts via parse_result().
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

from backend.core.logging import get_logger
from backend.models.event import NormalizedEvent
from ingestion.field_mapper import FieldMapper
from ingestion.parsers.base import BaseParser

_field_mapper = FieldMapper()

log = get_logger(__name__)

_MAX_RAW = 8 * 1024  # 8 KB


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return None


def _safe_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _columns_to_event(
    query_name: str,
    unix_time: int | None,
    columns: dict[str, Any],
    source_file: str,
    case_id: str | None,
    ingested_at: datetime,
) -> NormalizedEvent:
    """
    Map osquery columns dict to a NormalizedEvent.

    Handles both process and socket/network query output shapes.
    """
    raw_str = json.dumps(
        {"query_name": query_name, "columns": columns},
        default=str,
    )[:_MAX_RAW]
    columns = _field_mapper.map(columns)

    if unix_time:
        try:
            timestamp = datetime.fromtimestamp(unix_time, tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            timestamp = ingested_at
    else:
        timestamp = ingested_at

    # Process fields
    pid = _safe_int(columns.get("pid"))
    parent_pid = _safe_int(columns.get("parent") or columns.get("ppid"))
    proc_name = _safe_str(columns.get("name") or columns.get("path"))
    cmd_line = _safe_str(columns.get("cmdline") or columns.get("command_line"))
    if cmd_line:
        cmd_line = cmd_line[:_MAX_RAW]

    # User fields
    uid = _safe_str(columns.get("uid") or columns.get("username") or columns.get("user"))
    # uid is numeric in osquery process queries; treat as username only if non-numeric
    username: str | None = None
    if uid:
        try:
            int(uid)
            # It's a UID number — keep as attributes but don't set username
        except ValueError:
            username = uid

    # Fallback: actual username columns
    if not username:
        username = _safe_str(columns.get("username") or columns.get("user"))

    # Network / socket fields
    dst_ip = _safe_str(
        columns.get("remote_address")
        or columns.get("dst_ip")
        or columns.get("destination")
    )
    dst_port = _safe_int(
        columns.get("remote_port")
        or columns.get("dst_port")
    )
    src_ip = _safe_str(
        columns.get("local_address")
        or columns.get("src_ip")
        or columns.get("source")
    )
    src_port = _safe_int(
        columns.get("local_port")
        or columns.get("src_port")
    )

    # Determine event type from query name
    event_type: str | None = None
    qn_lower = query_name.lower()
    if any(kw in qn_lower for kw in ("process", "proc", "startup")):
        event_type = "process_create"
    elif any(kw in qn_lower for kw in ("socket", "network", "listen", "open_socket")):
        event_type = "network_connect"
    elif any(kw in qn_lower for kw in ("file", "path")):
        event_type = "file_create"
    elif any(kw in qn_lower for kw in ("user", "account", "login")):
        event_type = "logon_event"

    # File / path
    file_path = _safe_str(
        columns.get("path")
        if "path" in columns and proc_name != columns.get("path") else None
    )

    return NormalizedEvent(
        event_id=str(uuid4()),
        timestamp=timestamp,
        ingested_at=ingested_at,
        source_type="osquery",
        source_file=source_file,
        hostname=_safe_str(columns.get("hostname") or columns.get("host")),
        username=username,
        process_name=proc_name,
        process_id=pid,
        parent_process_id=parent_pid,
        file_path=file_path,
        command_line=cmd_line,
        src_ip=src_ip,
        src_port=src_port,
        dst_ip=dst_ip,
        dst_port=dst_port,
        event_type=event_type,
        raw_event=raw_str,
        case_id=case_id,
        tags=f"osquery:{query_name}",
    )


class OsqueryParser(BaseParser):
    """
    Parse osquery result log files (JSON format).

    osquery writes results in one of two formats depending on
    ``--logger_plugin``:

    1. **Result log** (default) — each line is one osquery result envelope:
       ``{"name": "...", "unixTime": N, "action": "added", "columns": {...}}``

    2. **Snapshot** — the entire file is a JSON object:
       ``{"action": "snapshot", "name": "...", "snapshot": [...]}``

    Both formats are handled.  The ``supported_extensions`` list is intentionally
    empty so this parser is not picked up by the extension-based registry — it
    should be used programmatically or registered explicitly.
    """

    supported_extensions: list[str] = []  # Not extension-based

    def parse(
        self,
        file_path: str,
        case_id: str | None = None,
    ) -> Iterator[NormalizedEvent]:
        now = datetime.now(tz=timezone.utc)
        parsed = 0
        errors = 0

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError as exc:
            log.error("Cannot open osquery file", file_path=file_path, error=str(exc))
            return

        # Detect format: single JSON object vs NDJSON
        stripped = content.strip()
        if stripped.startswith("["):
            # JSON array of result envelopes
            try:
                records = json.loads(stripped)
            except json.JSONDecodeError as exc:
                log.error("osquery JSON array parse error", file_path=file_path, error=str(exc))
                return
            for record in records:
                try:
                    yield from self._handle_record(record, file_path, case_id, now)
                    parsed += 1
                except Exception as exc:
                    errors += 1
                    log.warning("osquery record error", error=str(exc))
        elif stripped.startswith("{"):
            # Try as single JSON object
            try:
                record = json.loads(stripped)
                yield from self._handle_record(record, file_path, case_id, now)
                parsed += 1
            except json.JSONDecodeError:
                # Fall through to NDJSON
                for lineno, line in enumerate(stripped.splitlines(), 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        yield from self._handle_record(record, file_path, case_id, now)
                        parsed += 1
                    except Exception as exc:
                        errors += 1
                        log.warning(
                            "osquery NDJSON line error",
                            file_path=file_path,
                            lineno=lineno,
                            error=str(exc),
                        )

        log.info(
            "osquery parse complete",
            file_path=file_path,
            parsed=parsed,
            errors=errors,
        )

    def _handle_record(
        self,
        record: dict[str, Any],
        source_file: str,
        case_id: str | None,
        ingested_at: datetime,
    ) -> Iterator[NormalizedEvent]:
        """Dispatch a single osquery result envelope to yield NormalizedEvents."""
        query_name = str(record.get("name") or record.get("queryName") or "unknown")
        unix_time = _safe_int(record.get("unixTime") or record.get("calendarTime"))

        # Snapshot format: {"snapshot": [...], ...}
        snapshot = record.get("snapshot")
        if snapshot and isinstance(snapshot, list):
            for row in snapshot:
                if isinstance(row, dict):
                    yield _columns_to_event(
                        query_name, unix_time, row, source_file, case_id, ingested_at
                    )
            return

        # Differential format: {"columns": {...}, "action": "added"}
        columns = record.get("columns")
        if columns and isinstance(columns, dict):
            yield _columns_to_event(
                query_name, unix_time, columns, source_file, case_id, ingested_at
            )
            return

        # "data" list variant
        data = record.get("data")
        if data and isinstance(data, list):
            for row in data:
                if isinstance(row, dict):
                    yield _columns_to_event(
                        query_name, unix_time, row, source_file, case_id, ingested_at
                    )

    def parse_result(
        self,
        result: dict[str, Any],
        source_file: str = "osquery_live",
        case_id: str | None = None,
    ) -> list[NormalizedEvent]:
        """
        Convert a single in-memory osquery result dict to a list of events.

        Convenience method for programmatic use (e.g., live osquery stream).
        """
        now = datetime.now(tz=timezone.utc)
        return list(self._handle_record(result, source_file, case_id, now))
