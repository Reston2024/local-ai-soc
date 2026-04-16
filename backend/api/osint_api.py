"""
OSINT enrichment API.

GET /api/osint/{ip} — Returns cached or fresh OSINT enrichment for an IP address.
Used by hunt results panel and detection detail view.

Phase 51 additions:
POST   /api/osint/investigate          — Start SpiderFoot OSINT investigation
GET    /api/osint/investigate/{job_id} — Poll status + findings
GET    /api/osint/investigate/{job_id}/stream — SSE live findings stream
GET    /api/osint/investigations        — List all investigations
DELETE /api/osint/investigate/{job_id} — Cancel + delete investigation
POST   /api/osint/dnstwist             — Synchronous DNSTwist permutation scan
"""

from __future__ import annotations

import asyncio
import dataclasses
import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.services.osint import OsintService

router = APIRouter(prefix="/osint", tags=["osint"])


# ---------------------------------------------------------------------------
# Phase 32: IP enrichment
# ---------------------------------------------------------------------------

@router.get("/{ip}", summary="Get OSINT enrichment for an IP address")
async def get_osint(ip: str, request: Request) -> JSONResponse:
    """
    Return OSINT enrichment data for a public IP address.

    Sources (all optional — skipped gracefully when API keys are absent):
    - WHOIS (no key required)
    - MaxMind GeoLite2 (local mmdb file, no external API call)
    - AbuseIPDB (requires ABUSEIPDB_API_KEY)
    - VirusTotal (requires VT_API_KEY)
    - Shodan (requires SHODAN_API_KEY)

    Results are cached for 24 hours. Subsequent requests within the TTL return
    cached=true with no external API calls.

    Raises 400 for private, loopback, or invalid IP addresses.
    """
    stores = request.app.state.stores
    service = OsintService(sqlite_store=stores.sqlite)

    try:
        result = await service.enrich(ip)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    return JSONResponse(status_code=200, content=dataclasses.asdict(result))


# ---------------------------------------------------------------------------
# Phase 51: SpiderFoot investigation routes
# ---------------------------------------------------------------------------

class InvestigateRequest(BaseModel):
    target: str
    usecase: str = "passive"  # passive | all


class DnsTwistRequest(BaseModel):
    domain: str


@router.post("/investigate", summary="Start SpiderFoot OSINT investigation")
async def start_investigation(body: InvestigateRequest, request: Request) -> JSONResponse:
    """
    Start a SpiderFoot investigation for the given target (IP or domain).
    Returns immediately with {job_id, status: RUNNING}.
    Background poller harvests results and handles 30-min timeout.
    """
    from backend.services.spiderfoot_client import SpiderFootClient
    from backend.services.osint_poller import poll_to_completion
    from backend.core.config import settings

    osint_store = getattr(request.app.state, "osint_store", None)
    if osint_store is None:
        return JSONResponse(status_code=503, content={"error": "OSINT store not initialized"})

    client = SpiderFootClient(base_url=settings.SPIDERFOOT_BASE_URL)

    # Check SpiderFoot is reachable
    if not await client.ping():
        return JSONResponse(
            status_code=503,
            content={
                "error": "SpiderFoot container not reachable. Start it with: "
                         "docker compose -f infra/docker-compose.spiderfoot.yml up -d"
            },
        )

    # Create placeholder job in SQLite first
    placeholder_id = await asyncio.to_thread(
        osint_store.create_investigation, body.target, body.usecase
    )

    # Start SpiderFoot scan
    try:
        scan_id = await client.start_scan(body.target, body.usecase)
    except Exception as exc:
        await asyncio.to_thread(
            osint_store.update_investigation_status,
            placeholder_id, "ERROR-FAILED", None, str(exc),
        )
        return JSONResponse(status_code=500, content={"error": f"SpiderFoot start failed: {exc}"})

    # Replace placeholder UUID with actual SpiderFoot scan ID
    await asyncio.to_thread(osint_store.update_job_id, placeholder_id, scan_id)

    # Launch background poller (non-blocking, 30-min ceiling)
    asyncio.create_task(
        poll_to_completion(scan_id, client, osint_store, timeout_seconds=1800)
    )

    return JSONResponse(status_code=202, content={"job_id": scan_id, "status": "RUNNING"})


