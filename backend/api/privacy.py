"""Phase 53: Privacy monitoring — detection scanner + REST API.

Scanner: run_privacy_scan(app) — queries DuckDB for HTTP events exceeding thresholds,
filters against PrivacyBlocklistStore, inserts detection records.

Module-level helpers _query_http_events and _is_tracker are exposed for unit-test
patching (same testability pattern used in Phase 43/48/49).

API:
  GET /api/privacy/hits   — list detections with detection_source='privacy'
  GET /api/privacy/feeds  — blocklist feed status
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Router — exported as both `router` (test stub contract) and `privacy_router`
# (plan wiring alias).
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/privacy", tags=["privacy"])
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
    """Synchronous helper: query DuckDB for HTTP events matching threshold.

    Exposed at module level so tests can patch backend.api.privacy._query_http_events.
    In production, called inside asyncio.to_thread().
    """
    import duckdb as _duckdb
    conn = duckdb_store.get_read_conn()
    try:
        rows = conn.execute(sql, [threshold]).fetchall()
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
    """Scan recent HTTP events for cookie exfil and tracking pixels.

    Synchronous for unit-test compatibility (Wave-0 stubs call without await).
    Background loop wraps this via asyncio.to_thread().

    Returns: list of detection dicts with keys:
        hit_type, rule_id, rule_name, detection_source, entity_key,
        event_id, domain, body_len, mime_type (optional)
    """
    try:
        duckdb_store = app.state.duckdb_store
        privacy_store = app.state.privacy_store
        sqlite_store = app.state.sqlite_store
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
            # Persist to SQLite
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

    if detections:
        cookie_count = sum(1 for d in detections if d["hit_type"] == "cookie_exfil")
        pixel_count = sum(1 for d in detections if d["hit_type"] == "tracking_pixel")
        logger.info(
            "privacy_scan: findings cookie_exfil=%d tracking_pixel=%d",
            cookie_count, pixel_count,
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
    """Run privacy scan every interval_sec seconds. Non-fatal."""
    while True:
        try:
            await asyncio.sleep(interval_sec)
            await run_privacy_scan_async(app)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("privacy_scan_loop: unhandled error: %s", exc)


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@router.get("/hits")
async def get_privacy_hits(request: Request):
    """Return recent privacy detections (detection_source='privacy')."""
    try:
        sqlite_store = request.app.state.sqlite_store
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
        return JSONResponse({"feeds": feeds})
    except Exception as exc:
        logger.warning("GET /api/privacy/feeds failed: %s", exc)
        return JSONResponse({"feeds": [], "error": str(exc)})
