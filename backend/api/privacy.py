"""Phase 53: Privacy monitoring — detection scanner + REST API.

Scanner: run_privacy_scan(app) — queries DuckDB for HTTP and DNS events,
filters against PrivacyBlocklistStore, inserts detection records.

Module-level helpers _query_http_events and _is_tracker are exposed for unit-test
patching (same testability pattern used in Phase 43/48/49).

API:
  GET /api/privacy/hits        — list detections with detection_source='privacy'
  GET /api/privacy/feeds       — blocklist feed status
  GET /api/privacy/http-events — recent HTTP events with tracker flagging
  GET /api/privacy/dns-events  — recent DNS queries with tracker flagging
  GET /api/privacy/tls-events  — recent TLS connection flows (no SNI available)
  POST /api/privacy/scan       — manually trigger a scan
"""
from __future__ import annotations

import asyncio
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from backend.core.auth import verify_token
from backend.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Router — exported as both `router` (test stub contract) and `privacy_router`
# (plan wiring alias).
# All routes require Bearer token authentication via verify_token dependency.
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/api/privacy",
    tags=["privacy"],
    dependencies=[Depends(verify_token)],
)
privacy_router = router  # alias so main.py can use either name

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

_COOKIE_EXFIL_SQL = """
    SELECT event_id, src_ip, domain, http_uri,
           http_referrer, http_request_body_len, timestamp
    FROM normalized_events
    WHERE event_type = 'http'
      AND http_request_body_len > ?
      AND domain IS NOT NULL
      AND ingested_at > CURRENT_TIMESTAMP - INTERVAL '1 hour'
    ORDER BY timestamp DESC
    LIMIT 500
"""

_TRACKING_PIXEL_SQL = """
    SELECT event_id, src_ip, domain, http_uri,
           http_referrer, http_response_body_len, http_resp_mime_type, timestamp
    FROM normalized_events
    WHERE event_type = 'http'
      AND http_response_body_len > 0
      AND http_response_body_len < ?
      AND (
          http_resp_mime_type IN ('image/gif', 'image/png', 'image/jpeg', 'image/webp')
          OR http_resp_mime_type IS NULL
      )
      AND domain IS NOT NULL
      AND ingested_at > CURRENT_TIMESTAMP - INTERVAL '1 hour'
    ORDER BY timestamp DESC
    LIMIT 500
"""

# DNS-based tracker detection: look for DNS queries to known tracker domains
_DNS_TRACKER_SQL = """
    SELECT event_id, src_ip, dns_query, dns_query_type, dns_answers, timestamp
    FROM normalized_events
    WHERE event_type IN ('dns', 'dns_query', 'zeek/dns', 'dns_zeek')
      AND dns_query IS NOT NULL
      AND ingested_at > CURRENT_TIMESTAMP - INTERVAL '1 hour'
    ORDER BY timestamp DESC
    LIMIT 1000
"""

_RECENT_HTTP_SQL = """
    SELECT event_id, src_ip, domain, http_uri, http_method,
           http_status_code, http_user_agent, http_request_body_len,
           http_response_body_len, http_resp_mime_type, timestamp
    FROM normalized_events
    WHERE event_type = 'http'
      AND domain IS NOT NULL
    ORDER BY timestamp DESC
    LIMIT 200
"""

_RECENT_DNS_SQL = """
    SELECT event_id, src_ip, dns_query, dns_query_type, dns_answers, timestamp
    FROM normalized_events
    WHERE event_type IN ('dns', 'dns_query', 'zeek/dns', 'dns_zeek')
      AND dns_query IS NOT NULL
    ORDER BY timestamp DESC
    LIMIT 500
"""

# TLS connection flows — Malcolm/Suricata sessions don't include SNI
# so we show raw connection metadata (src_ip → dst_ip:port)
_RECENT_TLS_SQL = """
    SELECT event_id, src_ip, dst_ip, dst_port, tls_version, tls_ja3, timestamp
    FROM normalized_events
    WHERE event_type IN ('ssl', 'tls', 'zeek/ssl')
    ORDER BY timestamp DESC
    LIMIT 500
"""

_HITS_SQL = """
    SELECT id, rule_id, rule_name, severity, matched_event_ids, created_at, entity_key
    FROM detections
    WHERE detection_source = 'privacy'
    ORDER BY created_at DESC
    LIMIT 200
"""


# ---------------------------------------------------------------------------
# Module-level testability helpers (patchable by unit tests)
# ---------------------------------------------------------------------------

