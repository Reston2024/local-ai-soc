# Phase 4: Graph + Correlation — Research

**Researched:** 2026-03-15
**Domain:** Graph correlation engine, connected-components clustering, FastAPI graph API, Cytoscape.js enhancements
**Confidence:** HIGH — all findings verified against the existing codebase directly

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Graph Node Types (LOCKED)** — Six node types, two optional:
- `host`, `ip`, `domain`, `alert` (always emitted when data present)
- `process` — optional; emit only if `process` field present in event data
- `user` — optional; emit only if `user` field present in event data

Node schema: `{id: str, type: NodeType, label: str, attributes: dict, first_seen: str, last_seen: str, evidence: list[str]}`

**Graph Edge Types (LOCKED)** — Six edge types, one optional:
- `dns_query`, `connection`, `alert_trigger`, `related_event`, `observed_on`
- `process_spawn` — optional; only if parent_pid data present

Edge schema: `{id: str, type: EdgeType, src: str, dst: str, timestamp: str, evidence_event_ids: list[str]}`

**Correlation Logic (LOCKED)** — Four patterns:
1. Repeated DNS to suspicious domain — ≥2 events same `query` → `related_event` edges
2. DNS→connection chain — `dns_query` to domain X followed by `connection` to IP Y within 60s same host
3. Shared entity — ≥2 alerts same `host`/`src_ip`/`dst_ip` → `related_event` + merged `alert_trigger`
4. Temporal proximity — same host events within 30s → `related_event` edges (max 10 per event)

**Graph Builder Location (LOCKED)** — Extend `backend/src/graph/builder.py`
Function signatures:
- `build_graph(events: list[dict], alerts: list[dict]) -> GraphResponse`
- `_extract_nodes(events, alerts) -> dict[str, GraphNode]`
- `_extract_edges(events, alerts, nodes) -> list[GraphEdge]`
- `_correlate(events, nodes, edges) -> list[GraphEdge]`
- `_group_attack_paths(nodes, edges) -> list[AttackPath]`

**API Response Schema (LOCKED)** — `GET /graph` returns:
```json
{
  "nodes": [...],
  "edges": [...],
  "attack_paths": [{"id","node_ids","edge_ids","severity","first_event","last_event"}],
  "stats": {"node_count","edge_count","event_count","alert_count"}
}
```

**Compatibility (LOCKED)**:
- Existing `/graph` endpoint keeps same request contract (no breaking changes)
- All Phase 2/3 routes preserved
- All 41 existing tests must continue passing

**Pydantic Models (LOCKED)** — New models in `backend/src/api/models.py`:
`GraphNode`, `GraphEdge`, `AttackPath`, `GraphResponse`

**Frontend Location (LOCKED)** — Extend `frontend/src/components/graph/ThreatGraph.svelte`
- Attack path highlighting: CSS class `attack-path-highlight`
- Node detail: click → side panel showing `node.attributes` + `node.evidence`
- Edge detail: hover/click → tooltip showing `edge.evidence_event_ids`
- Correlation grouping: visually group nodes in same `attack_path`

### Claude's Discretion
- Whether to use networkx or implement BFS/connected-components manually (prefer manual — no new deps)
- Exact Svelte component structure and CSS styling
- Whether `build_graph` is called inline in the route or via a service wrapper
- Test fixture design (synthetic events + alerts in test files)

### Deferred Ideas (OUT OF SCOPE)
- Case management module — Phase 5
- SQLite persistence for graph nodes/edges — Phase 5
- `process_spawn` edges — scaffold with comment unless test data has parent_pid
- User nodes — scaffold unless user field in test fixtures
- Graph export (PNG/JSON download) — Phase 5
- Maximum node/edge limits + truncation metadata — Phase 5
- 2-hop entity expansion endpoint (`GET /graph/entity/{id}`) — Phase 5
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FR-4.1 | Graph query service: expand(depth=N), path(src,tgt), subgraph(ids) over SQLite edges. Max depth 3, max 200 nodes. Each node includes DuckDB attributes. | Root-level `graph/builder.py` already implements BFS traversal over SQLite; extend pattern for path-finding. |
| FR-4.2 | `GET /graph/entity/{id}?depth=2` and `GET /graph/path?from&to`. Response: `{nodes,edges}`. | `backend/api/graph.py` already has `/graph/entity/{id}` and `/graph/traverse/{id}`; add path endpoint. |
| FR-4.3 | Event clustering: shared-entity cluster, temporal cluster (5 min), causal chain (PID tree). relatedness_score 0-1. | `correlation/clustering.py` already implements Union-Find entity clustering and sliding-window temporal clustering. |
| FR-4.4 | Alert aggregation into investigation threads (same process tree / user / 15 min). Thread includes: detection IDs, time range, entities, techniques. | New `correlation/aggregation.py` needed; builds on clustering patterns already in `correlation/clustering.py`. |
| FR-4.5 | `GET /graph/correlate?event_id={id}` returns all correlated events/detections/entities + investigation thread. | New route in `backend/api/graph.py`; calls clustering + aggregation + graph builder. |
</phase_requirements>

