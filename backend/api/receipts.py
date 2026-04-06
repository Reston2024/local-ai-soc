"""
Execution receipt ingestion route (Phase 25).

Routes:
  POST /api/receipts — ingest a receipt, propagate case state, emit notifications
"""

import asyncio
import json as _json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.models.receipt import (
    CASE_STATE_MAP,
    NOTIFICATION_TRIGGERS,
    REQUIRED_ACTION_MAP,
    ReceiptIngest,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/receipts", tags=["receipts"])

_INSERT_RECEIPT = """
INSERT INTO execution_receipts (
    receipt_id, recommendation_id, case_id, failure_taxonomy,
    executed_at, executor_version, detail, raw_receipt, received_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_INSERT_NOTIFICATION = """
INSERT INTO notifications (
    notification_id, case_id, receipt_id, required_action, status, created_at
) VALUES (?, ?, ?, ?, ?, ?)
"""


@router.post("", status_code=202)
async def ingest_receipt(body: ReceiptIngest, request: Request) -> JSONResponse:
    stores = request.app.state.stores
    now = datetime.now(timezone.utc).isoformat()

    # Step 1: Store receipt (audit-first — never skip even if downstream fails)
    raw = _json.dumps(body.model_dump())
    try:
        await stores.duckdb.execute_write(
            _INSERT_RECEIPT,
            [
                body.receipt_id,
                body.recommendation_id,
                body.case_id,
                body.failure_taxonomy,
                body.executed_at,
                body.executor_version,
                body.detail,
                raw,
                now,
            ],
        )
    except Exception as exc:
        if "PRIMARY KEY" in str(exc) or "Constraint" in str(exc):
            raise HTTPException(status_code=409, detail="receipt_id already exists")
        raise

    # Step 2: Propagate case state (best-effort — log on failure, do not roll back receipt)
    new_status = CASE_STATE_MAP[body.failure_taxonomy]
    try:
        await asyncio.to_thread(
            stores.sqlite.update_investigation_case,
            body.case_id,
            {"case_status": new_status},
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "Case state propagation failed — receipt stored but case not updated",
            extra={"case_id": body.case_id, "error": str(exc)},
        )

    # Step 3: Emit notification if required
    if body.failure_taxonomy in NOTIFICATION_TRIGGERS:
        notif_id = str(uuid4())
        required_action = REQUIRED_ACTION_MAP[body.failure_taxonomy]
        try:
            await stores.duckdb.execute_write(
                _INSERT_NOTIFICATION,
                [notif_id, body.case_id, body.receipt_id, required_action, "pending", now],
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "Notification emit failed",
                extra={"receipt_id": body.receipt_id, "error": str(exc)},
            )

    return JSONResponse(content={"receipt_id": body.receipt_id}, status_code=202)
