"""
Passive OSINT enrichment service. Read-only lookups against public APIs. No active scanning.

Given an IP address, the service queries:
- WHOIS (python-whois, no API key required)
- AbuseIPDB (optional — skipped if ABUSEIPDB_API_KEY is unset)
- MaxMind GeoLite2 (local mmdb file — no external API call at request time)
- VirusTotal (optional — skipped if VT_API_KEY is unset)
- Shodan (optional — skipped if SHODAN_API_KEY is unset)

Results are cached 24h in SQLite. Per-source rate limiting prevents free-tier exhaustion.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from backend.core.config import settings as _default_settings
from backend.core.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Per-source rate limiters — module-level singletons
# ---------------------------------------------------------------------------

# VirusTotal free tier: 4 req/min → 1 per 15s to be safe
_vt_lock = asyncio.Lock()
_VT_INTERVAL = 15.0  # seconds between VirusTotal requests

# AbuseIPDB free tier: 1000 checks/day → ~1 per 86s; use 90s for safety
_abuse_lock = asyncio.Lock()
_ABUSE_INTERVAL = 90.0

# Shodan free tier: no hard rate limit stated but 1 req/s is safe
_shodan_lock = asyncio.Lock()
_SHODAN_INTERVAL = 1.0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_geo_warned_once: bool = False


def _sanitize_ip(ip: str) -> str:
    """Validate and sanitize an IP address string.

    Raises ValueError for:
    - Non-IP strings (invalid IP)
    - Private/RFC1918 addresses (private IP not enriched)
    - Loopback addresses (loopback IP not enriched)

    Returns the canonical string form of the public IP.
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        raise ValueError(f"invalid IP: {ip!r}")

    if addr.is_loopback:
        raise ValueError(f"loopback IP not enriched: {ip!r}")

    if addr.is_private:
        raise ValueError(f"private IP not enriched: {ip!r}")

    return str(addr)


def _is_cache_valid(fetched_at: str | None, ttl_hours: int = 24) -> bool:
    """Return True if fetched_at is within ttl_hours of now (UTC).

    Returns False if fetched_at is None or the entry has expired.
    """
    if fetched_at is None:
        return False
    try:
        ts = datetime.fromisoformat(fetched_at)
        # Ensure timezone-aware comparison
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = datetime.now(tz=timezone.utc) - ts
        return age < timedelta(hours=ttl_hours)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# OsintResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class OsintResult:
    """Aggregated OSINT enrichment result for a single IP address."""

    ip: str
    whois: dict | None
    abuseipdb: dict | None
    geo: dict | None
    virustotal: dict | None
    shodan: dict | None
    cached: bool = False
    fetched_at: str = ""


# ---------------------------------------------------------------------------
# OsintService
# ---------------------------------------------------------------------------


