"""Suricata EVE JSON parser — Phase 5.

parse_eve_line: accepts one newline-delimited EVE JSON string, returns a
normalized-compatible dict suitable for normalize() in normalizer.py.

Handles event types: alert, flow, dns, http, tls.
Falls back gracefully for unknown types (no crash, no exception).

CRITICAL field mapping traps documented here:
  - EVE uses dest_ip / dest_port (NOT dst_ip / dst_port). Map dest_ip -> dst_ip.
  - Severity is INVERTED: 1=critical, 2=high, 3=medium, 4=low (Snort convention).
"""


def parse_eve_line(line: str) -> dict:
    """Parse a single Suricata EVE JSON line into normalized-compatible dict.

    Not yet implemented — raises NotImplementedError until Plan 01.
    """
    raise NotImplementedError("parse_eve_line not implemented — see Plan 01")
