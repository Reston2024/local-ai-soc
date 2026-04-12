"""Map data API — GET /api/map/data?window=24h"""
from __future__ import annotations

import asyncio
import ipaddress
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from backend.core.auth import verify_token

router = APIRouter()

WINDOW_TO_SECONDS: dict[str, int] = {
    "1h": 3600,
    "6h": 21600,
    "24h": 86400,
    "7d": 604800,
}

_FLOW_SQL = """
SELECT src_ip, dst_ip, COUNT(*) AS conn_count
FROM normalized_events
WHERE event_type = 'network_connection'
  AND timestamp > ?
  AND (src_ip IS NOT NULL OR dst_ip IS NOT NULL)
GROUP BY src_ip, dst_ip
ORDER BY conn_count DESC
LIMIT 500
"""


def _is_private(ip: str) -> bool:
    """Return True if IP is RFC1918, loopback, or link-local."""
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return False


def detect_direction(src_ip: str, dst_ip: str) -> str:
    """Classify flow direction based on RFC1918 address ranges.

    Returns:
        "outbound" — src is private, dst is public
        "inbound"  — dst is private, src is public
        "lateral"  — both public (external-to-external)
    Note: internal-to-internal flows (both RFC1918) are treated as outbound
    since they radiate from the LAN node.
    """
    src_private = _is_private(src_ip) if src_ip else False
    dst_private = _is_private(dst_ip) if dst_ip else False
    if src_private:
        return "outbound"
    if dst_private:
        return "inbound"
    return "lateral"


def parse_ipsum_line(line: str) -> tuple[str, int] | None:
    """Parse a single ipsum.txt data line. Returns (ip, tier) or None for comments/blanks."""
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    parts = line.split('\t')
    if len(parts) < 2:
        return None
    try:
        return parts[0].strip(), int(parts[1].strip())
    except (ValueError, IndexError):
        return None


def _resolve_ip_type(cached: dict) -> str | None:
    """Derive ip_type string from cached classification fields."""
    if cached.get("is_tor"):
        return "tor"
    if cached.get("is_proxy"):
        return "vpn"
    if cached.get("is_datacenter"):
        return "datacenter"
    # ip-api.com proxy/hosting fields (pre-Phase-41 cache may have these as booleans in result_json)
    result = {}
    if cached.get("result_json"):
        try:
            result = json.loads(cached["result_json"])
        except (json.JSONDecodeError, TypeError):
            pass
    if result.get("proxy"):
        return "vpn"
    if result.get("hosting"):
        return "datacenter"
    if result.get("mobile"):
        return "isp"
    return None


def build_map_stats(
    unique_ips: list[str],
    ip_data: dict[str, dict],
    flow_count: int,
) -> dict[str, Any]:
    """Aggregate classification statistics across all unique IPs."""
    tor_count = 0
    vpn_count = 0
    dc_count = 0
    country_counts: dict[str, int] = {}

    for ip, info in ip_data.items():
        ip_type = info.get("ip_type")
        if ip_type == "tor":
            tor_count += 1
        elif ip_type == "vpn":
            vpn_count += 1
        elif ip_type == "datacenter":
            dc_count += 1
        country = info.get("country")
        if country:
            country_counts[country] = country_counts.get(country, 0) + info.get("_conn_total", 1)

    top_country = max(country_counts, key=lambda k: country_counts[k]) if country_counts else None
    top_count = country_counts.get(top_country, 0) if top_country else 0

    return {
        "total_ips": len(unique_ips),
        "tor_count": tor_count,
        "vpn_count": vpn_count,
        "datacenter_count": dc_count,
        "top_src_country": top_country,
        "top_src_country_conn_count": top_count,
        "flow_count": flow_count,
    }


