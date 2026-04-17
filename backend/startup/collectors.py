"""
backend.startup.collectors — Data-collection task startup.

Called once during FastAPI lifespan startup, after stores are initialised.
Returns the list of asyncio.Task objects created so the lifespan can cancel
them cleanly on shutdown.

Collectors included:
  - OsqueryCollector  (OSQUERY_ENABLED)
  - FirewallCollector (FIREWALL_ENABLED)
  - MalcolmCollector  (MALCOLM_ENABLED)
  - WinEventCollector (WINEVENT_ENABLED, default True)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from backend.core.config import Settings
from backend.core.deps import Stores
from backend.core.logging import get_logger

if TYPE_CHECKING:
    from fastapi import FastAPI

log = get_logger(__name__)


async def init_collectors(
    app: "FastAPI",
    stores: Stores,
    settings: Settings,
) -> list[asyncio.Task]:
    """Start all enabled data-collection tasks.

    Returns a list of asyncio.Task objects for the caller to cancel on shutdown.
    """
    tasks: list[asyncio.Task] = []

    ollama = app.state.ollama
    asset_store = app.state.asset_store

    # The three IngestionLoader instances below are constructed lazily inside
    # each conditional block so they only import when the collector is enabled.

    # ------------------------------------------------------------------
    # Osquery live telemetry collector
    # ------------------------------------------------------------------
    if settings.OSQUERY_ENABLED:
        try:
            from pathlib import Path as _Path
            from ingestion.osquery_collector import OsqueryCollector

            _collector = OsqueryCollector(
                log_path=_Path(settings.OSQUERY_LOG_PATH),
                duckdb_store=stores.duckdb,
                interval_sec=settings.OSQUERY_POLL_INTERVAL,
            )
            osquery_task: asyncio.Task = asyncio.ensure_future(_collector.run())
            tasks.append(osquery_task)
            app.state.osquery_collector = _collector
            log.info(
                "OsqueryCollector started",
                log_path=settings.OSQUERY_LOG_PATH,
                interval_sec=settings.OSQUERY_POLL_INTERVAL,
            )
        except ImportError as exc:
            log.warning("OsqueryCollector not available — skipping: %s", exc)
    else:
        log.info("osquery collection disabled (OSQUERY_ENABLED=False)")
        app.state.osquery_collector = None

    # ------------------------------------------------------------------
    # Firewall telemetry collector (IPFire syslog + Suricata EVE JSON)
    # ------------------------------------------------------------------
    if settings.FIREWALL_ENABLED:
        try:
            from pathlib import Path as _FWPath
            from ingestion.jobs.firewall_collector import FirewallCollector as _FWCollector
            from ingestion.loader import IngestionLoader as _FWLoader

            _fw_loader = _FWLoader(stores=stores, ollama_client=ollama)
            _fw_collector = _FWCollector(
                syslog_path=_FWPath(settings.FIREWALL_SYSLOG_PATH),
                eve_path=_FWPath(settings.FIREWALL_EVE_PATH),
                loader=_fw_loader,
                sqlite_store=stores.sqlite,
                interval_sec=settings.FIREWALL_POLL_INTERVAL,
            )
            firewall_task: asyncio.Task = asyncio.ensure_future(_fw_collector.run())
            tasks.append(firewall_task)
            app.state.firewall_collector = _fw_collector
            log.info(
                "FirewallCollector started",
                syslog_path=settings.FIREWALL_SYSLOG_PATH,
                eve_path=settings.FIREWALL_EVE_PATH,
            )
        except ImportError as exc:
            log.warning("FirewallCollector not available — skipping: %s", exc)
            app.state.firewall_collector = None
    else:
        log.info("Firewall collection disabled (FIREWALL_ENABLED=False)")
        app.state.firewall_collector = None

    # ------------------------------------------------------------------
    # Malcolm NSM OpenSearch collector
    # ------------------------------------------------------------------
    if settings.MALCOLM_ENABLED:
        try:
            from ingestion.jobs.malcolm_collector import MalcolmCollector as _MCCollector
            from ingestion.loader import IngestionLoader as _MCLoader

            _mc_loader = _MCLoader(stores=stores, ollama_client=ollama, asset_store=asset_store)
            _mc_collector = _MCCollector(
                loader=_mc_loader,
                sqlite_store=stores.sqlite,
                interval_sec=settings.MALCOLM_POLL_INTERVAL,
                opensearch_url=settings.MALCOLM_OPENSEARCH_URL,
                opensearch_user=settings.MALCOLM_OPENSEARCH_USER,
                opensearch_pass=settings.MALCOLM_OPENSEARCH_PASS,
                verify_ssl=settings.MALCOLM_OPENSEARCH_VERIFY_SSL,
            )
            malcolm_task: asyncio.Task = asyncio.ensure_future(_mc_collector.run())
            tasks.append(malcolm_task)
            app.state.malcolm_collector = _mc_collector
            log.info(
                "MalcolmCollector started",
                opensearch_url=settings.MALCOLM_OPENSEARCH_URL,
                interval_sec=settings.MALCOLM_POLL_INTERVAL,
            )
        except ImportError as exc:
            log.warning("MalcolmCollector not available — skipping: %s", exc)
            app.state.malcolm_collector = None
    else:
        log.info("Malcolm collection disabled (MALCOLM_ENABLED=False)")
        app.state.malcolm_collector = None

    # ------------------------------------------------------------------
    # Windows Event Log live collector (Sysmon + Security + PowerShell + WMI)
    # ------------------------------------------------------------------
    if getattr(settings, "WINEVENT_ENABLED", True):
        try:
            from ingestion.jobs.winevent_collector import WinEventCollector as _WECollector
            from ingestion.loader import IngestionLoader as _WELoader

            _we_loader = _WELoader(stores=stores, ollama_client=ollama, asset_store=asset_store)
            _we_collector = _WECollector(
                loader=_we_loader,
                sqlite_store=stores.sqlite,
                interval_sec=getattr(settings, "WINEVENT_POLL_INTERVAL", 30),
            )
            winevent_task: asyncio.Task = asyncio.ensure_future(_we_collector.start())
            tasks.append(winevent_task)
            app.state.winevent_collector = _we_collector
            log.info(
                "WinEventCollector started (interval=%ds)",
                getattr(settings, "WINEVENT_POLL_INTERVAL", 30),
            )
        except Exception as exc:
            log.warning("WinEventCollector not available — skipping: %s", exc)
            app.state.winevent_collector = None
    else:
        log.info("Windows Event Log collection disabled (WINEVENT_ENABLED=False)")
        app.state.winevent_collector = None

    return tasks
