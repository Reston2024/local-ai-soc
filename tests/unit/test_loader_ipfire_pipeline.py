"""
Pipeline test: IngestionLoader._write_graph() calls extract_perimeter_entities()
for IPFire syslog events and persists the resulting edges to SQLiteStore.

Exercises the loader pipeline path — not just the pure function.

NOTE: SQLiteStore does not have get_edges_for_entity(). Instead we use:
  - get_edges_from(entity_id, depth=1) for outbound edges from a source entity
  - get_entity(entity_id) for entity lookup
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.event import NormalizedEvent
from backend.stores.sqlite_store import SQLiteStore
from ingestion.loader import IngestionLoader


def _make_ipfire_event(
    event_id: str,
    event_outcome: str,
    src_ip: str | None,
    dst_ip: str,
    tags: list[str],
) -> NormalizedEvent:
    # NormalizedEvent.tags is a comma-separated str (not a list).
    # ingested_at is required by the model.
    return NormalizedEvent(
        event_id=event_id,
        source_type="ipfire_syslog",
        event_type="network_firewall",
        event_outcome=event_outcome,
        severity="medium",
        src_ip=src_ip,
        dst_ip=dst_ip,
        tags=",".join(tags) if tags else None,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ingested_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _make_stores(tmp_path: Path):
    """Build a Stores-like mock with a real SQLiteStore for graph writes."""
    sqlite = SQLiteStore(str(tmp_path / "test.db"))

    # DuckDB mock — deduplication returns empty (all events are "new"),
    # execute_write is a no-op.
    duckdb = MagicMock()
    duckdb.fetch_all = AsyncMock(return_value=[])   # no duplicates
    duckdb.execute_write = AsyncMock(return_value=None)

    # Chroma mock — embed_batch returns empty embeddings (non-fatal path)
    chroma = MagicMock()

    stores = MagicMock()
    stores.sqlite = sqlite
    stores.duckdb = duckdb
    stores.chroma = chroma
    return stores, sqlite


def _make_ollama():
    ollama = MagicMock()
    ollama.embed_batch = AsyncMock(return_value=[[]])
    return ollama


@pytest.mark.asyncio
async def test_loader_ipfire_drop_produces_blocks_edge(tmp_path):
    """IPFire DROP event via loader -> blocks edge in SQLite."""
    stores, sqlite = _make_stores(tmp_path)
    loader = IngestionLoader(stores, _make_ollama())

    event = _make_ipfire_event(
        event_id="ipfire-drop-001",
        event_outcome="failure",
        src_ip="10.0.0.1",
        dst_ip="8.8.8.8",
        tags=["zone:red"],
    )

    result = await loader.ingest_events([event])
    assert result.edges_created >= 1, f"Expected >=1 edges, got {result.edges_created}"

    # get_edges_from returns outbound edges from the source entity
    edges = sqlite.get_edges_from("firewall_zone:red", depth=1)
    assert edges, "No edges found for firewall_zone:red in SQLite"
    edge_types = [e["edge_type"] for e in edges]
    assert "blocks" in edge_types, f"Expected blocks edge, got: {edge_types}"


@pytest.mark.asyncio
async def test_loader_ipfire_forward_produces_traverses_edge(tmp_path):
    """IPFire FORWARDFW event (src + dst) via loader -> traverses edge in SQLite."""
    stores, sqlite = _make_stores(tmp_path)
    loader = IngestionLoader(stores, _make_ollama())

    event = _make_ipfire_event(
        event_id="ipfire-fwd-001",
        event_outcome="success",
        src_ip="192.168.1.10",
        dst_ip="1.2.3.4",
        tags=["zone:green"],
    )

    result = await loader.ingest_events([event])
    assert result.edges_created >= 1

    edges = sqlite.get_edges_from("firewall_zone:green", depth=1)
    assert edges, "No edges found for firewall_zone:green in SQLite"
    edge_types = [e["edge_type"] for e in edges]
    assert "traverses" in edge_types, f"Expected traverses edge, got: {edge_types}"


@pytest.mark.asyncio
async def test_loader_non_ipfire_no_firewall_zone_entity(tmp_path):
    """Non-IPFire event via loader -> no firewall_zone entity written."""
    stores, sqlite = _make_stores(tmp_path)
    loader = IngestionLoader(stores, _make_ollama())

    event = NormalizedEvent(
        event_id="win-001",
        source_type="windows_evtx",
        event_type="logon_success",
        severity="low",
        hostname="WORKSTATION1",
        username="alice",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ingested_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    await loader.ingest_events([event])

    # No firewall_zone entity should exist
    entity = sqlite.get_entity("firewall_zone:red")
    assert entity is None, "firewall_zone entity created for non-IPFire event"
