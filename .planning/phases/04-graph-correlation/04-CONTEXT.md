# Phase 4: Graph + Correlation — Context

**Gathered:** 2026-03-15
**Status:** Ready for planning
**Source:** PRD Express Path (inline command args)

<domain>
## Phase Boundary

Phase 4 enhances the existing graph builder to correlate multiple security events and reconstruct attack paths across time. The system already has an in-memory event/alert store plus a `/graph` endpoint; this phase makes that endpoint meaningful for investigation by adding correlated edges, attack-path grouping, and a richer UI visualization.

Deliverables:
1. **Graph correlation engine** — links events, alerts, hosts, IPs, domains by shared entities and temporal proximity
2. **Extended graph builder** — `backend/src/graph/builder.py` generates correlated edges with timestamps + evidence refs, groups into attack paths
3. **Richer `/graph` API response** — correlated nodes/edges, evidence references per node
4. **Frontend graph enhancements** — attack path highlighting, node/edge detail inspection, correlation grouping
5. **Tests** — graph node generation, edge creation, correlation logic, alert-to-event linking, API responses
6. **Docs** — `docs/decision-log.md`, `docs/manifest.md`, `docs/reproducibility.md`

</domain>

<decisions>
## Implementation Decisions

### Graph Node Types (LOCKED)
Six node types, two optional:
- `host` — a machine (identified by hostname or IP)
- `ip` — a network address (src or dst IP in events)
- `domain` — a DNS query target
- `alert` — a fired detection alert (links back to its triggering event)
- `process` — optional; emit only if `process` field present in event data
- `user` — optional; emit only if `user` field present in event data

Node schema: `{id: str, type: NodeType, label: str, attributes: dict, first_seen: str, last_seen: str, evidence: list[str]}`

### Graph Edge Types (LOCKED)
Six edge types, one optional:
- `dns_query` — host → domain (from dns_query events)
- `connection` — ip → ip (from connection events with src_ip + dst_ip)
- `alert_trigger` — alert → host/ip/domain (alert fired against an entity)
- `related_event` — event A shares entity with event B (shared host/IP/domain)
- `observed_on` — ip/domain → host (entity seen originating from host)
- `process_spawn` — optional; process → process (only if parent_pid data present)

Edge schema: `{id: str, type: EdgeType, src: str, dst: str, timestamp: str, evidence_event_ids: list[str]}`

### Correlation Logic (LOCKED)
Four correlation patterns to detect:
1. **Repeated DNS to suspicious domain** — ≥2 events with same `query` field within any time window → `related_event` edges between them
2. **DNS → connection chain** — a `dns_query` event to domain X followed by a `connection` event to IP Y (within 60s same host) → `dns_query` + `connection` edges linking domain → ip → host
3. **Shared entity** — two or more alerts referencing the same `host`, `src_ip`, or `dst_ip` → `related_event` edges and merged `alert_trigger` edges
4. **Temporal proximity** — events from the same host within 30s window get `related_event` edges (max 10 edges per event to prevent explosion)

### Graph Builder Location (LOCKED)
Extend: `backend/src/graph/builder.py`
- `build_graph(events: list[dict], alerts: list[dict]) -> GraphResponse` — main entry point
- `_extract_nodes(events, alerts) -> dict[str, GraphNode]`
- `_extract_edges(events, alerts, nodes) -> list[GraphEdge]`
- `_correlate(events, nodes, edges) -> list[GraphEdge]` — runs 4 correlation patterns
- `_group_attack_paths(nodes, edges) -> list[AttackPath]` — connected component grouping

### API Response Schema (LOCKED)
`GET /graph` returns:
```json
{
  "nodes": [...],
  "edges": [...],
  "attack_paths": [
    {
      "id": "path-1",
      "node_ids": [...],
      "edge_ids": [...],
      "severity": "high",
      "first_event": "<iso>",
      "last_event": "<iso>"
    }
  ],
  "stats": {
    "node_count": N,
    "edge_count": N,
    "event_count": N,
    "alert_count": N
  }
}
```

### Compatibility (LOCKED)
- Existing `/graph` endpoint continues to accept same request (no breaking change)
- All Phase 2 ingestion routes preserved unchanged
- All Phase 3 Sigma + OpenSearch routes preserved unchanged
- All existing 41 tests must continue passing

### Pydantic Models
New models in `backend/src/api/models.py`:
- `GraphNode`, `GraphEdge`, `AttackPath`, `GraphResponse`
- Import `GraphResponse` in routes.py

### Frontend Location
- Extend `frontend/src/components/Graph.svelte` (or equivalent existing component)
- If no Graph component exists: create `frontend/src/components/GraphView.svelte`
- Attack path highlighting: CSS class `attack-path-highlight` on path nodes/edges
- Node detail: click → side panel showing `node.attributes` + `node.evidence`
- Edge detail: hover/click → tooltip showing `edge.evidence_event_ids`
- Correlation grouping: visually group nodes in same `attack_path` (e.g. light background fill)

### Claude's Discretion
- Whether to use networkx for graph algorithms or implement BFS/connected-components manually (prefer manual if networkx not already in deps — avoid adding new deps)
- Exact Svelte component structure and CSS styling (follow existing patterns)
- Whether `build_graph` is called inline in the route or via a service wrapper
- Test fixture design (synthetic events + alerts in test files)

</decisions>

<specifics>
## Specific Ideas

- Temporal window constants as module-level: `DNS_CHAIN_WINDOW_SEC = 60`, `PROXIMITY_WINDOW_SEC = 30`, `MAX_PROXIMITY_EDGES_PER_EVENT = 10`
- Node IDs: deterministic — e.g. `host:{hostname}`, `ip:{addr}`, `domain:{fqdn}`, `alert:{alert_id}`
- Edge IDs: `{type}:{src_id}:{dst_id}:{timestamp_ms}` (include timestamp to allow parallel edges)
- Attack path severity = max severity of any alert in the path; if no alerts, severity = "info"
- Frontend should call `GET /graph` via existing `api.ts` typed client (add `getGraph()` function)
- Graph API currently returns `{"nodes": [], "edges": []}` — extend to new schema while keeping nodes/edges keys intact

</specifics>

<deferred>
## Deferred Ideas

- Case management module — deferred to Phase 5
- SQLite persistence for graph nodes/edges — deferred to Phase 5
- `process_spawn` edges — implement only if process data present in test fixtures; otherwise scaffold with comment
- User nodes — implement only if user field populated in test data; otherwise scaffold
- Graph export (PNG/JSON download) — Phase 5
- Maximum node/edge limits + truncation metadata — Phase 5
- 2-hop entity expansion endpoint (`GET /graph/entity/{id}`) — Phase 5

</deferred>

---

*Phase: 04-graph-correlation*
*Context gathered: 2026-03-15 via PRD Express Path (inline)*
