"""OpenSearch indexing sink — Phase 3 (unconditional, OPENSEARCH_URL must be set in env).

This module indexes NormalizedEvent objects to OpenSearch.
OPENSEARCH_URL must be set in the environment (e.g. http://opensearch:9200).
If OPENSEARCH_URL is absent, try_index() returns False immediately without
attempting a network connection (avoids constructing a broken URL).

Connection:
  OPENSEARCH_URL  — e.g. http://opensearch:9200 (docker-compose service name)
  INDEX_NAME      — default: soc-events

Usage (called from routes.py):
  from backend.src.ingestion.opensearch_sink import try_index
  try_index(event)  # returns False gracefully when OpenSearch not reachable
"""
import os
import json
import logging
from backend.src.api.models import NormalizedEvent

logger = logging.getLogger(__name__)

OPENSEARCH_URL: str | None = os.getenv("OPENSEARCH_URL")
INDEX_NAME: str = os.getenv("OPENSEARCH_INDEX", "soc-events")

# httpx client (lazy, None until first use)
_client = None


def _get_client():
    """Return a shared httpx.Client, creating on first call."""
    global _client
    if _client is None:
        try:
            import httpx  # already in project deps
            _client = httpx.Client(timeout=5.0)
        except ImportError:
            logger.warning("httpx not available — OpenSearch sink disabled")
    return _client


def try_index(event: NormalizedEvent) -> bool:
    """Index event to OpenSearch. Returns True on success, False otherwise.

    Always attempts indexing. Returns False gracefully on connection failure or missing URL.
    """
    if not OPENSEARCH_URL:
        return False

    client = _get_client()
    if client is None:
        return False

    url = f"{OPENSEARCH_URL}/{INDEX_NAME}/_doc/{event.id}"
    payload = event.model_dump()
    payload["source"] = payload["source"] if isinstance(payload["source"], str) else payload["source"].value

    try:
        r = client.put(url, content=json.dumps(payload),
                       headers={"Content-Type": "application/json"})
        if r.status_code not in (200, 201):
            logger.debug("OpenSearch index failed: %s %s", r.status_code, r.text[:200])
            return False
        return True
    except Exception as exc:
        logger.debug("OpenSearch sink error (non-fatal): %s", exc)
        return False
