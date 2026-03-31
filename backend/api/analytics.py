"""
Analytics API — MITRE ATT&CK coverage reporting.

Endpoints:
  GET /api/analytics/mitre-coverage  — cross-reference detections and playbooks
                                        against the MITRE ATT&CK tactic list
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.core.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# ---------------------------------------------------------------------------
# MITRE ATT&CK tactic ordering (Enterprise ATT&CK v14)
# ---------------------------------------------------------------------------

MITRE_TACTICS: list[str] = [
    "reconnaissance",
    "resource-development",
    "initial-access",
    "execution",
    "persistence",
    "privilege-escalation",
    "defense-evasion",
    "credential-access",
    "discovery",
    "lateral-movement",
    "collection",
    "command-and-control",
    "exfiltration",
    "impact",
]

_TECHNIQUE_RE = re.compile(r"^T\d{4}")


# ---------------------------------------------------------------------------
# GET /api/analytics/mitre-coverage
# ---------------------------------------------------------------------------


@router.get("/mitre-coverage")
async def mitre_coverage(request: Request) -> JSONResponse:
    """Return a MITRE ATT&CK coverage matrix cross-referencing detections and playbooks.

    Response shape::

        {
            "tactics": ["reconnaissance", ...],
            "coverage": {
                "execution": {
                    "T1059": {"sources": ["detected", "playbook_covered"], "status": "detected"}
                }
            }
        }
    """
    stores = request.app.state.stores

    # 1. Fetch detection technique/tactic pairs
    rows: list[dict[str, Any]] = await asyncio.to_thread(
        stores.sqlite.get_detection_techniques
    )

    # 2. Fetch playbook trigger_conditions (raw JSON strings)
    tc_jsons: list[str] = await asyncio.to_thread(
        stores.sqlite.get_playbook_trigger_conditions
    )

    # Parse playbook techniques — any element matching ^T\d{4} is a technique ref
    playbook_techniques: set[str] = set()
    for tc_json in tc_jsons:
        try:
            items = json.loads(tc_json) if isinstance(tc_json, str) else []
        except (json.JSONDecodeError, TypeError):
            items = []
        for item in items:
            if isinstance(item, str) and _TECHNIQUE_RE.match(item):
                playbook_techniques.add(item)

    # 3. Build coverage dict from detections
    # coverage[tactic][technique] = {"sources": [...], "status": str}
    coverage: dict[str, dict[str, dict[str, Any]]] = {}

    # Track technique → tactic mapping for playbook enrichment
    technique_to_tactic: dict[str, str] = {}

    for row in rows:
        technique: str = row["attack_technique"]
        raw_tactic: str | None = row.get("attack_tactic")
        tactic = (raw_tactic or "").strip().lower() or "other"
        if tactic not in MITRE_TACTICS:
            tactic = "other"

        technique_to_tactic[technique] = tactic

        if tactic not in coverage:
            coverage[tactic] = {}
        if technique not in coverage[tactic]:
            coverage[tactic][technique] = {"sources": ["detected"], "status": "detected"}
        elif "detected" not in coverage[tactic][technique]["sources"]:
            coverage[tactic][technique]["sources"].append("detected")

    # 4. Enrich from playbook trigger_conditions
    for technique in playbook_techniques:
        tactic = technique_to_tactic.get(technique, "other")
        if tactic not in MITRE_TACTICS:
            tactic = "other"

        if tactic in coverage and technique in coverage[tactic]:
            # Already seen via detection — append source if missing
            if "playbook_covered" not in coverage[tactic][technique]["sources"]:
                coverage[tactic][technique]["sources"].append("playbook_covered")
        else:
            # Not in any detection — create entry under resolved tactic
            if tactic not in coverage:
                coverage[tactic] = {}
            coverage[tactic][technique] = {
                "sources": ["playbook_covered"],
                "status": "playbook_covered",
            }

    # 5. Set final status for each technique
    for tactic_data in coverage.values():
        for entry in tactic_data.values():
            sources: list[str] = entry["sources"]
            if "detected" in sources:
                entry["status"] = "detected"
            elif "hunted" in sources:
                entry["status"] = "hunted"
            elif "playbook_covered" in sources:
                entry["status"] = "playbook_covered"
            else:
                entry["status"] = "not_covered"

    log.debug(
        "MITRE coverage computed",
        tactic_count=len(coverage),
        total_techniques=sum(len(v) for v in coverage.values()),
    )

    return JSONResponse(
        content={
            "tactics": MITRE_TACTICS,
            "coverage": coverage,
        }
    )