def _query_http_events(duckdb_store, sql: str, threshold: int) -> list[dict]:
    """Synchronous helper: query DuckDB for events matching threshold.

    Exposed at module level so tests can patch backend.api.privacy._query_http_events.
    In production, called inside asyncio.to_thread().
    """
    import duckdb as _duckdb
    conn = duckdb_store.get_read_conn()
    try:
        params = [threshold] if "?" in sql else []
        rows = conn.execute(sql, params).fetchall()
        desc = conn.description or []
        if desc:
            cols = [d[0] for d in desc]
            return [dict(zip(cols, row)) for row in rows]
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _is_tracker(privacy_store, domain: str) -> bool:
    """Synchronous helper: check if domain is in the privacy blocklist.

    Exposed at module level so tests can patch backend.api.privacy._is_tracker.
    """
    try:
        return privacy_store.is_tracker(domain)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def run_privacy_scan(app) -> list[dict]:
    """Scan recent HTTP and DNS events for tracker contacts.

    Synchronous for unit-test compatibility (Wave-0 stubs call without await).
    Background loop wraps this via asyncio.to_thread().

    Detection types:
      cookie_exfil    — large HTTP POST body to known tracker domain
      tracking_pixel  — tiny image response from known tracker domain
      dns_tracker     — DNS query for a known tracker domain

    Returns list of detection dicts.
    """
    try:
        duckdb_store = app.state.stores.duckdb
        privacy_store = app.state.privacy_store
        sqlite_store = app.state.stores.sqlite
    except AttributeError as exc:
        logger.warning("privacy_scan: missing app.state attribute: %s", exc)
        return []

    try:
        from backend.core.config import settings as _settings
        cookie_threshold = int(_settings.PRIVACY_COOKIE_EXFIL_THRESHOLD_BYTES)
        pixel_max = int(_settings.PRIVACY_PIXEL_MAX_BODY_BYTES)
    except Exception:
        cookie_threshold = 4096
        pixel_max = 128

    detections: list[dict] = []

    # --- Cookie exfil ---
    try:
        rows = _query_http_events(duckdb_store, _COOKIE_EXFIL_SQL, cookie_threshold)
        for row in rows:
            domain = (row.get("domain") or "").lower()
            if not domain:
                continue
            if not _is_tracker(privacy_store, domain):
                continue
            event_id = row.get("event_id") or str(uuid4())
            body_len = row.get("http_request_body_len")
            det = {
                "hit_type": "cookie_exfil",
                "rule_id": "privacy-cookie_exfil",
                "rule_name": "Privacy: Cookie Exfiltration",
                "detection_source": "privacy",
                "entity_key": domain,
                "event_id": event_id,
                "domain": domain,
                "body_len": body_len,
            }
            detections.append(det)
            try:
                sqlite_store.insert_detection(
                    str(uuid4()),
                    "privacy-cookie_exfil",
                    "Privacy: Cookie Exfiltration",
                    "medium",
                    [event_id],
                    None,
                    None,
                    f"Large HTTP request body ({body_len} bytes) to known tracker {domain}",
                    None,
                    domain,
                    "privacy",
                )
            except Exception as exc:
                logger.warning("privacy_scan: insert_detection failed for cookie_exfil: %s", exc)
    except Exception as exc:
        logger.warning("privacy_scan: cookie_exfil scan failed: %s", exc)

    # --- Tracking pixel ---
    try:
        rows = _query_http_events(duckdb_store, _TRACKING_PIXEL_SQL, pixel_max)
        for row in rows:
            domain = (row.get("domain") or "").lower()
            if not domain:
                continue
            if not _is_tracker(privacy_store, domain):
                continue
            event_id = row.get("event_id") or str(uuid4())
            body_len = row.get("http_response_body_len")
            mime = row.get("http_resp_mime_type") or "unknown"
            det = {
                "hit_type": "tracking_pixel",
                "rule_id": "privacy-tracking_pixel",
                "rule_name": "Privacy: Tracking Pixel",
                "detection_source": "privacy",
                "entity_key": domain,
                "event_id": event_id,
                "domain": domain,
                "body_len": body_len,
                "mime_type": mime,
            }
            detections.append(det)
            try:
                sqlite_store.insert_detection(
                    str(uuid4()),
                    "privacy-tracking_pixel",
                    "Privacy: Tracking Pixel",
                    "medium",
                    [event_id],
                    None,
                    None,
                    f"Tiny {mime} response ({body_len} bytes) from known tracker {domain}",
                    None,
                    domain,
                    "privacy",
                )
            except Exception as exc:
                logger.warning("privacy_scan: insert_detection failed for tracking_pixel: %s", exc)
    except Exception as exc:
        logger.warning("privacy_scan: tracking_pixel scan failed: %s", exc)

    # --- DNS tracker queries ---
    # For TLS 1.3 networks where SNI is not available, DNS queries are the most
    # reliable signal for tracker domain contacts.
    try:
        rows = _query_http_events(duckdb_store, _DNS_TRACKER_SQL, 0)
        # Deduplicate by (src_ip, dns_query) to avoid flooding on repeated queries
        seen: set[tuple] = set()
        for row in rows:
            query = (row.get("dns_query") or "").lower().rstrip(".")
            if not query:
                continue
            if not _is_tracker(privacy_store, query):
                continue
            src_ip = row.get("src_ip") or "unknown"
            key = (src_ip, query)
            if key in seen:
                continue
            seen.add(key)
            event_id = row.get("event_id") or str(uuid4())
            det = {
                "hit_type": "dns_tracker",
                "rule_id": "privacy-dns_tracker",
                "rule_name": "Privacy: Tracker DNS Query",
                "detection_source": "privacy",
                "entity_key": query,
                "event_id": event_id,
                "domain": query,
            }
            detections.append(det)
            try:
                sqlite_store.insert_detection(
                    str(uuid4()),
                    "privacy-dns_tracker",
                    "Privacy: Tracker DNS Query",
                    "medium",
                    [event_id],
                    None,
                    None,
                    f"DNS query for known tracker domain {query} from {src_ip}",
                    None,
                    query,
                    "privacy",
                )
            except Exception as exc:
                logger.warning("privacy_scan: insert_detection failed for dns_tracker: %s", exc)
    except Exception as exc:
        logger.warning("privacy_scan: dns_tracker scan failed: %s", exc)

    if detections:
        cookie_count = sum(1 for d in detections if d["hit_type"] == "cookie_exfil")
        pixel_count  = sum(1 for d in detections if d["hit_type"] == "tracking_pixel")
        dns_count    = sum(1 for d in detections if d["hit_type"] == "dns_tracker")
        logger.info(
            "privacy_scan: findings cookie_exfil=%d tracking_pixel=%d dns_tracker=%d",
            cookie_count, pixel_count, dns_count,
        )
    return detections


