"""
Assets API — Phase 34 asset inventory endpoints.

Endpoints:
  GET  /api/assets              — list all observed assets
  GET  /api/assets/{ip}         — detail for a single asset (404 if not found)
  POST /api/assets/{ip}/tag     — manually override asset tag (internal | external)

All endpoints require authentication via verify_token dependency.
Store access goes through app.state.asset_store (AssetStore instance).
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.core.auth import verify_token

router = APIRouter()


@router.get("/assets", dependencies=[Depends(verify_token)])
async def list_assets(request: Request, limit: int = 200):
    """Return all assets ordered by last_seen DESC."""
    assets = await asyncio.to_thread(request.app.state.asset_store.list_assets, limit)
    return assets


@router.get("/assets/{ip:path}", dependencies=[Depends(verify_token)])
async def get_asset(ip: str, request: Request):
    """Return a single asset dict by IP address. Returns 404 if not found."""
    asset = await asyncio.to_thread(request.app.state.asset_store.get_asset, ip)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.post("/assets/{ip:path}/tag", dependencies=[Depends(verify_token)])
async def tag_asset(ip: str, request: Request):
    """Override the tag for an asset. tag must be 'internal' or 'external'."""
    body = await request.json()
    tag = body.get("tag", "").strip()
    if tag not in ("internal", "external"):
        raise HTTPException(status_code=422, detail="tag must be 'internal' or 'external'")
    await asyncio.to_thread(request.app.state.asset_store.set_tag, ip, tag)
    return {"status": "ok", "ip": ip, "tag": tag}
