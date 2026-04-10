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
    """Return feed health status for all 3 feeds."""
    status = await asyncio.to_thread(request.app.state.ioc_store.get_feed_status)
    return status
