"""
Telemetry API — live collection status endpoints.

Endpoints:
  GET /telemetry/osquery/status  — OsqueryCollector health and state
  GET /telemetry/summary         — 24h telemetry rollup for Overview dashboard
"""
from __future__ import annotations

import asyncio
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


@router.get("/summary")
async def telemetry_summary(request: Request) -> JSONResponse:
    """Return 24h telemetry summary for the Overview dashboard."""
    stores = request.app.state.stores

    # --- DuckDB queries (async) ---
    try:
        type_rows = await stores.duckdb.fetch_all(
            """SELECT event_type, COUNT(*) AS cnt
               FROM normalized_events
               WHERE timestamp > datetime('now', '-1 day')
               GROUP BY event_type ORDER BY cnt DESC"""
        )
        event_type_counts = {r[0] or "unknown": int(r[1]) for r in type_rows}
        total_events = sum(event_type_counts.values())

        ioc_rows = await stores.duckdb.fetch_all(
            """SELECT COUNT(*) FROM normalized_events
               WHERE timestamp > datetime('now', '-1 day') AND ioc_matched = true"""
        )
        ioc_matches = int(ioc_rows[0][0]) if ioc_rows else 0
    except Exception as exc:
        log.warning("DuckDB telemetry query failed: %s", exc)
        event_type_counts = {}
        total_events = 0
        ioc_matches = 0

    # --- SQLite queries (sync via to_thread) ---
    def _sqlite_stats(conn):
        det_count = conn.execute(
            "SELECT COUNT(*) FROM detections WHERE created_at > datetime('now', '-1 day')"
        ).fetchone()[0]
        asset_count = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        top_rows = conn.execute(
            """SELECT rule_name, severity, COUNT(*) AS cnt
               FROM detections
               WHERE created_at > datetime('now', '-1 day')
               GROUP BY rule_name, severity
               ORDER BY cnt DESC LIMIT 5"""
        ).fetchall()
        top_rules = [
            {"rule_name": r[0], "severity": r[1], "count": r[2]} for r in top_rows
        ]
        return det_count, asset_count, top_rules

    try:
        total_detections, assets_count, top_rules = await asyncio.to_thread(
            _sqlite_stats, stores.sqlite._conn
        )
    except Exception as exc:
        log.warning("SQLite telemetry query failed: %s", exc)
        total_detections, assets_count, top_rules = 0, 0, []

    return JSONResponse({
        "event_type_counts": event_type_counts,
        "total_events": total_events,
        "total_detections": total_detections,
        "ioc_matches": ioc_matches,
        "assets_count": assets_count,
        "top_rules": top_rules,
    })
