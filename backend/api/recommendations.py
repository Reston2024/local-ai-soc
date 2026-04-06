"""
Recommendation artifact CRUD routes (Phase 24).

Routes:
  POST   /api/recommendations           — create draft
  GET    /api/recommendations/{id}      — retrieve by ID
  GET    /api/recommendations           — list with optional filters
  PATCH  /api/recommendations/{id}/approve  — human-in-the-loop approval gate (ADR-030)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from backend.core.logging import get_logger
from backend.models.recommendation import ApproveRequest, RecommendationCreate

log = get_logger(__name__)
router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])

# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------

_INSERT_SQL = """
INSERT INTO recommendations (
    recommendation_id, case_id, schema_version, type, proposed_action,
    target, scope, rationale, evidence_event_ids, retrieval_sources,
    inference_confidence, model_id, model_run_id, prompt_inspection,
    generated_at, analyst_approved, approved_by, override_log,
    expires_at, status, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_SELECT_BY_ID = "SELECT * FROM recommendations WHERE recommendation_id = ?"

_SELECT_COLS = [
    "recommendation_id", "case_id", "schema_version", "type", "proposed_action",
    "target", "scope", "rationale", "evidence_event_ids", "retrieval_sources",
    "inference_confidence", "model_id", "model_run_id", "prompt_inspection",
    "generated_at", "analyst_approved", "approved_by", "override_log",
    "expires_at", "status", "created_at",
]

_JSON_COLS = {"rationale", "evidence_event_ids", "retrieval_sources", "prompt_inspection", "override_log"}


def _row_to_dict(row: tuple) -> dict:
    """Map a DuckDB tuple row to a named dict, parsing JSON TEXT columns."""
    result = dict(zip(_SELECT_COLS, row))
    for col in _JSON_COLS:
        if result.get(col) is not None:
            val = result[col]
            if isinstance(val, str):
                result[col] = json.loads(val)
    # DuckDB returns BOOLEAN as bool; normalize to Python bool explicitly
    result["analyst_approved"] = bool(result.get("analyst_approved", False))
    # Convert timestamps to ISO string if returned as datetime objects
    for ts_col in ("generated_at", "expires_at", "created_at"):
        val = result.get(ts_col)
        if isinstance(val, datetime):
            result[ts_col] = val.isoformat()
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("", status_code=201)
async def create_recommendation(body: RecommendationCreate, request: Request) -> JSONResponse:
    """Create a new draft recommendation artifact."""
    stores = request.app.state.stores
    rec_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    await stores.duckdb.execute_write(
        _INSERT_SQL,
        [
            rec_id,
            body.case_id,
            "1.0.0",
            body.type,
            body.proposed_action,
            body.target,
            body.scope,
            json.dumps(body.rationale),
            json.dumps(body.evidence_event_ids),
            json.dumps(body.retrieval_sources.model_dump(mode="json")),
            body.inference_confidence,
            body.model_id,
            body.model_run_id,
            json.dumps(body.prompt_inspection.model_dump(mode="json")),
            body.generated_at,
            False,
            "",
            None,
            body.expires_at,
            "draft",
            now,
        ],
    )
    log.info("Created recommendation", recommendation_id=rec_id, case_id=body.case_id)
    return JSONResponse(content={"recommendation_id": rec_id}, status_code=201)


@router.get("/{recommendation_id}")
async def get_recommendation(recommendation_id: str, request: Request) -> JSONResponse:
    """Retrieve a recommendation artifact by ID."""
    stores = request.app.state.stores
    rows = await stores.duckdb.fetch_all(_SELECT_BY_ID, [recommendation_id])
    if not rows:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return JSONResponse(content=_row_to_dict(rows[0]))


@router.get("")
async def list_recommendations(
    request: Request,
    status: Optional[str] = Query(default=None),
    case_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JSONResponse:
    """List recommendation artifacts with optional filters."""
    stores = request.app.state.stores

    filters: list[str] = []
    params: list = []

    if status is not None:
        filters.append("status = ?")
        params.append(status)
    if case_id is not None:
        filters.append("case_id = ?")
        params.append(case_id)

    where_clause = ("WHERE " + " AND ".join(filters)) if filters else ""

    count_sql = f"SELECT COUNT(*) FROM recommendations {where_clause}"
    count_rows = await stores.duckdb.fetch_all(count_sql, params if params else None)
    total = count_rows[0][0] if count_rows else 0

    data_sql = f"SELECT * FROM recommendations {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?"
    data_rows = await stores.duckdb.fetch_all(data_sql, params + [limit, offset])

    items = [_row_to_dict(row) for row in data_rows]
    return JSONResponse(content={"items": items, "total": total})


# ---------------------------------------------------------------------------
# Approval gate helpers
# ---------------------------------------------------------------------------


def _run_approval_gate(rec: dict, body: ApproveRequest) -> list[str]:
    """
    Enforce ADR-030 §2 + §4 approval conditions.

    Returns a list of error strings. Empty list means all conditions pass.
    Does NOT handle the double-approval 409 — caller checks analyst_approved separately.
    """
    errors: list[str] = []

    # Condition 1: approved_by must be non-empty
    if not body.approved_by.strip():
        errors.append("approved_by must be non-empty")

    # Condition 2: expires_at must be in the future (timezone-aware comparison)
    # DuckDB may strip timezone info — use .replace("Z", "+00:00") for safety
    expires_raw = rec.get("expires_at", "")
    if isinstance(expires_raw, datetime):
        expires_dt = expires_raw if expires_raw.tzinfo else expires_raw.replace(tzinfo=timezone.utc)
    else:
        expires_dt = datetime.fromisoformat(str(expires_raw).replace("Z", "+00:00"))
        if expires_dt.tzinfo is None:
            expires_dt = expires_dt.replace(tzinfo=timezone.utc)

    if expires_dt <= datetime.now(timezone.utc):
        errors.append("expires_at is in the past — artifact has expired")

    # Condition 3: override_log required for low/none confidence or failed inspection
    confidence: str = rec.get("inference_confidence", "")
    inspection = rec.get("prompt_inspection", {})
    if isinstance(inspection, str):
        inspection = json.loads(inspection)

    needs_override = confidence in ("low", "none") or not inspection.get("passed", True)
    if needs_override and body.override_log is None:
        errors.append(
            "override_log is required when inference_confidence is 'low'/'none' "
            "or prompt_inspection.passed is false"
        )

    return errors


# ---------------------------------------------------------------------------
# Approval gate endpoint
# ---------------------------------------------------------------------------


@router.patch("/{recommendation_id}/approve")
async def approve_recommendation(
    recommendation_id: str, body: ApproveRequest, request: Request
) -> JSONResponse:
    """
    Human-in-the-loop approval gate (ADR-030).

    Sets analyst_approved=True and status='approved'. This is the ONLY path
    that sets analyst_approved=True — POST creates drafts with False always.
    """
    stores = request.app.state.stores

    rows = await stores.duckdb.fetch_all(_SELECT_BY_ID, [recommendation_id])
    if not rows:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec = _row_to_dict(rows[0])

    # Guard: immutability after approval (ADR-030 §1) — returns 409, not 422
    if rec.get("analyst_approved") is True:
        raise HTTPException(
            status_code=409,
            detail="artifact is immutable after approval",
        )

    # Run the gate
    gate_errors = _run_approval_gate(rec, body)
    if gate_errors:
        raise HTTPException(
            status_code=422,
            detail={"gate_errors": gate_errors},
        )

    # All conditions passed — write approval
    override_json = (
        json.dumps(body.override_log.model_dump(mode="json")) if body.override_log else None
    )

    await stores.duckdb.execute_write(
        """
        UPDATE recommendations
        SET analyst_approved = TRUE,
            approved_by      = ?,
            override_log     = ?,
            status           = 'approved'
        WHERE recommendation_id = ?
        """,
        [body.approved_by, override_json, recommendation_id],
    )

    log.info(
        "Recommendation approved",
        recommendation_id=recommendation_id,
        approved_by=body.approved_by,
    )
    return JSONResponse(
        content={"status": "approved", "recommendation_id": recommendation_id},
        status_code=200,
    )
