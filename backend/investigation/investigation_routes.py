"""Investigation API endpoints — Phase 7 Plan 04.

8 endpoints for case management, threat hunting, timeline reconstruction,
and artifact upload.  The router falls back to a module-level in-memory
SQLiteStore when app.state.stores is not initialised (test environment).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel

from backend.investigation.case_manager import CaseManager
from backend.investigation.hunt_engine import execute_hunt, HUNT_TEMPLATES
from backend.investigation.timeline_builder import build_timeline
from backend.investigation.artifact_store import save_artifact
from backend.core.logging import get_logger

log = get_logger(__name__)

investigation_router = APIRouter(prefix="/api", tags=["investigation"])
_case_manager = CaseManager()

# ---------------------------------------------------------------------------
# Module-level fallback store (used when app.state.stores is absent, e.g. tests)
# ---------------------------------------------------------------------------
_fallback_sqlite: object | None = None
_fallback_duckdb: object | None = None


def _get_fallback_sqlite():
    """Lazily create an in-memory SQLiteStore for test environments."""
    global _fallback_sqlite
    if _fallback_sqlite is None:
        try:
            from backend.stores.sqlite_store import SQLiteStore
            import tempfile
            _fallback_sqlite = SQLiteStore(data_dir=tempfile.mkdtemp())
        except Exception as exc:
            log.warning("Could not create fallback SQLiteStore: %s", exc)
            return None
    return _fallback_sqlite


def _get_stores(request: Request):
    """Return (sqlite_store, duckdb_store) from app state or fallback."""
    try:
        stores = request.app.state.stores
        return stores.sqlite, stores.duckdb
    except AttributeError:
        sqlite = _get_fallback_sqlite()
        return sqlite, None


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class CreateCaseRequest(BaseModel):
    title: str
    description: str = ""


class CaseUpdateRequest(BaseModel):
    case_status: Optional[str] = None
    analyst_notes: Optional[str] = None
    tags: Optional[list[str]] = None
    related_alerts: Optional[list[str]] = None
    related_entities: Optional[list[str]] = None


class HuntRequest(BaseModel):
    template: str
    params: dict = {}


# ---------------------------------------------------------------------------
# POST /api/cases — create investigation case
# ---------------------------------------------------------------------------

@investigation_router.post("/cases")
async def create_case(body: CreateCaseRequest, request: Request):
    sqlite, _ = _get_stores(request)
    if sqlite is None:
        raise HTTPException(status_code=503, detail="SQLite store not available")

    case_id = await asyncio.to_thread(
        sqlite.create_investigation_case, body.title, body.description
    )
    case = await asyncio.to_thread(sqlite.get_investigation_case, case_id)
    if case is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve created case")
    return {
        "case_id": case_id,
        "title": case["title"],
        "case_status": case["case_status"],
        "created_at": case["created_at"],
    }


# ---------------------------------------------------------------------------
# GET /api/cases — list investigation cases
# ---------------------------------------------------------------------------

@investigation_router.get("/cases")
async def list_cases(
    request: Request,
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
):
    sqlite, _ = _get_stores(request)
    if sqlite is None:
        raise HTTPException(status_code=503, detail="SQLite store not available")

    cases = await asyncio.to_thread(sqlite.list_investigation_cases, status)
    paginated = cases[offset: offset + limit]
    return {"cases": paginated, "total": len(cases), "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id} — case detail
# ---------------------------------------------------------------------------

@investigation_router.get("/cases/{case_id}")
async def get_case(case_id: str, request: Request):
    sqlite, _ = _get_stores(request)
    if sqlite is None:
        raise HTTPException(status_code=503, detail="SQLite store not available")

    case = await asyncio.to_thread(sqlite.get_investigation_case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


# ---------------------------------------------------------------------------
# PATCH /api/cases/{case_id} — partial update
# ---------------------------------------------------------------------------

@investigation_router.patch("/cases/{case_id}")
async def update_case(case_id: str, body: CaseUpdateRequest, request: Request):
    sqlite, _ = _get_stores(request)
    if sqlite is None:
        raise HTTPException(status_code=503, detail="SQLite store not available")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {"case_id": case_id, "updated": False}

    await asyncio.to_thread(sqlite.update_investigation_case, case_id, updates)
    case = await asyncio.to_thread(sqlite.get_investigation_case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id}/timeline — reconstructed timeline
# ---------------------------------------------------------------------------

@investigation_router.get("/cases/{case_id}/timeline")
async def get_timeline(case_id: str, request: Request):
    sqlite, duckdb = _get_stores(request)
    if sqlite is None:
        raise HTTPException(status_code=503, detail="SQLite store not available")

    # Verify case exists
    case = await asyncio.to_thread(sqlite.get_investigation_case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    timeline = await build_timeline(case_id, duckdb, sqlite)
    return {"case_id": case_id, "timeline": timeline, "total_events": len(timeline)}


# ---------------------------------------------------------------------------
# POST /api/cases/{case_id}/artifacts — upload artifact
# ---------------------------------------------------------------------------

@investigation_router.post("/cases/{case_id}/artifacts")
async def upload_artifact(
    case_id: str,
    request: Request,
    file: UploadFile = File(...),
    description: str = Form(""),
):
    sqlite, _ = _get_stores(request)
    if sqlite is None:
        raise HTTPException(status_code=503, detail="SQLite store not available")

    # Verify case exists
    case = await asyncio.to_thread(sqlite.get_investigation_case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    content = await file.read()
    try:
        data_dir = request.app.state.data_dir
    except AttributeError:
        try:
            data_dir = str(request.app.state.settings.DATA_DIR)
        except AttributeError:
            data_dir = "data"

    result = await save_artifact(
        data_dir,
        case_id,
        None,  # auto-generate artifact_id
        file.filename or "artifact",
        content,
        sqlite,
        description=description,
        mime_type=file.content_type,
    )

    # Append artifact_id to the case's artifacts list
    current_case = await asyncio.to_thread(sqlite.get_investigation_case, case_id)
    if current_case is not None:
        artifacts = current_case.get("artifacts", []) or []
        if result["artifact_id"] not in artifacts:
            artifacts.append(result["artifact_id"])
        await asyncio.to_thread(
            sqlite.update_investigation_case, case_id, {"artifacts": artifacts}
        )

    return result


# ---------------------------------------------------------------------------
# GET /api/hunt/templates — list hunt templates
# ---------------------------------------------------------------------------

@investigation_router.get("/hunt/templates")
async def list_hunt_templates():
    templates = [
        {"name": t.name, "description": t.description, "param_keys": t.param_keys}
        for t in HUNT_TEMPLATES.values()
    ]
    return {"templates": templates}


# ---------------------------------------------------------------------------
# POST /api/hunt — execute hunt query
# ---------------------------------------------------------------------------

@investigation_router.post("/hunt")
async def execute_hunt_query(body: HuntRequest, request: Request):
    _, duckdb = _get_stores(request)
    if duckdb is None:
        # Return empty results when DuckDB unavailable (test environment)
        return {
            "template": body.template,
            "params": body.params,
            "results": [],
            "result_count": 0,
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }

    try:
        results = await execute_hunt(duckdb, body.template, body.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "template": body.template,
        "params": body.params,
        "results": results,
        "result_count": len(results),
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }
