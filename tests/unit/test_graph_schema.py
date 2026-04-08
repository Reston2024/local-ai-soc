"""Tests for phase-26 graph schema additions.

Covers:
- P26-T02: firewall_zone and network_segment added to ENTITY_TYPES
- P26-T03: blocks, permits, traverses added to EDGE_TYPES;
           extract_perimeter_entities() emits correct edge types
- P26-T04: additive-only guard — no pre-existing constants removed
"""

import pytest

# ---------------------------------------------------------------------------
# P26-T02: new entity types
# ---------------------------------------------------------------------------

ORIGINAL_ENTITY_TYPES = [
    "host",
    "user",
    "process",
    "file",
    "network_connection",
    "domain",
    "ip",
    "detection",
    "artifact",
    "incident",
    "attack_technique",
]

ORIGINAL_EDGE_TYPES = [
    "executed_by",
    "ran_on",
    "accessed",
    "connected_to",
    "resolved_to",
    "triggered",
    "maps_to",
    "part_of",
    "spawned",
    "wrote",
    "logged_into",
    "related_to",
]


def test_firewall_zone_in_entity_types():
    """firewall_zone must be present in ENTITY_TYPES and pass is_valid_entity_type (P26-T02)."""
    from graph.schema import ENTITY_TYPES, is_valid_entity_type

    assert "firewall_zone" in ENTITY_TYPES, "firewall_zone missing from ENTITY_TYPES"
    assert is_valid_entity_type("firewall_zone") is True


def test_network_segment_in_entity_types():
    """network_segment must be present in ENTITY_TYPES and pass is_valid_entity_type (P26-T02)."""
    from graph.schema import ENTITY_TYPES, is_valid_entity_type

    assert "network_segment" in ENTITY_TYPES, "network_segment missing from ENTITY_TYPES"
    assert is_valid_entity_type("network_segment") is True


# ---------------------------------------------------------------------------
# P26-T03: new edge types
# ---------------------------------------------------------------------------


def test_new_edge_types_present():
    """blocks, permits, traverses must all be in EDGE_TYPES and is_valid_edge_type (P26-T03)."""
    from graph.schema import EDGE_TYPES, is_valid_edge_type

    for edge in ("blocks", "permits", "traverses"):
        assert edge in EDGE_TYPES, f"{edge!r} missing from EDGE_TYPES"
        assert is_valid_edge_type(edge) is True, f"is_valid_edge_type({edge!r}) returned False"


# ---------------------------------------------------------------------------
# P26-T04: additive-only guard
# ---------------------------------------------------------------------------


def test_pre_existing_entity_types_preserved():
    """All 11 original entity types must still be present after schema expansion (P26-T04)."""
    from graph.schema import ENTITY_TYPES

    for entity_type in ORIGINAL_ENTITY_TYPES:
        assert entity_type in ENTITY_TYPES, (
            f"Pre-existing entity type {entity_type!r} was removed — schema must be additive only"
        )


def test_pre_existing_edge_types_preserved():
    """All 12 original edge types must still be present after schema expansion (P26-T04)."""
    from graph.schema import EDGE_TYPES

    for edge_type in ORIGINAL_EDGE_TYPES:
        assert edge_type in EDGE_TYPES, (
            f"Pre-existing edge type {edge_type!r} was removed — schema must be additive only"
        )


# ---------------------------------------------------------------------------
# P26-T03: extract_perimeter_entities() integration tests
# ---------------------------------------------------------------------------


def test_extract_perimeter_entities_blocks():
    """Given an ipfire_syslog event with failure outcome, expects a 'blocks' edge (P26-T03).

    extract_perimeter_entities() returns (entities, edges) — a two-tuple.
    The edge_type is determined by event_outcome: failure -> blocks.
    A dst_ip is required for the function to emit any output.
    """
    from ingestion.entity_extractor import extract_perimeter_entities
    from backend.models.event import NormalizedEvent
    from datetime import datetime, timezone

    event = NormalizedEvent(
        event_id="test-blocks-001",
        source_type="ipfire_syslog",
        event_type="network_firewall",
        event_outcome="failure",
        severity="medium",
        src_ip="10.0.0.1",
        dst_ip="8.8.8.8",
        tags="zone:red",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ingested_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    entities, edges = extract_perimeter_entities(event)
    edge_types = [e["edge_type"] for e in edges]
    assert "blocks" in edge_types, f"Expected 'blocks' edge for DROP event, got edge_types={edge_types!r}"
    entity_types = [e["type"] for e in entities]
    assert "firewall_zone" in entity_types, f"Expected firewall_zone entity, got: {entity_types}"


def test_extract_perimeter_entities_permits():
    """Given an ipfire_syslog event with success outcome and no src_ip, expects 'permits' edge (P26-T03).

    When event_outcome == 'success' but src_ip is None, edge_type is 'permits' (not 'traverses').
    A dst_ip is required for the function to emit any output.
    """
    from ingestion.entity_extractor import extract_perimeter_entities
    from backend.models.event import NormalizedEvent
    from datetime import datetime, timezone

    event = NormalizedEvent(
        event_id="test-permits-001",
        source_type="ipfire_syslog",
        event_type="network_firewall",
        event_outcome="success",
        severity="low",
        src_ip=None,
        dst_ip="1.2.3.4",
        tags="zone:green",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ingested_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    entities, edges = extract_perimeter_entities(event)
    edge_types = [e["edge_type"] for e in edges]
    assert "permits" in edge_types, f"Expected 'permits' edge for ACCEPT event, got edge_types={edge_types!r}"