# ---------------------------------------------------------------------------
# Async wrapper for background loop use
# ---------------------------------------------------------------------------

async def run_privacy_scan_async(app) -> list[dict]:
    """Async wrapper: run_privacy_scan in a thread pool."""
    return await asyncio.to_thread(run_privacy_scan, app)


# ---------------------------------------------------------------------------
# Background loop (same pattern as _auto_triage_loop in triage.py)
# ---------------------------------------------------------------------------

async def _privacy_scan_loop(app, interval_sec: int = 300) -> None:
    """Run privacy scan every interval_sec seconds. Non-fatal.

    Scans immediately on first iteration so hits populate at startup
    (mirrors feed_sync.py sync-first pattern).
    """
    # Short initial delay to let the privacy blocklist worker finish its
    # first sync before we scan (PrivacyWorker also runs immediately now).
    await asyncio.sleep(30)
    while True:
        try:
            await run_privacy_scan_async(app)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("privacy_scan_loop: unhandled error: %s", exc)
        await asyncio.sleep(interval_sec)


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@router.get("/hits")
async def get_privacy_hits(request: Request):
    """Return recent privacy detections (detection_source='privacy')."""
    try:
        sqlite_store = request.app.state.stores.sqlite
        rows = await asyncio.to_thread(
            lambda: sqlite_store._conn.execute(_HITS_SQL).fetchall()
        )
        hits = [
            {
                "id": r[0],
                "rule_id": r[1],
                "rule_name": r[2],
                "severity": r[3],
                "matched_event_ids": json.loads(r[4]) if r[4] else [],
                "created_at": r[5],
                "entity_key": r[6],
            }
            for r in rows
        ]
        return JSONResponse({"hits": hits})
    except Exception as exc:
        logger.warning("GET /api/privacy/hits failed: %s", exc)
        return JSONResponse({"hits": [], "error": str(exc)})


@router.get("/feeds")
async def get_privacy_feeds(request: Request):
    """Return blocklist feed sync status."""
    try:
        privacy_store = request.app.state.privacy_store
        if privacy_store is None:
            return JSONResponse({"feeds": []})
        feeds = await asyncio.to_thread(privacy_store.get_feed_status)
        domain_count = await asyncio.to_thread(privacy_store.get_domain_count)
        return JSONResponse({"feeds": feeds, "domain_count": domain_count})
    except Exception as exc:
        logger.warning("GET /api/privacy/feeds failed: %s", exc)
        return JSONResponse({"feeds": [], "domain_count": 0, "error": str(exc)})


