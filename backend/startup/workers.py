"""
backend.startup.workers — Background async worker tasks.

Called once during FastAPI lifespan startup, after stores are initialised.
Returns the list of asyncio.Task objects created so the lifespan can cancel
them cleanly on shutdown.

Workers included:
  - Auto-triage loop (Phase 35, 60s poll)
  - Daily KPI snapshot scheduler (APScheduler cron — midnight)
  - IOC confidence decay (APScheduler cron — 00:05)
  - Event retention purge (APScheduler cron R-13 — 00:10)
  - Daily Parquet backup (APScheduler cron R-15 — 00:15)
"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.core.config import Settings, settings
from backend.core.deps import Stores
from backend.core.logging import get_logger
from backend.services.metrics_service import MetricsService

if TYPE_CHECKING:
    from fastapi import FastAPI

log = get_logger(__name__)

# Module-level reference so shutdown can access the scheduler
_daily_snapshot_scheduler: AsyncIOScheduler | None = None


# ---------------------------------------------------------------------------
# KPI / backup helpers (unchanged from original main.py)
# ---------------------------------------------------------------------------


async def _take_daily_kpi_snapshot(stores: Stores) -> None:
    """Compute and upsert today's KPI snapshot. Called by APScheduler at midnight."""
    try:
        svc = MetricsService(stores)
        snap = await svc.compute_all_kpis()
        today = date.today().isoformat()

        inv_rows = await asyncio.to_thread(stores.sqlite.list_investigations)
        det_rows = await asyncio.to_thread(stores.sqlite.list_detections)
        inv_count = len(inv_rows) if inv_rows else 0
        det_count = len(det_rows) if det_rows else 0

        await stores.duckdb.upsert_daily_kpi_snapshot(
            snapshot_date=today,
            mttd_minutes=snap.mttd.value,
            mttr_minutes=snap.mttr.value,
            mttc_minutes=snap.mttc.value,
            alert_volume=int(snap.alert_volume_24h.value),
            false_positive_count=int(
                snap.false_positive_rate.value * max(snap.alert_volume_24h.value, 1)
            ),
            investigation_count=inv_count,
            detection_count=det_count,
        )
        log.info("Daily KPI snapshot upserted", date=today)
    except Exception as exc:
        log.warning("Daily KPI snapshot failed: %s", exc)


def _export_events_parquet_sync(db_path: str, backup_path: str) -> None:
    """R-15: Export all events to Parquet using a dedicated read connection."""
    conn = duckdb.connect(db_path, read_only=True)
    try:
        conn.execute(f"COPY (SELECT * FROM events) TO '{backup_path}' (FORMAT PARQUET)")
    finally:
        conn.close()


async def _daily_parquet_backup(stores: Stores, data_dir: str) -> None:
    """R-15: Write a daily Parquet snapshot of the events table to data/backups/."""
    backup_dir = Path(data_dir) / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    backup_path = str(backup_dir / f"events_{today}.parquet")
    db_path = stores.duckdb._db_path
    try:
        await asyncio.to_thread(_export_events_parquet_sync, db_path, backup_path)
        log.info("Daily Parquet backup complete", path=backup_path)
    except Exception as exc:
        log.warning("Daily Parquet backup failed: %s", exc)


async def _purge_old_events(
    stores: Stores, retention_days: int | None = None
) -> None:
    """R-13: Delete events older than retention_days from DuckDB.

    After a successful purge, runs VACUUM to reclaim space when
    settings.VACUUM_ENABLED is True. Vacuum is skipped on purge failure
    so we do not compound errors.
    """
    if retention_days is None:
        retention_days = settings.RETENTION_DAYS
    cutoff_sql = f"CURRENT_TIMESTAMP - INTERVAL '{retention_days} days'"
    try:
        await stores.duckdb.execute_write(
            f"DELETE FROM events WHERE timestamp < {cutoff_sql}",
            [],
        )
        log.info("Event retention purge complete", retention_days=retention_days)
    except Exception as exc:
        log.warning("Event retention purge failed: %s", exc)
        return

    if settings.VACUUM_ENABLED:
        try:
            await stores.duckdb.vacuum()
            log.info("DuckDB VACUUM complete", retention_days=retention_days)
        except Exception as exc:
            log.warning("DuckDB VACUUM failed: %s", exc)
    else:
        log.info("DuckDB VACUUM skipped (VACUUM_ENABLED=False)")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def init_workers(
    app: "FastAPI",
    stores: Stores,
    settings: Settings,
) -> list[asyncio.Task]:
    """Register all background worker tasks and schedulers.

    Returns a list of asyncio.Task objects for the caller to cancel on shutdown.
    Note: APScheduler instances are stored on app.state and must be shut down
    separately by the lifespan (they are not asyncio Tasks).
    """
    global _daily_snapshot_scheduler
    tasks: list[asyncio.Task] = []

    # ------------------------------------------------------------------
    # Auto-triage background worker (Phase 35 — 60s poll)
    # ------------------------------------------------------------------
    try:
        from backend.api.triage import _auto_triage_loop
        asyncio.ensure_future(_auto_triage_loop(app))
        log.info("Auto-triage worker started (60s poll)")
    except Exception as exc:
        log.warning("Auto-triage worker failed to start: %s", exc)

    # ------------------------------------------------------------------
    # Daily KPI snapshot + maintenance jobs (APScheduler cron)
    # ------------------------------------------------------------------
    ioc_store = app.state.ioc_store

    _daily_snapshot_scheduler = AsyncIOScheduler()
    _daily_snapshot_scheduler.add_job(
        _take_daily_kpi_snapshot,
        "cron",
        hour=0,
        minute=0,
        args=[stores],
        id="daily_kpi_snapshot",
        replace_existing=True,
    )
    # Phase 33: IOC confidence decay (00:05)
    _daily_snapshot_scheduler.add_job(
        ioc_store.decay_confidence,
        "cron",
        hour=0,
        minute=5,
        id="daily_ioc_decay",
        replace_existing=True,
    )
    # R-13: Configurable DuckDB event retention purge (00:10)
    _daily_snapshot_scheduler.add_job(
        _purge_old_events,
        "cron",
        hour=0,
        minute=10,
        args=[stores, settings.RETENTION_DAYS],
        id="daily_event_retention",
        replace_existing=True,
    )
    # R-15: Daily Parquet backup (00:15)
    _daily_snapshot_scheduler.add_job(
        _daily_parquet_backup,
        "cron",
        hour=0,
        minute=15,
        args=[stores, settings.DATA_DIR],
        id="daily_parquet_backup",
        replace_existing=True,
    )
    _daily_snapshot_scheduler.start()
    log.info(
        "Scheduler started: KPI@00:00, IOC decay@00:05, retention purge@00:10, Parquet backup@00:15"
    )

    # Store on app.state so lifespan shutdown can stop it
    app.state._daily_snapshot_scheduler = _daily_snapshot_scheduler

    return tasks
