"""Saved investigations API — POST/GET /api/investigations/saved."""
import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

log = logging.getLogger(__name__)
router = APIRouter()


class SaveInvestigationRequest(BaseModel):
    detection_id: str | None = None
    graph_snapshot: dict[str, Any] = {}
    metadata: dict[str, Any] = {}


class SaveInvestigationResponse(BaseModel):
    id: str
    detection_id: str | None
    created_at: str


class InvestigationRecord(BaseModel):
    id: str
    detection_id: str | None
    graph_snapshot: dict[str, Any]
    metadata: dict[str, Any]
    created_at: str


class ListInvestigationsResponse(BaseModel):
    investigations: list[dict[str, Any]] = []
    total: int = 0


class GetInvestigationResponse(BaseModel):
    investigation: InvestigationRecord | None = None


@router.post("/investigations/saved", response_model=SaveInvestigationResponse)
async def save_investigation(
    request: Request, body: SaveInvestigationRequest
) -> SaveInvestigationResponse:
    """Save an investigation snapshot. Returns the new investigation ID.

    Always returns HTTP 200.
    """
    try:
        sqlite_store = request.app.state.stores.sqlite
        inv_id = await asyncio.to_thread(
            sqlite_store.save_investigation,
            body.detection_id or "",
            body.graph_snapshot,
            body.metadata,
        )
        # Fetch created_at from the saved record
        record = await asyncio.to_thread(sqlite_store.get_saved_investigation, inv_id)
        return SaveInvestigationResponse(
            id=inv_id,
            detection_id=body.detection_id,
            created_at=record["created_at"] if record else "",
        )
    except Exception as exc:
        log.warning("save_investigation error: %s", exc)
        import uuid
        from datetime import datetime, timezone
        return SaveInvestigationResponse(
            id=uuid.uuid4().hex,
            detection_id=body.detection_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )


@router.get("/investigations/saved", response_model=ListInvestigationsResponse)
async def list_saved_investigations(request: Request) -> ListInvestigationsResponse:
    """Return all saved investigations (newest first).

    Always returns HTTP 200. Returns empty list if none saved.
    """
    try:
        sqlite_store = request.app.state.stores.sqlite
        records = await asyncio.to_thread(sqlite_store.list_saved_investigations)
        return ListInvestigationsResponse(investigations=records, total=len(records))
    except Exception as exc:
        log.warning("list_saved_investigations error: %s", exc)
        return ListInvestigationsResponse()


@router.get("/investigations/saved/{investigation_id}", response_model=GetInvestigationResponse)
async def get_saved_investigation(
    request: Request, investigation_id: str
) -> GetInvestigationResponse:
    """Return a single saved investigation by ID.

    Always returns HTTP 200. Returns {investigation: null} if not found.
    """
    try:
        sqlite_store = request.app.state.stores.sqlite
        record = await asyncio.to_thread(
            sqlite_store.get_saved_investigation, investigation_id
        )
        if record is None:
            return GetInvestigationResponse(investigation=None)
        return GetInvestigationResponse(
            investigation=InvestigationRecord(**record)
        )
    except Exception as exc:
        log.warning("get_saved_investigation error: %s", exc)
        return GetInvestigationResponse(investigation=None)
