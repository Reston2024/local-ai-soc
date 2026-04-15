"""Threat Intelligence API — IOC hits and feed health endpoints."""
import asyncio
from fastapi import APIRouter, Depends, Request

from backend.core.auth import verify_token

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
