"""
JSON / NDJSON / JSONL parser for security event files.

Auto-detects format:
- NDJSON/JSONL: one JSON object per line
- JSON array:  top-level array of objects
- JSON object: single event wrapped in a list

Field name variants are mapped to NormalizedEvent canonical names.
Unmapped fields are preserved in raw_event as a JSON string.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

from backend.core.logging import get_logger
from backend.models.event import NormalizedEvent
from ingestion.parsers.base import BaseParser

log = get_logger(__name__)

_MAX_RAW = 8 * 1024  # 8 KB


# ---------------------------------------------------------------------------
# Field mapping — variant names → NormalizedEvent field name
# ---------------------------------------------------------------------------

_HOSTNAME_KEYS = frozenset({"hostname", "host", "computer", "computername", "machine", "node"})
_USERNAME_KEYS = frozenset({"username", "user", "account", "subjectusername", "targetusername", "user_name", "account_name"})
_PROCESS_KEYS = frozenset({"process", "process_name", "image", "newprocessname", "processname", "process_image"})
_PID_KEYS = frozenset({"pid", "process_id", "processid", "newprocessid"})
_PPID_KEYS = frozenset({"ppid", "parent_pid", "parent_process_id", "parentprocessid"})
_PARENT_PROC_KEYS = frozenset({"parent_process", "parent_process_name", "parentimage", "parentprocessname"})
_CMDLINE_KEYS = frozenset({"commandline", "command_line", "cmdline", "cmd", "image_loaded", "processcommandline"})
_DST_IP_KEYS = frozenset({"dst_ip", "dest_ip", "destinationip", "destination_ip", "dest", "dst"})
_DST_PORT_KEYS = frozenset({"dst_port", "dest_port", "destinationport", "destination_port"})
_SRC_IP_KEYS = frozenset({"src_ip", "source_ip", "sourceip", "src"})
_SRC_PORT_KEYS = frozenset({"src_port", "source_port", "sourceport"})
_FILE_PATH_KEYS = frozenset({"file_path", "filepath", "targetfilename", "targetobject", "filename", "path"})
_FILE_HASH_KEYS = frozenset({"file_hash_sha256", "sha256", "hash", "hashes"})
_DOMAIN_KEYS = frozenset({"domain", "destinationhostname", "dest_hostname", "fqdn", "queryname"})
_TIMESTAMP_KEYS = frozenset({"timestamp", "time", "eventtime", "@timestamp", "date", "created_at", "event_time", "datetime"})
_EVENT_TYPE_KEYS = frozenset({"event_type", "eventtype", "type", "action", "category"})
_SEVERITY_KEYS = frozenset({"severity", "level", "alert_severity", "priority"})
_TAGS_KEYS = frozenset({"tags", "labels"})
_CASE_KEYS = frozenset({"case_id", "caseid", "case"})
_URL_KEYS = frozenset({"url", "uri", "http_url", "request_url"})


def _first(record: dict[str, Any], keys: frozenset[str]) -> Any:
    """Return the first value whose lower-cased key matches one of *keys*."""
    for k, v in record.items():
        if k.lower() in keys and v is not None:
            return v
    return None


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _parse_timestamp(ts: Any) -> datetime | None:
    """
    Parse a timestamp from various formats:
    - ISO-8601 string
    - Unix epoch (int or float, seconds)
    - Windows FILETIME (int > 1e17, 100-ns intervals since 1601-01-01)
    """
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        # Windows FILETIME threshold: values > 1e17 are 100-ns intervals
        if ts > 1e17:
            # Convert FILETIME to Unix timestamp
            # FILETIME epoch is 1601-01-01; Unix epoch is 1970-01-01
            # Difference is 11644473600 seconds; 1 FILETIME tick = 100ns
            unix_ts = (ts / 1e7) - 11644473600
            try:
                return datetime.fromtimestamp(unix_ts, tz=timezone.utc)
            except (OSError, ValueError, OverflowError):
                return None
        else:
            try:
                return datetime.fromtimestamp(float(ts), tz=timezone.utc)
            except (OSError, ValueError, OverflowError):
                return None
    if isinstance(ts, str):
        ts = ts.strip()
        if not ts:
            return None
        # Try ISO-8601 with/without Z suffix
        for fmt_ts in (ts.replace("Z", "+00:00"), ts):
            try:
                dt = datetime.fromisoformat(fmt_ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
    return None


def _record_to_event(
    record: dict[str, Any],
    source_type: str,
    source_file: str,
    case_id: str | None,
    ingested_at: datetime,
) -> NormalizedEvent:
    """Map a raw dict to a NormalizedEvent, preserving unmapped fields in raw_event."""
    raw_str = json.dumps(record, default=str)[:_MAX_RAW]

    ts_raw = _first(record, _TIMESTAMP_KEYS)
    timestamp = _parse_timestamp(ts_raw) or ingested_at

    # Username: combine multiple possible sources, prefer TargetUserName style
    username_val = _first(record, _USERNAME_KEYS)
    if username_val:
        username_val = str(username_val).strip() or None

    process_name = _first(record, _PROCESS_KEYS)
    if process_name:
        process_name = str(process_name).strip() or None

    command_line = _first(record, _CMDLINE_KEYS)
    if command_line:
        command_line = str(command_line)[:_MAX_RAW]

    file_hash = _first(record, _FILE_HASH_KEYS)
    if file_hash and isinstance(file_hash, str):
        # Strip "SHA256=..." prefix if present
        for part in file_hash.split(","):
            if part.upper().startswith("SHA256="):
                file_hash = part.split("=", 1)[1]
                break

    severity = _first(record, _SEVERITY_KEYS)
    if severity:
        severity = str(severity).lower()
        if severity not in {"critical", "high", "medium", "low", "info", "informational"}:
            severity = None

    tags = _first(record, _TAGS_KEYS)
    if isinstance(tags, list):
        tags = ",".join(str(t) for t in tags)
    elif tags:
        tags = str(tags)

    return NormalizedEvent(
        event_id=str(uuid4()),
        timestamp=timestamp,
        ingested_at=ingested_at,
        source_type=source_type,
        source_file=source_file,
        hostname=str(_first(record, _HOSTNAME_KEYS) or "").strip() or None,
        username=username_val,
        process_name=process_name,
        process_id=_safe_int(_first(record, _PID_KEYS)),
        parent_process_name=str(_first(record, _PARENT_PROC_KEYS) or "").strip() or None,
        parent_process_id=_safe_int(_first(record, _PPID_KEYS)),
        file_path=str(_first(record, _FILE_PATH_KEYS) or "").strip() or None,
        file_hash_sha256=str(file_hash).strip() if file_hash else None,
        command_line=command_line,
        src_ip=str(_first(record, _SRC_IP_KEYS) or "").strip() or None,
        src_port=_safe_int(_first(record, _SRC_PORT_KEYS)),
        dst_ip=str(_first(record, _DST_IP_KEYS) or "").strip() or None,
        dst_port=_safe_int(_first(record, _DST_PORT_KEYS)),
        domain=str(_first(record, _DOMAIN_KEYS) or "").strip() or None,
        url=str(_first(record, _URL_KEYS) or "").strip() or None,
        event_type=str(_first(record, _EVENT_TYPE_KEYS) or "").strip() or None,
        severity=severity,
        raw_event=raw_str,
        tags=tags,
        case_id=case_id,
    )


class JsonParser(BaseParser):
    """
    Parse JSON / NDJSON / JSONL files into NormalizedEvent streams.

    Format detection priority:
    1. First non-empty line starts with '{' → NDJSON
    2. First non-empty line starts with '[' → JSON array
    3. Entire file is a single JSON object → single event
    """

    supported_extensions: list[str] = [".json", ".ndjson", ".jsonl"]

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
                first_char = ""
                # Peek at first non-whitespace byte to decide format
                for line in fh:
                    stripped = line.strip()
                    if stripped:
                        first_char = stripped[0]
                        break

            if first_char == "{":
                source_type = "ndjson"
                yield from self._parse_ndjson(file_path, source_type, case_id, now)
            elif first_char == "[":
                source_type = "json"
                yield from self._parse_json_array(file_path, source_type, case_id, now)
            else:
                # Try NDJSON as fallback, it may be jsonl with blank leading lines
                source_type = "json"
                yield from self._parse_ndjson(file_path, source_type, case_id, now)

        except OSError as exc:
            log.error("Cannot open JSON file", file_path=file_path, error=str(exc))
            return

        log.info(
            "JSON parse complete",
            file_path=file_path,
            parsed=parsed,
            errors=errors,
        )

    def _parse_ndjson(
        self,
        file_path: str,
        source_type: str,
        case_id: str | None,
        ingested_at: datetime,
    ) -> Iterator[NormalizedEvent]:
        """Yield one event per non-empty line."""
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if isinstance(record, dict):
                        yield _record_to_event(
                            record, source_type, file_path, case_id, ingested_at
                        )
                    elif isinstance(record, list):
                        for item in record:
                            if isinstance(item, dict):
                                yield _record_to_event(
                                    item, source_type, file_path, case_id, ingested_at
                                )
                except (json.JSONDecodeError, Exception) as exc:
                    log.warning(
                        "NDJSON line parse error — skipping",
                        file_path=file_path,
                        lineno=lineno,
                        error=str(exc),
                    )

    def _parse_json_array(
        self,
        file_path: str,
        source_type: str,
        case_id: str | None,
        ingested_at: datetime,
    ) -> Iterator[NormalizedEvent]:
        """Parse a JSON array of objects (loads entire file into memory)."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            log.error(
                "JSON array parse error",
                file_path=file_path,
                error=str(exc),
            )
            return

        if isinstance(data, dict):
            # Single object — treat as one event
            yield _record_to_event(data, source_type, file_path, case_id, ingested_at)
            return

        if not isinstance(data, list):
            log.warning(
                "JSON file root is neither array nor object",
                file_path=file_path,
                type=type(data).__name__,
            )
            return

        for i, record in enumerate(data):
            try:
                if isinstance(record, dict):
                    yield _record_to_event(
                        record, source_type, file_path, case_id, ingested_at
                    )
            except Exception as exc:
                log.warning(
                    "JSON array record error — skipping",
                    file_path=file_path,
                    index=i,
                    error=str(exc),
                )
