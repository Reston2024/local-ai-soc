# Phase 6: Threat Causality & Investigation Engine - Research

**Researched:** 2026-03-16
**Domain:** Causal graph construction, entity resolution, MITRE ATT&CK mapping, attack-chain visualization
**Confidence:** HIGH (core patterns verified against existing codebase and official docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Normalize entity types: host, user, process, IP, domain, file, event, alert — each to a canonical ID form
- Entity resolution happens before causal chain construction
- Required backend modules: `backend/causality/engine.py`, `entity_resolver.py`, `attack_chain_builder.py`, `mitre_mapper.py`, `scoring.py`
- Required API endpoints: `GET /api/graph/{alert_id}`, `GET /api/entity/{entity_id}`, `GET /api/attack_chain/{alert_id}`, `POST /api/query`
- Dashboard: render attack graphs with interactive node expansion, attack-path highlighting, pivot alerts → entities → chains, timeline filtering, graph traversal
- AI investigation summaries: generate via Ollama, read-only mode, accessible from investigation views
- Completion criteria: alerts generate attack graphs, events link into causal chains, MITRE mappings in investigations, analysts can visually trace attack path from first event to final detection

### Claude's Discretion
- Graph schema specifics (node/edge field names beyond Phase 4 baseline)
- Internal engine data structures (intermediate representations)
- Scoring algorithm weights and thresholds
- Svelte component names and file structure in dashboard
- Database storage strategy for causality graph (DuckDB vs in-memory)
- Test file organization and fixture data
- Documentation format
- API response schemas (beyond required endpoints)
- Import/module organization within backend/causality/

### Deferred Ideas (OUT OF SCOPE)
- Case management integration (assign investigations to analysts)
- Export of attack chain to STIX/TAXII format
- Multi-tenant investigation isolation
- Real-time streaming updates to graph via WebSocket
- Automated remediation suggestions
- Integration with external threat intelligence APIs
- Persistent storage of resolved attack chains (Phase 6 computes on-demand)
- Original roadmap Phase 6 scope (osquery, IOC matching, operational scripts, reproducibility receipt, security hardening)
</user_constraints>

---

## Summary

Phase 6 builds a Causality Engine on top of the existing Phase 4 graph infrastructure (`backend/src/graph/builder.py`). The existing `build_graph()` function already constructs `GraphNode`, `GraphEdge`, `AttackPath`, and `GraphResponse` objects using Union-Find clustering. Phase 6 adds a new `backend/causality/` package that enriches this foundation with: (1) entity resolution that normalizes heterogeneous event fields into canonical IDs, (2) a causal chain builder that follows temporal event-entity-event relationships through the existing in-memory stores, (3) MITRE ATT&CK technique/tactic mapping that extends the existing `attack_mapper.py` static table, and (4) a severity-weighted chain scoring model.

The critical integration insight is that Phase 6 does NOT replace the Phase 4 graph builder — it wraps it. The causality engine calls `build_graph()` internally, then adds enrichment layers (entity resolution, ATT&CK mapping, chain scoring) before returning a richer response through new API endpoints. The new `GET /api/graph/{alert_id}`, `GET /api/entity/{entity_id}`, and `GET /api/attack_chain/{alert_id}` endpoints are thin adapters over the causality engine, not independent implementations.

The dashboard extension adds an `AttackChain.svelte` component that reuses the existing Cytoscape.js instance from `ThreatGraph.svelte`. Attack-path highlighting uses Cytoscape's CSS selector API to color edges belonging to an `AttackPath` in a distinct color. The `cytoscape-dagre` npm package (already available as a Cytoscape extension) provides hierarchical layout for attack chains. AI investigation summaries call the existing Ollama HTTP client via a new prompt template in `prompts/`.

**Primary recommendation:** Build `backend/causality/` as a pure enrichment layer over `build_graph()`. Use in-memory computation (no new DuckDB tables). Entity resolution is a normalization function — not a lookup service.

---

## Standard Stack

### Core (Already Installed in Project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | existing | API routing for new endpoints | Established in Phase 1 |
| Pydantic | existing | Request/response models for causality | Already used for GraphNode/GraphEdge/AttackPath |
| cytoscape | existing (dashboard) | Attack graph visualization | Already used in ThreatGraph.svelte |
| httpx (async) | existing | Ollama HTTP client for AI summaries | Established in Phase 3 |

### New Dependencies Needed
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| cytoscape-dagre | ^2.5.0 | Hierarchical DAG layout for attack chains | For attack chain view (process trees, tactic ordering) |
| mitreattack-python | ^5.4.x | Official MITRE ATT&CK STIX lookups | If expanding beyond the 5-entry static map in attack_mapper.py |

**Decision on mitreattack-python:** The existing `attack_mapper.py` has a 5-entry static table. Phase 6's `mitre_mapper.py` should expand this significantly. Two approaches:
1. Expand the static dict (no new dep — simpler, faster, fits project "no external services" constraint)
2. Add `mitreattack-python` and load `enterprise-attack.json` locally

**Recommendation:** Use expanded static dict approach for `mitre_mapper.py`. The `mitreattack-python` library requires downloading a large STIX bundle (~12MB) and introduces a new network/file dependency. The static approach is consistent with how `attack_mapper.py` was built in Phase 5, requires no new pip dependency, and is sufficient for the required 11 MITRE ATT&CK tactics.

### npm Additions
```bash
npm install cytoscape-dagre
```

### Python Additions (No New deps Needed)
The `backend/causality/` package uses only stdlib + existing project deps.

---

## Architecture Patterns

### Recommended Module Structure
```
backend/causality/
├── __init__.py
├── engine.py            # Orchestrator: takes alert_id → CausalityResult
├── entity_resolver.py   # Normalize raw field values → canonical entity IDs
├── attack_chain_builder.py  # DAG construction from events + entities
├── mitre_mapper.py      # Extended ATT&CK static mapping (all 11 tactics)
└── scoring.py           # Chain severity scoring (additive model)
```

New API endpoints live in:
```
backend/src/api/routes.py   # Add new /api/graph/{alert_id} etc. here
```
OR a new router:
```
backend/src/api/causality_routes.py  # Clean separation option
```

Dashboard additions:
```
frontend/src/components/
├── graph/
│   ├── ThreatGraph.svelte        # Existing — reuse
│   └── AttackChain.svelte        # New — dagre layout, attack-path highlight
├── panels/
│   ├── EvidencePanel.svelte      # Existing — extend
│   └── InvestigationPanel.svelte # New — AI summary + MITRE tactics sidebar
└── investigation/
    └── AttackChainView.svelte    # New page-level container
```

### Pattern 1: Entity Resolution — Canonical ID Form
**What:** Normalize heterogeneous event fields to a stable `type:value` canonical ID.
**When to use:** Before building any causal relationship. Canonical IDs ensure that `process:powershell.exe` from a Sysmon event and `process:powershell.exe` from a Suricata event link to the same node.

```python
# Source: project pattern established in backend/src/graph/builder.py lines 83-99
# The existing builder already uses this pattern — causality engine formalizes it.

ENTITY_PREFIXES = {
    "host": "host",
    "user": "user",
    "process": "process",
    "ip": "ip",
    "domain": "domain",
    "file": "file",
    "event": "event",
    "alert": "alert",
}

def resolve_entity(entity_type: str, raw_value: str) -> str:
    """Normalize to canonical ID: 'type:normalized_value'."""
    value = raw_value.strip().lower()  # Lowercase for case-insensitive matching
    return f"{entity_type}:{value}"
```

**Key normalization rules per entity type:**
- `host`: lowercase, strip domain suffix for Windows hostnames (`WORKSTATION01.corp.com` → `host:workstation01`)
- `user`: lowercase, strip domain prefix (`CORP\jsmith` → `user:jsmith`, `jsmith@corp.com` → `user:jsmith`)
- `process`: lowercase basename only (`C:\Windows\System32\cmd.exe` → `process:cmd.exe`)
- `ip`: normalize IPv4 form, strip port (`192.168.1.1:443` → `ip:192.168.1.1`)
- `domain`: lowercase, strip trailing dot (`evil.com.` → `domain:evil.com`)
- `file`: lowercase basename only (for matching; full path stored as attribute)

### Pattern 2: Attack Chain as Ordered Edge List (Not Pure DAG)
**What:** Represent the attack chain as a list of `(source_entity_id, edge_type, target_entity_id, timestamp)` tuples sorted by timestamp. This is simpler than a full adjacency list and supports temporal ordering.
**When to use:** Always. The attack chain is fundamentally temporal — "what happened before what."

```python
# Pseudo-code for attack_chain_builder.py
from dataclasses import dataclass
from typing import NamedTuple

class ChainEdge(NamedTuple):
    timestamp: str          # ISO 8601
    src_entity_id: str      # canonical ID
    edge_type: str          # spawned | connected_to | accessed | detected_by
    dst_entity_id: str
    evidence_event_id: str  # backing event UUID

@dataclass
class AttackChain:
    alert_id: str
    edges: list[ChainEdge]  # sorted by timestamp
    entity_ids: set[str]    # all entities in chain
    technique_ids: list[str]  # e.g. ["T1059.001", "T1071.004"]
    severity: str
    score: int              # 0-100
    first_event: str        # ISO timestamp
    last_event: str         # ISO timestamp
```

**Cycle detection:** When traversing event-entity-event relationships, keep a `visited_entity_ids: set[str]` to prevent infinite loops in causal chains. Max depth should be capped at 5 hops to prevent hairball output.

### Pattern 3: Causality Engine Orchestration
**What:** The engine takes an `alert_id`, finds the triggering event, resolves entities, traverses related events via shared entities, builds the chain, maps MITRE, and scores.

```python
# backend/causality/engine.py
async def build_causality(alert_id: str, events: list[dict], alerts: list[dict]) -> dict:
    """
    1. Find alert by alert_id in alerts list
    2. Find triggering event from alert.event_id
    3. Resolve entities from triggering event via entity_resolver
    4. BFS over shared-entity events (max depth 5, max 50 events)
    5. Build ordered ChainEdge list via attack_chain_builder
    6. Map MITRE ATT&CK via mitre_mapper (from alert.attack_tags + Sigma rule tags)
    7. Score chain via scoring.score_chain()
    8. Call build_graph(chain_events, chain_alerts) for graph structure
    9. Return enriched CausalityResult
    """
```

**Async pattern:** All BFS traversal and graph building is CPU-bound (no I/O), so it runs synchronously. The endpoint wraps it in `asyncio.to_thread()` consistent with the project pattern for blocking operations.

```python
# In routes.py — consistent with existing DuckDB pattern (CLAUDE.md)
@router.get("/api/graph/{alert_id}")
async def get_causality_graph(alert_id: str):
    result = await asyncio.to_thread(
        lambda: build_causality_sync(alert_id, _events, _alerts)
    )
    return result
```

### Pattern 4: MITRE Mapping Expansion
**What:** `mitre_mapper.py` extends the existing 5-entry `attack_mapper.py` dict with all 11 ATT&CK tactics. The mapper takes a list of Sigma rule tags AND event fields and returns a list of `{tactic, technique, technique_name}` dicts.

The existing `attack_mapper.py` maps alert+event → single tag. `mitre_mapper.py` is richer: it returns multiple techniques per event (an alert may match multiple tactics), includes `technique_name` for display, and handles graceful degradation for unknown techniques.

```python
# backend/causality/mitre_mapper.py
TECHNIQUE_CATALOG = {
    # Full 11-tactic mapping for common SOC detections
    "T1059.001": {"tactic": "Execution", "name": "PowerShell"},
    "T1059.003": {"tactic": "Execution", "name": "Windows Command Shell"},
    "T1003.001": {"tactic": "Credential Access", "name": "LSASS Memory"},
    "T1071.001": {"tactic": "Command and Control", "name": "Web Protocols"},
    "T1071.004": {"tactic": "Command and Control", "name": "DNS"},
    "T1055": {"tactic": "Defense Evasion", "name": "Process Injection"},
    "T1021.001": {"tactic": "Lateral Movement", "name": "Remote Desktop Protocol"},
    "T1078": {"tactic": "Defense Evasion", "name": "Valid Accounts"},
    "T1566.001": {"tactic": "Initial Access", "name": "Spearphishing Attachment"},
    # ... extend to 20-30 common techniques
}

def map_techniques(sigma_tags: list[str], event_type: str, alert_category: str) -> list[dict]:
    """Returns list of {tactic, technique, name} — empty list if no match."""
    results = []
    for tag in sigma_tags:
        # Parse 'attack.t1059.001' → 'T1059.001'
        if tag.startswith("attack.t"):
            tid = "T" + tag[8:].upper()
            if tid in TECHNIQUE_CATALOG:
                entry = TECHNIQUE_CATALOG[tid]
                results.append({"technique": tid, **entry})
    return results or _fallback_map(event_type, alert_category)
```

### Pattern 5: AI Investigation Summary
**What:** New prompt template `prompts/investigation_summary.py` that takes attack chain nodes + MITRE techniques and generates an analyst-readable investigation narrative via Ollama streaming.

```python
# prompts/investigation_summary.py — follows existing prompt template pattern
SYSTEM = """You are a SOC analyst assistant. Based ONLY on the provided attack chain data,
generate a concise investigation summary. Do not speculate beyond the provided evidence."""

TEMPLATE = """
## Attack Chain Summary Request

Alert ID: {alert_id}
Severity: {severity}
Time Range: {first_event} to {last_event}
MITRE Techniques: {techniques}

Entities involved:
{entity_list}

Key events (chronological):
{event_list}

Generate a 3-5 sentence investigation summary covering:
1. Initial detection trigger
2. Key entities and their roles
3. MITRE ATT&CK techniques observed
4. Recommended next investigation step
"""
```

The summary endpoint uses `asyncio.to_thread()` wrapping the Ollama httpx call, consistent with the project async pattern.

### Anti-Patterns to Avoid
- **Building a new graph store**: Phase 6 computes on-demand from in-memory `_events` + `_alerts`. Do NOT add DuckDB tables for causality — this is deferred per CONTEXT.md.
- **Replacing build_graph()**: The causality engine wraps and enriches it, does not rewrite it.
- **Module-level Ollama calls**: Mirroring the Phase 5 deferred-import pattern, causality module imports must not fail-hard at startup.
- **Unbounded BFS**: Without a depth cap and visited-set, shared-entity traversal will produce hairball graphs from large event sets. Cap at depth=5, max 50 events.
- **LangChain wrapper for Ollama**: Banned per CLAUDE.md. Use httpx async client directly or the existing Ollama service pattern.
- **Storing attack chains**: CONTEXT.md explicitly defers persistent storage of resolved attack chains. All computation is on-demand.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Graph node/edge models | Custom dataclasses | Existing `GraphNode`, `GraphEdge`, `AttackPath` from `backend/src/api/models.py` | Already schema-locked in Phase 4 |
| Union-Find clustering | Custom | Existing `_group_attack_paths()` in `builder.py` | Already battle-tested in Phase 4 |
| Cytoscape rendering | Custom SVG/Canvas | Existing `ThreatGraph.svelte` + Cytoscape.js | Node colors, selection, pan/zoom already implemented |
| Attack path highlighting | Custom CSS | Cytoscape selector API: `cy.edges('[attackPath]').style(...)` | Built into Cytoscape — 2 lines |
| Sigma tag parsing | Custom regex | Existing pySigma tag convention: `attack.t1059.001` → strip `attack.` prefix | Already used in Phase 3 detection |
| Ollama streaming | Custom HTTP | Existing `httpx` async pattern from Phase 3 RAG pipeline | Already established in project |
| MITRE technique resolution | mitreattack-python library | Expanded static dict in `mitre_mapper.py` | No external data file needed; simpler; sufficient for SOC use case |

**Key insight:** The Phase 4 graph infrastructure is the foundation. The causality engine's job is to narrow the input (events/alerts relevant to one alert_id) and enrich the output (MITRE mapping, scoring, AI summary) — not to re-implement graph building.

---

## Common Pitfalls

### Pitfall 1: ThreatGraph.svelte uses `e.source`/`e.target` but GraphEdge uses `e.src`/`e.dst`
**What goes wrong:** The existing `ThreatGraph.svelte` line 28 maps `e.source` and `e.target` (Cytoscape field names), but `GraphEdge` uses `src`/`dst` fields. The Phase 4 note in STATE.md records: "GraphEdge uses src/dst fields (not source/target) — ThreatGraph.svelte maps e.src/e.dst to Cytoscape source/target." But the ACTUAL code in ThreatGraph.svelte line 28 shows `source: e.source, target: e.target` — this is wrong and will break when `AttackChain.svelte` consumes the API response.
**Why it happens:** The component was written before the schema lock, or it reads from a different data source than the raw GraphEdge.
**How to avoid:** In `AttackChain.svelte`, always map explicitly: `source: e.src, target: e.dst`.
**Warning signs:** Graph renders with no edges despite nodes being present.

### Pitfall 2: Entity Resolution Case Sensitivity Breaks Joins
**What goes wrong:** `host:WORKSTATION01` and `host:workstation01` are treated as different entities, fragmenting the causal graph.
**Why it happens:** Windows hostnames and usernames are case-insensitive but stored with original casing from event sources.
**How to avoid:** Always lowercase in `resolve_entity()`. Apply normalization in `entity_resolver.py` before any ID comparison.
**Warning signs:** Attack chain contains duplicate entity nodes for the same host.

### Pitfall 3: In-Memory Store Reference Timing
**What goes wrong:** The causality engine receives stale snapshots of `_events` and `_alerts` if they are passed by value rather than referenced at call time.
**Why it happens:** The in-memory `_events` list in `routes.py` grows at runtime. If the causality module holds a reference taken at import time, it will always see an empty list.
**How to avoid:** Pass `_events` and `_alerts` as function arguments at call time, not as module-level imports. The engine signature must be `build_causality(alert_id, events, alerts)`.
**Warning signs:** `GET /api/graph/{alert_id}` always returns empty chains even after ingesting events.

### Pitfall 4: Deferred Import Pattern Must be Mirrored
**What goes wrong:** Causality module imports that fail (e.g., missing `mitreattack-python`) crash the entire FastAPI startup.
**Why it happens:** Module-level imports in Python run at startup.
**How to avoid:** Causality imports in routes must follow the Phase 5 deferred-import pattern:
```python
try:
    from backend.causality.engine import build_causality as _build_causality
except ImportError:
    _build_causality = None
```
Then check `if _build_causality is None: raise HTTPException(503)` in the route handler.
**Warning signs:** Backend fails to start with ImportError traceback.

### Pitfall 5: Cytoscape dagre Plugin Registration
**What goes wrong:** `cy.layout({ name: 'dagre' })` throws "Layout dagre not found" at runtime.
**Why it happens:** The dagre layout is a plugin that must be registered before use: `cytoscape.use(dagre)`.
**How to avoid:** Register the dagre plugin in the component's `<script>` block before any `cytoscape()` call.
```typescript
import dagre from 'cytoscape-dagre'
cytoscape.use(dagre)
```
**Warning signs:** "Layout 'dagre' not found" error in browser console.

### Pitfall 6: `/api/` Route Prefix Mismatch
**What goes wrong:** The CONTEXT.md specifies `GET /api/graph/{alert_id}` but the existing router mounts at root (`/graph`, `/alerts`, etc. with no `/api/` prefix in routes.py).
**Why it happens:** Phase 4 endpoints use `/graph/correlate` not `/api/graph/correlate`.
**How to avoid:** Either (a) add new causality endpoints to the existing router without `/api/` prefix, or (b) mount a new `causality_router` with prefix `/api`. Recommend option (a) for consistency: the new endpoints become `GET /graph/{alert_id}`, `GET /entity/{entity_id}`, `GET /attack_chain/{alert_id}`, `POST /query`.
**Warning signs:** 404 errors on all new endpoints from the frontend.

---

## Code Examples

Verified patterns from project codebase:

### Entity Resolution (Extend Existing Pattern)
```python
# Source: backend/src/graph/builder.py lines 31-65 — existing _get_or_create_node pattern
# entity_resolver.py formalizes this into a reusable function

def resolve_canonical_id(event: dict, entity_type: str) -> str | None:
    """Extract and normalize entity ID from event dict.
    Returns None if the entity_type field is absent in the event.
    """
    field_map = {
        "host": "host",
        "user": "user",
        "process": "process",
        "ip_src": "src_ip",
        "ip_dst": "dst_ip",
        "domain": "query",
        "file": "file_path",
    }
    raw_value = event.get(field_map.get(entity_type, entity_type))
    if not raw_value:
        return None
    return f"{entity_type}:{str(raw_value).strip().lower()}"
```

### Shared-Entity BFS (Causal Chain Traversal)
```python
# Source: Pattern adapted from backend/src/api/routes.py lines 143-163 (get_graph_correlate)
# attack_chain_builder.py extends this to multi-hop with depth cap

def find_causal_chain(
    start_event_id: str,
    all_events: list[dict],
    max_depth: int = 5,
    max_events: int = 50,
) -> list[dict]:
    """BFS over events sharing entities with start_event. Returns ordered event list."""
    visited_event_ids = {start_event_id}
    chain_events = []
    start_event = next((e for e in all_events if e.get("id") == start_event_id), None)
    if not start_event:
        return []

    queue = [(start_event, 0)]  # (event, depth)
    while queue and len(chain_events) < max_events:
        current_event, depth = queue.pop(0)
        chain_events.append(current_event)
        if depth >= max_depth:
            continue
        # Entity keys from current event
        entity_keys = {
            k: v for k, v in current_event.items()
            if k in ("host", "src_ip", "dst_ip", "query", "user", "process")
            and v is not None
        }
        # Find events sharing any entity key
        for ev in all_events:
            if ev.get("id") in visited_event_ids:
                continue
            if any(ev.get(k) == v for k, v in entity_keys.items()):
                visited_event_ids.add(ev["id"])
                queue.append((ev, depth + 1))

    # Sort by timestamp
    return sorted(chain_events, key=lambda e: e.get("timestamp", ""))
```

### Cytoscape Attack Path Highlighting
```typescript
// Source: Cytoscape.js official docs (https://js.cytoscape.org/#style)
// Pattern for AttackChain.svelte — extend ThreatGraph.svelte approach

// In the Cytoscape style array, add a selector for attack-path edges:
{
  selector: 'edge[attackPath]',
  style: {
    'line-color': '#f97316',     // orange — distinct from normal grey
    'target-arrow-color': '#f97316',
    'width': 3,
    'line-style': 'solid',
    'z-index': 10,
  }
},
{
  selector: 'node[attackPath]',
  style: {
    'border-width': 3,
    'border-color': '#f97316',
    'border-style': 'solid',
  }
}

// After graph load, mark attack path elements:
function highlightAttackPath(cy: any, pathNodeIds: string[], pathEdgeIds: string[]) {
  pathNodeIds.forEach(id => {
    cy.getElementById(id).data('attackPath', true)
  })
  pathEdgeIds.forEach(id => {
    cy.getElementById(id).data('attackPath', true)
  })
}
```

### Dagre Plugin Registration (Svelte 5)
```typescript
// Source: cytoscape-dagre npm (https://www.npmjs.com/package/cytoscape-dagre)
// In AttackChain.svelte script block:

import { onMount, onDestroy } from 'svelte'
import cytoscape from 'cytoscape'
import dagre from 'cytoscape-dagre'

// Register ONCE at module level — safe to call multiple times
cytoscape.use(dagre)

onMount(() => {
  const cy = cytoscape({
    container,
    layout: { name: 'dagre', rankDir: 'TB', nodeSep: 50, rankSep: 80 },
    // ... rest of config
  })
})
```

### FastAPI Endpoint with asyncio.to_thread
```python
# Source: CLAUDE.md project conventions — all blocking I/O via asyncio.to_thread
import asyncio
from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get("/graph/{alert_id}")
async def get_causality_graph(alert_id: str):
    """Return attack graph centered on a specific alert."""
    try:
        from backend.causality.engine import build_causality_sync
    except ImportError:
        raise HTTPException(status_code=503, detail="Causality engine not available")

    alert = next((a for a in _alerts if a.get("id") == alert_id), None)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id!r} not found")

    result = await asyncio.to_thread(
        lambda: build_causality_sync(alert_id, _events, _alerts)
    )
    return result
```

### Scoring Algorithm (Additive Model)
```python
# Source: backend/src/detection/threat_scorer.py (Phase 5 pattern)
# scoring.py extends the same additive 0-100 model to chains

def score_chain(
    chain_events: list[dict],
    chain_alerts: list[dict],
    techniques: list[dict],
) -> int:
    """Additive 0-100 score for an attack chain."""
    score = 0

    # Max alert severity in chain (40 pts)
    severity_points = {"critical": 40, "high": 30, "medium": 20, "low": 10}
    max_sev = max(
        (severity_points.get(a.get("severity", "").lower(), 0) for a in chain_alerts),
        default=0,
    )
    score += max_sev

    # MITRE technique count (up to 20 pts — 5 pts per technique, max 4)
    score += min(len(techniques) * 5, 20)

    # Chain length (up to 20 pts — more hops = more sophisticated)
    score += min(len(chain_events) * 2, 20)

    # Recurrence: same entity in 3+ events (+20 pts)
    entity_counts: dict[str, int] = {}
    for ev in chain_events:
        for field in ("host", "user", "process"):
            val = ev.get(field)
            if val:
                entity_counts[val] = entity_counts.get(val, 0) + 1
    if any(v >= 3 for v in entity_counts.values()):
        score += 20

    return min(score, 100)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Static ATT&CK table (5 entries) | Expanded static table in mitre_mapper.py (20-30 entries) | Phase 6 | Broader technique coverage without new deps |
| attack_mapper returns `list[dict]` with 1 entry | mitre_mapper returns multiple techniques per chain | Phase 6 | Richer MITRE coverage for multi-step attacks |
| GraphEdge: no causal type | New edge types: `spawned`, `accessed`, `triggered_by` | Phase 6 | Richer semantic edges for investigation |
| ThreatGraph.svelte: COSE layout only | AttackChain.svelte: dagre layout for trees + COSE for discovery | Phase 6 | Better readability for attack chains |
| build_graph takes all events | causality engine takes alert_id scoped events | Phase 6 | Focused graph — not entire dataset |
| DuckDB USING KEY (v1.3+) | Available if DuckDB queries needed for graph BFS | 2025 | Not needed for Phase 6 (in-memory), but available for future persistence |

**Deprecated/outdated:**
- `ThreatGraph.svelte` line 28: uses `e.source`/`e.target` — the existing code maps wrongly from `GraphEdge.src`/`GraphEdge.dst`. Any new component must use `e.src`/`e.dst` explicitly mapped to Cytoscape's `source`/`target` fields.
- The `attack_mapper.py` 5-entry static table: Phase 6 `mitre_mapper.py` should supersede it with a proper 20-30 entry mapping covering all 11 ATT&CK tactics relevant to Windows endpoint + network events.

---

## Open Questions

1. **Route prefix `/api/` vs root prefix**
   - What we know: Existing routes use no prefix (e.g., `/graph`, `/alerts`). CONTEXT.md specifies `/api/graph/{alert_id}`.
   - What's unclear: Should new causality routes be at `/api/` (separate router) or `/graph/{alert_id}` (existing router with renamed paths)?
   - Recommendation: Add causality routes at root (no `/api/` prefix) to match existing router convention. Use `/graph/{alert_id}`, `/entity/{entity_id}`, `/attack_chain/{alert_id}`, `/query`. The planner should confirm this and document as a locked decision.

2. **ThreatGraph.svelte source/target bug**
   - What we know: The file maps `source: e.source, target: e.target` (line 28) but `GraphEdge` has `.src`/`.dst`. This means the existing ThreatGraph likely has no edges rendering.
   - What's unclear: Was this intentional (mapping a different data shape) or a latent bug?
   - Recommendation: Phase 6 Wave 0 should fix this mapping in `ThreatGraph.svelte` or confirm it by rendering the graph and checking edge visibility. The fix is `source: e.src, target: e.dst`.

3. **Ollama AI Summary: streaming vs single shot**
   - What we know: Phase 3 established SSE streaming for `POST /query`. The CONTEXT.md says AI summaries must be accessible from investigation views.
   - What's unclear: Should the investigation summary use SSE streaming (like `/query`) or return a completed string (simpler for investigation sidepanel)?
   - Recommendation: Return as a completed string via `POST /investigate/{alert_id}/summary` with `asyncio.to_thread()`. Streaming adds complexity without clear UX benefit for a summary (vs. a Q&A session).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + fastapi.testclient (existing, auto mode) |
| Config file | pyproject.toml (pytest-asyncio mode: auto) |
| Quick run command | `uv run pytest backend/src/tests/test_phase6.py -v` |
| Full suite command | `uv run pytest backend/src/tests/ -v` |

### Phase Requirements → Test Map

The following test classes mirror the Phase 4/5 wave-0 stub pattern used in `test_phase4.py` and `test_phase5.py`:

| Test Class | Behavior | Test Type | Automated Command |
|-----------|----------|-----------|-------------------|
| TestEntityResolver | resolve_canonical_id normalizes host/user/process | unit | `pytest test_phase6.py::TestEntityResolver` |
| TestEntityResolverCaseFolding | host:WORKSTATION01 == host:workstation01 | unit | `pytest test_phase6.py::TestEntityResolverCaseFolding` |
| TestAttackChainBuilder | find_causal_chain returns events ordered by timestamp | unit | `pytest test_phase6.py::TestAttackChainBuilder` |
| TestAttackChainDepthCap | BFS stops at max_depth=5 | unit | `pytest test_phase6.py::TestAttackChainDepthCap` |
| TestAttackChainCycleDetection | circular entity refs don't loop infinitely | unit | `pytest test_phase6.py::TestAttackChainCycleDetection` |
| TestMitreMapper | map_techniques parses Sigma tag attack.t1059.001 → T1059.001 | unit | `pytest test_phase6.py::TestMitreMapper` |
| TestMitreMapperGraceful | unknown tag returns [] not exception | unit | `pytest test_phase6.py::TestMitreMapperGraceful` |
| TestScoring | score_chain returns 0-100, cap at 100 | unit | `pytest test_phase6.py::TestScoring` |
| TestCausalityEngine | build_causality_sync returns dict with nodes/edges/chain | unit | `pytest test_phase6.py::TestCausalityEngine` |
| TestGraphEndpoint | GET /graph/{alert_id} returns 200 with graph payload | integration | `pytest test_phase6.py::TestGraphEndpoint` |
| TestEntityEndpoint | GET /entity/{entity_id} returns 200 with entity data | integration | `pytest test_phase6.py::TestEntityEndpoint` |
| TestAttackChainEndpoint | GET /attack_chain/{alert_id} returns 200 with chain | integration | `pytest test_phase6.py::TestAttackChainEndpoint` |
| TestQueryEndpoint | POST /query returns 200 | integration | `pytest test_phase6.py::TestQueryEndpoint` |
| TestDashboardBuild | npm run build exits 0 after AttackChain.svelte added | build | `cd frontend && npm run build` |

### Sampling Rate
- **Per task commit:** `uv run pytest backend/src/tests/test_phase6.py -v`
- **Per wave merge:** `uv run pytest backend/src/tests/ -v`
- **Phase gate:** Full suite green + `npm run build` exits 0 before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/src/tests/test_phase6.py` — 14 xfail stubs covering all test classes above
- [ ] `backend/causality/__init__.py` — empty stub
- [ ] `backend/causality/engine.py` — stub with `def build_causality_sync(*args): return {}`
- [ ] `backend/causality/entity_resolver.py` — stub with `def resolve_canonical_id(*args): return None`
- [ ] `backend/causality/attack_chain_builder.py` — stub with `def find_causal_chain(*args): return []`
- [ ] `backend/causality/mitre_mapper.py` — stub with `def map_techniques(*args): return []`
- [ ] `backend/causality/scoring.py` — stub with `def score_chain(*args): return 0`

---

## Sources

### Primary (HIGH confidence)
- Project codebase: `backend/src/graph/builder.py` — existing Union-Find, BFS correlation, GraphNode/GraphEdge/AttackPath patterns
- Project codebase: `backend/src/api/models.py` — established Pydantic schema (Phase 4 locks)
- Project codebase: `backend/src/detection/attack_mapper.py` — existing ATT&CK static mapping pattern
- Project codebase: `backend/src/api/routes.py` — deferred import pattern, asyncio.to_thread conventions
- Project codebase: `frontend/src/components/graph/ThreatGraph.svelte` — existing Cytoscape.js integration
- CLAUDE.md — canonical project conventions (asyncio.to_thread, DuckDB write queue, Svelte 5 runes)
- [DuckDB WITH RECURSIVE docs](https://duckdb.org/docs/stable/sql/query_syntax/with) — recursive CTE support confirmed
- [DuckDB USING KEY (2025)](https://duckdb.org/2025/05/23/using-key) — v1.3+ graph query optimization (available, not needed for Phase 6 in-memory)
- [cytoscape-dagre npm](https://www.npmjs.com/package/cytoscape-dagre) — v2.5.0, install command confirmed
- [Cytoscape.js official docs](https://js.cytoscape.org/) — selector API, edge styling, layout patterns

### Secondary (MEDIUM confidence)
- [mitreattack-python docs v5.4.1](https://mitreattack-python.readthedocs.io/) — official library API verified; decided NOT to use (static dict approach preferred)
- [mitre-attack/mitreattack-python GitHub](https://github.com/mitre-attack/mitreattack-python) — confirmed: `pip install mitreattack-python` + STIX bundle download required
- [LangGraph streaming docs](https://docs.langchain.com/oss/python/langgraph/streaming) — `astream_events()` confirmed for SSE streaming pattern
- [FastAPI Background Tasks docs](https://fastapi.tiangolo.com/tutorial/background-tasks/) — confirmed: `asyncio.to_thread()` pattern for CPU-bound work in async handlers

### Tertiary (LOW confidence — not needed for this phase)
- WebSearch: DuckPGQ extension for graph queries — available in DuckDB, but Phase 6 uses in-memory not DuckDB graph queries
- WebSearch: cytoscape.js-dagre attack path highlighting — no canonical source found; pattern synthesized from Cytoscape selector API docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all core dependencies are existing project dependencies; cytoscape-dagre is the only new npm package
- Architecture: HIGH — patterns directly validated against existing Phase 4/5 code in the codebase
- Pitfalls: HIGH (2), MEDIUM (4) — the src/target vs src/dst bug is confirmed by reading ThreatGraph.svelte; route prefix ambiguity is confirmed by comparing CONTEXT.md vs routes.py
- MITRE mapping: MEDIUM — static dict approach validated against existing attack_mapper.py pattern; coverage count (20-30 entries) is discretionary
- AI summary integration: MEDIUM — Ollama/LangGraph streaming pattern is well-documented; exact endpoint shape is Claude's discretion per CONTEXT.md

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (stable stack; only DuckDB USING KEY is fast-moving — not used in Phase 6)
