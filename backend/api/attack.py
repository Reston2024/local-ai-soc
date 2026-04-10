"""
Attack API — Phase 34 MITRE ATT&CK coverage and actor-matching endpoints.

Endpoints:
  GET /api/attack/coverage       — per-tactic ATT&CK coverage based on Sigma rules
  GET /api/attack/actor-matches  — top-3 threat actor groups matching recent detections

All endpoints require authentication via verify_token dependency.
Store access goes through app.state.attack_store (AttackStore instance).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, Request

from backend.core.auth import verify_token
from backend.api.analytics import MITRE_TACTICS
from backend.services.attack.attack_store import scan_rules_dir_for_coverage

router = APIRouter()

# ---------------------------------------------------------------------------
# Tactic short-label map
# ---------------------------------------------------------------------------

TACTIC_SHORTS: dict[str, str] = {
    "reconnaissance": "Recon",
    "resource-development": "ResDev",
    "initial-access": "InitAcc",
    "execution": "Exec",
    "persistence": "Persist",
    "privilege-escalation": "PrivEsc",
    "defense-evasion": "DefEva",
    "credential-access": "CredAcc",
    "discovery": "Disc",
    "lateral-movement": "LatMov",
    "collection": "Collect",
    "command-and-control": "C2",
    "exfiltration": "Exfil",
    "impact": "Impact",
}


# ---------------------------------------------------------------------------
# GET /api/attack/coverage
# ---------------------------------------------------------------------------


@router.get("/attack/coverage", dependencies=[Depends(verify_token)])
async def get_attack_coverage(request: Request):
    """
    Return per-tactic ATT&CK coverage data derived from Sigma rules on disk.

    For each tactic in MITRE_TACTICS order:
      - Fetches techniques from AttackStore (loaded at startup via STIX bootstrap)
      - Cross-references with Sigma rules in detections/rules/
      - Returns tactic, total_techniques, covered_count, techniques list

    Returns [] if attack_store is not yet initialised or rules directory absent.
    """
    attack_store = getattr(request.app.state, "attack_store", None)
    if attack_store is None:
        return []

    rules_dir = Path("detections/rules")
    if not rules_dir.exists():
        coverage_map: dict[str, list[str]] = {}
    else:
        coverage_map = await asyncio.to_thread(scan_rules_dir_for_coverage, rules_dir)

    result = []
    for tactic in MITRE_TACTICS:
        techniques = await asyncio.to_thread(
            attack_store.list_techniques_by_tactic, tactic
        )
        tech_list = [
            {
                "tech_id": t["tech_id"],
                "name": t["name"],
                "covered": t["tech_id"] in coverage_map,
                "rule_titles": coverage_map.get(t["tech_id"], []),
            }
            for t in techniques
        ]
        covered_count = sum(1 for t in tech_list if t["covered"])
        result.append(
            {
                "tactic": tactic,
                "tactic_short": TACTIC_SHORTS.get(tactic, tactic),
                "total_techniques": len(tech_list),
                "covered_count": covered_count,
                "techniques": tech_list,
            }
        )

    return result


# ---------------------------------------------------------------------------
# GET /api/attack/actor-matches
# ---------------------------------------------------------------------------


@router.get("/attack/actor-matches", dependencies=[Depends(verify_token)])
async def get_actor_matches(request: Request):
    """
    Return top-3 threat actor groups whose TTP sets best match recent detections.

    Queries detection_techniques from the last 30 days, then delegates to
    AttackStore.actor_matches() for overlap scoring.

    Returns [] if no attack_store, no detections, or no STIX groups loaded.
    """
    attack_store = getattr(request.app.state, "attack_store", None)
    if attack_store is None:
        return []

    # Query recent tech_ids via the SQLite connection shared with attack_store
    def _fetch_recent_tech_ids() -> list[str]:
        try:
            cursor = attack_store._conn.execute(
                """
                SELECT DISTINCT tech_id
                FROM detection_techniques
                WHERE detection_id IN (
                    SELECT id FROM detections
                    WHERE created_at >= datetime('now', '-30 days')
                )
                """
            )
            return [row[0] for row in cursor.fetchall()]
        except Exception:
            # Table may not exist yet if no detections have been saved
            return []

    tech_ids = await asyncio.to_thread(_fetch_recent_tech_ids)

    if not tech_ids:
        return []

    matches = await asyncio.to_thread(attack_store.actor_matches, tech_ids)
    return matches
