"""Normalize raw event dicts into NormalizedEvent shape."""
import uuid
from backend.src.api.models import NormalizedEvent

def normalize(raw: dict) -> NormalizedEvent:
    return NormalizedEvent(
        id=str(uuid.uuid4()),
        timestamp=raw.get("timestamp", ""),
        host=raw.get("host", "unknown"),
        src_ip=raw.get("src_ip"),
        dst_ip=raw.get("dst_ip"),
        event_type=raw.get("event", raw.get("event_type", "unknown")),
        query=raw.get("query"),
        port=raw.get("port"),
        protocol=raw.get("protocol"),
        severity=raw.get("severity", "info"),
        raw=raw,
    )
