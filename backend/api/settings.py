"""
Settings API — system configuration and model drift status.

Endpoints:
  GET /settings/model-status  — active model, last-known model, drift alert
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from backend.core.logging import get_logger
from backend.core.rbac import require_role

log = get_logger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


@router.get(
    "/model-status",
    dependencies=[Depends(require_role("analyst", "admin"))],
)
async def get_model_status(request: Request) -> JSONResponse:
    """
    Return the current model status including active model, last-known model,
    and whether a drift event has been detected.
    """
    stores = request.app.state.stores
    ollama = request.app.state.ollama

    # Fetch active model from Ollama (non-fatal)
    active_model: str | None = None
    try:
        models = await ollama.list_models()
        if models:
            # Use configured model if in list, otherwise first available
            configured = getattr(ollama, "model", None)
            active_model = configured if (configured and configured in models) else models[0]
    except Exception as exc:
        log.warning("list_models() failed during model-status check", error=str(exc))

    # Load stored model status
    try:
        status_data = await asyncio.to_thread(stores.sqlite.get_model_status)
    except Exception as exc:
        log.warning("get_model_status() failed", error=str(exc))
        status_data = {"last_known_model": None, "last_change": None}

    last_known = status_data.get("last_known_model")
    last_change = status_data.get("last_change")

    # Detect drift: active_model known and differs from last-known
    drift_detected = (
        active_model is not None
        and last_known is not None
        and active_model != last_known
    )

    # Update last-known model if Ollama is reachable and returned a non-empty list
    if active_model is not None:
        try:
            existing = await asyncio.to_thread(stores.sqlite.get_kv, "last_known_model")
            if existing != active_model:
                if existing is not None:
                    # Record the change before updating
                    await asyncio.to_thread(
                        stores.sqlite.record_model_change,
                        existing,
                        active_model,
                    )
                await asyncio.to_thread(
                    stores.sqlite.set_kv,
                    "last_known_model",
                    active_model,
                )
                log.info(
                    "Model change detected and recorded",
                    previous=existing,
                    active=active_model,
                )
        except Exception as exc:
            log.warning("Model drift write failed (non-fatal)", error=str(exc))

    return JSONResponse(
        content={
            "active_model": active_model,
            "last_known_model": last_known,
            "drift_detected": drift_detected,
            "last_change": last_change,
        }
    )
