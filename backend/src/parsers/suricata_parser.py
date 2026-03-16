"""Suricata EVE JSON parser — Phase 5.

parse_eve_line: accepts one newline-delimited EVE JSON string, returns a
normalized-compatible dict suitable for normalize() in normalizer.py.

Handles event types: alert, flow, dns, http, tls.
Falls back gracefully for unknown types (no crash, no exception).

CRITICAL field mapping traps documented here:
  - TRAP 1: EVE uses dest_ip / dest_port (NOT dst_ip / dst_port).
    Always use data.get("dest_ip") to get dst_ip — never data.get("dst_ip").
  - TRAP 2: Severity is INVERTED (Snort convention): 1=critical (highest),
    2=high, 3=medium, 4=low (lowest). Do NOT treat 1 as lowest.
"""
import json

# Severity mapping: Suricata/Snort inverted scale
# 1 = most critical, 4 = least critical
_SEVERITY_MAP: dict[int, str] = {
    1: "critical",
    2: "high",
    3: "medium",
    4: "low",
}


def parse_eve_line(line: str) -> dict:
    """Parse a single Suricata EVE JSON line into a normalized-compatible dict.

    Returns a dict with keys compatible with normalize() in normalizer.py:
      event_type, host, src_ip, dst_ip, query, port, protocol, severity, raw

    On invalid JSON: returns a safe fallback dict (does NOT raise).
    On unknown EVE event types: prefixes event_type with 'suricata_' (does NOT raise).
    """
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return {
            "event_type": "suricata_parse_error",
            "host": "unknown",
            "severity": "info",
            "raw": {"_parse_error": True, "_raw_line": line[:200]},
        }

    event_type_raw = data.get("event_type", "unknown")

    # TRAP 1: EVE uses dest_ip, not dst_ip — always extract via dest_ip key
    dst_ip = data.get("dest_ip")
    src_ip = data.get("src_ip")
    host = data.get("host", "unknown")
    timestamp = data.get("timestamp", "")
    proto = data.get("proto")

    # src_port maps to port; dest_port stored in raw
    src_port_raw = data.get("src_port")
    port = int(src_port_raw) if src_port_raw is not None else None

    # Build raw dict preserving full input for traceability
    raw: dict = {
        "flow_id": data.get("flow_id"),
        "dest_port": data.get("dest_port"),
        "src_port": src_port_raw,
        "proto": proto,
    }
    # Include the full original record
    raw["_eve"] = data

    if event_type_raw == "alert":
        alert = data.get("alert", {})
        signature = alert.get("signature", "suricata_alert")
        # TRAP 2: Severity is inverted — 1=critical, 4=low
        sev_int = alert.get("severity", 3)
        severity = _SEVERITY_MAP.get(sev_int, "medium")
        raw["alert"] = alert
        return {
            "event_type": signature,
            "host": host,
            "timestamp": timestamp,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "port": port,
            "protocol": proto,
            "severity": severity,
            "raw": raw,
        }

    elif event_type_raw == "dns":
        dns = data.get("dns", {})
        query = dns.get("rrname")
        raw["dns"] = dns
        return {
            "event_type": "dns_query",
            "host": host,
            "timestamp": timestamp,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "port": port,
            "protocol": proto,
            "severity": "info",
            "query": query,
            "raw": raw,
        }

    elif event_type_raw == "flow":
        flow = data.get("flow", {})
        raw["flow"] = flow
        return {
            "event_type": "connection",
            "host": host,
            "timestamp": timestamp,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "port": port,
            "protocol": proto,
            "severity": "info",
            "raw": raw,
        }

    elif event_type_raw == "http":
        http = data.get("http", {})
        raw["http"] = http
        return {
            "event_type": "http_request",
            "host": host,
            "timestamp": timestamp,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "port": port,
            "protocol": proto,
            "severity": "info",
            "raw": raw,
        }

    elif event_type_raw == "tls":
        tls = data.get("tls", {})
        # tls.sni takes priority; fall back to subject
        query = tls.get("sni") or tls.get("subject")
        raw["tls"] = tls
        return {
            "event_type": "tls_session",
            "host": host,
            "timestamp": timestamp,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "port": port,
            "protocol": proto,
            "severity": "info",
            "query": query,
            "raw": raw,
        }

    else:
        # Unknown event type: prefix with 'suricata_' — do NOT raise
        return {
            "event_type": f"suricata_{event_type_raw}",
            "host": host,
            "timestamp": timestamp,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "port": port,
            "protocol": proto,
            "severity": "info",
            "raw": raw,
        }
