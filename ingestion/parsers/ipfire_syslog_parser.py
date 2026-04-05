"""
IPFire iptables syslog parser.

Parses RFC 3164 syslog lines produced by IPFire's netfilter/iptables logging
into NormalizedEvent objects with perimeter-visibility fields populated.

Format example:
  Aug 10 18:44:55 ipfire kernel: FORWARDFW IN=green0 OUT=red0 ... SRC=... DST=...

Used programmatically (no file extension registration).
Exposed exports: IPFireSyslogParser
"""

from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from typing import Iterator
from uuid import uuid4

from backend.core.logging import get_logger
from backend.models.event import NormalizedEvent
from ingestion.parsers.base import BaseParser

log = get_logger(__name__)

_MAX_RAW = 8 * 1024  # 8 KB — matches osquery_parser.py

# ---------------------------------------------------------------------------
# Compiled regexes
# ---------------------------------------------------------------------------

# RFC 3164 syslog header: "Mon DD HH:MM:SS host kernel: <body>"
_RFC3164_RE = re.compile(
    r'^(?P<month>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+'
    r'(?P<host>\S+)\s+kernel:\s+(?P<body>.+)$'
)

# Key=value pairs in the iptables body (e.g. SRC=1.2.3.4 DPT=443)
_KV_RE = re.compile(r'(\w+)=(\S*)')

# Log prefix: the first word before IN= (e.g. FORWARDFW, DROP_CTINVALID)
_PREFIX_RE = re.compile(r'^(\S+)\s+IN=')

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ZONE_MAP: dict[str, str] = {
    "green0": "green",
    "red0": "red",
    "blue0": "blue",
    "orange0": "orange",
}

_SUCCESS_PREFIXES: frozenset[str] = frozenset({"FORWARDFW", "INPUTFW"})


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_timestamp(month: str, day: str, time_str: str) -> datetime:
    """
    Parse RFC 3164 date/time fields into a timezone-aware UTC datetime.

    RFC 3164 omits the year, so we infer the current year and subtract one
    if the parsed date is more than 30 days in the future (handles the
    December -> January log-rotation edge case).
    """
    day_padded = day.rjust(2)
    naive = datetime.strptime(f"{month} {day_padded} {time_str}", "%b %d %H:%M:%S")
    now = datetime.now()
    ts = naive.replace(year=now.year)
    # If the resulting timestamp is more than 30 days ahead of now, subtract a year
    if ts > now + timedelta(days=30):
        ts = ts.replace(year=now.year - 1)
    return ts.replace(tzinfo=timezone.utc)


def _extract_action(prefix: str) -> str:
    """Map a log prefix to an event_outcome value."""
    return "success" if prefix in _SUCCESS_PREFIXES else "failure"


def _extract_severity(prefix: str) -> str:
    """Map a log prefix to a severity level."""
    if prefix in _SUCCESS_PREFIXES:
        return "info"
    # DROP_* and REJECT_* are security-relevant — elevate to medium
    return "medium"


# ---------------------------------------------------------------------------
# Parser class
# ---------------------------------------------------------------------------

