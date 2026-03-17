"""
Telemetry API — live collection status endpoints.

Endpoints:
  GET /telemetry/osquery/status  — OsqueryCollector health and state
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.core.config import settings as _default_settings
from backend.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get("/osquery/status")
async def osquery_status(request: Request) -> JSONResponse:
    """
    Return current osquery collector status.

    Always returns HTTP 200 — 'enabled' reflects OSQUERY_ENABLED setting.
    Safe to call even when osquery is not installed.
    """
    # Prefer settings from app.state (set in lifespan) over module singleton
    cfg = getattr(request.app.state, "settings", _default_settings)
    collector = getattr(request.app.state, "osquery_collector", None)

    log_path = cfg.OSQUERY_LOG_PATH
    log_exists = Path(log_path).exists()

    if collector is not None:
        try:
            collector_status = collector.status()
        except Exception:
            collector_status = {"running": False, "lines_processed": 0, "error": "status() unavailable"}
    else:
        collector_status = {
            "running": False,
            "lines_processed": 0,
            "error": None,
        }

    return JSONResponse({
        "enabled": cfg.OSQUERY_ENABLED,
        "log_path": log_path,
        "log_exists": log_exists,
        "running": collector_status.get("running", False),
        "lines_processed": collector_status.get("lines_processed", 0),
        "error": collector_status.get("error"),
    })