---

## Summary

Phase 4 builds on a **rich and already-functional codebase**. The project has two separate graph subsystems that must be reconciled: the in-memory `backend/src/graph/builder.py` used by the existing `/graph` route (Phase 2/3 system, `TestClient`-tested), and the richer production-ready `graph/builder.py` + `backend/api/graph.py` system that queries SQLite entities and edges. The CONTEXT.md decisions target the in-memory system (`backend/src/graph/builder.py`) which is what the 41 passing tests exercise.

The correlation engine also already has substantial infrastructure: `correlation/clustering.py` provides Union-Find shared-entity clustering and sliding-window temporal clustering with `relatedness_score`. These implementations can be reused or referenced directly. The missing pieces are: (1) the four correlation patterns added to the in-memory graph builder, (2) `AttackPath` model + connected-components grouping, (3) the `/graph/correlate` endpoint, and (4) alert aggregation into investigation threads.

The frontend graph component (`ThreatGraph.svelte`) already uses Cytoscape.js (^3.31.0) with COSE layout. The `getGraph()` API call uses the existing `GraphResponse` shape (`{nodes, edges}`). The Phase 4 API response adds `attack_paths` and `stats` fields — the frontend must be extended to consume these while the component's existing node/edge rendering continues to work.

**Primary recommendation:** Extend the in-memory builder at `backend/src/graph/builder.py` with the four correlation patterns and `AttackPath` grouping; update `backend/src/api/models.py` with the new Pydantic models; add the `/graph/correlate` route in `backend/src/api/routes.py`; extend `ThreatGraph.svelte` for attack path highlighting. Use Union-Find for connected-components — do not add networkx.

---

## Standard Stack

### Core (already installed — no new deps needed)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| Python stdlib `collections.deque` | stdlib | BFS frontier | Used in root-level `graph/builder.py` — same pattern applies |
| Python stdlib `collections.defaultdict` | stdlib | Reverse-index for clustering | Used in `correlation/clustering.py` |
| Pydantic v2 | >=2.0 (pinned) | GraphNode, GraphEdge, AttackPath models | Already in `backend/src/api/models.py` |
| FastAPI | 0.115.12 | Route handlers | `APIRouter` in `backend/src/api/routes.py` |
| Cytoscape.js | ^3.31.0 (in package.json) | Frontend graph rendering | Already used in `ThreatGraph.svelte` |

### No New Dependencies Required
The decisions explicitly prefer manual BFS/Union-Find over adding networkx. All necessary algorithms (BFS, Union-Find, sliding window) are already present in the codebase at `graph/builder.py` and `correlation/clustering.py`. There is nothing to install for Phase 4.

---

## Architecture Patterns

### Recommended Project Structure for Phase 4 Changes

```
backend/src/
├── api/
│   ├── models.py          ← ADD: GraphNode, GraphEdge, AttackPath, GraphResponse (new schema)
│   └── routes.py          ← ADD: GET /graph/correlate route
├── graph/
│   └── builder.py         ← EXTEND: build_graph(events, alerts), _correlate(), _group_attack_paths()
correlation/               ← REUSE for reference; correlation logic lives in builder.py per CONTEXT
frontend/src/
└── components/graph/
    └── ThreatGraph.svelte ← EXTEND: attack_paths display, node/edge detail panels
```

### Pattern 1: Deterministic Node IDs (already in builder.py)
**What:** Node IDs derived from type + value so the same entity always gets the same ID.
**When to use:** Any time a node is created.
**Pattern from existing code:**
```python
# From backend/src/graph/builder.py (existing)
nid = f"host:{host}"
nid = f"ip:{src_ip}"
nid = f"domain:{query}"
nid = f"alert:{alert_id}"
```
**Phase 4 additions per CONTEXT specifics:**
```python
# Edge IDs include timestamp_ms for parallel edges
edge_id = f"{edge_type}:{src_id}:{dst_id}:{timestamp_ms}"
```

