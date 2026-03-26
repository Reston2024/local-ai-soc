"""GET /api/top-threats — return top N detections ranked by risk_score."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Query, Request

from pydantic import BaseModel

log = logging.getLogger(__name__)
router = APIRouter()


class ThreatItem(BaseModel):
    id: str
    rule_name: str
    severity: str
    risk_score: int
    attack_technique: str | None = None
    attack_tactic: str | None = None


class TopThreatsResponse(BaseModel):
    threats: list[ThreatItem] = []
    total: int = 0


@router.get("/top-threats", response_model=TopThreatsResponse)
async def get_top_threats(
    request: Request,
    limit: int = Query(default=10, ge=1, le=100),
) -> TopThreatsResponse:
    """Return top N detections ranked by risk_score DESC.

    Always returns HTTP 200. Returns empty list if no detections scored yet.
    Scores are populated by POST /api/score — call that first for non-zero results.
    """
    try:
        return await _fetch_top_threats(request, limit)
    except Exception as exc:
        log.warning("top-threats endpoint error (returning empty): %s", exc)
        return TopThreatsResponse()


async def _fetch_top_threats(request: Request, limit: int) -> TopThreatsResponse:
    stores = request.app.state.stores
    sqlite_store = stores.sqlite

    rows = await asyncio.to_thread(
        lambda: sqlite_store._conn.execute(
            "SELECT id, rule_name, severity, risk_score, attack_technique, attack_tactic "
            "FROM detections ORDER BY risk_score DESC LIMIT ?",
            (limit,),
        ).fetchall()
    )

    threats = [
        ThreatItem(
            id=row[0],
            rule_name=row[1] or "Unknown",
            severity=row[2] or "info",
            risk_score=row[3] or 0,
            attack_technique=row[4],
            attack_tactic=row[5],
        )
        for row in rows
    ]
    return TopThreatsResponse(threats=threats, total=len(threats))