@router.post("/scan")
async def trigger_privacy_scan(request: Request):
    """Manually trigger a privacy scan cycle. Returns detections found."""
    try:
        detections = await run_privacy_scan_async(request.app)
        return JSONResponse({"triggered": True, "detections_found": len(detections)})
    except Exception as exc:
        logger.warning("POST /api/privacy/scan failed: %s", exc)
        return JSONResponse({"triggered": False, "error": str(exc)}, status_code=500)


@router.get("/http-events")
async def get_recent_http_events(request: Request):
    """Return recent HTTP events with tracker domain flagging for the Privacy view."""
    try:
        duckdb_store = request.app.state.stores.duckdb
        privacy_store = request.app.state.privacy_store

        rows = await asyncio.to_thread(_query_http_events, duckdb_store, _RECENT_HTTP_SQL, 0)

        def flag_row(row: dict) -> dict:
            domain = (row.get("domain") or "").lower()
            is_tracker = _is_tracker(privacy_store, domain) if privacy_store else False
            ts = row.get("timestamp")
            return {
                "event_id": row.get("event_id"),
                "src_ip": row.get("src_ip"),
                "domain": domain,
                "uri": row.get("http_uri"),
                "method": row.get("http_method"),
                "status": row.get("http_status_code"),
                "user_agent": row.get("http_user_agent"),
                "req_bytes": row.get("http_request_body_len"),
                "resp_bytes": row.get("http_response_body_len"),
                "mime": row.get("http_resp_mime_type"),
                "is_tracker": is_tracker,
                "timestamp": str(ts) if ts else None,
            }

        events = [flag_row(r) for r in rows]
        tracker_count = sum(1 for e in events if e["is_tracker"])
        return JSONResponse({"events": events, "total": len(events), "tracker_count": tracker_count})
    except Exception as exc:
        logger.warning("GET /api/privacy/http-events failed: %s", exc)
        return JSONResponse({"events": [], "total": 0, "tracker_count": 0, "error": str(exc)})


@router.get("/dns-events")
async def get_recent_dns_events(request: Request):
    """Return recent DNS queries with tracker domain flagging for the Privacy view."""
    try:
        duckdb_store = request.app.state.stores.duckdb
        privacy_store = request.app.state.privacy_store

        rows = await asyncio.to_thread(_query_http_events, duckdb_store, _RECENT_DNS_SQL, 0)

        def flag_dns(row: dict) -> dict:
            query = (row.get("dns_query") or "").lower().rstrip(".")
            is_tracker = _is_tracker(privacy_store, query) if (privacy_store and query) else False
            ts = row.get("timestamp")
            return {
                "event_id": row.get("event_id"),
                "src_ip": row.get("src_ip"),
                "query": query,
                "qtype": row.get("dns_query_type"),
                "answers": row.get("dns_answers"),
                "is_tracker": is_tracker,
                "timestamp": str(ts) if ts else None,
            }

        events = [flag_dns(r) for r in rows]
        tracker_count = sum(1 for e in events if e["is_tracker"])
        return JSONResponse({"events": events, "total": len(events), "tracker_count": tracker_count})
    except Exception as exc:
        logger.warning("GET /api/privacy/dns-events failed: %s", exc)
        return JSONResponse({"events": [], "total": 0, "tracker_count": 0, "error": str(exc)})


@router.get("/tls-events")
async def get_recent_tls_events(request: Request):
    """Return recent TLS connection flows.

    Note: Malcolm/Suricata session records don't carry SNI in the stored format.
    Events show src_ip → dst_ip:port without hostname. Use dns-events for
    hostname-based tracker detection on encrypted traffic.
    """
    try:
        duckdb_store = request.app.state.stores.duckdb

        rows = await asyncio.to_thread(_query_http_events, duckdb_store, _RECENT_TLS_SQL, 0)

        def format_tls(row: dict) -> dict:
            ts = row.get("timestamp")
            return {
                "event_id": row.get("event_id"),
                "src_ip": row.get("src_ip"),
                "dst_ip": row.get("dst_ip"),
                "dst_port": row.get("dst_port"),
                "tls_version": row.get("tls_version"),
                "ja3": row.get("tls_ja3"),
                "timestamp": str(ts) if ts else None,
            }

        events = [format_tls(r) for r in rows]
        return JSONResponse({"events": events, "total": len(events)})
    except Exception as exc:
        logger.warning("GET /api/privacy/tls-events failed: %s", exc)
        return JSONResponse({"events": [], "total": 0, "error": str(exc)})


# Keep ssl-events as an alias for backward compatibility
@router.get("/ssl-events")
async def get_recent_ssl_events(request: Request):
    """Alias for /tls-events (backward compat)."""
    return await get_recent_tls_events(request)