### Pattern 2: Union-Find Connected Components (reference: correlation/clustering.py)
**What:** Merge events/nodes that share an entity into the same component without networkx.
**When to use:** `_group_attack_paths()` to group nodes into `AttackPath` objects.

```python
# Source: correlation/clustering.py (existing — reference pattern only)
parent = {node_id: node_id for node_id in nodes}

def find(x: str) -> str:
    while parent[x] != x:
        parent[x] = parent[parent[x]]  # path compression
        x = parent[x]
    return x

def union(x: str, y: str) -> None:
    px, py = find(x), find(y)
    if px != py:
        parent[px] = py

# For each edge, union the src and dst nodes
for edge in edges:
    if edge.src in parent and edge.dst in parent:
        union(edge.src, edge.dst)

# Collect components
groups: dict[str, list[str]] = defaultdict(list)
for node_id in nodes:
    groups[find(node_id)].append(node_id)
```

### Pattern 3: Correlation Pattern — DNS→Connection Chain
**What:** Link a dns_query event followed within 60s by a connection event on the same host.
**Key fields:** `event_type` (or `event`), `query` (domain), `host`, `timestamp`, `dst_ip`
**Implementation note:** The in-memory `_events` list stores NormalizedEvent dicts. The `query` field holds the DNS target. After building base nodes/edges, sort events by timestamp and pair dns_query events with subsequent connection events on the same host within `DNS_CHAIN_WINDOW_SEC = 60`.

```python
# Module-level constants (per CONTEXT specifics)
DNS_CHAIN_WINDOW_SEC = 60
PROXIMITY_WINDOW_SEC = 30
MAX_PROXIMITY_EDGES_PER_EVENT = 10
```

### Pattern 4: Temporal Proximity Edges
**What:** Events from the same host within 30s get `related_event` edges.
**Guard:** Cap at MAX_PROXIMITY_EDGES_PER_EVENT = 10 per event to prevent O(n²) explosion.
**Implementation:** Sort events by (host, timestamp). For each event, scan forward up to 30s; add edges until cap reached.

### Pattern 5: Pydantic Model Extension — Backward Compatibility
**Critical:** The existing `GET /graph` route returns `GraphResponse(nodes, edges)`. The test `test_graph_returns_nodes_and_edges` in `smoke_test.py` only checks `"nodes" in data` and `"edges" in data`. The new `GraphResponse` adds `attack_paths` and `stats` — this is backward compatible because it adds new keys without removing existing ones.

**Existing models.py GraphNode/GraphEdge must be replaced with the locked schema:**
```python
# CURRENT (to be replaced):
class GraphNode(BaseModel):
    id: str; type: str; label: str

class GraphEdge(BaseModel):
    id: str; source: str; target: str; type: str

class GraphResponse(BaseModel):
    nodes: list[GraphNode]; edges: list[GraphEdge]
```

```python
# PHASE 4 TARGET (backend/src/api/models.py):
class GraphNode(BaseModel):
    id: str
    type: str  # host|ip|domain|alert|process|user
    label: str
    attributes: dict = Field(default_factory=dict)
    first_seen: str = ""
    last_seen: str = ""
    evidence: list[str] = Field(default_factory=list)

class GraphEdge(BaseModel):
    id: str
    type: str  # dns_query|connection|alert_trigger|related_event|observed_on
    src: str
    dst: str
    timestamp: str = ""
    evidence_event_ids: list[str] = Field(default_factory=list)

class AttackPath(BaseModel):
    id: str
    node_ids: list[str]
    edge_ids: list[str]
    severity: str  # max severity of alerts in path; "info" if no alerts
    first_event: str
    last_event: str

class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    attack_paths: list[AttackPath] = Field(default_factory=list)
    stats: dict = Field(default_factory=dict)
```

**IMPORTANT:** The existing `ThreatGraph.svelte` maps `e.source` and `e.target` from edge data. The CONTEXT schema renames these to `src`/`dst`. The Cytoscape data mapping in the frontend must update from `{ source: e.source, target: e.target }` to `{ source: e.src, target: e.dst }`.

### Pattern 6: Attack Path Severity
**Rule from CONTEXT specifics:** severity = max severity of any alert in the path. If no alerts: severity = "info".
**Severity ordering:** `critical > high > medium > low > info`

```python
SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}

def _path_severity(path_node_ids: list[str], nodes: dict[str, GraphNode]) -> str:
    max_rank = 0
    max_sev = "info"
    for nid in path_node_ids:
        node = nodes.get(nid)
        if node and node.type == "alert":
            sev = node.attributes.get("severity", "info")
            if SEVERITY_RANK.get(sev, 0) > max_rank:
                max_rank = SEVERITY_RANK[sev]
                max_sev = sev
    return max_sev
```

### Pattern 7: build_graph() Signature Change
**Current:** `build_graph(events: list[dict]) -> GraphResponse`
**Phase 4 target:** `build_graph(events: list[dict], alerts: list[dict]) -> GraphResponse`

The route handler currently calls `build_graph(_events)`. It must be updated to `build_graph(_events, _alerts)`.

### Pattern 8: GET /graph/correlate Route
**New route** added to `backend/src/api/routes.py`:
```python
@router.get("/graph/correlate")
def get_graph_correlate(event_id: str):
    # 1. Find the event in _events
    # 2. Extract its entities (host, src_ip, dst_ip, query)
    # 3. Find all events sharing those entities
    # 4. Find all alerts triggered against those entities
    # 5. Build graph of correlated set
    # 6. Find the investigation thread (which attack_path contains this event's nodes)
    # Returns: {events, alerts, graph, investigation_thread}
```

### Anti-Patterns to Avoid

- **Adding networkx:** It's not in pyproject.toml. Implement BFS/Union-Find manually (already proven in correlation/clustering.py).
- **Modifying the `source`/`target` field names in GraphEdge without updating ThreatGraph.svelte:** The frontend uses `e.source`/`e.target` directly in Cytoscape `data`. The rename to `src`/`dst` requires a frontend update.
- **Breaking the existing GraphResponse shape:** The smoke test checks only for `nodes` and `edges` keys — safe to add `attack_paths` and `stats`.
- **Forgetting `_alerts` is a list of dicts:** `_alerts.extend(a.model_dump() for a in new_alerts)` — so alerts in `_alerts` are plain dicts, not `Alert` objects.
- **Calling `_correlate()` on a hot path without the 10-edge cap:** Without `MAX_PROXIMITY_EDGES_PER_EVENT`, temporal proximity creates O(n²) edges for dense event sets.

---

## Codebase State (Critical Discoveries)

### TWO Graph Systems Exist — Must Not Confuse Them

| System | Location | Used By | Backing Store |
|--------|----------|---------|---------------|
| **In-memory (Phase 2/3)** | `backend/src/graph/builder.py` | `GET /graph` in `backend/src/api/routes.py` | `_events` list in routes.py |
| **SQLite-backed (production)** | `graph/builder.py` + `backend/api/graph.py` | `GET /graph/entity/`, `GET /graph/traverse/`, etc. | SQLite entities+edges tables |

Phase 4 CONTEXT decisions target the **in-memory system**. The locked `build_graph(events, alerts) -> GraphResponse` function signature is for `backend/src/graph/builder.py`. The 41 tests use `TestClient(app)` which imports `backend/src/api/main.py` — the in-memory app.

The production system at `backend/api/graph.py` is separate and more complete, but the tests don't exercise it via TestClient. Phase 4 work is on the in-memory system to keep all 41 tests green.

### Existing In-Memory GraphNode/GraphEdge Fields
The current `GraphNode` has only `id, type, label`. ThreatGraph.svelte reads `n.id, n.label, n.type` for nodes and `e.id, e.source, e.target, e.type` for edges. After Phase 4:
- Node data structure gains `attributes, first_seen, last_seen, evidence`
- Edge field names change: `source`→`src`, `target`→`dst`
- ThreatGraph.svelte's Cytoscape data mapping must update accordingly

### Sigma Alerts in _alerts Store
From routes.py line 64: `_alerts.extend(a.model_dump() for a in new_alerts)`.
Alert dict keys (from `Alert` model in models.py): `id, timestamp, rule, severity, event_id, description`.
The `event_id` field links an alert back to its triggering event — use this to build `alert_trigger` edges.

### NormalizedEvent Fields Available for Correlation
From `backend/src/api/models.py`:
- `id` — event UUID
- `host` — hostname
- `src_ip`, `dst_ip` — network IPs
- `query` — DNS query target (domain)
- `event_type` — dns, dns_query, connection, etc.
- `timestamp` — ISO string
- `user` — optional username
- `severity` — info/low/medium/high/critical

When events are stored via `_store_event`, `event.model_dump()` is called — so fields are stored as their Python values. The `event_type` field (not `event`) holds the type after normalization.

