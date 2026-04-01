"""
FieldMapper — centralised ECS dotted-path → NormalizedEvent snake_case translation.

Pure module: no I/O, no logging, no imports from backend.
Used by all four ingestion parsers to translate ECS-style keys before
NormalizedEvent construction.
"""

from __future__ import annotations

from typing import Any

# ECS dotted-path keys → NormalizedEvent / DuckDB column names (snake_case).
# PascalCase EVTX keys (Image, CommandLine, ...) are intentionally absent —
# those are already handled by the parser-level extraction logic.
_FIELD_VARIANTS: dict[str, str] = {
    # Process
    "process.name": "process_name",
    "process.pid": "process_id",
    "process.command_line": "command_line",
    "process.executable": "process_executable",
    "process.parent.name": "parent_process_name",
    "process.parent.pid": "parent_process_id",
    # User
    "user.name": "username",
    "user.domain": "user_domain",
    # Host
    "host.hostname": "hostname",
    "host.name": "hostname",
    # Network — source
    "source.ip": "src_ip",
    "source.port": "src_port",
    # Network — destination
    "destination.ip": "dst_ip",
    "destination.port": "dst_port",
    "destination.domain": "domain",
    # File
    "file.path": "file_path",
    "file.hash.sha256": "file_hash_sha256",
    # Network attributes
    "network.protocol": "network_protocol",
    "network.direction": "network_direction",
    # Event
    "event.action": "event_type",
    "event.outcome": "event_outcome",
    "event.original": "raw_event",
    # Threat
    "threat.technique.id": "attack_technique",
    "threat.tactic.name": "attack_tactic",
    # URL / DNS
    "url.original": "url",
    "dns.question.name": "domain",
}


class FieldMapper:
    """Translate a raw event dict's keys from ECS dotted-path to snake_case.

    Behaviour:
    - Keys present in _FIELD_VARIANTS are translated to their canonical name.
    - Unknown keys pass through unchanged.
    - Case-insensitive fallback: if exact key not found, try key.lower().
    """

    def map(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Return a new dict with ECS keys translated to NormalizedEvent field names."""
        result: dict[str, Any] = {}
        for k, v in raw.items():
            canonical = _FIELD_VARIANTS.get(k) or _FIELD_VARIANTS.get(k.lower())
            result[canonical if canonical else k] = v
        return result


__all__ = ["FieldMapper"]
