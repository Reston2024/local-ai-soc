"""Threat Intelligence API — IOC hits and feed health endpoints."""
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from backend.core.auth import verify_token
from backend.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter()


@router.get("/ioc-hits", dependencies=[Depends(verify_token)])
async def get_ioc_hits(request: Request, limit: int = 200):
    """Return IOC hit list sorted by risk_score descending."""
    hits = await asyncio.to_thread(request.app.state.ioc_store.list_hits, limit)
    return hits


@router.get("/feeds", dependencies=[Depends(verify_token)])
async def get_feeds(request: Request):
    """Return feed health status for all feeds (feodo, cisa_kev, threatfox, misp)."""
    status = await asyncio.to_thread(request.app.state.ioc_store.get_feed_status)
    return status


@router.get("/misp-events", dependencies=[Depends(verify_token)])
async def get_misp_events(request: Request, limit: int = 50):
    """Return MISP-sourced IOCs with confidence scores and event context.
    Populates ThreatIntelView MISP Intel section."""
    iocs = await asyncio.to_thread(request.app.state.ioc_store.list_misp_iocs, limit)
    return iocs


@router.get("/feeds/misp-status", dependencies=[Depends(verify_token)])
async def get_misp_feed_status(request: Request):
    """Return MISP connection health — last sync timestamp and IOC count."""
    status = await asyncio.to_thread(request.app.state.ioc_store.get_feed_status)
    # Filter to just the MISP entry
    misp = next(
        (s for s in status if s["feed"] == "misp"),
        {"feed": "misp", "status": "never", "ioc_count": 0, "last_sync": None},
    )
    return misp


@router.post("/feeds/sync", dependencies=[Depends(verify_token)])
async def trigger_feed_sync(request: Request):
    """Manually trigger an immediate MISP sync.

    Finds the live MispFeedSync worker on app.state and calls _sync() directly.
    Returns the new feed status after the sync completes.
    """
    try:
        misp_worker = getattr(request.app.state, "_misp_feed_worker", None)
        if misp_worker is None:
            return JSONResponse(
                status_code=503,
                content={"ok": False, "detail": "MISP feed worker not running"},
            )
        log.info("Manual MISP sync triggered via /api/intel/feeds/sync")
        success = await misp_worker._sync()
        status = await asyncio.to_thread(request.app.state.ioc_store.get_feed_status)
        misp_status = next(
            (s for s in status if s["feed"] == "misp"),
            {"feed": "misp", "status": "unknown"},
        )
        return JSONResponse(content={
            "ok": success,
            "triggered_at": datetime.now(tz=timezone.utc).isoformat(),
            "misp": misp_status,
        })
    except Exception as exc:
        log.warning("Manual MISP sync failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "detail": str(exc)},
        )
