"""
ATT&CK Detection Coverage API — Phase 40.

Provides coverage metrics across ingested events and playbook steps:
  GET /api/coverage/attack   — technique coverage summary (heat-map data)
  GET /api/coverage/summary  — high-level coverage stats

Coverage is computed by:
  1. Scanning normalized_events for attack_technique values (live detection hits)
  2. Scanning all playbook steps for attack_techniques lists (playbook coverage)
  3. Cross-referencing against a curated set of high-priority ATT&CK techniques

This gives two distinct views:
  - "detected" → techniques actually seen in ingested telemetry
  - "playbooked" → techniques covered by a playbook response procedure

Used by the dashboard coverage widget and gap-analysis UI.
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.core.logging import get_logger
from backend.data.builtin_playbooks import BUILTIN_PLAYBOOKS

log = get_logger(__name__)
router = APIRouter(prefix="/api/coverage", tags=["coverage"])

# ---------------------------------------------------------------------------
# High-priority ATT&CK techniques relevant to this environment
# Drawn from CISA KEV, red-team TTPs common in SMB/home-lab threat model
# ---------------------------------------------------------------------------

_PRIORITY_TECHNIQUES: dict[str, dict[str, str]] = {
    # Initial Access
    "T1566":     {"name": "Phishing",                     "tactic": "Initial Access"},
    "T1566.001": {"name": "Spearphishing Attachment",     "tactic": "Initial Access"},
    "T1566.002": {"name": "Spearphishing Link",           "tactic": "Initial Access"},
    "T1190":     {"name": "Exploit Public-Facing App",    "tactic": "Initial Access"},
    "T1133":     {"name": "External Remote Services",     "tactic": "Initial Access"},
    "T1078":     {"name": "Valid Accounts",               "tactic": "Initial Access"},
    # Execution
    "T1059":     {"name": "Command & Scripting Interpreter", "tactic": "Execution"},
    "T1059.001": {"name": "PowerShell",                   "tactic": "Execution"},
    "T1059.003": {"name": "Windows Command Shell",        "tactic": "Execution"},
    "T1204":     {"name": "User Execution",               "tactic": "Execution"},
    "T1047":     {"name": "WMI",                          "tactic": "Execution"},
    # Persistence
    "T1053":     {"name": "Scheduled Task/Job",           "tactic": "Persistence"},
    "T1053.005": {"name": "Scheduled Task",               "tactic": "Persistence"},
    "T1547":     {"name": "Boot/Logon Autostart",         "tactic": "Persistence"},
    "T1136":     {"name": "Create Account",               "tactic": "Persistence"},
    "T1197":     {"name": "BITS Jobs",                    "tactic": "Persistence"},
    # Privilege Escalation
    "T1055":     {"name": "Process Injection",            "tactic": "Privilege Escalation"},
    "T1068":     {"name": "Exploitation for PrivEsc",     "tactic": "Privilege Escalation"},
    "T1134":     {"name": "Access Token Manipulation",    "tactic": "Privilege Escalation"},
    # Defense Evasion
    "T1036":     {"name": "Masquerading",                 "tactic": "Defense Evasion"},
    "T1112":     {"name": "Modify Registry",              "tactic": "Defense Evasion"},
    "T1218":     {"name": "Signed Binary Proxy Execution","tactic": "Defense Evasion"},
    "T1070":     {"name": "Indicator Removal",            "tactic": "Defense Evasion"},
    "T1027":     {"name": "Obfuscated Files/Info",        "tactic": "Defense Evasion"},
    # Credential Access
    "T1003":     {"name": "OS Credential Dumping",        "tactic": "Credential Access"},
    "T1110":     {"name": "Brute Force",                  "tactic": "Credential Access"},
    "T1555":     {"name": "Credentials from Password Stores", "tactic": "Credential Access"},
    "T1552":     {"name": "Unsecured Credentials",        "tactic": "Credential Access"},
    # Discovery
    "T1082":     {"name": "System Info Discovery",        "tactic": "Discovery"},
    "T1083":     {"name": "File & Directory Discovery",   "tactic": "Discovery"},
    "T1046":     {"name": "Network Service Discovery",    "tactic": "Discovery"},
    "T1057":     {"name": "Process Discovery",            "tactic": "Discovery"},
    "T1018":     {"name": "Remote System Discovery",      "tactic": "Discovery"},
    # Lateral Movement
    "T1021":     {"name": "Remote Services",              "tactic": "Lateral Movement"},
    "T1021.001": {"name": "Remote Desktop Protocol",      "tactic": "Lateral Movement"},
    "T1021.002": {"name": "SMB/Windows Admin Shares",     "tactic": "Lateral Movement"},
    "T1570":     {"name": "Lateral Tool Transfer",        "tactic": "Lateral Movement"},
    "T1534":     {"name": "Internal Spearphishing",       "tactic": "Lateral Movement"},
    # Collection
    "T1114":     {"name": "Email Collection",             "tactic": "Collection"},
    "T1560":     {"name": "Archive Collected Data",       "tactic": "Collection"},
    "T1074":     {"name": "Data Staged",                  "tactic": "Collection"},
    # Command & Control
    "T1071":     {"name": "App Layer Protocol",           "tactic": "Command & Control"},
    "T1071.001": {"name": "Web Protocols",                "tactic": "Command & Control"},
    "T1572":     {"name": "Protocol Tunneling",           "tactic": "Command & Control"},
    "T1095":     {"name": "Non-Appl Layer Protocol",      "tactic": "Command & Control"},
    "T1105":     {"name": "Ingress Tool Transfer",        "tactic": "Command & Control"},
    # Exfiltration
    "T1041":     {"name": "Exfil over C2 Channel",        "tactic": "Exfiltration"},
    "T1048":     {"name": "Exfil over Alt Protocol",      "tactic": "Exfiltration"},
    "T1567":     {"name": "Exfil over Web Service",       "tactic": "Exfiltration"},
    # Impact
    "T1486":     {"name": "Data Encrypted for Impact",    "tactic": "Impact"},
    "T1490":     {"name": "Inhibit System Recovery",      "tactic": "Impact"},
    "T1489":     {"name": "Service Stop",                 "tactic": "Impact"},
    "T1657":     {"name": "Financial Theft",              "tactic": "Impact"},
    "T1498":     {"name": "Network DoS",                  "tactic": "Impact"},
    "T1496":     {"name": "Resource Hijacking",           "tactic": "Impact"},
}

_T_PATTERN = re.compile(r"^T\d{4}(\.\d{3})?$")


def _build_playbook_coverage() -> dict[str, list[str]]:
    """Map technique → list of playbook names that cover it."""
    coverage: dict[str, list[str]] = {}
    for pb in BUILTIN_PLAYBOOKS:
        for step in pb.get("steps", []):
            for tech in step.get("attack_techniques", []):
                if _T_PATTERN.match(tech):
                    coverage.setdefault(tech, [])
                    if pb["name"] not in coverage[tech]:
                        coverage[tech].append(pb["name"])
        # Also include trigger_conditions T-numbers
        for tc in pb.get("trigger_conditions", []):
            if _T_PATTERN.match(tc):
                coverage.setdefault(tc, [])
                if pb["name"] not in coverage[tc]:
                    coverage[tc].append(pb["name"])
    return coverage


@router.get("/attack")
async def attack_coverage(request: Request) -> JSONResponse:
    """
    Return per-technique coverage matrix for the ATT&CK heat-map widget.

    Response shape per technique:
      {
        "technique_id": "T1059.001",
        "name": "PowerShell",
        "tactic": "Execution",
        "priority": true,
        "detected_count": 42,        # events with this attack_technique in last 30d
        "playbooked": true,           # at least one playbook covers this technique
        "playbooks": ["Malware / Intrusion Response"],
        "status": "detected" | "playbooked_only" | "gap"
      }
    """
    stores = request.app.state.stores

    # 1. Count detected techniques from DuckDB (last 30 days)
    detected: dict[str, int] = {}
    try:
        rows = await stores.duckdb.fetch_all(
            """
            SELECT attack_technique, COUNT(*) AS cnt
            FROM normalized_events
            WHERE attack_technique IS NOT NULL
              AND timestamp >= now() - INTERVAL '30 days'
            GROUP BY attack_technique
            ORDER BY cnt DESC
            LIMIT 500
            """
        )
        for row in rows:
            tech = str(row[0]).strip().upper() if row[0] else ""
            # Handle comma-separated values like "T1059.001,T1059"
            for t in tech.split(","):
                t = t.strip()
                if _T_PATTERN.match(t):
                    detected[t] = detected.get(t, 0) + int(row[1])
    except Exception as exc:
        log.warning("coverage: DuckDB query failed: %s", exc)

    # 2. Build playbook coverage map
    pb_coverage = _build_playbook_coverage()

    # 3. Compute all unique techniques (priority + detected + playbooked)
    all_techs: set[str] = set(_PRIORITY_TECHNIQUES.keys()) | set(detected.keys()) | set(pb_coverage.keys())

    # 4. Build response items
    items: list[dict[str, Any]] = []
    for tech_id in sorted(all_techs):
        meta = _PRIORITY_TECHNIQUES.get(tech_id)
        det_count = detected.get(tech_id, 0)
        pbs = pb_coverage.get(tech_id, [])

        if det_count > 0 and pbs:
            status = "detected_and_playbooked"
        elif det_count > 0:
            status = "detected"
        elif pbs:
            status = "playbooked_only"
        else:
            status = "gap"

        items.append({
            "technique_id": tech_id,
            "name": meta["name"] if meta else tech_id,
            "tactic": meta["tactic"] if meta else "Unknown",
            "priority": tech_id in _PRIORITY_TECHNIQUES,
            "detected_count": det_count,
            "playbooked": bool(pbs),
            "playbooks": pbs,
            "status": status,
        })

    return JSONResponse({"techniques": items, "total": len(items)})


@router.get("/summary")
async def coverage_summary(request: Request) -> JSONResponse:
    """
    Return high-level coverage statistics for the dashboard header.

    Response shape:
      {
        "priority_techniques": 56,
        "detected": 12,           # priority techniques seen in events
        "playbooked": 38,         # priority techniques with a playbook
        "coverage_pct": 68,       # (detected + playbooked_only) / priority * 100
        "gaps": 18,               # priority techniques with no coverage at all
        "enforcement_policy": {...}
      }
    """
    stores = request.app.state.stores

    detected: set[str] = set()
    try:
        rows = await stores.duckdb.fetch_all(
            """
            SELECT DISTINCT attack_technique
            FROM normalized_events
            WHERE attack_technique IS NOT NULL
              AND timestamp >= now() - INTERVAL '30 days'
            LIMIT 1000
            """
        )
        for row in rows:
            tech = str(row[0]).strip() if row[0] else ""
            for t in tech.split(","):
                t = t.strip()
                if _T_PATTERN.match(t):
                    detected.add(t)
    except Exception as exc:
        log.warning("coverage summary: DuckDB query failed: %s", exc)

    pb_coverage = _build_playbook_coverage()
    playbooked: set[str] = set(pb_coverage.keys())

    priority = set(_PRIORITY_TECHNIQUES.keys())
    covered = (detected | playbooked) & priority
    gaps = priority - covered

    coverage_pct = round(len(covered) / len(priority) * 100) if priority else 0

    # Enforcement policy status
    try:
        from backend.core.config import settings as _cfg
        from backend.enforcement.policy import EnforcementPolicy
        policy = EnforcementPolicy.from_settings(_cfg)
        policy_status = policy.status()
    except Exception:
        policy_status = {}

    return JSONResponse({
        "priority_techniques": len(priority),
        "detected": len(detected & priority),
        "playbooked": len(playbooked & priority),
        "covered": len(covered),
        "coverage_pct": coverage_pct,
        "gaps": len(gaps),
        "gap_techniques": sorted(gaps)[:10],   # sample of top gaps
        "enforcement_policy": policy_status,
    })
