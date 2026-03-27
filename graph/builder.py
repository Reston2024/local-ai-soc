"""
Graph builder for subgraph retrieval.

get_entity_subgraph() assembles a GraphResponse centred on a single entity,
performing a breadth-first traversal of the SQLite edge table up to *depth*
hops.  Results are capped at *max_nodes* to prevent runaway responses on
dense graphs; when the cap is hit the response is still valid but nodes at
the frontier are elided.

Usage::

    from graph.builder import get_entity_subgraph
    response = await get_entity_subgraph(stores, "host:workstation01", depth=2)
"""

from __future__ import annotations

import asyncio
from collections import deque
from typing import Any

from backend.core.deps import Stores
from backend.core.logging import get_logger
from backend.models.event import GraphResponse

log = get_logger(__name__)


async def get_entity_subgraph(
    stores: Stores,
    entity_id: str,
    depth: int = 2,
    max_nodes: int = 100,
    entity_type_filter: list[str] | None = None,
) -> GraphResponse:
    """
    Build a subgraph centred on *entity_id*.

    Performs a bidirectional BFS (outgoing + incoming edges) up to *depth*
    hops from the root entity.  When the discovered node count exceeds
    *max_nodes*, expansion stops but already-queued edges are still returned.

    Args:
        stores:             Data store container.
        entity_id:          ID of the starting entity (e.g. "host:dc01").
        depth:              Maximum hop count (1 = direct neighbours only).
        max_nodes:          Soft limit on total nodes in response.
        entity_type_filter: If provided, only include entity types in this list.

    Returns:
        GraphResponse with entities and edges lists populated.
    """
    if depth < 1:
        depth = 1
    if depth > 10:
        depth = 10  # Hard cap to prevent runaway queries
    if max_nodes < 1:
        max_nodes = 1

    def _sync_build() -> GraphResponse:
        sqlite = stores.sqlite

        # BFS state
        visited_nodes: set[str] = set()
        visited_edges: set[tuple[str, str, str]] = set()  # (src, edge_type, tgt)
        frontier: deque[tuple[str, int]] = deque()  # (entity_id, current_depth)

        # Check root entity exists; create a stub if not
        root_entity_data = sqlite.get_entity(entity_id)
        if root_entity_data is None:
            # Entity not in SQLite — return empty graph
            log.warning("Root entity not found in graph", entity_id=entity_id)
            return GraphResponse(
                entities=[],
                edges=[],
                root_entity_id=entity_id,
                depth=depth,
                total_entities=0,
                total_edges=0,
            )

        visited_nodes.add(entity_id)
        frontier.append((entity_id, 0))

        collected_entity_ids: set[str] = {entity_id}
        collected_edges: list[dict[str, Any]] = []

        while frontier:
            current_id, current_depth = frontier.popleft()

            if current_depth >= depth:
                continue

            if len(collected_entity_ids) >= max_nodes:
                break

            # Outgoing edges
            out_edges = sqlite.get_edges_from(current_id, depth=1)
            for edge in out_edges:
                src_id = edge["source_id"]
                tgt_id = edge["target_id"]
                edge_key = (src_id, edge["edge_type"], tgt_id)
                if edge_key in visited_edges:
                    continue
                visited_edges.add(edge_key)

                # Apply entity type filter to target
                if entity_type_filter and edge["target_type"] not in entity_type_filter:
                    continue

                collected_edges.append(edge)

                if tgt_id not in collected_entity_ids:
                    if len(collected_entity_ids) < max_nodes:
                        collected_entity_ids.add(tgt_id)
                        frontier.append((tgt_id, current_depth + 1))

            # Incoming edges (reverse traversal)
            in_edges = sqlite.get_edges_to(current_id)
            for edge in in_edges:
                src_id = edge["source_id"]
                tgt_id = edge["target_id"]
                edge_key = (src_id, edge["edge_type"], tgt_id)
                if edge_key in visited_edges:
                    continue
                visited_edges.add(edge_key)

                # Apply entity type filter to source
                if entity_type_filter and edge["source_type"] not in entity_type_filter:
                    continue

                collected_edges.append(edge)

                if src_id not in collected_entity_ids:
                    if len(collected_entity_ids) < max_nodes:
                        collected_entity_ids.add(src_id)
                        frontier.append((src_id, current_depth + 1))

        # Fetch entity records for all collected IDs
        entity_records: list[dict[str, Any]] = []
        for eid in collected_entity_ids:
            entity_data = sqlite.get_entity(eid)
            if entity_data:
                # Apply type filter
                if entity_type_filter and entity_data.get("type") not in entity_type_filter:
                    continue
                entity_records.append(entity_data)
            else:
                # Entity ID referenced in edges but not in entities table
                # Create a minimal stub
                parts = eid.split(":", 1)
                entity_records.append({
                    "id": eid,
                    "type": parts[0] if len(parts) == 2 else "unknown",
                    "name": parts[1] if len(parts) == 2 else eid,
                    "attributes": None,
                    "case_id": None,
                    "created_at": None,
                })

        # Convert to model objects — only include edges where both endpoints
        # are in our collected set (may be pruned by max_nodes or type filter)
        valid_ids = {e["id"] for e in entity_records}
        filtered_edges = [
            e for e in collected_edges
            if e["source_id"] in valid_ids and e["target_id"] in valid_ids
        ]

        # Deduplicate edges by (source_id, edge_type, target_id)
        seen_edge_keys: set[tuple[str, str, str]] = set()
        deduped_edges: list[dict[str, Any]] = []
        for edge in filtered_edges:
            key = (edge["source_id"], edge["edge_type"], edge["target_id"])
            if key not in seen_edge_keys:
                seen_edge_keys.add(key)
                deduped_edges.append(edge)

        return GraphResponse.from_stores(
            entities=entity_records,
            edges=deduped_edges,
            root_entity_id=entity_id,
            depth=depth,
        )

    try:
        response = await asyncio.to_thread(_sync_build)
    except Exception as exc:
        log.error(
            "Graph builder error",
            entity_id=entity_id,
            depth=depth,
            error=str(exc),
        )
        raise

    log.info(
        "Subgraph built",
        entity_id=entity_id,
        depth=depth,
        nodes=response.total_entities,
        edges=response.total_edges,
    )
    return response


async def get_entity_neighbours(
    stores: Stores,
    entity_id: str,
    entity_type_filter: list[str] | None = None,
) -> GraphResponse:
    """
    Return the direct (depth=1) neighbours of an entity.

    Convenience wrapper around get_entity_subgraph().
    """
    return await get_entity_subgraph(
        stores=stores,
        entity_id=entity_id,
        depth=1,
        max_nodes=50,
        entity_type_filter=entity_type_filter,
    )
