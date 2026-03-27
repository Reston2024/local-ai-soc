"""
Detection API — manage and retrieve correlated detections.

Endpoints:
  GET  /detect                    — list detections with optional filters
  GET  /detect/{detection_id}     — single detection by ID
  POST /detect                    — manually create a detection record
  GET  /detect/case/{case_id}     — all detections for a case
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.core.logging import get_logger
from backend.core.rate_limit import limiter

log = get_logger(__name__)
router = APIRouter(prefix="/detect", tags=["detect"])


def _get_stores(request: Request):
    return request.app.state.stores


# ---------------------------------------------------------------------------
# Request model for manual detection creation
# ---------------------------------------------------------------------------


class CreateDetectionRequest(BaseModel):
    rule_id: str = Field(min_length=1)
    rule_name: str = Field(min_length=1)
    severity: str = Field(description="critical | high | medium | low | informational")
    matched_event_ids: list[str] = Field(default_factory=list)
    attack_technique: Optional[str] = None
    attack_tactic: Optional[str] = None
    explanation: Optional[str] = None
    case_id: Optional[str] = None


# ---------------------------------------------------------------------------
# GET /detect
# ---------------------------------------------------------------------------


@router.get("")
async def list_detections(
    request: Request,
    case_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    rule_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> JSONResponse:
    """List detections with optional filters."""
    stores = request.app.state.stores

    def _query() -> list[dict]:
        conditions = []
        params: list = []

        if case_id:
            conditions.append("case_id = ?")
            params.append(case_id)
        if severity:
            conditions.append("LOWER(severity) = LOWER(?)")
            params.append(severity)
        if rule_id:
            conditions.append("rule_id = ?")
            params.append(rule_id)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"""
            SELECT * FROM detections {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params += [limit, offset]

        rows = stores.sqlite._conn.execute(sql, params).fetchall()
        import json as _json
        result = []
        for row in rows:
            d = dict(row)
            if d.get("matched_event_ids"):
                try:
                    d["matched_event_ids"] = _json.loads(d["matched_event_ids"])
                except Exception:
                    pass
            result.append(d)
        return result

    detections = await asyncio.to_thread(_query)
    return JSONResponse(content={"detections": detections, "total": len(detections)})


# ---------------------------------------------------------------------------
# POST /detect/run — must be registered BEFORE /{detection_id} catch-all
# ---------------------------------------------------------------------------


@limiter.limit("10/minute")
@router.post("/run")
async def run_detection(
    request: Request,
    case_id: Optional[str] = Query(default=None),
) -> JSONResponse:
    """Run all Sigma rules against stored events. Returns new DetectionRecords."""
    stores = _get_stores(request)

    from detections.matcher import SigmaMatcher
    from pathlib import Path as _Path

    matcher = SigmaMatcher(stores=stores)

    rules_dirs = [_Path("fixtures/sigma"), _Path("rules/sigma")]
    loaded = 0
    for d in rules_dirs:
        if d.exists():
            loaded += matcher.load_rules_dir(str(d))

    log.info("run_detection: loaded %d Sigma rules, running...", loaded)

    detections = await matcher.run_all(case_id=case_id)
    if detections:
        await matcher.save_detections(detections)

    log.info("run_detection: found %d detections", len(detections))
    return JSONResponse(
        content={
            "count": len(detections),
            "detections": [d.model_dump(mode="json") for d in detections],
        }
    )


# ---------------------------------------------------------------------------
# GET /detect/case/{case_id}
# ---------------------------------------------------------------------------


@router.get("/case/{case_id}")
async def get_detections_by_case(case_id: str, request: Request) -> JSONResponse:
    """Return all detections associated with a given case."""
    stores = request.app.state.stores
    detections = await asyncio.to_thread(stores.sqlite.get_detections_by_case, case_id)
    return JSONResponse(content={"case_id": case_id, "detections": detections})


# ---------------------------------------------------------------------------
# POST /detect
# ---------------------------------------------------------------------------


@router.post("", status_code=201)
async def create_detection(
    body: CreateDetectionRequest, request: Request
) -> JSONResponse:
    """Manually create a detection record (e.g. from Sigma rule match)."""
    stores = request.app.state.stores
    detection_id = str(uuid4())

    await asyncio.to_thread(
        stores.sqlite.insert_detection,
        detection_id,
        body.rule_id,
        body.rule_name,
        body.severity,
        body.matched_event_ids,
        body.attack_technique,
        body.attack_tactic,
        body.explanation,
        body.case_id,
    )

    log.info(
        "Detection created",
        detection_id=detection_id,
        rule=body.rule_name,
        severity=body.severity,
    )
    return JSONResponse(
        status_code=201,
        content={"detection_id": detection_id, "status": "created"},
    )


# ---------------------------------------------------------------------------
# GET /detect/{detection_id}
# ---------------------------------------------------------------------------


@router.get("/{detection_id}")
async def get_detection(detection_id: str, request: Request) -> JSONResponse:
    """Return a single detection by ID."""
    stores = request.app.state.stores
    detection = await asyncio.to_thread(stores.sqlite.get_detection, detection_id)

    if not detection:
        raise HTTPException(
            status_code=404, detail=f"Detection {detection_id!r} not found"
        )

    return JSONResponse(content=detection)
