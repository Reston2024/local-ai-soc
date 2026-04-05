"""
Suricata EVE JSON (NDJSON) parser.

Handles the standard Suricata EVE output format where each line is a JSON
object with event_type in: alert, dns, flow, http, tls, heartbeat, etc.

Used programmatically (no file extension registration) — call parse() with
a path to a Suricata EVE NDJSON file, or use parse_record() with an in-memory
dict.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterator
from uuid import uuid4

from backend.core.logging import get_logger
from backend.models.event import NormalizedEvent
from ingestion.parsers.base import BaseParser

log = get_logger(__name__)

_MAX_RAW = 8 * 1024  # 8 KB

# Suricata EVE event_type → NormalizedEvent event_type
_EVE_TYPE_MAP: dict[str, str] = {
    "alert": "detection",
    "flow": "network_connect",
    "dns": "dns_query",
    "http": "network_connect",
    "tls": "network_connect",
    "heartbeat": "heartbeat",
}

# Suricata alert severity (1=highest) → NormalizedEvent severity string
_EVE_SEVERITY_MAP: dict[int, str] = {
    1: "critical",
    2: "high",
    3: "medium",
    4: "low",
}

# Suricata alert action → NormalizedEvent event_outcome
_EVE_ACTION_MAP: dict[str, str] = {
    "allowed": "success",
    "blocked": "failure",
}


def _parse_eve_timestamp(ts_str: str) -> datetime:
    """Parse a Suricata EVE timestamp string to a UTC-aware datetime.

    EVE timestamps look like ``2026-01-15T10:23:45.123456+0000`` or
    ``2026-01-15T10:23:45.123456Z``.  Both are valid ISO-8601.

    Falls back to ``datetime.now(timezone.utc)`` on any parse error.
    """
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        log.warning("suricata_eve: unparseable timestamp, using now", raw_ts=ts_str)
        return datetime.now(timezone.utc)


class SuricataEveParser(BaseParser):
    """Parse Suricata EVE JSON NDJSON files into NormalizedEvent objects.

    Each line of the input file is one JSON object representing one network
    event.  The parser handles alert, dns, flow, http, tls, and heartbeat
    event types; unknown types are passed through as-is.

    The ``supported_extensions`` list is intentionally empty — this parser is
    used programmatically, not via the extension-based registry.
    """

    supported_extensions: list[str] = []  # Programmatic use only

    def parse_record(
        self,
        record: dict,
        source_file: str = "suricata_eve",
        case_id: str | None = None,
    ) -> NormalizedEvent | None:
        """Map a single EVE JSON record (in-memory dict) to a NormalizedEvent.

        Returns None if the record cannot be mapped (e.g. missing timestamp).
        """
        # --- timestamp ---
        ts_raw = record.get("timestamp")
        if ts_raw:
            timestamp = _parse_eve_timestamp(str(ts_raw))
        else:
            timestamp = datetime.now(timezone.utc)

        ingested_at = datetime.now(timezone.utc)

        # --- common network fields ---
        src_ip: str | None = record.get("src_ip")
        dst_ip: str | None = record.get("dest_ip")   # EVE uses dest_ip
        src_port: int | None = _safe_int(record.get("src_port"))
        dst_port: int | None = _safe_int(record.get("dest_port"))
        network_protocol: str | None = record.get("proto")
        hostname: str | None = record.get("host")

        # --- event_type mapping ---
        eve_type: str = record.get("event_type") or ""
        event_type: str | None = _EVE_TYPE_MAP.get(eve_type, eve_type or None)

        # --- per-type fields ---
        severity: str | None = None
        detection_source: str | None = None
        event_outcome: str | None = None
        attack_technique: str | None = None
        attack_tactic: str | None = None
        domain: str | None = None
        url: str | None = None
        tag_parts: list[str] = []

        if eve_type == "alert":
            alert = record.get("alert") or {}
            sev_int = alert.get("severity", 4)
            severity = _EVE_SEVERITY_MAP.get(sev_int, "low")
            detection_source = alert.get("signature")
            event_outcome = _EVE_ACTION_MAP.get(alert.get("action", ""), None)

            # MITRE ATT&CK metadata extraction
            metadata = alert.get("metadata") or {}
            attack_technique = (metadata.get("mitre_attack_id") or [None])[0]
            attack_tactic = (metadata.get("mitre_tactic_name") or [None])[0]

            # Tags: sid and category
            sid = alert.get("signature_id")
            category = alert.get("category")
            if sid is not None:
                tag_parts.append(f"sid:{sid}")
            if category:
                tag_parts.append(f"category:{category}")

        elif eve_type == "dns":
            dns = record.get("dns") or {}
            domain = dns.get("rrname")
            rrtype = dns.get("rrtype", "")
            if rrtype:
                tag_parts.append(f"dns_type:{rrtype}")

        elif eve_type == "http":
            http = record.get("http") or {}
            domain = http.get("hostname")
            url = http.get("url")
            method = http.get("http_method", "")
            if method:
                tag_parts.append(f"method:{method}")

        elif eve_type == "flow":
            flow = record.get("flow") or {}
            if flow.get("state") == "closed":
                event_outcome = "success"

        # For non-alert events default severity to "info"
        if severity is None:
            severity = "info"

        # flow_id tag (common across all EVE event types)
        flow_id = record.get("flow_id")
        if flow_id is not None:
            tag_parts.append(f"flow_id:{flow_id}")

        tags: str | None = ",".join(filter(None, tag_parts)) or None
        raw_event: str = json.dumps(record, default=str)[:_MAX_RAW]

        return NormalizedEvent(
            event_id=str(uuid4()),
            timestamp=timestamp,
            ingested_at=ingested_at,
            source_type="suricata_eve",
            source_file=source_file,
            hostname=hostname,
            src_ip=src_ip,
            src_port=src_port,
            dst_ip=dst_ip,
            dst_port=dst_port,
            domain=domain,
            url=url,
            event_type=event_type,
            severity=severity,
            detection_source=detection_source,
            attack_technique=attack_technique,
            attack_tactic=attack_tactic,
            network_protocol=network_protocol,
            event_outcome=event_outcome,
            tags=tags,
            raw_event=raw_event,
            case_id=case_id,
        )

    def parse(
        self,
        file_path: str,
        case_id: str | None = None,
    ) -> Iterator[NormalizedEvent]:
        """Parse a Suricata EVE NDJSON file and yield NormalizedEvent objects.

        Skips (with a WARNING log) any line that fails JSON decoding.

        Args:
            file_path: Path to the EVE NDJSON file.
            case_id:   Optional investigation case ID to associate with events.

        Yields:
            NormalizedEvent for each parseable EVE record.
        """
        try:
            fh = open(file_path, encoding="utf-8", errors="replace")
        except OSError as exc:
            log.error(
                "suricata_eve: cannot open file",
                file_path=file_path,
                error=str(exc),
            )
            return

        parsed = 0
        errors = 0
        with fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    errors += 1
                    log.warning(
                        "suricata_eve: JSON decode error, skipping line",
                        file_path=file_path,
                        lineno=lineno,
                        error=str(exc),
                    )
                    continue

                event = self.parse_record(record, source_file=file_path, case_id=case_id)
                if event is not None:
                    parsed += 1
                    yield event

        log.info(
            "suricata_eve: parse complete",
            file_path=file_path,
            parsed=parsed,
            errors=errors,
        )


def _safe_int(v) -> int | None:
    """Safely coerce a value to int, returning None on failure."""
    if v is None:
        return None
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return None
