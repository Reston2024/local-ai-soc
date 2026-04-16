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
import socket
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.core.config import settings
from backend.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter(tags=["health"])

# ---------------------------------------------------------------------------
# Ollama version cache — GitHub is checked at most once per hour
# ---------------------------------------------------------------------------
_ollama_version_cache: dict[str, Any] = {
    "current": None,       # version string from local Ollama
    "latest": None,        # version string from GitHub
    "update_available": False,
    "last_github_check": None,  # datetime of last GitHub query
}
_GITHUB_CHECK_INTERVAL = 3600  # seconds (1 hour)


async def _fetch_ollama_versions(ollama) -> None:
    """Populate _ollama_version_cache with current and latest Ollama versions."""
    global _ollama_version_cache

    # --- current version from local Ollama ---
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(f"{ollama.base_url}/api/version")
            if r.status_code == 200:
                _ollama_version_cache["current"] = r.json().get("version")
    except Exception:
        pass

    # --- latest version from GitHub (rate-limited to once per hour) ---
    now = datetime.now(tz=timezone.utc)
    last = _ollama_version_cache["last_github_check"]
    if last is None or (now - last).total_seconds() > _GITHUB_CHECK_INTERVAL:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(
                    "https://api.github.com/repos/ollama/ollama/releases/latest",
                    headers={"Accept": "application/vnd.github+json"},
                )
                if r.status_code == 200:
                    tag = r.json().get("tag_name", "")          # e.g. "v0.6.5"
                    _ollama_version_cache["latest"] = tag.lstrip("v")
                    _ollama_version_cache["last_github_check"] = now
        except Exception:
            pass

    # --- compare ---
    cur = _ollama_version_cache["current"]
    lat = _ollama_version_cache["latest"]
    if cur and lat:
        try:
            from packaging.version import Version  # noqa: PLC0415
            _ollama_version_cache["update_available"] = Version(lat) > Version(cur)
        except Exception:
            _ollama_version_cache["update_available"] = lat != cur


async def _check_ollama(request: Request) -> dict[str, Any]:
    """Verify Ollama is reachable by calling GET /api/tags; include version info."""
    try:
        ollama = request.app.state.ollama
        ok = await ollama.health_check()
        if not ok:
            return {"status": "error", "detail": "GET /api/tags returned no models or failed"}

        # Fetch version info (current always; GitHub latest at most once/hour)
        await _fetch_ollama_versions(ollama)

        result: dict[str, Any] = {"status": "ok"}
        if _ollama_version_cache["current"]:
            result["version"] = _ollama_version_cache["current"]
        if _ollama_version_cache["latest"]:
            result["latest"] = _ollama_version_cache["latest"]
            result["update_available"] = _ollama_version_cache["update_available"]
        return result
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
        return {"status": "ok", "collections": collections, "mode": stores.chroma.mode}
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


async def _check_hayabusa(request: Request) -> dict[str, Any]:
    """Report Hayabusa binary availability and detection count from SQLite."""
    try:
        from ingestion.hayabusa_scanner import HAYABUSA_BIN  # noqa: PLC0415
        has_binary = HAYABUSA_BIN is not None

        # Count Hayabusa-sourced detections
        try:
            stores = request.app.state.stores
            row = await asyncio.to_thread(
                stores.sqlite._conn.execute,
                "SELECT COUNT(*) FROM detections WHERE detection_source = 'hayabusa'",
            )
            detection_count: int = row.fetchone()[0]
        except Exception:
            detection_count = 0

        return {
            "status": "ok" if has_binary else "warning",
            "binary": str(HAYABUSA_BIN) if has_binary else None,
            "detection_count": detection_count,
            "detail": None if has_binary else "binary not found — EVTX scanning disabled",
        }
    except Exception as exc:
        log.error("Health check failed for hayabusa: %s", str(exc))
        return {"status": "warning", "binary": None, "detection_count": 0, "detail": "check failed"}


async def _check_misp(request: Request) -> dict[str, Any]:
    """Report MISP feed status: enabled/disabled, IOC count, last sync age."""
    if not settings.MISP_ENABLED:
        return {"status": "disabled", "ioc_count": 0, "last_sync": None}
    try:
        ioc_store = request.app.state.ioc_store
        feed_statuses = await asyncio.to_thread(ioc_store.get_feed_status)
        misp = next((f for f in feed_statuses if f["feed"] == "misp"), None)
        if not misp:
            return {"status": "never", "ioc_count": 0, "last_sync": None}
        return {
            "status": misp["status"],
            "ioc_count": misp["ioc_count"],
            "last_sync": misp["last_sync"],
        }
    except Exception as exc:
        log.error("Health check failed for misp: %s", str(exc))
        return {"status": "error", "ioc_count": 0, "last_sync": None, "detail": "check failed"}