### Normalizer Maps `event` → `event_type`
From `backend/src/parsers/normalizer.py` (implied by test): raw dict key `"event"` maps to `NormalizedEvent.event_type`. So when checking event type in builder.py, check `ev.get("event_type")`, not `ev.get("event")`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Connected components | Custom DFS | Union-Find (copy pattern from `correlation/clustering.py`) | Already proven in this codebase; handles path compression |
| Multi-hop BFS | Recursive function | iterative `deque`-based BFS (copy from `graph/builder.py`) | Already handles visited set, depth limiting, max_nodes cap |
| Timestamp parsing | Custom string manipulation | `datetime.fromisoformat(ts.replace("Z", "+00:00"))` | Pattern already in clustering.py |
| Cytoscape layout | Custom force layout | `cose` built-in layout (already used in ThreatGraph.svelte) | Adequate for < 200 nodes; no extra plugin |

**Key insight:** The root-level `correlation/` and `graph/` directories contain production-quality implementations of every algorithm this phase needs. Study them as reference before implementing anything in the `backend/src/` layer.

---

## Common Pitfalls

### Pitfall 1: Edge Field Name Mismatch (CRITICAL)
**What goes wrong:** The current `GraphEdge` uses `source`/`target`. The new schema uses `src`/`dst`. ThreatGraph.svelte maps `{ source: e.source, target: e.target }` for Cytoscape. If models.py is updated without updating the frontend, Cytoscape will get `undefined` for source/target and all edges will break silently.
**How to avoid:** Update the Cytoscape data mapping in ThreatGraph.svelte in the same plan as models.py changes.
**Warning signs:** Graph renders nodes but no edges after the change.

### Pitfall 2: The `_alerts` List Contains Dicts, Not Objects
**What goes wrong:** `_alerts` is populated with `a.model_dump()` so iterating it yields plain dicts. Calling `.severity` on an alert dict will raise AttributeError.
**How to avoid:** Use `alert.get("severity")` and `alert.get("event_id")` when building `alert_trigger` edges.

### Pitfall 3: `event_type` vs `event` Field Name
**What goes wrong:** Raw events have key `"event"`. After normalization, the NormalizedEvent stores it as `event_type`. When `_store_event` calls `event.model_dump()`, the stored dict key is `event_type`, not `event`. The existing builder.py uses `ev.get("event", "connection")` — this will always fall back to the default after normalization.
**How to avoid:** In the new builder.py, check `ev.get("event_type") or ev.get("event")` to handle both raw and normalized events.

### Pitfall 4: Temporal Proximity O(n²) Without Cap
**What goes wrong:** If 1000 events arrive from the same host, the proximity window creates up to 1000×1000 = 1M `related_event` edges. The route times out or OOMs.
**How to avoid:** Implement `MAX_PROXIMITY_EDGES_PER_EVENT = 10` as a per-event counter; break the inner loop once the cap is reached.

### Pitfall 5: Attack Path Timestamps from Empty Event Sets
**What goes wrong:** `_group_attack_paths` calculates `first_event`/`last_event` from node timestamps. If a path has only IP/domain nodes (no events), timestamps are empty strings.
**How to avoid:** Default `first_event = ""` and `last_event = ""` in `AttackPath`; only populate from events that have timestamps.

### Pitfall 6: build_graph Called with Mutable Global Lists
**What goes wrong:** `_events` and `_alerts` are module-level lists. If `build_graph` is called in a test that also runs POST events, the lists grow between test runs causing test ordering issues.
**How to avoid:** Tests should already handle this (existing tests do); document that `GET /graph` is a point-in-time snapshot.

---

## Code Examples

### Full build_graph Skeleton
```python
# backend/src/graph/builder.py
DNS_CHAIN_WINDOW_SEC = 60
PROXIMITY_WINDOW_SEC = 30
MAX_PROXIMITY_EDGES_PER_EVENT = 10

def build_graph(events: list[dict], alerts: list[dict]) -> GraphResponse:
    nodes = _extract_nodes(events, alerts)
    edges = _extract_edges(events, alerts, nodes)
    corr_edges = _correlate(events, nodes, edges)
    all_edges = edges + corr_edges
    attack_paths = _group_attack_paths(nodes, all_edges)
    return GraphResponse(
        nodes=list(nodes.values()),
        edges=all_edges,
        attack_paths=attack_paths,
        stats={
            "node_count": len(nodes),
            "edge_count": len(all_edges),
            "event_count": len(events),
            "alert_count": len(alerts),
        },
    )
```

