"""Deterministic anomaly detection rules.

Pure-function module — no I/O, no database access.
Rules are Python dataclasses co-located with their logic for easy testing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

# ---------------------------------------------------------------------------
# Lookup sets
# ---------------------------------------------------------------------------

_OFFICE_APPS = {"winword.exe", "excel.exe", "powerpnt.exe", "outlook.exe", "mspub.exe"}
_SHELL_PROCS = {"cmd.exe", "powershell.exe", "wscript.exe", "cscript.exe", "mshta.exe", "rundll32.exe"}
_SYSTEM_PROCS = {"svchost.exe", "lsass.exe", "csrss.exe", "smss.exe", "winlogon.exe"}
_MASQUERADE_PATHS = {"appdata", "temp", "tmp", "programdata\\microsoft\\windows\\start menu"}
_STANDARD_PORTS = {80, 443, 8080, 8443, 53, 22, 21, 25, 587, 110, 143, 3389, 445, 139}
_RFC1918_PREFIXES = ("10.", "172.16.", "192.168.", "127.")


# ---------------------------------------------------------------------------
# Rule dataclass
# ---------------------------------------------------------------------------


@dataclass
class AnomalyRule:
    rule_id: str
    name: str
    description: str
    check: Callable[[dict], bool]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _is_external_ip(ip: str) -> bool:
    """Return True if ip is a non-RFC-1918, non-loopback address."""
    if not ip:
        return False
    for prefix in _RFC1918_PREFIXES:
        if ip.startswith(prefix):
            return False
    return True


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

ANOMALY_RULES: list[AnomalyRule] = [
    AnomalyRule(
        rule_id="ANO-001",
        name="office_spawns_shell",
        description="Office application spawning a shell or scripting process",
        check=lambda evt: (
            evt.get("parent_process_name", "").lower() in _OFFICE_APPS
            and evt.get("process_name", "").lower() in _SHELL_PROCS
        ),
    ),
    AnomalyRule(
        rule_id="ANO-002",
        name="system_process_unusual_parent",
        description="System process spawned by a non-system, non-services parent",
        check=lambda evt: (
            evt.get("process_name", "").lower() in _SYSTEM_PROCS
            and evt.get("parent_process_name", "").lower()
            not in (_SYSTEM_PROCS | {"services.exe", "wininit.exe", ""})
        ),
    ),
    AnomalyRule(
        rule_id="ANO-003",
        name="process_masquerading",
        description="Process with system-like name running from unexpected path (AppData/Temp)",
        check=lambda evt: (
            evt.get("process_name", "").lower() in _SYSTEM_PROCS
            and any(
                p in (evt.get("process_path", "") or "").lower()
                for p in _MASQUERADE_PATHS
            )
        ),
    ),
    AnomalyRule(
        rule_id="ANO-004",
        name="unusual_external_port",
        description="Connection to external IP on non-standard port (potential C2)",
        check=lambda evt: (
            _is_external_ip(evt.get("dest_ip", ""))
            and evt.get("dest_port") is not None
            and int(evt.get("dest_port", 0)) not in _STANDARD_PORTS
        ),
    ),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_event_anomalies(event: dict) -> list[str]:
    """Return list of rule_ids that fire for this event.

    Args:
        event: Dict with fields like parent_process_name, process_name,
               process_path, dest_ip, dest_port, etc.

    Returns:
        List of rule IDs (e.g. ["ANO-001", "ANO-003"]) that matched.
    """
    return [rule.rule_id for rule in ANOMALY_RULES if rule.check(event)]
