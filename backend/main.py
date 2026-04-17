"""
AI-SOC-Brain FastAPI application entry point.

Architecture notes:
- Single uvicorn worker (CRITICAL: DuckDB single-writer pattern requires single process)
- All stores are initialised in the lifespan context manager and stored on app.state
- The DuckDB write worker runs as a background asyncio task
- CORS is restricted to localhost origins only

Run with:
    uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
or via the startup script:
    scripts/start.cmd
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import AsyncIterator, Optional

import duckdb

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.core.auth import verify_token
from backend.core.config import Settings
from backend.core.deps import Stores
from backend.core.logging import get_logger, setup_logging
from backend.core.rate_limit import limiter

# ---------------------------------------------------------------------------
# Bootstrap logging ASAP (before any other import that might emit log records)
# ---------------------------------------------------------------------------
_tmp_settings = Settings()
setup_logging(log_level=_tmp_settings.LOG_LEVEL, log_dir="logs")
log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Import stores + services (after logging is set up)
# ---------------------------------------------------------------------------
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # noqa: E402
from backend.api.detect import router as detect_router  # noqa: E402
from backend.api.events import router as events_router  # noqa: E402
from backend.api.export import router as export_router  # noqa: E402
from backend.api.graph import router as graph_router  # noqa: E402

# ---------------------------------------------------------------------------
# Import routers
# ---------------------------------------------------------------------------
from backend.api.health import router as health_router  # noqa: E402
from backend.api.ingest import router as ingest_router  # noqa: E402
from backend.api.perf import router as perf_router  # noqa: E402
from backend.api.query import router as query_router  # noqa: E402
from backend.services.attack.asset_store import AssetStore  # noqa: E402
from backend.services.attack.attack_store import AttackStore  # noqa: E402
from backend.services.intel.feed_sync import CisaKevWorker, FeodoWorker, MispWorker, ThreatFoxWorker  # noqa: E402
from backend.services.intel.ioc_store import IocStore  # noqa: E402
from backend.services.ollama_client import OllamaClient  # noqa: E402
from backend.services.metrics_service import MetricsService  # noqa: E402
from backend.stores.chroma_store import ChromaStore  # noqa: E402
from backend.stores.duckdb_store import DuckDBStore  # noqa: E402
from backend.stores.sqlite_store import SQLiteStore  # noqa: E402

# ---------------------------------------------------------------------------
# Daily KPI snapshot — APScheduler midnight job
# ---------------------------------------------------------------------------

_daily_snapshot_scheduler: Optional[AsyncIOScheduler] = None


async def _take_daily_kpi_snapshot(stores) -> None:
    """Compute and upsert today's KPI snapshot. Called by APScheduler at midnight."""
    try:
        svc = MetricsService(stores)
        snap = await svc.compute_all_kpis()
        today = date.today().isoformat()

        # investigation_count and detection_count are NOT on KpiSnapshot —
        # query SQLite directly (asyncio.to_thread because SQLiteStore is synchronous).
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
    """R-15: Export all events to Parquet using a dedicated read connection.

    Opens a separate read-only DuckDB connection (external_access enabled, read-only)
    to write the export. This is intentional — the backup job is a controlled,
    local-only write to a known path, distinct from the E5-02 exfiltration threat.
    """
    conn = duckdb.connect(db_path, read_only=True)
    try:
        conn.execute(f"COPY (SELECT * FROM events) TO '{backup_path}' (FORMAT PARQUET)")
    finally:
        conn.close()


async def _daily_parquet_backup(stores, data_dir: str) -> None:
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


async def _purge_old_events(stores, retention_days: int = 90) -> None:
    """R-13: Delete events older than retention_days from DuckDB.

    Runs daily at 00:10 via APScheduler. Default retention: 90 days.
    The DELETE is issued through the write queue to honour the single-writer pattern.
    """
    cutoff_sql = f"CURRENT_TIMESTAMP - INTERVAL '{retention_days} days'"
    try:
        deleted = await stores.duckdb.execute_write(
            f"DELETE FROM events WHERE timestamp < {cutoff_sql}",
            [],
        )
        log.info("Event retention purge complete", retention_days=retention_days)
    except Exception as exc:
        log.warning("Event retention purge failed: %s", exc)


