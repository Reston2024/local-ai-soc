"""
Firewall telemetry API — connectivity status endpoint.

Endpoints:
  GET /api/firewall/status  — FirewallCollector connectivity state
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.core.config import settings as _default_settings
from backend.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/firewall", tags=["firewall"])


@router.get("/status")
async def firewall_status(request: Request) -> JSONResponse:
    """
    Return current firewall collector connectivity state.

    Status is derived from heartbeat recency stored in system_kv:
      - connected:  last heartbeat < FIREWALL_HEARTBEAT_THRESHOLD_SECONDS ago
      - degraded:   between threshold and FIREWALL_OFFLINE_THRESHOLD_SECONDS
      - offline:    beyond offline threshold OR never seen
    """
    cfg = getattr(request.app.state, "settings", _default_settings)
    stores = getattr(request.app.state, "stores", None)

    last_seen_str = None
    age_seconds = None
    status = "offline"

    if stores is not None:
        try:
            last_seen_str = await asyncio.to_thread(
                stores.sqlite.get_kv, "firewall.last_heartbeat"
            )
        except Exception as exc:
            log.warning("Failed to read firewall.last_heartbeat from system_kv", error=str(exc))

    if last_seen_str is not None:
        try:
            last_seen = datetime.fromisoformat(last_seen_str)
            age_seconds = (datetime.now(tz=timezone.utc) - last_seen).total_seconds()
            if age_seconds < cfg.FIREWALL_HEARTBEAT_THRESHOLD_SECONDS:
                status = "connected"
            elif age_seconds < cfg.FIREWALL_OFFLINE_THRESHOLD_SECONDS:
                status = "degraded"
            else:
                status = "offline"
        except (ValueError, TypeError) as exc:
            log.warning("Invalid firewall.last_heartbeat value", value=last_seen_str, error=str(exc))

    return JSONResponse({
        "status": status,
        "last_seen": last_seen_str,
        "age_seconds": age_seconds,
        "enabled": cfg.FIREWALL_ENABLED,
        "syslog_path": cfg.FIREWALL_SYSLOG_PATH,
        "eve_path": cfg.FIREWALL_EVE_PATH,
    })
