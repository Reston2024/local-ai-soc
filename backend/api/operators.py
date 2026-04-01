"""
Operator management API (Phase 19-04).

Endpoints:
  POST   /api/operators                        — create operator (admin only)
  GET    /api/operators                        — list operators (admin + analyst)
  DELETE /api/operators/{operator_id}          — deactivate operator (admin only)
  POST   /api/operators/{operator_id}/rotate-key — rotate API key (admin only)
  POST   /api/operators/{operator_id}/totp/enable — enable TOTP, return QR (admin only)
  DELETE /api/operators/{operator_id}/totp     — disable TOTP (admin only)

All endpoints require a valid Bearer token (verify_token is applied at router
registration in main.py). Write endpoints additionally use require_role("admin").
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.core.operator_utils import generate_api_key, hash_api_key, key_prefix
from backend.core.rbac import OperatorContext, require_role
from backend.core.totp_utils import (
    generate_totp_secret,
    get_provisioning_uri,
    totp_qr_png_b64,
)
from backend.models.operator import (
    OperatorCreate,
    OperatorCreateResponse,
    OperatorRead,
    OperatorRotateResponse,
)

router = APIRouter(tags=["operators"])


# ---------------------------------------------------------------------------
# POST /api/operators — create a new named operator
# ---------------------------------------------------------------------------

@router.post(
    "/operators",
    status_code=status.HTTP_201_CREATED,
    response_model=OperatorCreateResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def create_operator(
    body: OperatorCreate,
    request: Request,
) -> OperatorCreateResponse:
    """Create a named operator.  Returns the raw API key exactly once."""
    stores = request.app.state.stores

    operator_id = str(uuid4())
    raw_key = generate_api_key()
    hashed = hash_api_key(raw_key)
    prefix = key_prefix(raw_key)

    await asyncio.to_thread(
        stores.sqlite.create_operator,
        operator_id,
        body.username,
        hashed,
        prefix,
        body.role,
    )

    # Retrieve the created_at timestamp from the just-created row
    row = await asyncio.to_thread(
        _get_operator_row, stores.sqlite, operator_id
    )
    created_at = row["created_at"] if row else ""

    return OperatorCreateResponse(
        operator_id=operator_id,
        username=body.username,
        role=body.role,
        api_key=raw_key,
        created_at=created_at,
    )


def _get_operator_row(sqlite_store, operator_id: str) -> dict | None:
    """Synchronous helper: fetch one operator row by ID (all columns)."""
    row = sqlite_store._conn.execute(
        "SELECT * FROM operators WHERE operator_id = ?", (operator_id,)
    ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# GET /api/operators — list operators (safe fields only)
# ---------------------------------------------------------------------------

@router.get(
    "/operators",
    response_model=dict,
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def list_operators(request: Request) -> dict:
    """Return all operators.  hashed_key and totp_secret are never included."""
    stores = request.app.state.stores
    rows = await asyncio.to_thread(stores.sqlite.list_operators)
    operators = [
        OperatorRead(
            operator_id=r["operator_id"],
            username=r["username"],
            role=r["role"],
            is_active=bool(r["is_active"]),
            created_at=r["created_at"],
            last_seen_at=r.get("last_seen_at"),
        )
        for r in rows
    ]
    return {"operators": [op.model_dump() for op in operators]}


# ---------------------------------------------------------------------------
# DELETE /api/operators/{operator_id} — deactivate (soft-delete)
# ---------------------------------------------------------------------------

@router.delete(
    "/operators/{operator_id}",
    status_code=status.HTTP_200_OK,
)
async def deactivate_operator(
    operator_id: str,
    request: Request,
    ctx: OperatorContext = Depends(require_role("admin")),
) -> dict:
    """Set is_active=False for the given operator.

    Raises 400 if an admin attempts to deactivate their own account.
    """
    if operator_id == ctx.operator_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    stores = request.app.state.stores
    await asyncio.to_thread(stores.sqlite.deactivate_operator, operator_id)
    return {"detail": "Operator deactivated"}


# ---------------------------------------------------------------------------
# POST /api/operators/{operator_id}/rotate-key — generate new API key
# ---------------------------------------------------------------------------

@router.post(
    "/operators/{operator_id}/rotate-key",
    response_model=OperatorRotateResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def rotate_operator_key(
    operator_id: str,
    request: Request,
) -> OperatorRotateResponse:
    """Generate a new API key for the given operator.

    The new raw key is returned exactly once.  The old key is immediately
    invalidated.
    """
    stores = request.app.state.stores

    new_raw_key = generate_api_key()
    hashed = hash_api_key(new_raw_key)
    prefix = key_prefix(new_raw_key)

    await asyncio.to_thread(
        stores.sqlite.update_operator_key,
        operator_id,
        hashed,
        prefix,
    )

    return OperatorRotateResponse(
        operator_id=operator_id,
        api_key=new_raw_key,
    )


# ---------------------------------------------------------------------------
# POST /api/operators/{operator_id}/totp/enable — provision TOTP
# ---------------------------------------------------------------------------

@router.post(
    "/operators/{operator_id}/totp/enable",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_role("admin"))],
)
async def enable_totp(
    operator_id: str,
    request: Request,
) -> dict:
    """Generate a TOTP secret and return QR code + provisioning URI.

    The secret is persisted to the operators table.  From this point forward
    verify_token will require X-TOTP-Code header for this operator.
    """
    stores = request.app.state.stores

    # Resolve the operator's username for the provisioning URI
    row = await asyncio.to_thread(_get_operator_row, stores.sqlite, operator_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Operator not found")

    secret = generate_totp_secret()
    await asyncio.to_thread(stores.sqlite.set_totp_secret, operator_id, secret)

    uri = get_provisioning_uri(secret, row["username"])
    qr = totp_qr_png_b64(uri)

    return {"qr_code": qr, "provisioning_uri": uri}


# ---------------------------------------------------------------------------
# DELETE /api/operators/{operator_id}/totp — disable TOTP
# ---------------------------------------------------------------------------

@router.delete(
    "/operators/{operator_id}/totp",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_role("admin"))],
)
async def disable_totp(
    operator_id: str,
    request: Request,
) -> dict:
    """Clear the TOTP secret for the given operator, disabling MFA."""
    stores = request.app.state.stores
    await asyncio.to_thread(stores.sqlite.set_totp_secret, operator_id, None)
    return {"detail": "TOTP disabled"}