# ---------------------------------------------------------------------------
# Lifespan context manager
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application startup and shutdown logic.

    Startup order:
    1. Load settings
    2. Create data directory
    3. Initialise DuckDB store + start write worker background task
    4. Initialise Chroma store + default collections
    5. Initialise SQLite store
    6. Initialise OllamaClient
    7. Store all handles on app.state
    8. Yield (application is now serving)

    Shutdown order:
    1. Cancel DuckDB write worker
    2. Close DuckDB connections
    3. Close SQLite connection
    4. Close OllamaClient httpx session
    """
    # DuckDB single-writer safety: fail fast if running with multiple workers.
    # DuckDB does not support concurrent writers from separate processes.
    import multiprocessing
    import os
    _worker_count = int(os.environ.get("WEB_CONCURRENCY", "1"))
    if _worker_count > 1:
        raise RuntimeError(
            f"DuckDB single-writer constraint violated: WEB_CONCURRENCY={_worker_count}. "
            "This application must run with a single uvicorn worker. "
            "Remove --workers or set WEB_CONCURRENCY=1."
        )

    settings = Settings()
    setup_logging(log_level=settings.LOG_LEVEL, log_dir="logs")
    log.info(
        "AI-SOC-Brain starting",
        host=settings.HOST,
        port=settings.PORT,
        data_dir=settings.DATA_DIR,
        ollama_host=settings.OLLAMA_HOST,
    )

    # 1. Ensure data directory exists
    data_dir = Path(settings.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    log.info("Data directory ready", path=str(data_dir.resolve()))

    # 2. DuckDB store — start write worker FIRST, then initialise schema
    # (initialise_schema uses execute_write which requires the worker to be running)
    duckdb_store = DuckDBStore(data_dir=settings.DATA_DIR)
    write_worker_task = duckdb_store.start_write_worker()
    log.info("DuckDB write worker started")
    await duckdb_store.initialise_schema()

    # 3. Chroma store
    chroma_store = ChromaStore(
        data_dir=settings.DATA_DIR,
        chroma_url=settings.CHROMA_URL,
        chroma_token=settings.CHROMA_TOKEN,
    )
    await chroma_store.initialise_default_collections(embed_model=settings.OLLAMA_EMBED_MODEL)

    # 3b. Phase 44: feedback_verdicts Chroma collection for k-NN similar incident retrieval
    try:
        await chroma_store.get_or_create_collection_async(
            "feedback_verdicts",
            metadata={"embed_model": settings.OLLAMA_EMBED_MODEL, "hnsw:space": "cosine"},
        )
        log.info("feedback_verdicts Chroma collection ready (Phase 44)")
    except Exception as exc:
        log.warning("feedback_verdicts Chroma collection init failed (non-fatal): %s", exc)

    # 4. SQLite store
    sqlite_store = SQLiteStore(data_dir=settings.DATA_DIR)

    # 4b. Bootstrap legacy admin operator if operators table is empty
    sqlite_store.bootstrap_admin_if_empty(auth_token=settings.AUTH_TOKEN)
    log.info("Operator bootstrap complete")

    # 4a. Seed built-in playbooks (idempotent — no-op if already seeded)
    try:
        from backend.api.playbooks import seed_builtin_playbooks
        await seed_builtin_playbooks(sqlite_store)
    except Exception as exc:  # pragma: no cover
        log.warning("Built-in playbook seeding failed — continuing: %s", exc)

    # 5. Stores container
    stores = Stores(
        duckdb=duckdb_store,
        chroma=chroma_store,
        sqlite=sqlite_store,
    )

    # 6. Ollama client
    ollama = OllamaClient(
        base_url=settings.OLLAMA_HOST,
        model=settings.OLLAMA_MODEL,
        embed_model=settings.OLLAMA_EMBED_MODEL,
        cybersec_model=settings.OLLAMA_CYBERSEC_MODEL,
        duckdb_store=duckdb_store,
        sqlite_store=sqlite_store,
    )

    # 6a. Model digest verification (E6-03) — runs after OllamaClient is constructed.
    #     Gracefully skips if Ollama is unreachable; raises only when ENFORCE_DIGEST=True.
    if settings.OLLAMA_MODEL_DIGEST or settings.OLLAMA_EMBEDDING_DIGEST:
        log.info("Running Ollama model digest verification (E6-03)")
    if settings.OLLAMA_MODEL_DIGEST or not settings.OLLAMA_MODEL_DIGEST:
        # Always run for the primary model so the digest is always logged.
        await ollama.verify_model_digest(
            model_name=settings.OLLAMA_MODEL,
            expected_digest_prefix=settings.OLLAMA_MODEL_DIGEST,
            enforce=settings.OLLAMA_ENFORCE_DIGEST,
        )
    if settings.OLLAMA_EMBEDDING_DIGEST:
        await ollama.verify_model_digest(
            model_name=settings.OLLAMA_EMBED_MODEL,
            expected_digest_prefix=settings.OLLAMA_EMBEDDING_DIGEST,
            enforce=settings.OLLAMA_ENFORCE_DIGEST,
        )

    # 7. Attach to app.state
    app.state.settings = settings
    app.state.stores = stores
    app.state.ollama = ollama

    # 7a. Phase 33: Threat Intelligence — IocStore + feed workers
    ioc_store = IocStore(sqlite_store._conn)
    feodo_worker = FeodoWorker(ioc_store, sqlite_store._conn, duckdb_store=duckdb_store)
    cisa_kev_worker = CisaKevWorker(ioc_store, sqlite_store._conn, duckdb_store=duckdb_store)
    threatfox_worker = ThreatFoxWorker(ioc_store, sqlite_store._conn, duckdb_store=duckdb_store)
    misp_worker = MispWorker(
        ioc_store,
        sqlite_store._conn,
        interval_sec=settings.MISP_SYNC_INTERVAL_SEC,
        duckdb_store=duckdb_store,
        misp_url=settings.MISP_URL,
        misp_key=settings.MISP_KEY,
        misp_ssl=settings.MISP_SSL_VERIFY,
        last_hours=settings.MISP_SYNC_LAST_HOURS,
    )

    # Register feed workers as asyncio background tasks (run immediately on event loop)
    asyncio.ensure_future(feodo_worker.run())
    asyncio.ensure_future(cisa_kev_worker.run())
    asyncio.ensure_future(threatfox_worker.run())
    if settings.MISP_ENABLED:
        asyncio.create_task(misp_worker.run(), name="misp_worker")

    # Store ioc_store on app.state for use by the intel API router
    app.state.ioc_store = ioc_store
    log.info("Phase 33 feed workers registered (Feodo, CISA KEV, ThreatFox, MISP=%s)", settings.MISP_ENABLED)

    # CRITICAL (P33-T06): Wire ioc_store into EventIngester so at-ingest IOC matching
    # is active in production. EventIngester is added in Plan 02 (ingestion/loader.py).
    # This reference is here (not in Plan 02) to consolidate all main.py edits in Plan 01.
    # When Plan 02 creates EventIngester with ioc_store param, this wiring is already here.
    app.state._ioc_store_for_ingester = ioc_store  # Accessed by ingest.py route handlers

    # 7b. Phase 34: Asset inventory + ATT&CK stores (share SQLite connection)
    asset_store = AssetStore(sqlite_store._conn)
    app.state.asset_store = asset_store
    log.info("AssetStore initialised (Phase 34)")

    attack_store = AttackStore(sqlite_store._conn)
    app.state.attack_store = attack_store
    log.info("AttackStore initialised (Phase 34)")

    # Launch STIX bootstrap as a background task (non-blocking, idempotent)
    asyncio.ensure_future(bootstrap_attack_data(attack_store))
    log.info("ATT&CK STIX bootstrap task scheduled (Phase 34)")

    # 7d. Phase 39: CAR Analytics store
    from backend.services.car.car_store import CARStore, seed_car_analytics
    car_store = CARStore(sqlite_store._conn)
    app.state.car_store = car_store
    log.info("CARStore initialised (Phase 39)")
    asyncio.ensure_future(seed_car_analytics(car_store))
    log.info("CAR analytics seed task scheduled (Phase 39)")

    # 7e. Phase 40: Atomics (Atomic Red Team) store
    from backend.services.atomics.atomics_store import AtomicsStore, seed_atomics
    atomics_store = AtomicsStore(sqlite_store._conn)
    app.state.atomics_store = atomics_store
    log.info("AtomicsStore initialised (Phase 40)")
    asyncio.ensure_future(seed_atomics(atomics_store))
    log.info("Atomics seed task scheduled (Phase 40)")

    # 7f. Phase 42: Anomaly scoring — River HalfSpaceTrees per-entity behavioral profiling
    try:
        from backend.services.anomaly.scorer import AnomalyScorer as _AnomalyScorer
        _anomaly_scorer = _AnomalyScorer(model_dir=settings.ANOMALY_MODEL_DIR)
        app.state.anomaly_scorer = _anomaly_scorer
        app.state._anomaly_scorer_for_ingester = _anomaly_scorer
        log.info("AnomalyScorer initialised (Phase 42)", model_dir=settings.ANOMALY_MODEL_DIR)
    except Exception as exc:
        log.warning("AnomalyScorer failed to initialise — anomaly scoring disabled: %s", exc)
        app.state.anomaly_scorer = None
        app.state._anomaly_scorer_for_ingester = None

    # 7h. Phase 44: FeedbackClassifier — River LogisticRegression for TP/FP online learning
    try:
        from backend.services.feedback.classifier import FeedbackClassifier as _FeedbackClassifier
        app.state.feedback_classifier = _FeedbackClassifier()
        app.state.feedback_classifier.load()
        log.info("FeedbackClassifier loaded (Phase 44)", n_samples=app.state.feedback_classifier.n_samples)
    except Exception as exc:
        log.warning("FeedbackClassifier init failed — feedback scoring disabled: %s", exc)
        app.state.feedback_classifier = None

    # 7g. Phase 43: Correlation engine (port scan, brute force, beaconing)
    try:
        from detections.correlation_engine import CorrelationEngine as _CorrelationEngine
        from pathlib import Path as _CEPath
        _correlation_engine = _CorrelationEngine(stores=stores)
        app.state.correlation_engine = _correlation_engine
        app.state._correlation_engine_for_ingester = _correlation_engine
        # Load chain definitions from YAML (stubbed until Plan 43-03 creates the file)
        _chains_path = _CEPath(__file__).parent.parent / "detections" / "correlation_chains.yml"
        if _chains_path.exists():
            _chain_count = _correlation_engine.load_chains(str(_chains_path))
            log.info("Correlation chains loaded (Phase 43)", count=_chain_count)
        log.info("CorrelationEngine initialised (Phase 43)")
    except Exception as exc:
        log.warning("CorrelationEngine failed to initialise — correlation detection disabled: %s", exc)
        app.state.correlation_engine = None
        app.state._correlation_engine_for_ingester = None

    # 7c. Phase 35: Auto-triage background worker (60s poll)
    try:
        from backend.api.triage import _auto_triage_loop
        asyncio.ensure_future(_auto_triage_loop(app))
        log.info("Auto-triage worker started (60s poll)")
    except Exception as exc:
        log.warning("Auto-triage worker failed to start: %s", exc)


    # 7i. Phase 51: OSINT investigation store
    try:
        from backend.services.osint_investigation_store import OsintInvestigationStore
        osint_store = OsintInvestigationStore(sqlite_store._conn)
        app.state.osint_store = osint_store
        log.info("osint_investigation_store ready")
    except Exception as exc:
        log.warning("osint_investigation_store init failed", error=str(exc))
        app.state.osint_store = None

    # 7j. Phase 52: TheHive case management
    _thehive_scheduler = None
    try:
        if settings.THEHIVE_ENABLED:
            from backend.services.thehive_client import TheHiveClient as _TheHiveClient
            from backend.services.thehive_sync import sync_thehive_closures, drain_pending_cases
            from datetime import timedelta as _timedelta
            from datetime import datetime as _datetime
            _thehive_client = _TheHiveClient(url=settings.THEHIVE_URL, api_key=settings.THEHIVE_API_KEY)
            app.state.thehive_client = _thehive_client
            # Dedicated APScheduler for TheHive sync jobs (300s interval)
            _thehive_scheduler = AsyncIOScheduler()
            _thehive_scheduler.add_job(
                lambda: sync_thehive_closures(_thehive_client, sqlite_store._conn),
                "interval",
                seconds=300,
                id="thehive_sync",
            )
            _thehive_scheduler.add_job(
                lambda: drain_pending_cases(_thehive_client, sqlite_store._conn),
                "interval",
                seconds=300,
                start_date=_datetime.now() + _timedelta(seconds=30),
                id="thehive_drain",
            )
            _thehive_scheduler.start()
            log.info("TheHive client + APScheduler sync jobs started (300s interval)")
        else:
            app.state.thehive_client = None
            log.info("TheHive disabled (THEHIVE_ENABLED=False)")
    except Exception as exc:
        app.state.thehive_client = None
        log.warning("TheHive setup failed (non-fatal): %s", exc)

    # 7k. Phase 53: Privacy monitoring — PrivacyBlocklistStore + background worker
    try:
        from backend.services.intel.privacy_blocklist import (
            PrivacyBlocklistStore as _PrivacyBlocklistStore,
            PrivacyWorker as _PrivacyWorker,
        )
        if settings.PRIVACY_ENABLED:
            app.state.privacy_store = _PrivacyBlocklistStore(sqlite_store._conn)
            _privacy_worker = _PrivacyWorker(
                app.state.privacy_store,
                interval_sec=settings.PRIVACY_BLOCKLIST_REFRESH_INTERVAL_SEC,
            )
            asyncio.create_task(_privacy_worker.run())
            # Start privacy scan loop here (after privacy_store is ready)
            from backend.api.privacy import _privacy_scan_loop as _priv_loop
            asyncio.create_task(_priv_loop(app, interval_sec=300))
            log.info("Privacy blocklist store + worker + scan loop started (Phase 53)")
        else:
            app.state.privacy_store = None
            log.info("Privacy monitoring disabled (PRIVACY_ENABLED=False)")
    except Exception as _exc:
        log.warning("Phase 53 privacy store init failed (non-fatal): %s", _exc)
        app.state.privacy_store = None

    # 8. Conditional osquery live telemetry collector
    osquery_task: asyncio.Task | None = None
    if settings.OSQUERY_ENABLED:
        try:
            from pathlib import Path as _Path

            from ingestion.osquery_collector import OsqueryCollector
            _collector = OsqueryCollector(
                log_path=_Path(settings.OSQUERY_LOG_PATH),
                duckdb_store=duckdb_store,
                interval_sec=settings.OSQUERY_POLL_INTERVAL,
            )
            osquery_task = asyncio.ensure_future(_collector.run())
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

    # 8b. Conditional firewall telemetry collector (IPFire syslog + Suricata EVE JSON)
    firewall_task: asyncio.Task | None = None
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
                sqlite_store=sqlite_store,
                interval_sec=settings.FIREWALL_POLL_INTERVAL,
            )
            firewall_task = asyncio.ensure_future(_fw_collector.run())
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

    # 8c. Conditional Malcolm NSM OpenSearch collector
    malcolm_task: asyncio.Task | None = None
    if settings.MALCOLM_ENABLED:
        try:
            from ingestion.jobs.malcolm_collector import MalcolmCollector as _MCCollector
            from ingestion.loader import IngestionLoader as _MCLoader
            _mc_loader = _MCLoader(stores=stores, ollama_client=ollama, asset_store=asset_store)
            _mc_collector = _MCCollector(
                loader=_mc_loader,
                sqlite_store=sqlite_store,
                interval_sec=settings.MALCOLM_POLL_INTERVAL,
                opensearch_url=settings.MALCOLM_OPENSEARCH_URL,
                opensearch_user=settings.MALCOLM_OPENSEARCH_USER,
                opensearch_pass=settings.MALCOLM_OPENSEARCH_PASS,
                verify_ssl=settings.MALCOLM_OPENSEARCH_VERIFY_SSL,
            )
            malcolm_task = asyncio.ensure_future(_mc_collector.run())
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

    # 8d. Windows Event Log live collector (Sysmon + Security + PowerShell + WMI)
    winevent_task: asyncio.Task | None = None
    if getattr(settings, "WINEVENT_ENABLED", True):
        try:
            from ingestion.jobs.winevent_collector import WinEventCollector as _WECollector
            from ingestion.loader import IngestionLoader as _WELoader
            _we_loader = _WELoader(stores=stores, ollama_client=ollama, asset_store=asset_store)
            _we_collector = _WECollector(
                loader=_we_loader,
                sqlite_store=sqlite_store,
                interval_sec=getattr(settings, "WINEVENT_POLL_INTERVAL", 30),
            )
            winevent_task = asyncio.ensure_future(_we_collector.start())
            app.state.winevent_collector = _we_collector
            log.info("WinEventCollector started (interval=%ds)", getattr(settings, "WINEVENT_POLL_INTERVAL", 30))
        except Exception as exc:
            log.warning("WinEventCollector not available — skipping: %s", exc)
            app.state.winevent_collector = None
    else:
        log.info("Windows Event Log collection disabled (WINEVENT_ENABLED=False)")
        app.state.winevent_collector = None

    # 8a. Daily KPI snapshot scheduler (midnight cron job)
    global _daily_snapshot_scheduler
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
    # Phase 33: Add daily IOC confidence decay job (5 min after midnight, staggered)
    _daily_snapshot_scheduler.add_job(
        ioc_store.decay_confidence,
        "cron",
        hour=0,
        minute=5,
        id="daily_ioc_decay",
        replace_existing=True,
    )
    # R-13: 90-day DuckDB event retention purge (10 min after midnight, staggered)
    _daily_snapshot_scheduler.add_job(
        _purge_old_events,
        "cron",
        hour=0,
        minute=10,
        args=[stores],
        id="daily_event_retention",
        replace_existing=True,
    )
    # R-15: Daily Parquet export backup (15 min after midnight, staggered)
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

    log.info("All stores and services initialised — ready to serve requests")

    # Yield control to the running application
    yield

    # ---------------------
    # Shutdown
    # ---------------------
    log.info("AI-SOC-Brain shutting down...")

    # Stop daily KPI snapshot scheduler
    if _daily_snapshot_scheduler is not None:
        _daily_snapshot_scheduler.shutdown(wait=False)

    # Stop TheHive APScheduler if running (Phase 52)
    if _thehive_scheduler is not None:
        _thehive_scheduler.shutdown(wait=False)

    # Cancel osquery collector task if running
    if osquery_task is not None and not osquery_task.done():
        osquery_task.cancel()
        try:
            await osquery_task
        except asyncio.CancelledError:
            pass

    # Cancel firewall collector task if running
    if firewall_task is not None and not firewall_task.done():
        firewall_task.cancel()
        try:
            await firewall_task
        except asyncio.CancelledError:
            pass

    # Cancel malcolm collector task if running
    if malcolm_task is not None and not malcolm_task.done():
        malcolm_task.cancel()
        try:
            await malcolm_task
        except asyncio.CancelledError:
            pass

    # Cancel winevent collector task if running
    if winevent_task is not None and not winevent_task.done():
        winevent_task.cancel()
        try:
            await winevent_task
        except asyncio.CancelledError:
            pass

    # Cancel DuckDB write worker
    if not write_worker_task.done():
        write_worker_task.cancel()
        try:
            await write_worker_task
        except asyncio.CancelledError:
            pass

    await duckdb_store.close()
    sqlite_store.close()
    await ollama.close()

    log.info("AI-SOC-Brain shutdown complete")


# ---------------------------------------------------------------------------
# Phase 34: ATT&CK STIX bootstrap
# ---------------------------------------------------------------------------

_STIX_URL = (
    "https://raw.githubusercontent.com/mitre-attack/attack-stix-data"
    "/master/enterprise-attack/enterprise-attack.json"
)


async def bootstrap_attack_data(attack_store: "AttackStore") -> None:
    """
    Download and parse MITRE ATT&CK STIX bundle at startup.

    Skips download if techniques are already seeded (idempotent).
    Failures are non-fatal — logged as warnings only.
    """
    count = await asyncio.to_thread(attack_store.technique_count)
    if count > 0:
        log.info(
            "ATT&CK data already seeded (%d techniques) — skipping download", count
        )
        return
    try:
        import httpx

        async with httpx.AsyncClient() as client:
            log.info("Downloading ATT&CK STIX bundle from GitHub...")
            resp = await client.get(_STIX_URL, timeout=60.0)
            resp.raise_for_status()
            bundle = resp.json()
        await asyncio.to_thread(attack_store.bootstrap_from_objects, bundle["objects"])
        count = await asyncio.to_thread(attack_store.technique_count)
        log.info("ATT&CK bootstrap complete: %d techniques loaded", count)
    except Exception as exc:
        log.warning("ATT&CK STIX bootstrap failed (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """
    Construct and configure the FastAPI application.

    Separated from module-level instantiation so it can be called in tests
    with different configurations.
    """
    app = FastAPI(
        title="AI-SOC-Brain",
        description=(
            "Local Windows desktop AI cybersecurity investigation platform. "
            "Provides event ingestion, semantic search, detection correlation, "
            "graph traversal, and analyst Q&A via local LLM."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # -----------------------------------------------------------------------
    # CORS — restrict to localhost origins only (OWASP ASVS 4.2.2)
    # -----------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:8000",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://127.0.0.1:8000",
            "https://localhost",
            "https://127.0.0.1",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-TOTP-Code",
            "X-Request-ID",
            "Accept",
            "Origin",
        ],
    )

    # -----------------------------------------------------------------------
    # Rate limiting — disabled when TESTING=1 (SlowAPI via slowapi==0.1.9)
    # -----------------------------------------------------------------------
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # -----------------------------------------------------------------------
    # Routers
    # -----------------------------------------------------------------------
    app.include_router(health_router)                          # /health — unauthenticated
    app.include_router(events_router,  prefix="/api", dependencies=[Depends(verify_token)])   # /api/events
    app.include_router(ingest_router,  prefix="/api", dependencies=[Depends(verify_token)])   # /api/ingest
    app.include_router(query_router,   prefix="/api", dependencies=[Depends(verify_token)])   # /api/query
    app.include_router(detect_router,  prefix="/api", dependencies=[Depends(verify_token)])   # /api/detect
    app.include_router(graph_router,   prefix="/api", dependencies=[Depends(verify_token)])   # /api/graph
    app.include_router(export_router,  prefix="/api", dependencies=[Depends(verify_token)])   # /api/export
    app.include_router(perf_router,    prefix="/api", dependencies=[Depends(verify_token)])   # /api/metrics/perf

    # -----------------------------------------------------------------------
    # Deferred routers (graceful degradation if modules absent)
    # -----------------------------------------------------------------------
    try:
        from backend.causality.causality_routes import causality_router
        app.include_router(causality_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Causality router mounted at /api/causality")
    except ImportError as exc:
        log.warning("Causality module not available — skipping router mount: %s", exc)

    try:
        from backend.investigation.investigation_routes import investigation_router
        app.include_router(investigation_router, dependencies=[Depends(verify_token)])
        log.info("Investigation router mounted at /api")
    except ImportError as exc:
        log.warning("Investigation module not available — skipping router mount: %s", exc)

    try:
        from backend.api.correlate import router as correlate_router
        app.include_router(correlate_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Correlate router mounted at /api/correlate")
    except ImportError as exc:
        log.warning("Correlate router not available: %s", exc)

    try:
        from backend.api.investigate import router as investigate_router
        app.include_router(investigate_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Investigate router mounted at /api/investigate")
    except ImportError as exc:
        log.warning("Investigate router not available: %s", exc)

    try:
        from backend.api.telemetry import router as telemetry_router
        app.include_router(telemetry_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Telemetry router mounted at /api/telemetry")
    except ImportError as exc:
        log.warning("Telemetry module not available — skipping router mount: %s", exc)

    try:
        from backend.api.score import router as score_router
        app.include_router(score_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("score router mounted at /api/score")
    except ImportError as exc:
        log.warning("score router not available: %s", exc)

    try:
        from backend.api.top_threats import router as top_threats_router
        app.include_router(top_threats_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("top-threats router mounted at /api/top-threats")
    except ImportError as exc:
        log.warning("top-threats router not available: %s", exc)

    try:
        from backend.api.explain import router as explain_router
        app.include_router(explain_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("explain router mounted at /api/explain")
    except ImportError as exc:
        log.warning("explain router not available: %s", exc)

    try:
        from backend.api.investigations import router as investigations_router
        app.include_router(investigations_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("investigations router mounted at /api/investigations")
    except ImportError as exc:
        log.warning("investigations router not available: %s", exc)

    try:
        from backend.api.metrics import router as metrics_router
        app.include_router(metrics_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("metrics router mounted at /api/metrics")
    except ImportError as exc:
        log.warning("metrics router not available: %s", exc)

    try:
        from backend.api.timeline import router as timeline_router
        app.include_router(timeline_router, dependencies=[Depends(verify_token)])
        log.info("timeline router mounted at /api/investigations/{id}/timeline")
    except ImportError as exc:
        log.warning("timeline router not available: %s", exc)

    try:
        from backend.api.chat import router as chat_router
        app.include_router(chat_router, dependencies=[Depends(verify_token)])
        log.info("chat router mounted at /api/investigations/{id}/chat")
    except ImportError as exc:
        log.warning("chat router not available: %s", exc)

    try:
        from backend.api.playbooks import router as playbooks_router
        from backend.api.playbooks import runs_router as playbook_runs_router
        app.include_router(playbooks_router, dependencies=[Depends(verify_token)])
        app.include_router(playbook_runs_router, dependencies=[Depends(verify_token)])
        log.info("playbooks router mounted at /api/playbooks and /api/playbook-runs")
    except ImportError as exc:
        log.warning("playbooks router not available: %s", exc)

    try:
        from backend.api.reports import router as reports_router
        app.include_router(reports_router, dependencies=[Depends(verify_token)])
        log.info("reports router mounted at /api/reports")
    except ImportError as exc:
        log.warning("reports router not available: %s", exc)

    try:
        from backend.api.report_templates import router as report_templates_router
        app.include_router(report_templates_router, dependencies=[Depends(verify_token)])
        log.info("report_templates router mounted at /api/reports (templates)")
    except ImportError as exc:
        log.warning("report_templates router not available: %s", exc)

    try:
        from backend.api.analytics import router as analytics_router
        app.include_router(analytics_router, dependencies=[Depends(verify_token)])
        log.info("analytics router mounted at /api/analytics")
    except ImportError as exc:
        log.warning("analytics router not available: %s", exc)

    try:
        from backend.api.operators import router as operators_router
        app.include_router(operators_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("operators router mounted at /api/operators")
    except ImportError as exc:
        log.warning("operators router not available: %s", exc)

    try:
        from backend.api.settings import router as settings_router  # noqa: E402
        app.include_router(settings_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("settings router mounted at /api/settings")
    except ImportError as exc:
        log.warning("settings router not available: %s", exc)

    try:
        from backend.api.provenance import router as provenance_router
        app.include_router(provenance_router, dependencies=[Depends(verify_token)])
        log.info("provenance router mounted at /api/provenance")
    except ImportError as exc:
        log.warning("provenance router not available: %s", exc)

    try:
        from backend.api.firewall import router as firewall_router
        app.include_router(firewall_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Firewall router mounted at /api/firewall")
    except ImportError as exc:
        log.warning("Firewall router not available: %s", exc)

    try:
        from backend.api.recommendations import router as recommendations_router  # noqa: E402
        app.include_router(recommendations_router, dependencies=[Depends(verify_token)])  # /api/recommendations
        log.info("Recommendations router mounted at /api/recommendations")
    except ImportError as exc:
        log.warning("Recommendations router not available: %s", exc)

    try:
        from backend.api.receipts import router as receipts_router  # noqa: E402
        app.include_router(receipts_router, dependencies=[Depends(verify_token)])  # /api/receipts
        log.info("Receipts router mounted at /api/receipts")
    except ImportError as exc:
        log.warning("Receipts router not available: %s", exc)

    try:
        from backend.api.notifications import router as notifications_router  # noqa: E402
        app.include_router(notifications_router, dependencies=[Depends(verify_token)])  # /api/notifications
        log.info("Notifications router mounted at /api/notifications")
    except ImportError as exc:
        log.warning("Notifications router not available: %s", exc)

    try:
        from backend.api.hunting import router as hunting_router
        app.include_router(hunting_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Hunting router mounted at /api/hunts")
    except Exception as exc:
        log.warning("Hunting router not available: %s", exc)

    try:
        from backend.api.osint_api import router as osint_router
        app.include_router(osint_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("OSINT router mounted at /api/osint")
    except Exception as exc:
        log.warning("OSINT router not available: %s", exc)

    try:
        from backend.api import intel as intel_api
        app.include_router(intel_api.router, prefix="/api/intel", tags=["intel"])
        log.info("Intel router mounted at /api/intel")
    except Exception as exc:
        log.warning("Intel router not available: %s", exc)

    try:
        from backend.api.assets import router as assets_router
        app.include_router(assets_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Assets router registered at /api/assets")
    except Exception as exc:
        log.warning("Assets router failed to load: %s", exc)

    try:
        from backend.api.attack import router as attack_router
        app.include_router(attack_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Attack router registered at /api/attack")
    except Exception as exc:
        log.warning("Attack router failed to load: %s", exc)

    try:
        from backend.api.triage import router as triage_router
        app.include_router(triage_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Triage router mounted at /api/triage")
    except ImportError as exc:
        log.warning("Triage router not available: %s", exc)

    try:
        from backend.api.atomics import router as atomics_router
        app.include_router(atomics_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Atomics router mounted at /api/atomics")
    except Exception as exc:
        log.warning("Atomics router not available: %s", exc)

    try:
        from backend.api.map import router as map_router
        app.include_router(map_router, prefix="/api/map", tags=["map"])
        log.info("Map router mounted at /api/map")
    except Exception as exc:
        log.warning("Map router not available: %s", exc)

    try:
        from backend.api.anomaly import router as anomaly_router
        app.include_router(anomaly_router)
        log.info("Anomaly router mounted at /api/anomaly")
    except Exception as exc:
        log.warning("Anomaly router not available: %s", exc)

    try:
        from backend.api.feedback import feedback_router
        app.include_router(feedback_router, prefix="/api/feedback", tags=["feedback"])
        log.info("Feedback router mounted at /api/feedback (Phase 44)")
    except Exception as exc:
        log.warning("Feedback router not available: %s", exc)

    try:
        from backend.api.coverage import router as coverage_router
        app.include_router(coverage_router, dependencies=[Depends(verify_token)])
        log.info("Coverage router mounted at /api/coverage (Phase 40)")
    except Exception as exc:
        log.warning("Coverage router not available: %s", exc)

    try:
        from backend.api.privacy import privacy_router as _privacy_router
        app.include_router(_privacy_router)
        log.info("Privacy router mounted at /api/privacy (Phase 53)")
    except Exception as exc:
        log.warning("Phase 53 privacy router failed to load: %s", exc)

    # -----------------------------------------------------------------------
    # Static files — serve the Svelte dashboard if built
    # -----------------------------------------------------------------------
    dashboard_dist = Path("dashboard") / "dist"
    if dashboard_dist.is_dir():
        # Mount under /app for backward compat (Caddy /app/* still works)
        app.mount(
            "/app",
            StaticFiles(directory=str(dashboard_dist), html=True),
            name="dashboard",
        )
        log.info("Dashboard static files mounted", path=str(dashboard_dist))

        # Store index path for SPA 404 handler below
        _spa_index = dashboard_dist / "index.html"

    else:
        log.info("Dashboard not built — skipping static file mount", path=str(dashboard_dist))
        _spa_index = None

    # -----------------------------------------------------------------------
    # Exception handlers
    # -----------------------------------------------------------------------

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        log.warning(
            "Request validation error",
            path=str(request.url),
            errors=exc.errors(),
        )
        return JSONResponse(
            status_code=422,
            content={
                "detail": exc.errors(),
                "message": "Request validation failed",
            },
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> FileResponse | JSONResponse:
        # Serve the SPA index.html for any non-API, non-health path so that
        # client-side routes like /detections, /overview, /events work on direct navigation.
        path = request.url.path
        if (
            _spa_index is not None
            and not path.startswith("/api")
            and not path.startswith("/health")
            and not path.startswith("/app")
        ):
            return FileResponse(str(_spa_index))
        return JSONResponse(
            status_code=404,
            content={"detail": "Not found", "path": path},
        )

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        log.error(
            "Unhandled internal error",
            path=str(request.url),
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    # Root redirect to docs
    @app.get("/", include_in_schema=False)
    async def root() -> JSONResponse:
        return JSONResponse(
            content={
                "name": "AI-SOC-Brain",
                "version": "0.1.0",
                "docs": "/docs",
                "health": "/health",
            }
        )

    return app


# ---------------------------------------------------------------------------
# Module-level app instance (used by uvicorn)
# ---------------------------------------------------------------------------
app = create_app()


# ---------------------------------------------------------------------------
# Direct execution entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    settings = Settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        log_level=settings.LOG_LEVEL.lower(),
        # CRITICAL: single worker required for DuckDB single-writer pattern
        workers=1,
    )
