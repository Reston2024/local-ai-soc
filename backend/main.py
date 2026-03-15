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
    scripts/start.sh
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.core.config import Settings
from backend.core.deps import Stores
from backend.core.logging import get_logger, setup_logging

# ---------------------------------------------------------------------------
# Bootstrap logging ASAP (before any other import that might emit log records)
# ---------------------------------------------------------------------------
_tmp_settings = Settings()
setup_logging(log_level=_tmp_settings.LOG_LEVEL, log_dir="logs")
log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Import stores + services (after logging is set up)
# ---------------------------------------------------------------------------
from backend.stores.chroma_store import ChromaStore
from backend.stores.duckdb_store import DuckDBStore
from backend.stores.sqlite_store import SQLiteStore
from backend.services.ollama_client import OllamaClient

# ---------------------------------------------------------------------------
# Import routers
# ---------------------------------------------------------------------------
from backend.api.health import router as health_router
from backend.api.ingest import router as ingest_router
from backend.api.query import router as query_router
from backend.api.detect import router as detect_router
from backend.api.graph import router as graph_router
from backend.api.events import router as events_router
from backend.api.export import router as export_router


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

    # 2. DuckDB store
    duckdb_store = DuckDBStore(data_dir=settings.DATA_DIR)
    await duckdb_store.initialise_schema()
    write_worker_task = duckdb_store.start_write_worker()
    log.info("DuckDB write worker started")

    # 3. Chroma store
    chroma_store = ChromaStore(data_dir=settings.DATA_DIR)
    await chroma_store.initialise_default_collections(embed_model=settings.OLLAMA_EMBED_MODEL)

    # 4. SQLite store
    sqlite_store = SQLiteStore(data_dir=settings.DATA_DIR)

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
    )

    # 7. Attach to app.state
    app.state.settings = settings
    app.state.stores = stores
    app.state.ollama = ollama

    log.info("All stores and services initialised — ready to serve requests")

    # Yield control to the running application
    yield

    # ---------------------
    # Shutdown
    # ---------------------
    log.info("AI-SOC-Brain shutting down...")

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
    settings = Settings()

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
            "http://localhost:8000",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8000",
            "https://localhost",
            "https://127.0.0.1",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # -----------------------------------------------------------------------
    # Routers
    # -----------------------------------------------------------------------
    app.include_router(health_router)
    app.include_router(events_router)
    app.include_router(ingest_router)
    app.include_router(query_router)
    app.include_router(detect_router)
    app.include_router(graph_router)
    app.include_router(export_router)

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
