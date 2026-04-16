"""
SpiderFootClient — async httpx client for SpiderFoot REST API (Phase 51).

SpiderFoot REST API runs on CherryPy, port 5001.
CRITICAL: POST endpoints (/startscan, /stopscan, /scandelete) use
application/x-www-form-urlencoded — pass data={}, NOT json={}.
/startscan returns plain text scan ID, NOT JSON.
"""
from __future__ import annotations

import asyncio
import httpx
from backend.core.logging import get_logger

log = get_logger(__name__)

SPIDERFOOT_BASE_DEFAULT = "http://localhost:5001"


class SpiderFootClient:
    def __init__(self, base_url: str = SPIDERFOOT_BASE_DEFAULT) -> None:
        self._base = base_url.rstrip("/")

    async def ping(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(f"{self._base}/ping")
            return r.status_code == 200
        except Exception:
            return False

    async def start_scan(self, target: str, usecase: str = "passive") -> str:
        """Returns scan ID string. Form-encoded POST — not JSON."""
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                f"{self._base}/startscan",
                data={
                    "scanname": f"AI-SOC: {target}",
                    "scantarget": target,
                    "usecase": usecase,
                    "modulelist": "",
                    "typelist": "",
                },
            )
        r.raise_for_status()
        return r.text.strip()

    async def get_status(self, scan_id: str) -> str:
        """Returns status string from index[6] of the scanstatus response."""
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{self._base}/scanstatus", params={"id": scan_id})
        r.raise_for_status()
        data = r.json()
        return data[6] if isinstance(data, list) and len(data) > 6 else "UNKNOWN"

    async def get_summary(self, scan_id: str) -> list:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f"{self._base}/scansummary", params={"id": scan_id, "by": "type"})
        r.raise_for_status()
        return r.json()

    async def get_events(self, scan_id: str, event_type: str) -> list:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.get(
                f"{self._base}/scaneventresults",
                params={"id": scan_id, "eventType": event_type, "filterfp": "1"},
            )
        r.raise_for_status()
        return r.json()

    async def get_graph(self, scan_id: str) -> dict:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.get(f"{self._base}/scanviz", params={"id": scan_id})
        r.raise_for_status()
        return r.json()

    async def stop_scan(self, scan_id: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                await c.post(f"{self._base}/stopscan", data={"id": scan_id})
        except Exception as exc:
            log.warning("stop_scan failed", scan_id=scan_id, error=str(exc))

    async def delete_scan(self, scan_id: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                await c.post(f"{self._base}/scandelete", data={"id": scan_id})
        except Exception as exc:
            log.warning("delete_scan failed", scan_id=scan_id, error=str(exc))