async def _check_spiderfoot() -> dict:
    """Ping SpiderFoot container on port 5001."""
    try:
        from backend.services.spiderfoot_client import SpiderFootClient
        from backend.core.config import settings
        client = SpiderFootClient(base_url=settings.SPIDERFOOT_BASE_URL)
        alive = await client.ping()
        return {"status": "ok" if alive else "unreachable", "port": 5001}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def _check_thehive(request: Request) -> dict[str, Any]:
    """Report TheHive status: enabled/disabled, reachable/unreachable."""
    try:
        client = getattr(request.app.state, "thehive_client", None)
        if client is None:
            return {"status": "disabled", "enabled": False}
        ok = await asyncio.to_thread(client.ping)
        return {
            "status": "healthy" if ok else "unreachable",
            "enabled": True,
            "url": settings.THEHIVE_URL,
        }
    except Exception as exc:
        log.error("Health check failed for thehive: %s", str(exc))
        return {"status": "error", "error": str(exc)}


async def _check_chainsaw(request: Request) -> dict[str, Any]:
    """Report Chainsaw binary availability and detection count from SQLite."""
    try:
        from ingestion.chainsaw_scanner import CHAINSAW_BIN  # noqa: PLC0415
        has_binary = CHAINSAW_BIN is not None

        try:
            stores = request.app.state.stores
            row = await asyncio.to_thread(
                stores.sqlite._conn.execute,
                "SELECT COUNT(*) FROM detections WHERE detection_source = 'chainsaw'",
            )
            detection_count: int = int(row.fetchone()[0])
        except Exception:
            detection_count = 0

        return {
            "status": "ok" if has_binary else "warning",
            "binary": str(CHAINSAW_BIN) if has_binary else None,
            "detection_count": detection_count,
            "detail": None if has_binary else "binary not found — EVTX scanning disabled",
        }
    except Exception as exc:
        log.error("Health check failed for chainsaw: %s", str(exc))
        return {"status": "warning", "binary": None, "detection_count": 0, "detail": "check failed"}


def _tcp_check(host: str, port: int, timeout: float = 2.0) -> bool:
    """Return True if TCP connection to host:port succeeds within timeout."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@router.get("/health/network")
async def network_health() -> JSONResponse:
    """
    GET /health/network

    TCP reachability check for configured network devices.
    Returns status for router, firewall, and GMKtec (Malcolm box).
    Devices with empty host config are omitted from the response.

    No auth required — used by the dashboard sidebar on page load.
    """
    devices: dict[str, dict[str, Any]] = {}

    checks: list[tuple[str, str]] = []
    for label, host_port in (
        ("router",   settings.MONITOR_ROUTER_HOST),
        ("firewall", settings.MONITOR_FIREWALL_HOST),
        ("gmktec",   settings.MONITOR_GMKTEC_HOST),
    ):
        if not host_port:
            continue
        try:
            host, port_str = host_port.rsplit(":", 1)
            checks.append((label, host, int(port_str)))
        except ValueError:
            devices[label] = {"status": "error", "detail": "bad config"}

    async def _check(label: str, host: str, port: int) -> tuple[str, dict]:
        ok = await asyncio.to_thread(_tcp_check, host, port)
        return label, {"status": "up" if ok else "down", "host": host, "port": port}

    results = await asyncio.gather(*[_check(l, h, p) for l, h, p in checks])
    for label, info in results:
        devices[label] = info

    return JSONResponse(content={"devices": devices, "timestamp": datetime.now(tz=timezone.utc).isoformat()})


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    """
    Check the health of all backend components.

    Runs checks concurrently; overall status is:
    - healthy:   all components ok
    - degraded:  some components ok (Ollama failures are degraded, not fatal)
    - unhealthy: core storage components (DuckDB, SQLite) failed
    """
    ollama_result, duckdb_result, chroma_result, sqlite_result, hayabusa_result, chainsaw_result, misp_result, spiderfoot_result, thehive_result = await asyncio.gather(
        _check_ollama(request),
        _check_duckdb(request),
        _check_chroma(request),
        _check_sqlite(request),
        _check_hayabusa(request),
        _check_chainsaw(request),
        _check_misp(request),
        _check_spiderfoot(),
        _check_thehive(request),
        return_exceptions=False,
    )

    components = {
        "ollama": ollama_result,
        "duckdb": duckdb_result,
        "chroma": chroma_result,
        "sqlite": sqlite_result,
        "hayabusa": hayabusa_result,
        "chainsaw": chainsaw_result,
        "misp": misp_result,
        "spiderfoot": spiderfoot_result,
        "thehive": thehive_result,
    }

    # Determine overall status:
    # - DuckDB and SQLite are critical storage layers
    # - Chroma failure is degraded (RAG unavailable but events still work)
    # - Ollama failure is degraded (AI features unavailable)
    core_ok = (
        duckdb_result["status"] == "ok"
        and sqlite_result["status"] == "ok"
    )
    # Optional components: spiderfoot (on-demand OSINT), hayabusa/chainsaw (warning = binary present but no detections)
    # These don't drive overall degraded status — only core storage + Ollama/Chroma matter.
    optional_keys = {"spiderfoot", "hayabusa", "chainsaw", "thehive"}
    all_ok = core_ok and all(
        v["status"] in ("ok", "warning") for k, v in components.items() if k not in optional_keys
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
