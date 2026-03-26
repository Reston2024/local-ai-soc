"""
Post-parsing event normalisation.

normalize_event() is a pure function (no I/O) that:
- Ensures event_id and ingested_at are populated
- Normalises severity to a controlled vocabulary
- Ensures timestamps are timezone-aware UTC datetimes
- Strips null bytes and control characters from string fields
- Strips prompt-injection patterns from string fields
- Truncates command_line and raw_event to 8 KB
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import uuid4

from backend.core.logging import get_logger
from backend.models.event import NormalizedEvent

log = get_logger(__name__)

_MAX_CMDLINE = 8 * 1024   # 8 KB
_MAX_RAW     = 8 * 1024   # 8 KB

# Compiled regex of known prompt-injection patterns (case-insensitive)
_INJECTION_PATTERNS = re.compile(
    r"(?i)(?:"
    r"ignore\s+previous\s+instructions?"
    r"|\[/?INST\]"
    r"|<\|(?:system|user|assistant)\|>"
    r"|###"
    r"|---SYSTEM"
    r"|---INSTRUCTION"
    r"|ignore\s+\S+\s+(?:instruction|prompt|context)"
    r")",
)


def _scrub_injection(text: str) -> str:
    """Strip prompt-injection patterns from a string field.

    Called after null-byte/_clean_str stripping (step 5 in normalize_event).
    Does NOT log the original value — caller is responsible for audit trail
    if needed.
    """
    return _INJECTION_PATTERNS.sub("", text).strip()


# Mapping of severity aliases to canonical values
_SEVERITY_MAP: dict[str, str] = {
    "critical": "critical",
    "crit":     "critical",
    "high":     "high",
    "hi":       "high",
    "medium":   "medium",
    "med":      "medium",
    "moderate": "medium",
    "warning":  "medium",
    "warn":     "medium",
    "low":      "low",
    "informational": "info",
    "information":   "info",
    "info":     "info",
    "debug":    "info",
    "verbose":  "info",
    "unknown":  "info",
}

# Regex that matches null bytes and C0/C1 control characters (except \t \n \r)
_CONTROL_RE = re.compile(r"[\x00\x01-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _strip_controls(value: str) -> str:
    """Remove null bytes and stray control characters from *value*."""
    return _CONTROL_RE.sub("", value)


def _clean_str(value: str | None) -> str | None:
    """Strip control characters; return None if the result is empty."""
    if value is None:
        return None
    cleaned = _strip_controls(value)
    return cleaned if cleaned else None


def _ensure_utc(dt: datetime) -> datetime:
    """Return *dt* as a timezone-aware UTC datetime."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_event(event: NormalizedEvent | dict) -> NormalizedEvent:
    """
    Return a new NormalizedEvent with normalised field values.

    This function is idempotent — calling it multiple times produces the
    same result as calling it once.

    Args:
        event: The raw event as produced by a parser, or a raw dict that
               will be coerced into a NormalizedEvent before normalisation.

    Returns:
        A new NormalizedEvent instance with all normalisation applied.
    """
    if isinstance(event, dict):
        # Provide defaults for required fields when accepting raw dicts
        raw = event.copy()
        raw.setdefault("event_id", str(uuid4()))
        now = datetime.now(tz=timezone.utc)
        raw.setdefault("timestamp", now)
        raw.setdefault("ingested_at", now)
        # Parse string timestamps to datetime so _ensure_utc() works correctly
        for _ts_field in ("timestamp", "ingested_at"):
            val = raw[_ts_field]
            if isinstance(val, str):
                try:
                    parsed = datetime.fromisoformat(val.replace("Z", "+00:00"))
                    raw[_ts_field] = parsed
                except ValueError:
                    raw[_ts_field] = now
        event = NormalizedEvent(**raw)
    updates: dict = {}

    # ------------------------------------------------------------------ #
    # 1. Ensure event_id
    # ------------------------------------------------------------------ #
    if not event.event_id or not event.event_id.strip():
        updates["event_id"] = str(uuid4())

    # ------------------------------------------------------------------ #
    # 2. Ensure ingested_at
    # ------------------------------------------------------------------ #
    now_utc = datetime.now(tz=timezone.utc)
    if not event.ingested_at:
        updates["ingested_at"] = now_utc
    else:
        updates["ingested_at"] = _ensure_utc(event.ingested_at)

    # ------------------------------------------------------------------ #
    # 3. Normalise timestamp → timezone-aware UTC
    # ------------------------------------------------------------------ #
    if event.timestamp:
        updates["timestamp"] = _ensure_utc(event.timestamp)
    else:
        updates["timestamp"] = now_utc

    # ------------------------------------------------------------------ #
    # 4. Normalise severity
    # ------------------------------------------------------------------ #
    if event.severity is not None:
        canon = _SEVERITY_MAP.get(event.severity.lower().strip())
        if canon:
            updates["severity"] = canon
        else:
            log.debug(
                "Unknown severity value — defaulting to info",
                event_id=event.event_id,
                severity=event.severity,
            )
            updates["severity"] = "info"

    # ------------------------------------------------------------------ #
    # 5. Strip null bytes / control chars from all string fields
    # ------------------------------------------------------------------ #
    for field_name in (
        "source_type", "source_file",
        "hostname", "username",
        "process_name", "parent_process_name",
        "file_path", "file_hash_sha256",
        "src_ip", "dst_ip", "domain", "url",
        "event_type", "detection_source",
        "attack_technique", "attack_tactic",
        "tags",
    ):
        raw_val = getattr(event, field_name, None)
        if isinstance(raw_val, str):
            cleaned = _clean_str(raw_val)
            if cleaned != raw_val:
                updates[field_name] = cleaned

    # ------------------------------------------------------------------ #
    # 6. Truncate command_line and raw_event to 8 KB
    # ------------------------------------------------------------------ #
    if event.command_line is not None:
        cl = _clean_str(event.command_line) or ""
        if len(cl.encode("utf-8")) > _MAX_CMDLINE:
            # Truncate at character boundary that keeps us under 8 KB
            encoded = cl.encode("utf-8")[:_MAX_CMDLINE]
            updates["command_line"] = encoded.decode("utf-8", errors="ignore")
        elif cl != event.command_line:
            updates["command_line"] = cl or None

    if event.raw_event is not None:
        re_val = event.raw_event
        if len(re_val.encode("utf-8")) > _MAX_RAW:
            encoded = re_val.encode("utf-8")[:_MAX_RAW]
            updates["raw_event"] = encoded.decode("utf-8", errors="ignore")

    # ------------------------------------------------------------------ #
    # 7. Strip prompt-injection patterns from risk-bearing string fields
    # ------------------------------------------------------------------ #
    # Operates on the already-cleaned values (incorporating step 5/6 updates)
    def _current(field: str) -> str | None:
        return updates.get(field, getattr(event, field, None))

    for _inj_field in ("command_line", "raw_event", "domain", "url", "file_path"):
        val = _current(_inj_field)
        if isinstance(val, str):
            scrubbed = _scrub_injection(val)
            if scrubbed != val:
                updates[_inj_field] = scrubbed or None

    # ------------------------------------------------------------------ #
    # Apply all collected updates atomically
    # ------------------------------------------------------------------ #
    if updates:
        return event.model_copy(update=updates)
    return event