### GraphNode Creation with Evidence
```python
def _get_or_create_node(nodes, nid, type_, label, ev_id=None, timestamp=None):
    if nid not in nodes:
        nodes[nid] = GraphNode(
            id=nid, type=type_, label=label,
            first_seen=timestamp or "",
            last_seen=timestamp or "",
            evidence=[ev_id] if ev_id else [],
        )
    else:
        node = nodes[nid]
        if ev_id and ev_id not in node.evidence:
            node.evidence.append(ev_id)
        if timestamp:
            if not node.first_seen or timestamp < node.first_seen:
                node.first_seen = timestamp
            if not node.last_seen or timestamp > node.last_seen:
                node.last_seen = timestamp
```

### Union-Find for Attack Paths
```python
def _group_attack_paths(nodes, edges):
    parent = {nid: nid for nid in nodes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for edge in edges:
        if edge.src in parent and edge.dst in parent:
            union(edge.src, edge.dst)

    # Group nodes by component root
    components: dict[str, list[str]] = defaultdict(list)
    for nid in nodes:
        components[find(nid)].append(nid)

    # Build edge→path mapping
    edge_by_src_dst = defaultdict(list)
    for edge in edges:
        edge_by_src_dst[(find(edge.src), find(edge.dst))].append(edge.id)

    paths = []
    for i, (root, node_ids) in enumerate(components.items()):
        path_edge_ids = [
            eid
            for edge in edges
            if find(edge.src) == root or find(edge.dst) == root
            for eid in [edge.id]
        ]
        # Get timestamps from alert nodes in this path
        sev = _path_severity(node_ids, nodes)
        times = [
            nodes[nid].first_seen
            for nid in node_ids
            if nodes[nid].first_seen
        ]
        paths.append(AttackPath(
            id=f"path-{i+1}",
            node_ids=node_ids,
            edge_ids=list(dict.fromkeys(path_edge_ids)),  # deduplicate preserving order
            severity=sev,
            first_event=min(times) if times else "",
            last_event=max(times) if times else "",
        ))
    return paths
```

### ThreatGraph.svelte — Updated Cytoscape Data Mapping
```typescript
// After Phase 4: src/dst fields instead of source/target
cy.add([
  ...data.nodes.map(n => ({
    data: { id: n.id, label: n.label, type: n.type, evidence: n.evidence },
    group: 'nodes' as const,
  })),
  ...data.edges.map(e => ({
    // CHANGED: e.src / e.dst  (was e.source / e.target)
    data: { id: e.id, source: e.src, target: e.dst, label: e.type,
            evidence_event_ids: e.evidence_event_ids },
    group: 'edges' as const,
  })),
])
```

### Attack Path Highlighting CSS Classes
```typescript
// In ThreatGraph.svelte — add per attack_path
if (data.attack_paths) {
  data.attack_paths.forEach((path, idx) => {
    path.node_ids.forEach(nid => {
      cy.getElementById(nid).addClass(`attack-path-highlight path-${idx}`)
    })
  })
}
```

```typescript
// Cytoscape style for attack paths
{
  selector: '.attack-path-highlight',
  style: { 'border-width': 2, 'border-color': '#f59e0b', 'border-opacity': 0.8 }
},
```

### GET /graph/correlate Route
```python
@router.get("/graph/correlate")
def get_graph_correlate(event_id: str):
    """Return all events, detections, entities correlated with event_id."""
    target = next((e for e in _events if e.get("id") == event_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id!r} not found")

    # Find shared-entity events
    entity_keys = {
        k: v for k, v in target.items()
        if k in ("host", "src_ip", "dst_ip", "query") and v
    }
    correlated_events = [
        e for e in _events
        if e.get("id") != event_id
        and any(e.get(k) == v for k, v in entity_keys.items())
    ]

    # Find related alerts
    correlated_alert_event_ids = {e.get("id") for e in correlated_events} | {event_id}
    correlated_alerts = [
        a for a in _alerts
        if a.get("event_id") in correlated_alert_event_ids
    ]

    # Build graph and find investigation thread
    all_events = [target] + correlated_events
    graph = build_graph(all_events, correlated_alerts)

    # Find which attack_path contains the target event's nodes
    target_node_ids = {f"host:{target.get('host')}", f"ip:{target.get('src_ip')}",
                       f"ip:{target.get('dst_ip')}"} - {None, "host:None", "ip:None"}
    investigation_thread = next(
        (p for p in graph.attack_paths
         if any(nid in target_node_ids for nid in p.node_ids)),
        None
    )

    return {
        "event_id": event_id,
        "correlated_event_count": len(correlated_events),
        "correlated_alert_count": len(correlated_alerts),
        "graph": graph.model_dump(mode="json"),
        "investigation_thread": investigation_thread.model_dump() if investigation_thread else None,
    }
```

