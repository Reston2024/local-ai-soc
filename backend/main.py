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
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

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
from backend.core.logging import get_logger, setup_logging
from backend.core.rate_limit import limiter

# ---------------------------------------------------------------------------
# Bootstrap logging ASAP (before any other import that might emit log records)
# ---------------------------------------------------------------------------
_tmp_settings = Settings()
setup_logging(log_level=_tmp_settings.LOG_LEVEL, log_dir="logs")
log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Startup modules (imported after logging is set up)
# ---------------------------------------------------------------------------
from backend.startup.stores import init_stores      # noqa: E402
from backend.startup.workers import init_workers    # noqa: E402
from backend.startup.collectors import init_collectors  # noqa: E402
from backend.startup.routers import mount_routers   # noqa: E402


# ---------------------------------------------------------------------------
# Lifespan context manager
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application startup and shutdown logic.

    Startup order:
    1. Load settings + validate single-worker constraint
    2. Create data directory
    3. init_stores  — DuckDB, Chroma, SQLite, OllamaClient, all service stores
    4. init_workers — APScheduler cron jobs + background loops
    5. init_collectors — osquery, firewall, Malcolm, WinEvent tasks
    6. Yield (application is now serving)

    Shutdown order:
    1. Cancel all collector tasks
    2. Stop APScheduler instances
    3. Cancel DuckDB write worker
    4. Close DuckDB / SQLite / OllamaClient
    """
    # DuckDB single-writer safety: fail fast if running with multiple workers.
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

    # Ensure data directory exists
    data_dir = Path(settings.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    log.info("Data directory ready", path=str(data_dir.resolve()))

    # --- Stores, services, and attached schedulers ---
    stores = await init_stores(app, settings)

    # --- Background worker tasks (APScheduler cron jobs + async loops) ---
    worker_tasks = await init_workers(app, stores, settings)

    # --- Data-collection tasks ---
    collector_tasks = await init_collectors(app, stores, settings)

    log.info("All stores and services initialised — ready to serve requests")

    # Yield control to the running application
    yield

    # ---------------------
    # Shutdown
    # ---------------------
    log.info("AI-SOC-Brain shutting down...")

    # Stop APScheduler instances
    _daily_sched = getattr(app.state, "_daily_snapshot_scheduler", None)
    if _daily_sched is not None:
        _daily_sched.shutdown(wait=False)

    _thehive_sched = getattr(app.state, "_thehive_scheduler", None)
    if _thehive_sched is not None:
        _thehive_sched.shutdown(wait=False)

    # Cancel collector tasks
    for task in collector_tasks:
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    # Cancel any worker tasks returned by init_workers
    for task in worker_tasks:
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    # Cancel DuckDB write worker (stored on app.state by init_stores)
    write_worker_task = getattr(app.state, "_duckdb_write_worker_task", None)
    if write_worker_task is not None and not write_worker_task.done():
        write_worker_task.cancel()
        try:
            await write_worker_task
        except asyncio.CancelledError:
            pass

    await stores.duckdb.close()
    stores.sqlite.close()
    await app.state.ollama.close()

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
    mount_routers(app)

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
