"""
GET /api/metrics/kpis — returns cached SOC KPI snapshot.

APScheduler AsyncIOScheduler recomputes every 60 seconds.
Endpoint returns the last cached value immediately (< 1ms response time).
On the first call (cache cold) the KPIs are computed inline.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.core.deps import StoresDep
from backend.services.metrics_service import KpiSnapshot, MetricsService

log = logging.getLogger(__name__)

router = APIRouter(tags=["metrics"])

# Module-level cache — shared across requests in the single-worker process
_kpi_cache: Optional[KpiSnapshot] = None
_scheduler: Optional[AsyncIOScheduler] = None


async def _refresh_kpis(stores) -> None:
    """Background scheduler job: recompute KPIs and update module-level cache."""
    global _kpi_cache
    try:
        svc = MetricsService(stores)
        _kpi_cache = await svc.compute_all_kpis()
        log.debug("KPI cache refreshed: computed_at=%s", _kpi_cache.computed_at)
    except Exception as exc:
        log.warning("KPI refresh failed: %s", exc)


@router.get("/metrics/kpis")
async def get_kpis(request: Request, stores: StoresDep) -> JSONResponse:
    """
    Return the most recent SOC KPI snapshot.

    The APScheduler job refreshes the cache every 60 seconds.
    On the first call (cache cold) KPIs are computed inline before returning.
    """
    global _kpi_cache, _scheduler

    # Start scheduler on first call (attaches to the running asyncio event loop)
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
        _scheduler.add_job(
            _refresh_kpis,
            "interval",
            seconds=60,
            args=[stores],
            id="kpi_refresh",
            replace_existing=True,
        )
        _scheduler.start()
        log.info("KPI APScheduler started (60s interval)")

    # Cold cache: compute inline so the first response is never empty
    if _kpi_cache is None:
        await _refresh_kpis(stores)

    if _kpi_cache is None:
        # Fallback if compute still failed (e.g. stores not ready)
        return JSONResponse(
            status_code=503,
            content={"detail": "KPI data unavailable"},
        )

    return JSONResponse(content=_kpi_cache.model_dump(mode="json"))
