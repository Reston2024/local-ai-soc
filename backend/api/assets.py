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
import json

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.core.auth import verify_token

router = APIRouter()


def _compute_alert_counts(sqlite_conn, duckdb_store) -> dict[str, int]:
    """
    Build a {src_ip: detection_count} map by cross-referencing SQLite detections
    (matched_event_ids JSON array) with DuckDB normalized_events (event_id → src_ip).

    Returns a dict mapping IP → number of detections that matched at least one
    event originating from that IP.
    """
    # 1. Fetch all detection matched_event_ids from SQLite
    rows = sqlite_conn.execute(
        "SELECT id, matched_event_ids FROM detections WHERE matched_event_ids IS NOT NULL"
    ).fetchall()

    detection_event_map: dict[str, list[str]] = {}
    all_event_ids: set[str] = set()
    for det_id, mei_json in rows:
        try:
            event_ids = json.loads(mei_json) if isinstance(mei_json, str) else (mei_json or [])
        except Exception:
            event_ids = []
        if event_ids:
            detection_event_map[det_id] = event_ids
            all_event_ids.update(event_ids)

    if not all_event_ids:
        return {}

    # 2. Query DuckDB for src_ip of those event IDs (batch via IN clause)
    #    Use get_read_conn() directly since we're already in a thread
    chunk_size = 500
    event_id_list = list(all_event_ids)
    event_ip_map: dict[str, str] = {}

    try:
        conn = duckdb_store.get_read_conn()
        try:
            for i in range(0, len(event_id_list), chunk_size):
                chunk = event_id_list[i : i + chunk_size]
                placeholders = ", ".join("?" * len(chunk))
                result = conn.execute(
                    f"SELECT event_id, src_ip FROM normalized_events "
                    f"WHERE event_id IN ({placeholders}) AND src_ip IS NOT NULL",
                    chunk,
                ).fetchall()
                for eid, sip in result:
                    event_ip_map[eid] = sip
        finally:
            conn.close()
    except Exception:
        pass  # DuckDB offline — return empty

    # 3. Aggregate: for each detection, count which IPs it hits
    ip_detection_count: dict[str, int] = {}
    for det_id, event_ids in detection_event_map.items():
        seen_ips: set[str] = set()
        for eid in event_ids:
            ip = event_ip_map.get(eid)
            if ip and ip not in seen_ips:
                seen_ips.add(ip)
                ip_detection_count[ip] = ip_detection_count.get(ip, 0) + 1

    return ip_detection_count


@router.get("/assets", dependencies=[Depends(verify_token)])
async def list_assets(request: Request, limit: int = 200):
    """Return all assets ordered by last_seen DESC with real alert_count and risk_score."""
    stores = request.app.state.stores
    asset_store = request.app.state.asset_store

    # Fetch base assets (alert_count/risk_score are 0 from SQLite-only query)
    assets = await asyncio.to_thread(asset_store.list_assets, limit)

    # Enrich with real detection counts from cross-DB join (runs in thread with assets fetch)
    try:
        alert_counts = await asyncio.to_thread(
            _compute_alert_counts,
            stores.sqlite._conn,
            stores.duckdb,
        )
        if alert_counts:
            for asset in assets:
                count = alert_counts.get(asset["ip"], 0)
                asset["alert_count"] = count
                asset["risk_score"] = min(100, count * 10)
    except Exception:
        pass  # Enrichment failure is non-critical — leave counts as 0

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