@router.get("/investigate/{job_id:path}/stream", summary="SSE stream of live OSINT findings")
async def stream_investigation(job_id: str, request: Request):
    """
    Server-Sent Events endpoint that streams new osint_findings rows as they
    are inserted by the background poller. The client connects while status is
    RUNNING and receives each new row as a JSON event.

    Protocol:
      - event: "finding"   data: <JSON row>
      - event: "status"    data: {"status": "FINISHED"} (terminal — client closes)
      - event: "keepalive" data: "" (every 5s to prevent proxy timeouts)

    Polls SQLite every 5 seconds; uses last_seen_id cursor to emit only new rows.
    """
    from sse_starlette.sse import EventSourceResponse

    osint_store = getattr(request.app.state, "osint_store", None)
    if osint_store is None:
        async def err_gen():
            yield {"event": "error", "data": '{"error":"OSINT store not initialized"}'}
        return EventSourceResponse(err_gen())

    _TERMINAL_STATES = {"FINISHED", "ERROR-FAILED", "ABORTED", "TIMEOUT"}

    async def event_generator():
        last_seen_id: int = 0
        while True:
            if await request.is_disconnected():
                break

            # Yield any new findings since last_seen_id
            new_rows = await asyncio.to_thread(
                osint_store.get_findings_since, job_id, last_seen_id
            )
            for row in new_rows:
                last_seen_id = max(last_seen_id, row["id"])
                yield {"event": "finding", "data": json.dumps(row)}

            # Check current status
            job = await asyncio.to_thread(osint_store.get_investigation, job_id)
            if job is None:
                yield {"event": "error", "data": '{"error":"not found"}'}
                break
            if job["status"] in _TERMINAL_STATES:
                yield {"event": "status", "data": json.dumps({"status": job["status"]})}
                break

            yield {"event": "keepalive", "data": ""}
            await asyncio.sleep(5)

    return EventSourceResponse(event_generator())


@router.get("/investigate/{job_id:path}", summary="Get OSINT investigation status and findings")
async def get_investigation(job_id: str, request: Request) -> JSONResponse:
    osint_store = getattr(request.app.state, "osint_store", None)
    if osint_store is None:
        return JSONResponse(status_code=503, content={"error": "OSINT store not initialized"})

    job = await asyncio.to_thread(osint_store.get_investigation, job_id)
    if job is None:
        return JSONResponse(status_code=404, content={"error": "investigation not found"})

    findings = await asyncio.to_thread(osint_store.get_findings, job_id)

    # Group findings by event_type for frontend display
    grouped: dict[str, list] = {}
    for f in findings:
        grouped.setdefault(f["event_type"], []).append(f)

    # Fetch DNSTwist findings for every unique DOMAIN_NAME in results
    domains = list({f["data"] for f in findings if f["event_type"] == "DOMAIN_NAME" and f["data"]})
    dnstwist_findings: dict[str, list] = {}
    for domain in domains:
        rows = await asyncio.to_thread(osint_store.get_dnstwist_findings, job_id, domain)
        if rows:
            dnstwist_findings[domain] = rows

    return JSONResponse(status_code=200, content={
        **job,
        "findings": findings,
        "findings_by_type": grouped,
        "findings_count": len(findings),
        "dnstwist_findings": dnstwist_findings,
    })


@router.get("/investigations", summary="List all OSINT investigations")
async def list_investigations(request: Request) -> JSONResponse:
    osint_store = getattr(request.app.state, "osint_store", None)
    if osint_store is None:
        return JSONResponse(status_code=503, content={"error": "OSINT store not initialized"})
    rows = await asyncio.to_thread(osint_store.list_investigations)
    return JSONResponse(status_code=200, content={"investigations": rows})


@router.delete("/investigate/{job_id:path}", summary="Cancel and delete OSINT investigation")
async def delete_investigation(job_id: str, request: Request) -> JSONResponse:
    from backend.services.spiderfoot_client import SpiderFootClient
    from backend.core.config import settings

    osint_store = getattr(request.app.state, "osint_store", None)
    if osint_store is None:
        return JSONResponse(status_code=503, content={"error": "OSINT store not initialized"})

    client = SpiderFootClient(base_url=settings.SPIDERFOOT_BASE_URL)
    # Best-effort stop — ignore failures (scan may already be finished)
    await client.stop_scan(job_id)
    await client.delete_scan(job_id)
    await asyncio.to_thread(
        osint_store.update_investigation_status, job_id, "ABORTED", None
    )
    return JSONResponse(status_code=200, content={"status": "cancelled"})


@router.post("/dnstwist", summary="Run DNSTwist permutation scan for a domain")
async def run_dnstwist_scan(body: DnsTwistRequest, request: Request) -> JSONResponse:
    """
    Synchronous DNSTwist scan. Completes in 10-120s for most domains.
    Returns {lookalikes: [...]} with registered lookalike domains only.
    """
    from backend.services.dnstwist_service import run_dnstwist
    try:
        lookalikes = await run_dnstwist(body.domain)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
    return JSONResponse(status_code=200, content={"lookalikes": lookalikes, "domain": body.domain})
