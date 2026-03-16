"""Normalize raw event dicts into NormalizedEvent shape.

Phase 2 changes:
  - accept IngestSource hint (passed by route handlers)
  - call enrichment pipeline after field mapping
"""
import uuid
from backend.src.api.models import NormalizedEvent, IngestSource
from backend.src.ingestion.enricher import enrich


def normalize(raw: dict, source: IngestSource = IngestSource.api) -> NormalizedEvent:
    """Map a raw dict to NormalizedEvent and apply enrichment pipeline.

    Args:
        raw:    Inbound event dict (from API, fixture, syslog, or Vector).
        source: Where this event originated — used for auditing and filtering.

    Returns:
        Enriched NormalizedEvent.
    """
    event = NormalizedEvent(
        id=str(uuid.uuid4()),
        timestamp=raw.get("timestamp", ""),
        host=raw.get("host", "unknown"),
        src_ip=raw.get("src_ip"),
        dst_ip=raw.get("dst_ip"),
        event_type=raw.get("event", raw.get("event_type", "unknown")),
        query=raw.get("query"),
        port=_safe_int(raw.get("port")),
        protocol=raw.get("protocol"),
        severity=raw.get("severity", "info"),
        source=source,
        user=raw.get("user"),
        raw=raw,
    )
    return enrich(event)


def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
