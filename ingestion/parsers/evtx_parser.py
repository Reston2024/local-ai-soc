"""
Windows EVTX parser using pyevtx-rs (``pip install evtx``).

Streams records from an .evtx file, mapping Windows Event Log fields to
the canonical NormalizedEvent schema.  Corrupt or unparseable records are
logged and skipped so a single bad record cannot abort a large ingestion job.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

import evtx  # pyevtx-rs

from backend.core.logging import get_logger
from backend.models.event import NormalizedEvent
from ingestion.parsers.base import BaseParser

log = get_logger(__name__)

# Maximum raw event string to store (8 KB)
_RAW_MAX = 8 * 1024


def _safe_int(value: Any) -> int | None:
    """Convert *value* to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _parse_timestamp(ts_str: str | None) -> datetime:
    """
    Parse an ISO-8601 timestamp string into a timezone-aware UTC datetime.

    Falls back to utcnow() if the string is missing or unparseable.
    """
    if not ts_str:
        return datetime.now(tz=timezone.utc)
    try:
        # pyevtx-rs emits timestamps like "2023-01-15T14:23:01.123456Z"
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return datetime.now(tz=timezone.utc)


def _extract_field(data: dict[str, Any], *keys: str) -> str | None:
    """Return the first non-empty value found for any of the given keys."""
    for key in keys:
        val = data.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return None


def _determine_event_type(event_id: int | None, channel: str | None) -> str | None:
    """Map Windows EventID / Channel to a canonical event_type string."""
    if event_id is None:
        return None
    # Sysmon event IDs
    sysmon_map: dict[int, str] = {
        1: "process_create",
        2: "file_creation_time_changed",
        3: "network_connect",
        5: "process_terminate",
        6: "driver_load",
        7: "image_load",
        8: "create_remote_thread",
        9: "raw_disk_access",
        10: "process_access",
        11: "file_create",
        12: "registry_event",
        13: "registry_value_set",
        14: "registry_key_rename",
        15: "file_create_stream_hash",
        17: "pipe_event",
        18: "pipe_connection",
        19: "wmi_event",
        20: "wmi_consumer",
        21: "wmi_subscription",
        22: "dns_query",
        23: "file_delete",
        24: "clipboard_event",
        25: "process_tampering",
        26: "file_delete_detected",
    }
    # Windows Security event IDs
    security_map: dict[int, str] = {
        4624: "logon_success",
        4625: "logon_failure",
        4634: "logoff",
        4648: "explicit_credential_logon",
        4672: "special_privileges_assigned",
        4688: "process_create",
        4698: "scheduled_task_created",
        4720: "user_account_created",
        4726: "user_account_deleted",
        4768: "kerberos_tgs_request",
        4769: "kerberos_service_ticket",
        4776: "ntlm_auth",
        4798: "user_group_membership_enumerated",
        4799: "security_group_enumerated",
    }
    if channel and "sysmon" in channel.lower():
        return sysmon_map.get(event_id)
    return security_map.get(event_id)


