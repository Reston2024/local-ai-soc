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
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.core.logging import get_logger
from backend.core.rate_limit import limiter
from detections.matcher import SigmaMatcher

# Phase 52: TheHive sync helper (synchronous, wrapped via asyncio.to_thread in route)
try:
    from backend.services.thehive_client import _maybe_create_thehive_case
    _THEHIVE_CLIENT_AVAILABLE = True
except ImportError:
    _THEHIVE_CLIENT_AVAILABLE = False


def _maybe_create_thehive_case_wrapper(thehive_client, detection: dict, sqlite_conn) -> None:
    """Thin sync wrapper: delegates to thehive_client._maybe_create_thehive_case."""
    if not _THEHIVE_CLIENT_AVAILABLE:
        return
    try:
        _maybe_create_thehive_case(thehive_client, detection, db_conn=sqlite_conn)
    except Exception as exc:
        log.warning("TheHive case creation wrapper failed: %s", exc)


def _get_spiderfoot_observables(osint_store, src_ip: str) -> list[dict]:
    """Query OsintInvestigationStore for HIGH/CRITICAL findings for src_ip.

    Returns up to 5 findings as TheHive observable dicts (dataType='other').
    Returns empty list on any error or if no matching investigations found.
    """
    try:
        # Find completed investigations targeting this IP
        osint_store._conn.row_factory = __import__("sqlite3").Row
        cursor = osint_store._conn.execute(
            """SELECT id FROM osint_investigations
               WHERE target = ? AND status = 'FINISHED'
               ORDER BY started_at DESC LIMIT 1""",
            (src_ip,),
        )
        row = cursor.fetchone()
        osint_store._conn.row_factory = None
        if row is None:
            return []
        job_id = row["id"]

        # Retrieve findings — filter for high-risk event types
        findings = osint_store.get_findings(job_id)
        # Convert top-5 findings to observable dicts
        observables: list[dict] = []
        for f in findings[:5]:
            event_type = f.get("event_type", "")
            data = f.get("data", "")
            if data:
                observables.append({
                    "dataType": "other",
                    "data": f"{event_type}: {data}"[:200],
                    "ioc": False,
                    "message": f"SpiderFoot finding: {event_type}",
                })
        return observables
    except Exception:
        return []

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

        where_clause = ("WHERE " + " AND ".join(f"d.{c}" for c in conditions)) if conditions else ""
        # Rebuild conditions with table alias for the JOIN query
        aliased_conditions = []
        if case_id:
            aliased_conditions.append("d.case_id = ?")
        if severity:
            aliased_conditions.append("LOWER(d.severity) = LOWER(?)")
        if rule_id:
            aliased_conditions.append("d.rule_id = ?")
        where_clause = ("WHERE " + " AND ".join(aliased_conditions)) if aliased_conditions else ""

        sql = f"""
            SELECT d.*, f.verdict AS verdict
            FROM detections d
            LEFT JOIN (SELECT detection_id, verdict FROM feedback) f
                ON d.id = f.detection_id
            {where_clause}
            ORDER BY d.created_at DESC
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
            # Phase 39: parse car_analytics JSON blob → list
            if d.get("car_analytics"):
                try:
                    d["car_analytics"] = _json.loads(d["car_analytics"])
                except Exception:
                    d["car_analytics"] = None
            # Phase 44: verdict is None for unreviewed detections — preserve as-is
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

    from pathlib import Path as _Path

    matcher = SigmaMatcher(stores=stores)

    rules_dirs = [_Path("fixtures/sigma"), _Path("rules/sigma")]
    loaded = 0
    for d in rules_dirs:
        if d.exists():
            loaded += matcher.load_rules_dir(str(d))

    if loaded == 0:
        log.warning(
            "run_detection: no Sigma rules found in any rules directory",
            checked=["fixtures/sigma", "rules/sigma"],
        )
        raise HTTPException(
            status_code=422,
            detail=(
                "No Sigma rules loaded — rules/sigma/ is empty or missing. "
                "Add Sigma YAML rule files to rules/sigma/ and retry."
            ),
        )

    log.info("run_detection: loaded %d Sigma rules, running...", loaded)

    detections = await matcher.run_all(case_id=case_id)
    if detections:
        await matcher.save_detections(detections)

    # Phase 52: Auto-create TheHive cases for High/Critical detections (fire-and-forget)
    thehive_client = getattr(request.app.state, "thehive_client", None)
    if thehive_client is not None and detections:
        sqlite_conn = request.app.state.stores.sqlite._conn
        osint_store = getattr(request.app.state, "osint_store", None)
        for det in detections:
            sev = (det.severity or "").lower()
            if sev not in ("high", "critical"):
                continue
            det_dict = det.model_dump(mode="json")
            # Enrich with SpiderFoot findings for src_ip observables
            if osint_store is not None and det_dict.get("src_ip"):
                try:
                    findings = await asyncio.to_thread(
                        _get_spiderfoot_observables, osint_store, det_dict["src_ip"]
                    )
                    det_dict["_spiderfoot_findings"] = findings
                except Exception:
                    pass
            asyncio.create_task(
                asyncio.to_thread(
                    _maybe_create_thehive_case_wrapper,
                    thehive_client, det_dict, sqlite_conn,
                )
            )

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