class IPFireSyslogParser(BaseParser):
    """
    Parse IPFire iptables syslog files into NormalizedEvent objects.

    Each non-empty line is expected to follow RFC 3164 format with an iptables
    log prefix (FORWARDFW, DROP_CTINVALID, REJECT_INPUT, etc.) in the kernel
    message body.

    ``supported_extensions`` is intentionally empty — this parser is used
    programmatically and registered explicitly rather than by file extension.
    """

    supported_extensions: list[str] = []  # Not extension-based

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(
        self,
        file_path: str,
        case_id: str | None = None,
    ) -> Iterator[NormalizedEvent]:
        """
        Parse a syslog file and yield NormalizedEvent objects.

        Lines that do not match the expected RFC 3164 / iptables format are
        silently skipped with a debug log entry.

        Args:
            file_path: Path to the syslog file.
            case_id:   Optional investigation case identifier.

        Yields:
            NormalizedEvent for each successfully parsed line.
        """
        try:
            with open(file_path, encoding="utf-8", errors="replace") as fh:
                for lineno, raw_line in enumerate(fh, 1):
                    stripped = raw_line.strip()
                    if not stripped:
                        continue
                    try:
                        event = self.parse_line(
                            stripped,
                            source_file=file_path,
                            case_id=case_id,
                        )
                        if event is not None:
                            yield event
                    except Exception as exc:
                        log.warning(
                            "ipfire_syslog: parse error on line",
                            file_path=file_path,
                            lineno=lineno,
                            error=str(exc),
                        )
        except OSError as exc:
            log.error(
                "ipfire_syslog: cannot open file",
                file_path=file_path,
                error=str(exc),
            )

    def parse_line(
        self,
        raw_line: str,
        source_file: str = "ipfire_syslog",
        case_id: str | None = None,
    ) -> NormalizedEvent | None:
        """
        Parse a single syslog line string into a NormalizedEvent.

        Args:
            raw_line:    A single stripped syslog line.
            source_file: Logical source identifier (file path or label).
            case_id:     Optional investigation case identifier.

        Returns:
            A NormalizedEvent if the line matches the expected format,
            or None if it cannot be parsed.
        """
        line = raw_line.strip()
        if not line:
            return None

        # Match RFC 3164 header
        hdr_match = _RFC3164_RE.match(line)
        if not hdr_match:
            log.debug("ipfire_syslog: line did not match RFC3164 header", line=line[:80])
            return None

        month = hdr_match.group("month")
        day = hdr_match.group("day")
        time_str = hdr_match.group("time")
        host = hdr_match.group("host")
        body = hdr_match.group("body")

        # Extract log prefix (FORWARDFW, DROP_CTINVALID, ...)
        prefix_match = _PREFIX_RE.match(body)
        if not prefix_match:
            log.debug("ipfire_syslog: no iptables prefix found", body=body[:80])
            return None

        prefix = prefix_match.group(1)

        # Parse key=value pairs from the body
        kv: dict[str, str] = dict(_KV_RE.findall(body))

        # Build tags: in/out interface names + zone labels
        tags_parts: list[str] = []
        in_iface = kv.get("IN", "")
        out_iface = kv.get("OUT", "")
        if in_iface:
            tags_parts.append(f"in:{in_iface}")
        if out_iface:
            tags_parts.append(f"out:{out_iface}")
        # Add zone tags for known interfaces
        for iface in (in_iface, out_iface):
            if iface and iface in _ZONE_MAP:
                tags_parts.append(f"zone:{_ZONE_MAP[iface]}")

        tags = ",".join(tags_parts) if tags_parts else None

        # Port numbers (absent for ICMP)
        src_port: int | None = int(kv["SPT"]) if "SPT" in kv else None
        dst_port: int | None = int(kv["DPT"]) if "DPT" in kv else None

        try:
            timestamp = _parse_timestamp(month, day, time_str)
        except ValueError as exc:
            log.warning("ipfire_syslog: timestamp parse failed", error=str(exc))
            timestamp = datetime.now(tz=timezone.utc)

        return NormalizedEvent(
            event_id=str(uuid4()),
            timestamp=timestamp,
            ingested_at=datetime.now(tz=timezone.utc),
            source_type="ipfire_syslog",
            source_file=source_file,
            hostname=host,
            src_ip=kv.get("SRC") or None,
            src_port=src_port,
            dst_ip=kv.get("DST") or None,
            dst_port=dst_port,
            event_type="network_connect",
            severity=_extract_severity(prefix),
            detection_source=prefix,
            raw_event=line[:_MAX_RAW],
            tags=tags,
            network_protocol=kv.get("PROTO") or None,
            event_outcome=_extract_action(prefix),
            case_id=case_id,
        )