@router.get("/data")
async def get_map_data(
    request: Request,
    window: str = Query(default="24h"),
    _token: str = Depends(verify_token),
) -> dict[str, Any]:
    """Return top-500 network_connection flows with geo + classification data.

    Query params:
        window: "1h" | "6h" | "24h" | "7d" (default: "24h")

    Returns:
        {
            "flows": [{"src_ip", "dst_ip", "conn_count", "direction"}],
            "ips": {"<ip>": {lat, lon, country, city, asn, ip_type, ipsum_tier,
                             is_tor, is_proxy, is_datacenter}},
            "stats": {total_ips, tor_count, vpn_count, datacenter_count,
                      top_src_country, top_src_country_conn_count, flow_count}
        }
    """
    window_seconds = WINDOW_TO_SECONDS.get(window, WINDOW_TO_SECONDS["24h"])
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(seconds=window_seconds)).isoformat()

    stores = request.app.state.stores
    duckdb_store = stores.duckdb
    sqlite_store = stores.sqlite

    # Fetch raw flows from DuckDB
    try:
        rows = await duckdb_store.fetch_df(_FLOW_SQL, [cutoff])
    except Exception:
        rows = []

    # Build flows list with direction annotation
    flows = []
    for row in rows:
        src_ip = row.get("src_ip") or ""
        dst_ip = row.get("dst_ip") or ""
        flows.append({
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "conn_count": int(row.get("conn_count", 0)),
            "direction": detect_direction(src_ip, dst_ip),
        })

    # Collect unique external IPs (RFC1918 become "LAN" node on frontend)
    unique_ips: set[str] = set()
    ip_conn_totals: dict[str, int] = {}
    for flow in flows:
        for ip in (flow["src_ip"], flow["dst_ip"]):
            if ip and not _is_private(ip):
                unique_ips.add(ip)
                ip_conn_totals[ip] = ip_conn_totals.get(ip, 0) + flow["conn_count"]

    # Fetch cached OSINT/classification for each unique IP (non-blocking — return null for misses)
    ip_data: dict[str, dict[str, Any]] = {}
    missing_ips: list[str] = []

    for ip in unique_ips:
        cached = await asyncio.to_thread(sqlite_store.get_osint_cache, ip)
        if cached:
            result = {}
            try:
                result = json.loads(cached.get("result_json") or "{}")
            except (json.JSONDecodeError, TypeError):
                pass

            # Classification columns (added in Plan 03; may be None on pre-41 cache)
            ip_type = cached.get("ip_type") or _resolve_ip_type({**cached, "result_json": cached.get("result_json")})
            ip_data[ip] = {
                "lat": result.get("lat"),
                "lon": result.get("lon"),
                "country": result.get("country"),
                "country_iso": result.get("countryCode"),
                "city": result.get("city"),
                "asn": result.get("as") or result.get("asn"),
                "ip_type": ip_type,
                "ipsum_tier": cached.get("ipsum_tier"),
                "is_tor": bool(cached.get("is_tor")),
                "is_proxy": bool(cached.get("is_proxy")),
                "is_datacenter": bool(cached.get("is_datacenter")),
                "_conn_total": ip_conn_totals.get(ip, 0),
            }
        else:
            missing_ips.append(ip)
            ip_data[ip] = {
                "lat": None, "lon": None, "country": None, "country_iso": None,
                "city": None, "asn": None, "ip_type": None,
                "ipsum_tier": None, "is_tor": False, "is_proxy": False, "is_datacenter": False,
                "_conn_total": ip_conn_totals.get(ip, 0),
            }

    # Fire background enrichment for cache-miss IPs (non-blocking)
    if missing_ips:
        from backend.services.osint import OsintService
        osint_service = OsintService(sqlite_store=sqlite_store)
        for ip in missing_ips:
            asyncio.ensure_future(osint_service.enrich(ip))

    # Strip internal _conn_total before returning (used for stats only)
    stats = build_map_stats(list(unique_ips), ip_data, len(flows))
    for info in ip_data.values():
        info.pop("_conn_total", None)

    return {"flows": flows, "ips": ip_data, "stats": stats}