class EvtxParser(BaseParser):
    """
    Stream-parse a Windows EVTX file into NormalizedEvent objects.

    Uses pyevtx-rs for fast Rust-backed parsing.  Each record's JSON
    representation is processed individually to minimise memory usage.
    """

    supported_extensions: list[str] = [".evtx"]

    def parse(
        self,
        file_path: str,
        case_id: str | None = None,
    ) -> Iterator[NormalizedEvent]:
        """Yield NormalizedEvent objects parsed from *file_path*."""
        now = datetime.now(tz=timezone.utc)
        record_count = 0
        error_count = 0

        try:
            parser = evtx.PyEvtxParser(file_path)
        except Exception as exc:
            log.error(
                "Failed to open EVTX file",
                file_path=file_path,
                error=str(exc),
            )
            return

        for record in parser.records_json():
            try:
                yield self._parse_record(record, file_path, case_id, now)
                record_count += 1
            except Exception as exc:
                error_count += 1
                log.warning(
                    "EVTX record parse error — skipping",
                    file_path=file_path,
                    record_num=record_count + error_count,
                    error=str(exc),
                )

        log.info(
            "EVTX parse complete",
            file_path=file_path,
            records_parsed=record_count,
            records_skipped=error_count,
        )

    def _parse_record(
        self,
        record: dict[str, Any],
        file_path: str,
        case_id: str | None,
        ingested_at: datetime,
    ) -> NormalizedEvent:
        """
        Convert a single pyevtx-rs JSON record into a NormalizedEvent.

        pyevtx-rs records_json() yields dicts with structure:
            {
              "event_record_id": int,
              "timestamp": "...",
              "data": "<json string>"
            }
        """
        # The "data" key is a JSON string containing the full event XML
        # converted to JSON by pyevtx-rs.
        raw_json_str: str = record.get("data", "{}")
        raw_str = raw_json_str[:_RAW_MAX]

        try:
            data = json.loads(raw_json_str) if isinstance(raw_json_str, str) else raw_json_str
        except (json.JSONDecodeError, TypeError):
            data = {}

        # Navigate the pyevtx-rs JSON structure:
        # {"Event": {"System": {...}, "EventData": {...}}}
        event_root: dict[str, Any] = data.get("Event", data)
        system: dict[str, Any] = event_root.get("System", {})
        event_data: dict[str, Any] = event_root.get("EventData", {})

        # Flatten EventData — pyevtx-rs may nest it as {"Data": [...]} or
        # {"Data": {"#attributes": ..., "#text": ...}} or a flat dict.
        flat_data = self._flatten_event_data(event_data)

        # System fields
        ts_str = (
            system.get("TimeCreated", {}).get("@SystemTime")
            or system.get("TimeCreated", {}).get("#attributes", {}).get("SystemTime")
            or record.get("timestamp")
        )
        timestamp = _parse_timestamp(ts_str)

        raw_event_id_node = system.get("EventID", {})
        if isinstance(raw_event_id_node, dict):
            win_event_id = _safe_int(
                raw_event_id_node.get("#text") or raw_event_id_node.get("@Qualifiers")
            )
            if win_event_id is None:
                win_event_id = _safe_int(raw_event_id_node.get("@Qualifiers", "").split(":")[0] if isinstance(raw_event_id_node.get("@Qualifiers"), str) else None)
        else:
            win_event_id = _safe_int(raw_event_id_node)

        channel = (
            system.get("Channel")
            or system.get("Channel", {}).get("#text")
            if isinstance(system.get("Channel"), str)
            else None
        )
        if isinstance(system.get("Channel"), dict):
            channel = system["Channel"].get("#text")
        else:
            channel = system.get("Channel")

        computer = system.get("Computer")
        if isinstance(computer, dict):
            computer = computer.get("#text")

        record_id = system.get("EventRecordID")
        if isinstance(record_id, dict):
            record_id = record_id.get("#text")

        # Build a deterministic but unique event_id
        evtx_record_id = record.get("event_record_id", record_id)
        if evtx_record_id and computer:
            event_id = f"evtx:{computer}:{evtx_record_id}"
        else:
            event_id = str(uuid4())

        # Map EventData fields to NormalizedEvent fields
        username = _extract_field(
            flat_data,
            "SubjectUserName",
            "TargetUserName",
            "User",
        )
        process_name = _extract_field(flat_data, "Image", "NewProcessName", "ProcessName")
        command_line = _extract_field(flat_data, "CommandLine")
        if command_line:
            command_line = command_line[:_RAW_MAX]

        process_id = _safe_int(_extract_field(flat_data, "ProcessId", "NewProcessId"))
        parent_process_id = _safe_int(_extract_field(flat_data, "ParentProcessId"))
        parent_process_name = _extract_field(flat_data, "ParentImage", "ParentProcessName")

        dst_ip = _extract_field(flat_data, "DestinationIp", "DestAddress")
        dst_port = _safe_int(_extract_field(flat_data, "DestinationPort", "DestPort"))
        src_ip = _extract_field(flat_data, "SourceIp", "SourceAddress")
        src_port = _safe_int(_extract_field(flat_data, "SourcePort"))
        domain = _extract_field(flat_data, "DestinationHostname", "QueryName")

        file_path_val = _extract_field(
            flat_data,
            "TargetFilename",
            "TargetObject",
            "ObjectName",
        )
        file_hash = _extract_field(flat_data, "Hashes", "Hash")
        if file_hash and "SHA256=" in file_hash.upper():
            # e.g. "MD5=abc,SHA256=def,SHA1=ghi"
            for part in file_hash.split(","):
                if part.upper().startswith("SHA256="):
                    file_hash = part.split("=", 1)[1]
                    break
            else:
                file_hash = None

        event_type = _determine_event_type(win_event_id, channel)

        return NormalizedEvent(
            event_id=event_id,
            timestamp=timestamp,
            ingested_at=ingested_at,
            source_type="evtx",
            source_file=file_path,
            hostname=computer,
            username=username,
            process_name=process_name,
            process_id=process_id,
            parent_process_name=parent_process_name,
            parent_process_id=parent_process_id,
            file_path=file_path_val,
            file_hash_sha256=file_hash,
            command_line=command_line,
            src_ip=src_ip,
            src_port=src_port,
            dst_ip=dst_ip,
            dst_port=dst_port,
            domain=domain,
            event_type=event_type,
            raw_event=raw_str,
            case_id=case_id,
        )

    @staticmethod
    def _flatten_event_data(event_data: dict[str, Any]) -> dict[str, Any]:
        """
        Normalise the EventData section into a flat {name: value} dict.

        pyevtx-rs can represent EventData in several shapes:
        - {"Data": [{"@Name": "field", "#text": "value"}, ...]}
        - {"Data": {"@Name": "field", "#text": "value"}}
        - {"field": "value", ...}  (already flat)
        """
        if not event_data:
            return {}

        raw_data = event_data.get("Data")
        if raw_data is None:
            # Already flat or no Data key; return as-is minus "Data"
            return {k: v for k, v in event_data.items() if k != "Data"}

        flat: dict[str, Any] = {}
        if isinstance(raw_data, list):
            for item in raw_data:
                if isinstance(item, dict):
                    name = item.get("@Name") or item.get("Name")
                    value = item.get("#text") or item.get("value")
                    if name:
                        flat[name] = value
        elif isinstance(raw_data, dict):
            name = raw_data.get("@Name") or raw_data.get("Name")
            value = raw_data.get("#text") or raw_data.get("value")
            if name:
                flat[name] = value
            else:
                # Could be a nested structure; copy fields directly
                flat.update({k: v for k, v in raw_data.items() if not k.startswith("@")})
        elif isinstance(raw_data, str):
            # Free-text data — store under "_text" key
            flat["_text"] = raw_data

        return flat
