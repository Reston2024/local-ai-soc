"""
Notifications read route (Phase 25).

Routes:
  GET /api/notifications — return all pending notifications as a flat list
"""

import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

_SELECT_PENDING = """
SELECT notification_id, case_id, receipt_id, required_action, status, created_at
FROM notifications
WHERE status = 'pending'
ORDER BY created_at DESC
"""


@router.get("")
async def list_notifications(request: Request) -> JSONResponse:
    stores = request.app.state.stores
    rows: list[Any] = await stores.duckdb.fetch_all(_SELECT_PENDING, None)
    items = [
        {
            "notification_id": r[0],
            "case_id": r[1],
            "receipt_id": r[2],
            "required_action": r[3],
            "status": r[4],
            "created_at": r[5],
        }
        for r in rows
    ]
    return JSONResponse(content={"notifications": items})
