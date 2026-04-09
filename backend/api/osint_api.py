"""
OSINT enrichment API.

GET /api/osint/{ip} — Returns cached or fresh OSINT enrichment for an IP address.
Used by hunt results panel and detection detail view.
"""

from __future__ import annotations

import dataclasses

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.services.osint import OsintService

router = APIRouter(prefix="/osint", tags=["osint"])


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
