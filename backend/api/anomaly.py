"""
Anomaly scoring API.

Endpoints:
  GET /api/anomaly                    — list high-anomaly events
  GET /api/anomaly/entity             — per-(subnet, process) profile
  GET /api/anomaly/trend              — score time-series for an entity
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from backend.core.auth import verify_token
from backend.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/api/anomaly", tags=["anomaly"])


@router.get("")
async def list_anomalies(
    request: Request,
    min_score: float = Query(0.5, ge=0.0, le=1.0),
    limit: int = Query(100, ge=1, le=1000),
    _token: str = Depends(verify_token),
) -> JSONResponse:
    """List events with anomaly_score >= min_score, sorted by score descending."""
    stores = request.app.state.stores
    rows = await stores.duckdb.fetch_df(
        """SELECT event_id, timestamp, hostname, process_name,
                  src_ip, event_type, severity, anomaly_score
           FROM normalized_events
           WHERE anomaly_score >= ?
           ORDER BY anomaly_score DESC
           LIMIT ?""",
        [min_score, limit],
    )
    return JSONResponse(content={"anomalies": rows, "total": len(rows)})


@router.get("/entity")
async def entity_profile(
    request: Request,
    subnet: str = Query(..., description="Subnet prefix e.g. 192.168.1"),
    process: str = Query(..., description="Process name e.g. svchost.exe"),
    _token: str = Depends(verify_token),
) -> JSONResponse:
    """Return score profile for a (subnet /24, process_name) peer group."""
    stores = request.app.state.stores
    # Build entity key using same logic as AnomalyScorer
    proc = process.lower().strip()

    rows = await stores.duckdb.fetch_df(
        """SELECT event_id, timestamp, anomaly_score
           FROM normalized_events
           WHERE anomaly_score IS NOT NULL
             AND src_ip LIKE ?
             AND LOWER(process_name) = ?
           ORDER BY timestamp DESC
           LIMIT 500""",
        [f"{subnet}.%", proc],
    )
    if not rows:
        return JSONResponse(content={
            "entity_key": f"{subnet}__{proc}",
            "event_count": 0,
            "avg_score": 0.0,
            "max_score": 0.0,
            "scores": [],
        })

    scores_only = [r["anomaly_score"] for r in rows if r.get("anomaly_score") is not None]
    avg_score = sum(scores_only) / len(scores_only) if scores_only else 0.0
    max_score = max(scores_only) if scores_only else 0.0
    sparkline = [
        {"timestamp": r["timestamp"], "score": r["anomaly_score"]}
        for r in rows
        if r.get("anomaly_score") is not None
    ]

    return JSONResponse(content={
        "entity_key": f"{subnet}__{proc}",
        "event_count": len(rows),
        "avg_score": round(avg_score, 4),
        "max_score": round(max_score, 4),
        "scores": sparkline,
    })


@router.get("/trend")
async def score_trend(
    request: Request,
    entity_key: str = Query(..., description="entity key 'subnet__process' e.g. '192.168.1__svchost.exe'"),
    hours: int = Query(24, ge=1, le=168),
    _token: str = Depends(verify_token),
) -> JSONResponse:
    """Return anomaly score time-series for entity_key over the last N hours."""
    stores = request.app.state.stores
    # Parse entity_key back to subnet + process
    parts = entity_key.split("__", 1)
    if len(parts) != 2:
        return JSONResponse(content=[])
    subnet, proc = parts[0], parts[1].lower()

    rows = await stores.duckdb.fetch_df(
        f"""SELECT timestamp, anomaly_score
           FROM normalized_events
           WHERE anomaly_score IS NOT NULL
             AND src_ip LIKE ?
             AND LOWER(process_name) = ?
             AND timestamp >= NOW() - INTERVAL '{hours} hours'
           ORDER BY timestamp ASC
           LIMIT 500""",
        [f"{subnet}.%", proc],
    )
    trend = [
        {"timestamp": r["timestamp"], "score": r["anomaly_score"]}
        for r in rows
        if r.get("anomaly_score") is not None
    ]
    return JSONResponse(content=trend)
