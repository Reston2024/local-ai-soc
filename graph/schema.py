"""
Entity and edge type definitions for the AI-SOC-Brain investigation graph.

These constants are used throughout the graph builder, entity extractor,
and API layer to ensure consistent type strings.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Entity (node) types
# ---------------------------------------------------------------------------

ENTITY_TYPES: list[str] = [
    "host",               # Workstation, server, or network device (ECS: host.hostname)
    "user",               # Windows / Linux user account (ECS: user.name, user.domain)
    "process",            # Running process instance (ECS: process.name, process.pid, process.executable)
    "file",               # File on disk (PE, script, document, …)
    "network_connection", # A specific connection tuple (src:port → dst:port) (ECS: network.protocol, source/destination.ip)
    "domain",             # Fully-qualified domain name (ECS: dns.question.name)
    "ip",                 # IP address (v4 or v6) (ECS: destination.ip)
    "detection",          # A detection/alert produced by a rule
    "artifact",           # Generic forensic artifact (registry key, service, …)
    "incident",           # A grouped investigation case
    "attack_technique",   # MITRE ATT&CK technique node (e.g. T1059.001)
]

# ---------------------------------------------------------------------------
# Edge (relationship) types
# ---------------------------------------------------------------------------

EDGE_TYPES: list[str] = [
    "executed_by",    # process → user: this process ran under this account
    "ran_on",         # process → host: this process ran on this host
    "accessed",       # process → file: process opened/read/wrote file
    "connected_to",   # process → ip: process made a network connection
    "resolved_to",    # domain → ip: DNS resolution result
    "triggered",      # event → detection: event caused a rule to fire
    "maps_to",        # detection → attack_technique: MITRE mapping
    "part_of",        # entity → incident: entity is part of an investigation
    "spawned",        # parent_process → child_process: process creation
    "wrote",          # process → file: process wrote to file
    "logged_into",    # user → host: authentication event
    "related_to",     # generic catch-all relationship
]

# ---------------------------------------------------------------------------
# Type validation helpers
# ---------------------------------------------------------------------------

_ENTITY_TYPES_SET: frozenset[str] = frozenset(ENTITY_TYPES)
_EDGE_TYPES_SET: frozenset[str] = frozenset(EDGE_TYPES)


def is_valid_entity_type(entity_type: str) -> bool:
    """Return True if *entity_type* is a recognised entity type string."""
    return entity_type in _ENTITY_TYPES_SET


def is_valid_edge_type(edge_type: str) -> bool:
    """Return True if *edge_type* is a recognised edge type string."""
    return edge_type in _EDGE_TYPES_SET