---

## State of the Art

| Old Approach | Current Approach | Phase | Impact |
|--------------|------------------|-------|--------|
| `GraphNode(id, type, label)` | `GraphNode(id, type, label, attributes, first_seen, last_seen, evidence)` | Phase 4 | Richer node data for investigation |
| `GraphEdge(id, source, target, type)` | `GraphEdge(id, type, src, dst, timestamp, evidence_event_ids)` | Phase 4 | Links edges to source events for audit |
| `GraphResponse(nodes, edges)` | `GraphResponse(nodes, edges, attack_paths, stats)` | Phase 4 | Attack path grouping for investigation |
| `build_graph(events)` | `build_graph(events, alerts)` | Phase 4 | Alerts become first-class graph citizens |
| No correlation | 4 correlation patterns | Phase 4 | Detects DNS chains, shared entities, temporal proximity |

---

## Open Questions

1. **Field name collision: `NormalizedEvent.event_type` vs raw dict `"event"`**
   - What we know: `model_dump()` stores `event_type`. The existing builder.py uses `ev.get("event", "connection")`.
   - What's unclear: Are any events in `_events` stored with their raw keys (before normalization)?
   - Recommendation: Check both — `ev.get("event_type") or ev.get("event")`. Existing builder.py behavior confirms the raw key is used, but after normalization it's `event_type`.

2. **`_alerts` dict key for event linkage**
   - What we know: `Alert.event_id` links alert to triggering event. The `_alerts` list has dicts.
   - What's unclear: The `NormalizedEvent.id` field vs. the dict key `"id"` after `model_dump()`.
   - Recommendation: Use `alert.get("event_id")` to find events; `ev.get("id")` to match event IDs.

3. **Process/user node scaffolding**
   - What we know: CONTEXT says "optional; emit only if field present in event data"
   - Deferred: User nodes only if `user` field populated. Process nodes only if `process` field present.
   - Recommendation: Add scaffold code with `if ev.get("user"):` / `if ev.get("process"):` guards. If test fixtures don't populate these, the nodes simply won't appear.

---

## Validation Architecture

> `nyquist_validation` is `true` in `.planning/config.json` — this section is required.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.5 + pytest-asyncio 0.25.0 |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` asyncio_mode = "auto", testpaths = ["tests"] |
| Quick run command | `uv run pytest backend/src/tests/ -x -q` |
| Full suite command | `uv run pytest -x -q` |
| Test count baseline | 41 tests passing (must remain green) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FR-4.1 (graph nodes) | `_extract_nodes` emits correct node types and IDs | unit | `uv run pytest backend/src/tests/test_phase4.py::TestGraphNodes -x` | ❌ Wave 0 |
| FR-4.1 (graph edges) | `_extract_edges` creates dns_query, connection, alert_trigger edges | unit | `uv run pytest backend/src/tests/test_phase4.py::TestGraphEdges -x` | ❌ Wave 0 |
| FR-4.1 (correlation) | `_correlate` detects all 4 patterns | unit | `uv run pytest backend/src/tests/test_phase4.py::TestCorrelation -x` | ❌ Wave 0 |
| FR-4.1 (attack paths) | `_group_attack_paths` groups connected nodes | unit | `uv run pytest backend/src/tests/test_phase4.py::TestAttackPaths -x` | ❌ Wave 0 |
| FR-4.2 (GET /graph) | Response has nodes, edges, attack_paths, stats keys | integration | `uv run pytest backend/src/tests/test_phase4.py::TestGraphRoute -x` | ❌ Wave 0 |
| FR-4.3 (clustering) | Process tree fixture → 1 cluster, score > 0.8 | unit | `uv run pytest backend/src/tests/test_phase4.py::TestClustering -x` | ❌ Wave 0 |
| FR-4.4 (aggregation) | 5 alerts from same process tree → 1 thread | unit | `uv run pytest backend/src/tests/test_phase4.py::TestAggregation -x` | ❌ Wave 0 |
| FR-4.5 (correlate EP) | GET /graph/correlate?event_id= returns 200 with graph | integration | `uv run pytest backend/src/tests/test_phase4.py::TestCorrelateRoute -x` | ❌ Wave 0 |
| Regression | All 41 existing tests still pass | regression | `uv run pytest backend/src/tests/ -x -q` | ✅ Exists |

### Sampling Rate
- **Per task commit:** `uv run pytest backend/src/tests/ -x -q` (runs all in-memory app tests)
- **Per wave merge:** `uv run pytest -x -q` (full suite including unit tests in `tests/`)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/src/tests/test_phase4.py` — Phase 4 test stubs. Must be created before any implementation. Classes: `TestGraphNodes`, `TestGraphEdges`, `TestCorrelation`, `TestAttackPaths`, `TestGraphRoute`, `TestClustering`, `TestAggregation`, `TestCorrelateRoute`
- [ ] Synthetic test fixtures in `test_phase4.py` — hand-crafted event and alert dicts covering all 4 correlation patterns. No new fixture files needed (inline in test).
- [ ] No framework install needed — pytest already configured.

