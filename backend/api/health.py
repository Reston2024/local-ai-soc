"""
Health check endpoint.

GET /health — returns component status for Ollama, DuckDB, Chroma, SQLite.

Response schema:
{
  "status": "healthy" | "degraded" | "unhealthy",
  "components": {
    "ollama":  {"status": "ok"|"error", "detail": "..."},
    "duckdb":  {"status": "ok"|"error", "detail": "..."},
    "chroma":  {"status": "ok"|"error", "detail": "..."},
    "sqlite":  {"status": "ok"|"error", "detail": "..."}
  },
  "timestamp": "<ISO-8601>"
}
"""

import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter(tags=["health"])


async def _check_ollama(request: Request) -> dict[str, Any]:
    """Verify Ollama is reachable by calling GET /api/tags."""
    try:
        ollama = request.app.state.ollama
        ok = await ollama.health_check()
        if ok:
            return {"status": "ok"}
        return {"status": "error", "detail": "GET /api/tags returned no models or failed"}
    except Exception as exc:
        log.error("Health check failed for ollama: %s", str(exc))
        return {"status": "error", "detail": "component unavailable"}


async def _check_duckdb(request: Request) -> dict[str, Any]:
    """Verify DuckDB by executing SELECT 1."""
    try:
        stores = request.app.state.stores
        rows = await stores.duckdb.fetch_all("SELECT 1 AS ping")
        if rows and rows[0][0] == 1:
            return {"status": "ok"}
        return {"status": "error", "detail": "Unexpected SELECT 1 result"}
    except Exception as exc:
        log.error("Health check failed for duckdb: %s", str(exc))
        return {"status": "error", "detail": "component unavailable"}


async def _check_chroma(request: Request) -> dict[str, Any]:
    """Verify Chroma by listing collections."""
    try:
        stores = request.app.state.stores
        collections = await stores.chroma.list_collections_async()
        return {"status": "ok", "collections": collections}
    except Exception as exc:
        log.error("Health check failed for chroma: %s", str(exc))
        return {"status": "error", "detail": "component unavailable"}


async def _check_sqlite(request: Request) -> dict[str, Any]:
    """Verify SQLite by running PRAGMA user_version."""
    try:
        stores = request.app.state.stores
        info = await asyncio.to_thread(stores.sqlite.health_check)
        return {"status": "ok", **info}
    except Exception as exc:
        log.error("Health check failed for sqlite: %s", str(exc))
        return {"status": "error", "detail": "component unavailable"}


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    """
    Check the health of all backend components.

    Runs checks concurrently; overall status is:
    - healthy:   all components ok
    - degraded:  some components ok (Ollama failures are degraded, not fatal)
    - unhealthy: core storage components (DuckDB, SQLite) failed
    """
    ollama_result, duckdb_result, chroma_result, sqlite_result = await asyncio.gather(
        _check_ollama(request),
        _check_duckdb(request),
        _check_chroma(request),
        _check_sqlite(request),
        return_exceptions=False,
    )

    components = {
        "ollama": ollama_result,
        "duckdb": duckdb_result,
        "chroma": chroma_result,
        "sqlite": sqlite_result,
    }

    # Determine overall status:
    # - DuckDB and SQLite are critical storage layers
    # - Chroma failure is degraded (RAG unavailable but events still work)
    # - Ollama failure is degraded (AI features unavailable)
    core_ok = (
        duckdb_result["status"] == "ok"
        and sqlite_result["status"] == "ok"
    )
    all_ok = core_ok and all(
        v["status"] == "ok" for v in components.values()
    )

    if all_ok:
        overall = "healthy"
        http_status = 200
    elif core_ok:
        overall = "degraded"
        http_status = 200
    else:
        overall = "unhealthy"
        http_status = 503

    log.info(
        "Health check",
        overall=overall,
        ollama=ollama_result["status"],
        duckdb=duckdb_result["status"],
        chroma=chroma_result["status"],
        sqlite=sqlite_result["status"],
    )

    return JSONResponse(
        status_code=http_status,
        content={
            "status": overall,
            "components": components,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        },
    )
