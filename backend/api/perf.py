"""GET /api/metrics/perf — live performance gauges for SOC Brain host and GMKtec/Malcolm.

Response shape:
{
  "soc_brain": {
    "cpu_pct": 23.5,
    "ram_pct": 61.2,
    "disk_pct": 45.8,
    "ram_detail": "9.8 / 16.0 GB",
    "disk_detail": "120 / 256 GB"
  },
  "gmktec": {
    "cpu_pct": 34.1,       # null if Malcolm unreachable
    "heap_pct": 52.3,
    "disk_pct": 71.4,
    "heap_detail": "4.0 / 8.0 GB",
    "disk_detail": "85 / 119 GB"
  },
  "timestamp": "2026-04-14T..."
}
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
import psutil

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.core.config import settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/metrics", tags=["metrics"])


def _soc_brain_metrics() -> dict[str, Any]:
    """Collect CPU / RAM / disk for the local machine via psutil."""
    cpu = psutil.cpu_percent(interval=0.3)

    ram = psutil.virtual_memory()
    ram_pct = ram.percent
    ram_used_gb = ram.used / 1024 ** 3
    ram_total_gb = ram.total / 1024 ** 3

    # Use C:\ on Windows, fall back to root
    try:
        disk = psutil.disk_usage("C:\\")
    except Exception:
        disk = psutil.disk_usage("/")
    disk_pct = disk.percent
    disk_used_gb = disk.used / 1024 ** 3
    disk_total_gb = disk.total / 1024 ** 3

    return {
        "cpu_pct": round(cpu, 1),
        "ram_pct": round(ram_pct, 1),
        "disk_pct": round(disk_pct, 1),
        "ram_detail": f"{ram_used_gb:.1f} / {ram_total_gb:.1f} GB",
        "disk_detail": f"{disk_used_gb:.0f} / {disk_total_gb:.0f} GB",
    }


async def _gmktec_metrics() -> dict[str, Any]:
    """Query Malcolm's OpenSearch /_nodes/stats for GMKtec hardware metrics.

    Uses the same URL/credentials as the Malcolm integration already configured
    in settings.  Returns nulls gracefully if Malcolm is unreachable.
    """
    null_result: dict[str, Any] = {
        "cpu_pct": None,
        "heap_pct": None,
        "disk_pct": None,
        "heap_detail": None,
        "disk_detail": None,
    }

    if not settings.MALCOLM_ENABLED:
        return null_result

    url = (
        f"{settings.MALCOLM_OPENSEARCH_URL}"
        "/_nodes/stats/os,jvm,fs"
        "?filter_path=nodes.*.os.cpu.percent"
        ",nodes.*.jvm.mem.heap_used_percent"
        ",nodes.*.jvm.mem.heap_used_in_bytes"
        ",nodes.*.jvm.mem.heap_max_in_bytes"
        ",nodes.*.fs.total.available_in_bytes"
        ",nodes.*.fs.total.total_in_bytes"
    )

    try:
        async with httpx.AsyncClient(
            verify=settings.MALCOLM_OPENSEARCH_VERIFY_SSL,
            auth=(settings.MALCOLM_OPENSEARCH_USER, settings.MALCOLM_OPENSEARCH_PASS),
            timeout=5.0,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        log.debug("GMKtec metrics fetch failed: %s", exc)
        return null_result

    nodes = data.get("nodes", {})
    if not nodes:
        return null_result

    # Take the first (and usually only) node
    node = next(iter(nodes.values()))

    cpu_pct: float | None = None
    try:
        cpu_pct = float(node["os"]["cpu"]["percent"])
    except (KeyError, TypeError, ValueError):
        pass

    heap_pct: float | None = None
    heap_detail: str | None = None
    try:
        heap_pct = float(node["jvm"]["mem"]["heap_used_percent"])
        heap_used = node["jvm"]["mem"]["heap_used_in_bytes"] / 1024 ** 3
        heap_max = node["jvm"]["mem"]["heap_max_in_bytes"] / 1024 ** 3
        heap_detail = f"{heap_used:.1f} / {heap_max:.1f} GB"
    except (KeyError, TypeError, ValueError):
        pass

    disk_pct: float | None = None
    disk_detail: str | None = None
    try:
        avail = node["fs"]["total"]["available_in_bytes"]
        total = node["fs"]["total"]["total_in_bytes"]
        used = total - avail
        disk_pct = round(used / total * 100, 1)
        disk_detail = f"{used / 1024**3:.0f} / {total / 1024**3:.0f} GB"
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        pass

    return {
        "cpu_pct": round(cpu_pct, 1) if cpu_pct is not None else None,
        "heap_pct": round(heap_pct, 1) if heap_pct is not None else None,
        "disk_pct": disk_pct,
        "heap_detail": heap_detail,
        "disk_detail": disk_detail,
    }


@router.get("/perf")
async def get_perf(request: Request) -> JSONResponse:  # noqa: ARG001
    """Return live CPU/RAM/disk gauges for SOC Brain host and GMKtec/Malcolm."""
    soc_brain, gmktec = await asyncio.gather(
        asyncio.to_thread(_soc_brain_metrics),
        _gmktec_metrics(),
    )
    return JSONResponse({
        "soc_brain": soc_brain,
        "gmktec": gmktec,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