### What Tests Prove the Correlation Engine Works
1. **Unit test for `_correlate()`:** Feed events with known DNS→connection pairs, repeated DNS queries, shared-entity alerts, and temporal proximity events. Assert the correct number and type of `related_event` edges are produced.
2. **Edge cap test:** Feed 20 events from the same host within 30s. Assert no event has more than 10 `related_event` edges.
3. **DNS chain test:** Feed a `dns_query` event at T=0 and a `connection` event at T=50s same host. Assert a `dns_query` + `connection` edge chain is produced. Feed T=0 and T=70s — assert no chain (outside 60s window).

### What Tests Prove the API Contract Works
1. `GET /graph` returns JSON with keys: `nodes`, `edges`, `attack_paths`, `stats`.
2. `GET /graph` after ingesting a connection event: `stats.node_count >= 2`, `stats.edge_count >= 1`.
3. `GET /graph/correlate?event_id=<known_id>` returns 200 with `graph` and `investigation_thread` keys.
4. `GET /graph/correlate?event_id=<unknown_id>` returns 404.
5. All 41 existing tests still pass (regression gate).

### Manual Verification Steps
1. Load fixture via `POST /fixtures/load`, then `GET /graph` — verify response has `attack_paths` array and `stats` dict (not just `{nodes, edges}`).
2. `POST /events` with a DNS event + connection event from the same host within 60s, then `GET /graph` — verify a path exists linking domain→ip→host.
3. `GET /graph/correlate?event_id=<id_from_GET /events>` — verify returned graph contains the shared-entity events.
4. In ThreatGraph.svelte: verify attack-path nodes get the yellow border (`attack-path-highlight` class) visible in the browser.
5. Click a node in the graph — verify side panel displays `attributes` and `evidence` data.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — `backend/src/graph/builder.py`, `backend/src/api/models.py`, `backend/src/api/routes.py`, `backend/src/tests/smoke_test.py`, `backend/src/tests/test_phase2.py`, `backend/src/tests/test_phase3.py`
- Direct codebase inspection — `graph/builder.py` (root-level BFS implementation)
- Direct codebase inspection — `correlation/clustering.py` (Union-Find + temporal clustering)
- Direct codebase inspection — `backend/api/graph.py` (production graph routes for reference)
- Direct codebase inspection — `backend/stores/sqlite_store.py` (SQLite schema and edge query methods)
- Direct codebase inspection — `frontend/src/components/graph/ThreatGraph.svelte` (Cytoscape.js integration)
- Direct codebase inspection — `frontend/src/lib/api.ts` (existing `getGraph()` function)
- Direct codebase inspection — `frontend/package.json` (cytoscape ^3.31.0, d3 ^7.9.0, svelte ^5.28.0)
- Direct codebase inspection — `pyproject.toml` (no networkx in deps)

### Secondary (MEDIUM confidence)
- `.planning/phases/04-graph-correlation/04-CONTEXT.md` — locked decisions for node/edge schemas, correlation patterns, function signatures

### Tertiary (LOW confidence — none in this research)
- No web searches were required; the codebase itself is the authoritative source.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies confirmed from pyproject.toml + package.json
- Architecture: HIGH — both graph systems fully read, patterns confirmed from existing implementations
- Pitfalls: HIGH — field name collision and edge field rename verified from direct code inspection
- Test patterns: HIGH — three test files read in full; conftest.py and fixture helpers confirmed

**Research date:** 2026-03-15
**Valid until:** Stable — no external dependencies. Valid until codebase changes.
