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
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
from backend.api.query import router as query_router  # noqa: E402
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
    from datetime import date
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
    chroma_store = ChromaStore(data_dir=settings.DATA_DIR)
    await chroma_store.initialise_default_collections(embed_model=settings.OLLAMA_EMBED_MODEL)

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
    )

    # 7. Attach to app.state
    app.state.settings = settings
    app.state.stores = stores
    app.state.ollama = ollama

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
    _daily_snapshot_scheduler.start()
    log.info("Daily KPI snapshot scheduler started")

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

    # Cancel osquery collector task if running
    if osquery_task is not None and not osquery_task.done():
        osquery_task.cancel()
        try:
            await osquery_task
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
        allow_headers=["*"],
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

    # -----------------------------------------------------------------------
    # Static files — serve the Svelte dashboard if built
    # -----------------------------------------------------------------------
    dashboard_dist = Path("dashboard") / "dist"
    if dashboard_dist.is_dir():
        app.mount(
            "/app",
            StaticFiles(directory=str(dashboard_dist), html=True),
            name="dashboard",
        )
        log.info("Dashboard static files mounted", path=str(dashboard_dist))
    else:
        log.info("Dashboard not built — skipping static file mount", path=str(dashboard_dist))

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
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": "Not found", "path": str(request.url.path)},
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
