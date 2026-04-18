"""
backend.api.services — Service restart / health-recovery endpoints.

POST /api/services/{service_name}/restart

Allows the dashboard System Health card to restart a downed service
without leaving the browser.  Only a small set of safe service names
are accepted; anything else returns 404.

Supported services
------------------
reranker    Kill stale process on port 8100, spawn scripts/start_reranker.py.
misp        Trigger an immediate MISP feed sync (delegates to the live worker).
spiderfoot  Start SpiderFoot OSINT platform on port 5001 if not already up.
ollama      Start the Ollama inference server if not responding.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.core.auth import verify_token
from backend.core.logging import get_logger

if TYPE_CHECKING:
    pass

log = get_logger(__name__)
router = APIRouter()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_LOGS_DIR = _PROJECT_ROOT / "logs"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _port_in_use(port: int) -> bool:
    """Return True if something is listening on 127.0.0.1:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _kill_port(port: int) -> None:
    """Kill the process listening on *port* (Windows: netstat + taskkill)."""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                pid = parts[-1]
                if pid.isdigit():
                    subprocess.run(
                        ["taskkill", "/F", "/PID", pid],
                        capture_output=True, timeout=5,
                    )
                    log.info("Killed PID %s that was listening on port %d", pid, port)
    except Exception as exc:
        log.warning("_kill_port(%d) failed: %s", port, exc)


def _spawn_detached(args: list[str], log_path: Path) -> subprocess.Popen:
    """Spawn a detached subprocess, redirecting stdout+stderr to *log_path*."""
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_fh = open(log_path, "a", encoding="utf-8")  # noqa: SIM115
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    return subprocess.Popen(
        args,
        stdout=log_fh,
        stderr=log_fh,
        cwd=str(_PROJECT_ROOT),
        creationflags=flags,
        close_fds=True,
    )


# ---------------------------------------------------------------------------
# Per-service restart implementations
# ---------------------------------------------------------------------------


async def _restart_reranker() -> dict:
    """Kill port 8100 if occupied, then spawn start_reranker.py."""
    def _do() -> dict:
        if _port_in_use(8100):
            _kill_port(8100)
            import time; time.sleep(1)  # give OS a moment to release the port

        reranker_script = _PROJECT_ROOT / "scripts" / "start_reranker.py"
        if not reranker_script.exists():
            return {"ok": False, "message": f"start_reranker.py not found at {reranker_script}"}

        _spawn_detached(
            [sys.executable, str(reranker_script)],
            _LOGS_DIR / "reranker.log",
        )
        return {"ok": True, "message": "Reranker process spawned — health check in ~10 s"}

    return await asyncio.to_thread(_do)


async def _restart_misp(request: Request) -> dict:
    """Trigger an immediate MISP feed sync via the live worker."""
    worker = getattr(request.app.state, "_misp_feed_worker", None)
    if worker is None:
        return {"ok": False, "message": "MISP feed worker not running (MISP_ENABLED=False?)"}
    try:
        success = await worker._sync()
        return {
            "ok": success,
            "message": "MISP sync complete" if success else "MISP sync returned failure",
        }
    except Exception as exc:
        return {"ok": False, "message": f"MISP sync error: {exc}"}


async def _restart_spiderfoot() -> dict:
    """Start SpiderFoot on port 5001 if not already running."""
    def _do() -> dict:
        if _port_in_use(5001):
            return {"ok": True, "message": "SpiderFoot already running on port 5001"}

        # Common install locations
        candidates = [
            Path("C:/SpiderFoot/sf.py"),
            Path("C:/Tools/spiderfoot/sf.py"),
            _PROJECT_ROOT / "spiderfoot" / "sf.py",
        ]
        sf_script = next((p for p in candidates if p.exists()), None)
        if sf_script is None:
            return {
                "ok": False,
                "message": "SpiderFoot not found. Install to C:\\SpiderFoot\\ or C:\\Tools\\spiderfoot\\",
            }

        _spawn_detached(
            [sys.executable, str(sf_script), "-l", "127.0.0.1:5001"],
            _LOGS_DIR / "spiderfoot.log",
        )
        return {"ok": True, "message": "SpiderFoot process spawned — UI at http://127.0.0.1:5001"}

    return await asyncio.to_thread(_do)


async def _restart_ollama() -> dict:
    """Start Ollama inference server if not already responding."""
    def _do() -> dict:
        if _port_in_use(11434):
            return {"ok": True, "message": "Ollama already running on port 11434"}

        # Try PATH first, then common Windows install location
        ollama_exe = shutil.which("ollama")
        if ollama_exe is None:
            local_app = os.environ.get("LOCALAPPDATA", "")
            fallback = Path(local_app) / "Programs" / "Ollama" / "ollama.exe"
            if fallback.exists():
                ollama_exe = str(fallback)

        if ollama_exe is None:
            return {"ok": False, "message": "Ollama binary not found on PATH or in %LOCALAPPDATA%\\Programs\\Ollama\\"}

        _spawn_detached(
            [ollama_exe, "serve"],
            _LOGS_DIR / "ollama.log",
        )
        return {"ok": True, "message": "Ollama process spawned — inference at http://127.0.0.1:11434"}

    return await asyncio.to_thread(_do)


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

_ALLOWED = {"reranker", "misp", "spiderfoot", "ollama"}


@router.post("/services/{service_name}/restart", dependencies=[Depends(verify_token)])
async def restart_service(service_name: str, request: Request) -> JSONResponse:
    """Restart (or recover) the named service.

    Returns ``{"ok": bool, "service": str, "message": str, "restarted_at": str}``.
    """
    if service_name not in _ALLOWED:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown service '{service_name}'. Supported: {sorted(_ALLOWED)}",
        )

    log.info("Service restart requested: %s", service_name)

    if service_name == "reranker":
        result = await _restart_reranker()
    elif service_name == "misp":
        result = await _restart_misp(request)
    elif service_name == "spiderfoot":
        result = await _restart_spiderfoot()
    elif service_name == "ollama":
        result = await _restart_ollama()
    else:
        result = {"ok": False, "message": "Unhandled service"}

    log.info("Service restart result for %s: ok=%s msg=%s", service_name, result.get("ok"), result.get("message"))
    return JSONResponse(
        status_code=200 if result["ok"] else 503,
        content={
            "ok": result["ok"],
            "service": service_name,
            "message": result["message"],
            "restarted_at": datetime.now(tz=timezone.utc).isoformat(),
        },
    )
