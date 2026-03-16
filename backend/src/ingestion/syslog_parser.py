"""Syslog parser — Phase 2 telemetry ingestion.

Supports three formats:
  RFC3164  — <PRI>Mon DD HH:MM:SS host message
  RFC5424  — <PRI>1 TIMESTAMP HOST APP PID MSGID SD MSG
  CEF      — CEF:0|Vendor|Product|Version|SigID|Name|Severity|Extensions

All produce a raw dict normalizable by backend.src.parsers.normalizer.

Unknown / unparseable lines are returned as-is with event_type="unknown".
"""
import re
from datetime import datetime, timezone

# --- Priority / Facility / Severity tables ---
_SEVERITY_NAMES = ["emerg", "alert", "crit", "err", "warn", "notice", "info", "debug"]
_SEVERITY_MAP = {"emerg": "critical", "alert": "critical", "crit": "critical",
                 "err": "high", "warn": "medium", "notice": "low",
                 "info": "info", "debug": "info"}

_RFC3164_RE = re.compile(
    r"^<(\d+)>(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+(.*)"
)
_RFC5424_RE = re.compile(
    r"^<(\d+)>1\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.*)"
)
_CEF_RE = re.compile(
    r"^CEF:(\d+)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|(.*)"
)

# Regex for extracting key=value pairs from CEF extension field
_CEF_KV = re.compile(r'(\w+)=((?:[^=\\]|\\.)*?)(?=\s+\w+=|$)')


def _decode_priority(pri: str) -> tuple[str, str]:
    """Return (facility_name, severity_label) from syslog priority integer."""
    p = int(pri)
    sev_idx = p & 0x07
    sev_name = _SEVERITY_NAMES[sev_idx] if sev_idx < len(_SEVERITY_NAMES) else "info"
    return _SEVERITY_MAP.get(sev_name, "info")


def parse_rfc3164(line: str) -> dict | None:
    m = _RFC3164_RE.match(line)
    if not m:
        return None
    pri, ts_str, host, message = m.groups()
    severity = _decode_priority(pri)
    return {
        "timestamp": _normalize_ts(ts_str),
        "host": host,
        "event": _classify_message(message),
        "severity": severity,
        "message": message,
        "raw_format": "rfc3164",
    }


def parse_rfc5424(line: str) -> dict | None:
    m = _RFC5424_RE.match(line)
    if not m:
        return None
    pri, timestamp, host, app, pid, msgid, rest = m.groups()
    severity = _decode_priority(pri)
    # structured data and message follow — split on first " " after SD
    message = rest.lstrip("- ")
    return {
        "timestamp": timestamp if timestamp != "-" else "",
        "host": host if host != "-" else "unknown",
        "event": _classify_message(message),
        "severity": severity,
        "app": app if app != "-" else None,
        "pid": pid if pid != "-" else None,
        "message": message,
        "raw_format": "rfc5424",
    }


def parse_cef(line: str) -> dict | None:
    m = _CEF_RE.match(line)
    if not m:
        return None
    _version, vendor, product, dev_version, sig_id, name, cef_severity, extensions = m.groups()

    # Map CEF severity (0-10) to our labels
    try:
        sev_int = int(cef_severity)
        if sev_int >= 9:
            severity = "critical"
        elif sev_int >= 7:
            severity = "high"
        elif sev_int >= 4:
            severity = "medium"
        elif sev_int >= 1:
            severity = "low"
        else:
            severity = "info"
    except ValueError:
        severity = "info"

    # Parse extensions key=value pairs
    ext: dict = {}
    for match in _CEF_KV.finditer(extensions):
        ext[match.group(1)] = match.group(2).strip()

    result: dict = {
        "timestamp": ext.get("rt", ext.get("start", "")),
        "host": ext.get("dhost", ext.get("shost", "unknown")),
        "src_ip": ext.get("src"),
        "dst_ip": ext.get("dst"),
        "port": _safe_int(ext.get("dpt", ext.get("destinationPort"))),
        "event": name or sig_id or "cef_event",
        "severity": severity,
        "vendor": vendor,
        "product": product,
        "sig_id": sig_id,
        "message": name,
        "raw_format": "cef",
    }
    # Merge remaining extension fields
    result.update({k: v for k, v in ext.items() if k not in result})
    return result


def parse_syslog_line(line: str) -> dict:
    """Parse a single syslog line — tries RFC5424 → RFC3164 → CEF → fallback.

    Always returns a dict suitable for normalization.
    """
    line = line.strip()

    # Try RFC5424 first (versioned)
    if line.startswith("<") and ">1 " in line:
        result = parse_rfc5424(line)
        if result:
            return result

    # Try CEF
    if line.startswith("CEF:"):
        result = parse_cef(line)
        if result:
            return result

    # Try RFC3164
    if line.startswith("<"):
        result = parse_rfc3164(line)
        if result:
            return result

    # Fallback — return as opaque message
    return {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "host": "unknown",
        "event": "unknown",
        "severity": "info",
        "message": line,
        "raw_format": "unknown",
    }


# ---- helpers ----------------------------------------------------------------

def _classify_message(msg: str) -> str:
    """Return a coarse event type from a syslog message string."""
    ml = msg.lower()
    if any(k in ml for k in ("connection", "connect", "tcp", "udp", "established")):
        return "connection"
    if any(k in ml for k in ("dns", "query", "nxdomain", "resolved")):
        return "dns_query"
    if any(k in ml for k in ("auth", "login", "logon", "failed password", "accepted password")):
        return "auth"
    if any(k in ml for k in ("drop", "deny", "block", "reject", "firewall")):
        return "firewall_drop"
    if any(k in ml for k in ("error", "failed", "failure", "err")):
        return "error"
    return "syslog"


def _normalize_ts(ts_str: str) -> str:
    """Best-effort timestamp normalisation for RFC3164 (no year)."""
    try:
        # RFC3164 has no year — assume current
        year = datetime.now().year
        dt = datetime.strptime(f"{year} {ts_str.strip()}", "%Y %b %d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return ts_str


def _safe_int(val: str | None) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
