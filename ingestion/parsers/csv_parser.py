"""
CSV parser for security event files.

Uses csv.DictReader to stream rows and applies the same field-name
mapping as the JSON parser to NormalizedEvent canonical fields.

Timestamp parsing supports:
- ISO-8601 strings
- Unix epoch (int or float in seconds)
- Windows FILETIME (int > 1e17)
"""

from __future__ import annotations

import csv
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

# ---------------------------------------------------------------------------
# Same field-key sets as json_parser (kept local to avoid circular imports)
# ---------------------------------------------------------------------------

_HOSTNAME_KEYS = frozenset({"hostname", "host", "computer", "computername", "machine", "node"})
_USERNAME_KEYS = frozenset({"username", "user", "account", "subjectusername", "targetusername", "user_name"})
_PROCESS_KEYS = frozenset({"process", "process_name", "image", "newprocessname", "processname"})
_PID_KEYS = frozenset({"pid", "process_id", "processid", "newprocessid"})
_PPID_KEYS = frozenset({"ppid", "parent_pid", "parent_process_id", "parentprocessid"})
_PARENT_PROC_KEYS = frozenset({"parent_process", "parent_process_name", "parentimage", "parentprocessname"})
_CMDLINE_KEYS = frozenset({"commandline", "command_line", "cmdline", "cmd"})
_DST_IP_KEYS = frozenset({"dst_ip", "dest_ip", "destinationip", "destination_ip"})
_DST_PORT_KEYS = frozenset({"dst_port", "dest_port", "destinationport", "destination_port"})
_SRC_IP_KEYS = frozenset({"src_ip", "source_ip", "sourceip"})
_SRC_PORT_KEYS = frozenset({"src_port", "source_port", "sourceport"})
_FILE_PATH_KEYS = frozenset({"file_path", "filepath", "targetfilename", "targetobject", "filename", "path"})
_FILE_HASH_KEYS = frozenset({"file_hash_sha256", "sha256", "hash", "hashes"})
_DOMAIN_KEYS = frozenset({"domain", "destinationhostname", "dest_hostname", "fqdn"})
_TIMESTAMP_KEYS = frozenset({"timestamp", "time", "eventtime", "@timestamp", "date", "created_at", "event_time", "datetime"})  # noqa: E501
_EVENT_TYPE_KEYS = frozenset({"event_type", "eventtype", "type", "action"})
_SEVERITY_KEYS = frozenset({"severity", "level", "priority"})
_TAGS_KEYS = frozenset({"tags", "labels"})
_URL_KEYS = frozenset({"url", "uri", "request_url"})


def _first(record: dict[str, Any], keys: frozenset[str]) -> Any:
    for k, v in record.items():
        if k.lower() in keys and v is not None and str(v).strip():
            return v
    return None


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return None


def _parse_timestamp(ts: Any) -> datetime | None:
    if ts is None:
        return None
    ts_str = str(ts).strip()
    if not ts_str:
        return None

    # Try numeric (epoch or FILETIME)
    try:
        numeric = float(ts_str)
        if numeric > 1e17:
            # Windows FILETIME: 100-ns intervals since 1601-01-01
            unix_ts = (numeric / 1e7) - 11644473600
            return datetime.fromtimestamp(unix_ts, tz=timezone.utc)
        else:
            return datetime.fromtimestamp(numeric, tz=timezone.utc)
    except (ValueError, TypeError, OSError, OverflowError):
        pass

    # Try ISO-8601
    for candidate in (ts_str.replace("Z", "+00:00"), ts_str):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    return None


class CsvParser(BaseParser):
    """
    Stream-parse a CSV file of security events.

    Column headers are matched case-insensitively against the same field-name
    variants used by JsonParser.  All columns that cannot be mapped to a
    NormalizedEvent field are serialised into raw_event as a JSON object.
    """

    supported_extensions: list[str] = [".csv"]

    def parse(
        self,
        file_path: str,
        case_id: str | None = None,
    ) -> Iterator[NormalizedEvent]:
        now = datetime.now(tz=timezone.utc)
        parsed = 0
        errors = 0

        try:
            with open(file_path, newline="", encoding="utf-8", errors="replace") as fh:
                reader = csv.DictReader(fh)
                for rownum, row in enumerate(reader, 1):
                    try:
                        event = self._row_to_event(row, file_path, case_id, now)
                        yield event
                        parsed += 1
                    except Exception as exc:
                        errors += 1
                        log.warning(
                            "CSV row parse error — skipping",
                            file_path=file_path,
                            row=rownum,
                            error=str(exc),
                        )
        except OSError as exc:
            log.error("Cannot open CSV file", file_path=file_path, error=str(exc))
            return

        log.info(
            "CSV parse complete",
            file_path=file_path,
            parsed=parsed,
            errors=errors,
        )

    @staticmethod
    def _row_to_event(
        row: dict[str, Any],
        source_file: str,
        case_id: str | None,
        ingested_at: datetime,
    ) -> NormalizedEvent:
        raw_str = json.dumps(row, default=str)[:_MAX_RAW]
        row = _field_mapper.map(row)

        ts_raw = _first(row, _TIMESTAMP_KEYS)
        timestamp = _parse_timestamp(ts_raw) or ingested_at

        username_val = _first(row, _USERNAME_KEYS)
        if username_val:
            username_val = str(username_val).strip() or None

        process_name = _first(row, _PROCESS_KEYS)
        if process_name:
            process_name = str(process_name).strip() or None

        command_line = _first(row, _CMDLINE_KEYS)
        if command_line:
            command_line = str(command_line)[:_MAX_RAW]

        file_hash = _first(row, _FILE_HASH_KEYS)
        if file_hash and isinstance(file_hash, str):
            for part in str(file_hash).split(","):
                if part.upper().startswith("SHA256="):
                    file_hash = part.split("=", 1)[1]
                    break

        severity = _first(row, _SEVERITY_KEYS)
        if severity:
            severity = str(severity).lower()
            if severity not in {"critical", "high", "medium", "low", "info", "informational"}:
                severity = None

        tags = _first(row, _TAGS_KEYS)
        if tags:
            tags = str(tags)

        return NormalizedEvent(
            event_id=str(uuid4()),
            timestamp=timestamp,
            ingested_at=ingested_at,
            source_type="csv",
            source_file=source_file,
            hostname=str(_first(row, _HOSTNAME_KEYS) or "").strip() or None,
            username=username_val,
            process_name=process_name,
            process_id=_safe_int(_first(row, _PID_KEYS)),
            parent_process_name=str(_first(row, _PARENT_PROC_KEYS) or "").strip() or None,
            parent_process_id=_safe_int(_first(row, _PPID_KEYS)),
            file_path=str(_first(row, _FILE_PATH_KEYS) or "").strip() or None,
            file_hash_sha256=str(file_hash).strip() if file_hash else None,
            command_line=command_line,
            src_ip=str(_first(row, _SRC_IP_KEYS) or "").strip() or None,
            src_port=_safe_int(_first(row, _SRC_PORT_KEYS)),
            dst_ip=str(_first(row, _DST_IP_KEYS) or "").strip() or None,
            dst_port=_safe_int(_first(row, _DST_PORT_KEYS)),
            domain=str(_first(row, _DOMAIN_KEYS) or "").strip() or None,
            url=str(_first(row, _URL_KEYS) or "").strip() or None,
            event_type=str(_first(row, _EVENT_TYPE_KEYS) or "").strip() or None,
            severity=severity,
            raw_event=raw_str,
            tags=tags,
            case_id=case_id,
        )