class OsintService:
    """Orchestrates passive OSINT lookups for IP addresses."""

    def __init__(self, sqlite_store: Any, settings_obj: Any = None) -> None:
        self._store = sqlite_store
        self._settings = settings_obj if settings_obj is not None else _default_settings

    async def enrich(self, ip: str) -> OsintResult:
        """Return OSINT enrichment for a public IP address.

        1. Validates the IP (raises ValueError for private/loopback/invalid).
        2. Checks the 24h SQLite cache.
        3. Runs all configured lookups concurrently.
        4. Stores result in cache and returns.
        """
        # Step 1: validate
        ip = _sanitize_ip(ip)

        # Step 2: check cache
        cached_entry = await asyncio.to_thread(self._store.get_osint_cache, ip)
        if cached_entry and _is_cache_valid(cached_entry.get("fetched_at")):
            data = cached_entry["data"]
            return OsintResult(
                ip=ip,
                whois=data.get("whois"),
                abuseipdb=data.get("abuseipdb"),
                geo=data.get("geo"),
                virustotal=data.get("virustotal"),
                shodan=data.get("shodan"),
                cached=True,
                fetched_at=cached_entry["fetched_at"],
            )

        # Step 3: run lookups concurrently
        tasks_list = [
            self._whois(ip),
            self._abuseipdb(ip) if self._settings.ABUSEIPDB_API_KEY else _async_none(),
            self._geo(ip),
            self._virustotal(ip) if self._settings.VT_API_KEY else _async_none(),
            self._shodan(ip) if self._settings.SHODAN_API_KEY else _async_none(),
        ]

        results = await asyncio.gather(*tasks_list, return_exceptions=True)

        def _safe(r: Any) -> dict | None:
            if isinstance(r, Exception):
                log.warning("OSINT lookup failed", error=str(r))
                return None
            return r

        whois_data = _safe(results[0])
        abuse_data = _safe(results[1])
        geo_data = _safe(results[2])
        vt_data = _safe(results[3])
        shodan_data = _safe(results[4])

        # Step 4: build result
        now = datetime.now(tz=timezone.utc)
        fetched_at = now.isoformat()
        expires_at = (now + timedelta(hours=24)).isoformat()

        result = OsintResult(
            ip=ip,
            whois=whois_data,
            abuseipdb=abuse_data,
            geo=geo_data,
            virustotal=vt_data,
            shodan=shodan_data,
            cached=False,
            fetched_at=fetched_at,
        )

        # Step 5: persist to cache
        data_dict = {
            "whois": result.whois,
            "abuseipdb": result.abuseipdb,
            "geo": result.geo,
            "virustotal": result.virustotal,
            "shodan": result.shodan,
        }
        await asyncio.to_thread(
            self._store.set_osint_cache,
            ip,
            json.dumps(data_dict),
            fetched_at,
            expires_at,
        )

        return result

    # -----------------------------------------------------------------------
    # Individual lookup methods
    # -----------------------------------------------------------------------

    async def _whois(self, ip: str) -> dict | None:
        """WHOIS lookup via python-whois. No API key required."""
        try:
            import whois as whois_lib  # type: ignore[import]

            data = await asyncio.to_thread(whois_lib.whois, ip)

            def _to_iso(val: Any) -> str | None:
                if val is None:
                    return None
                if isinstance(val, list):
                    val = val[0]
                if isinstance(val, datetime):
                    return val.isoformat()
                return str(val)

            return {
                "registrar": getattr(data, "registrar", None),
                "creation_date": _to_iso(getattr(data, "creation_date", None)),
                "expiration_date": _to_iso(getattr(data, "expiration_date", None)),
                "country": getattr(data, "country", None),
                "org": getattr(data, "org", None),
            }
        except Exception as exc:
            log.warning("WHOIS lookup failed", ip=ip, error=str(exc))
            return None

    async def _abuseipdb(self, ip: str) -> dict | None:
        """AbuseIPDB lookup — rate-limited to 1 req/90s."""
        async with _abuse_lock:
            await asyncio.sleep(_ABUSE_INTERVAL)
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(
                        "https://api.abuseipdb.com/api/v2/check",
                        params={"ipAddress": ip, "maxAgeInDays": 90},
                        headers={
                            "Key": self._settings.ABUSEIPDB_API_KEY,
                            "Accept": "application/json",
                        },
                    )
                if resp.status_code != 200:
                    return None
                d = resp.json().get("data", {})
                return {
                    "abuseConfidenceScore": d.get("abuseConfidenceScore"),
                    "totalReports": d.get("totalReports"),
                    "countryCode": d.get("countryCode"),
                    "usageType": d.get("usageType"),
                    "isp": d.get("isp"),
                    "domain": d.get("domain"),
                }
            except Exception as exc:
                log.warning("AbuseIPDB lookup failed", ip=ip, error=str(exc))
                return None

    async def _geo(self, ip: str) -> dict | None:
        """MaxMind GeoLite2 lookup from local mmdb file."""
        global _geo_warned_once
        import os

        mmdb_path = self._settings.GEOIP_DB_PATH
        if not os.path.exists(mmdb_path):
            if not _geo_warned_once:
                log.warning(
                    "GeoLite2-City.mmdb not found — geo lookup disabled",
                    path=mmdb_path,
                )
                _geo_warned_once = True
            return None

        try:
            import geoip2.database  # type: ignore[import]
            import geoip2.errors  # type: ignore[import]

            def _read() -> dict | None:
                with geoip2.database.Reader(mmdb_path) as reader:
                    try:
                        response = reader.city(ip)
                        return {
                            "country_name": response.country.name,
                            "country_iso_code": response.country.iso_code,
                            "city": response.city.name,
                            "latitude": response.location.latitude,
                            "longitude": response.location.longitude,
                            "autonomous_system_number": getattr(
                                response, "autonomous_system_number", None
                            ),
                            "autonomous_system_organization": getattr(
                                response, "autonomous_system_organization", None
                            ),
                        }
                    except geoip2.errors.AddressNotFoundError:
                        return {"country_name": None, "latitude": None, "longitude": None}

            return await asyncio.to_thread(_read)
        except Exception as exc:
            log.warning("GeoIP lookup failed", ip=ip, error=str(exc))
            return None

    async def _virustotal(self, ip: str) -> dict | None:
        """VirusTotal lookup — rate-limited to 1 req/15s."""
        async with _vt_lock:
            await asyncio.sleep(_VT_INTERVAL)
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        f"https://www.virustotal.com/api/v3/ip_addresses/{ip}",
                        headers={"x-apikey": self._settings.VT_API_KEY},
                    )
                if resp.status_code != 200:
                    return None
                attrs = resp.json().get("data", {}).get("attributes", {})
                stats = attrs.get("last_analysis_stats", {})
                return {
                    "malicious": stats.get("malicious"),
                    "suspicious": stats.get("suspicious"),
                    "harmless": stats.get("harmless"),
                    "undetected": stats.get("undetected"),
                    "country": attrs.get("country"),
                    "as_owner": attrs.get("as_owner"),
                    "reputation": attrs.get("reputation"),
                }
            except Exception as exc:
                log.warning("VirusTotal lookup failed", ip=ip, error=str(exc))
                return None

    async def _shodan(self, ip: str) -> dict | None:
        """Shodan lookup — rate-limited to 1 req/s."""
        async with _shodan_lock:
            await asyncio.sleep(_SHODAN_INTERVAL)
            try:
                import shodan as shodan_lib  # type: ignore[import]

                api = shodan_lib.Shodan(self._settings.SHODAN_API_KEY)
                host = await asyncio.to_thread(api.host, ip)
                return {
                    "org": host.get("org"),
                    "isp": host.get("isp"),
                    "country_name": host.get("country_name"),
                    "open_ports": host.get("ports", []),
                    "tags": host.get("tags", []),
                    "hostnames": host.get("hostnames", []),
                    "last_update": host.get("last_update"),
                }
            except Exception as exc:
                # Covers shodan.exception.APIError "no information available"
                log.warning("Shodan lookup failed", ip=ip, error=str(exc))
                return None


# ---------------------------------------------------------------------------
# Helper coroutine for skipped sources
# ---------------------------------------------------------------------------


async def _async_none() -> None:
    """Return None immediately — used when a source is skipped (API key not set)."""
    return None
