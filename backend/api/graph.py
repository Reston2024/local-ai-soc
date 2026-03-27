"""
Graph API — entity and relationship management for the investigation graph.

Endpoints:
  GET  /graph/entity/{entity_id}         — single entity + its edges
  POST /graph/entity                     — create/update an entity node
  POST /graph/edge                       — create a directed edge
  GET  /graph/traverse/{entity_id}       — multi-hop graph traversal
  GET  /graph/case/{case_id}             — full graph for a case
  DELETE /graph/entity/{entity_id}       — remove entity and its edges
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.core.logging import get_logger
from backend.models.event import GraphResponse

log = get_logger(__name__)
router = APIRouter(prefix="/graph", tags=["graph"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateEntityRequest(BaseModel):
    type: str = Field(
        description=(
            "host | user | process | file | network | domain | ip | "
            "detection | evidence | case | technique"
        )
    )
    name: str = Field(min_length=1)
    attributes: Optional[dict[str, Any]] = None
    case_id: Optional[str] = None
    entity_id: Optional[str] = None  # If omitted, derived from type+name


class CreateEdgeRequest(BaseModel):
    source_type: str
    source_id: str
    edge_type: str = Field(
        description=(
            "spawned | wrote | read | connected_to | resolved | "
            "triggered | belongs_to | related_to"
        )
    )
    target_type: str
    target_id: str
    properties: Optional[dict[str, Any]] = None


def _derive_entity_id(entity_type: str, name: str) -> str:
    """Derive a stable entity ID from type+name (SHA-256 prefix)."""
    raw = f"{entity_type}:{name}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


# ---------------------------------------------------------------------------
# POST /graph/entity
# ---------------------------------------------------------------------------


@router.post("/entity", status_code=201)
async def create_entity(body: CreateEntityRequest, request: Request) -> JSONResponse:
    """Create or update a graph entity node."""
    stores = request.app.state.stores

    entity_id = body.entity_id or _derive_entity_id(body.type, body.name)

    await asyncio.to_thread(
        stores.sqlite.upsert_entity,
        entity_id,
        body.type,
        body.name,
        body.attributes,
        body.case_id,
    )

    log.debug("Entity upserted", entity_id=entity_id, type=body.type, name=body.name)
    return JSONResponse(
        status_code=201,
        content={"entity_id": entity_id, "type": body.type, "name": body.name},
    )


# ---------------------------------------------------------------------------
# GET /graph/entities   (list all entities, optional type filter)
# ---------------------------------------------------------------------------


@router.get("/entities")
async def list_entities(
    request: Request,
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(100, ge=1, le=1000),
) -> JSONResponse:
    """List all known graph entities, optionally filtered by type."""
    stores = request.app.state.stores

    def _list() -> list[dict]:
        cur = stores.sqlite._conn.execute(
            "SELECT id, type, name, attributes, case_id, created_at FROM entities ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        import json as _json
        result = []
        for row in rows:
            d = dict(zip(cols, row))
            if entity_type and d.get("type") != entity_type:
                continue
            if isinstance(d.get("attributes"), str):
                try:
                    d["attributes"] = _json.loads(d["attributes"])
                except Exception:
                    pass
            result.append(d)
        return result

    entities = await asyncio.to_thread(_list)
    return JSONResponse(content={"entities": entities, "total": len(entities)})


# ---------------------------------------------------------------------------
# GET /graph/entity/{entity_id}
# ---------------------------------------------------------------------------


@router.get("/entity/{entity_id}")
async def get_entity(entity_id: str, request: Request) -> JSONResponse:
    """Return a single entity and its direct neighbours."""
    stores = request.app.state.stores

    entity = await asyncio.to_thread(stores.sqlite.get_entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id!r} not found")

    outbound, inbound = await asyncio.to_thread(stores.sqlite.get_neighbours, entity_id)

    return JSONResponse(
        content={
            "entity": entity,
            "outbound_edges": outbound,
            "inbound_edges": inbound,
        }
    )


# ---------------------------------------------------------------------------
# POST /graph/edge
# ---------------------------------------------------------------------------


@router.post("/edge", status_code=201)
async def create_edge(body: CreateEdgeRequest, request: Request) -> JSONResponse:
    """Create a directed edge between two entities."""
    stores = request.app.state.stores

    edge_id = await asyncio.to_thread(
        stores.sqlite.insert_edge,
        body.source_type,
        body.source_id,
        body.edge_type,
        body.target_type,
        body.target_id,
        body.properties,
    )

    if edge_id is None:
        return JSONResponse(
            status_code=200,
            content={
                "status": "already_exists",
                "source_id": body.source_id,
                "edge_type": body.edge_type,
                "target_id": body.target_id,
            },
        )

    log.debug(
        "Edge created",
        edge_id=edge_id,
        source=body.source_id,
        edge_type=body.edge_type,
        target=body.target_id,
    )
    return JSONResponse(
        status_code=201,
        content={
            "edge_id": edge_id,
            "source_id": body.source_id,
            "edge_type": body.edge_type,
            "target_id": body.target_id,
        },
    )


# ---------------------------------------------------------------------------
# GET /graph/traverse/{entity_id}
# ---------------------------------------------------------------------------


@router.get("/traverse/{entity_id}")
async def traverse(
    entity_id: str,
    request: Request,
    depth: int = Query(2, ge=1, le=5, description="Maximum traversal depth"),
) -> JSONResponse:
    """
    Multi-hop graph traversal starting from entity_id.

    Returns the GraphResponse (entities + edges) reachable within the
    given depth.  The root entity is always included.
    """
    stores = request.app.state.stores

    # Verify root entity exists
    root = await asyncio.to_thread(stores.sqlite.get_entity, entity_id)
    if not root:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id!r} not found")

    edges_raw = await asyncio.to_thread(stores.sqlite.get_edges_from, entity_id, depth)

    # Collect unique entity IDs to fetch
    entity_ids: set[str] = {entity_id}
    for edge in edges_raw:
        entity_ids.add(edge["source_id"])
        entity_ids.add(edge["target_id"])

    def _fetch_entities(ids: set[str]) -> list[dict]:
        result = []
        for eid in ids:
            e = stores.sqlite.get_entity(eid)
            if e:
                result.append(e)
        return result

    entities_raw = await asyncio.to_thread(_fetch_entities, entity_ids)

    response = GraphResponse.from_stores(
        entities=entities_raw,
        edges=edges_raw,
        root_entity_id=entity_id,
        depth=depth,
    )

    log.debug(
        "Graph traversal",
        root=entity_id,
        depth=depth,
        entities=response.total_entities,
        edges=response.total_edges,
    )
    return JSONResponse(content=response.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# GET /graph/case/{case_id}
# ---------------------------------------------------------------------------


@router.get("/case/{case_id}")
async def get_case_graph(case_id: str, request: Request) -> JSONResponse:
    """
    Return the complete entity graph for a given investigation case.

    Includes all entities associated with the case and all edges between them.
    """
    stores = request.app.state.stores

    entities_raw = await asyncio.to_thread(stores.sqlite.get_entities_by_case, case_id)
    if not entities_raw:
        return JSONResponse(
            content={
                "case_id": case_id,
                "entities": [],
                "edges": [],
                "total_entities": 0,
                "total_edges": 0,
            }
        )

    entity_ids = {e["id"] for e in entities_raw}

    def _fetch_edges(ids: set[str]) -> list[dict]:
        all_edges: list[dict] = []
        seen: set[int] = set()
        for eid in ids:
            for edge in stores.sqlite.get_edges_from(eid, depth=1):
                # Only include edges where both ends are in the case
                if edge["target_id"] in ids:
                    # Deduplicate by (source_id, edge_type, target_id)
                    key = hash((edge["source_id"], edge["edge_type"], edge["target_id"]))
                    if key not in seen:
                        seen.add(key)
                        all_edges.append(edge)
        return all_edges

    edges_raw = await asyncio.to_thread(_fetch_edges, entity_ids)

    response = GraphResponse.from_stores(
        entities=entities_raw,
        edges=edges_raw,
        root_entity_id=None,
        depth=None,
    )

    return JSONResponse(content={"case_id": case_id, **response.model_dump(mode="json")})


# ---------------------------------------------------------------------------
# DELETE /graph/entity/{entity_id}
# ---------------------------------------------------------------------------


@router.delete("/entity/{entity_id}", status_code=200)
async def delete_entity(entity_id: str, request: Request) -> JSONResponse:
    """
    Remove an entity and all its associated edges.

    This is a destructive operation and cannot be undone.
    """
    stores = request.app.state.stores

    entity = await asyncio.to_thread(stores.sqlite.get_entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id!r} not found")

    def _delete(eid: str) -> int:
        cur = stores.sqlite._conn.execute(
            "DELETE FROM edges WHERE source_id = ? OR target_id = ?", (eid, eid)
        )
        edge_count = cur.rowcount
        stores.sqlite._conn.execute("DELETE FROM entities WHERE id = ?", (eid,))
        stores.sqlite._conn.commit()
        return edge_count

    edges_deleted = await asyncio.to_thread(_delete, entity_id)
    log.info("Entity deleted", entity_id=entity_id, edges_removed=edges_deleted)

    return JSONResponse(
        content={
            "entity_id": entity_id,
            "status": "deleted",
            "edges_removed": edges_deleted,
        }
    )
