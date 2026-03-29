# Phase 15: Attack Graph UI - Research

**Researched:** 2026-03-28
**Domain:** Cytoscape.js graph visualization, Svelte 5 runes, FastAPI graph API, BFS attack path
**Confidence:** HIGH

---

## Summary

Phase 15 transforms the existing functional GraphView.svelte stub (which already uses Cytoscape.js 3.31 with basic cose layout) into a production-grade attack graph visualizer. The foundation is excellent: Cytoscape.js is already installed (`"cytoscape": "^3.31.0"` in package.json), the graph backend is fully operational (SQLite entities/edges, BFS traversal in `graph/builder.py`, `/api/graph/` router with 7 endpoints), and GraphView.svelte already renders nodes/edges with entity-type colouring. What is missing is: the two new API endpoints (`/api/graph/{investigation_id}` and `/api/graph/global`), fCoSE/dagre layout plugins, attack path BFS highlighting (thick red edges + pulsing nodes), MITRE ATT&CK tactic overlay on `attack_technique` nodes, and the bidirectional Graph ↔ InvestigationView navigation.

The codebase uses Svelte 5 runes throughout. GraphView.svelte currently mixes `onMount`/`onDestroy` (lifecycle hooks) with `$state` (runes). This is valid Svelte 5 — `onMount`/`onDestroy` still work in runes-mode components. The existing Cytoscape init pattern (`initCy()` called from `onMount`, `cy?.destroy()` in `onDestroy`) is the correct approach and should be preserved and extended rather than replaced.

Key architectural insight: the backend already exposes `/api/graph/case/{case_id}` which is exactly what `GET /api/graph/{investigation_id}` needs — only the URL alias and response shaping differ. The global graph can be served by adapting the `/api/graph/entities` + `/api/graph/traverse` combination. P15-T01 is therefore primarily an API routing addition, not new logic.

**Primary recommendation:** Add fCoSE layout plugin, extend GraphView.svelte in-place, add two API endpoints that reuse existing SQLite graph store methods, implement BFS highlighting using `cy.elements().dijkstra()`, and wire App.svelte for bidirectional navigation via lifted state or a simple callback prop.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P15-T01 | Graph data API — GET /api/graph/{investigation_id} + GET /api/graph/global returning nodes/edges from SQLite graph store | Existing `/api/graph/case/{case_id}` and `get_entity_subgraph()` already do this; new routes are thin wrappers |
| P15-T02 | Cytoscape.js GraphView.svelte — force-directed layout, risk-scored node sizing, entity-type colouring, edge labels | cytoscape 3.31 already installed; fCoSE plugin (`cytoscape-fcose 2.2.0`) is the recommended force-directed upgrade; node `width`/`height` can be data-driven by `risk_score` attribute |
| P15-T03 | Attack path highlighting — BFS shortest path from source to target entity with visual distinction | `cy.elements().dijkstra(root)` returns `.pathTo(target)` collection; apply CSS class `attack-path` with thick red edges and `cy.animate()` for pulse |
| P15-T04 | Graph ↔ Investigation integration — node click navigates to InvestigationView; "Open in Graph" from InvestigationView | App.svelte already lifts `investigatingId` state; GraphView needs `onNavigateInvestigation` callback prop; InvestigationView needs `onOpenInGraph` callback prop |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| cytoscape | ^3.31.0 (installed) | Graph rendering engine | Already in package.json; production-grade, MIT |
| cytoscape-fcose | 2.2.0 | Force-directed layout (upgrade from cose) | 2x faster than cose; best for 100-500 nodes; supports compound graphs |
| cytoscape-dagre | 2.5.0 | Hierarchical DAG layout (optional alt) | Useful for attack chain linear views; small file size |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| cytoscape (built-in algorithms) | included | BFS, Dijkstra, A* for path finding | Attack path highlighting (P15-T03) |
| Svelte 5 `onMount`/`onDestroy` | installed | Cytoscape lifecycle management | Cytoscape needs real DOM; init in onMount |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| cytoscape-fcose | D3.js force simulation | D3 is heavier, more complex; Cytoscape already integrated |
| cytoscape-fcose | cose-bilkent | fCoSE is faster and newer; cose-bilkent is older |
| Dijkstra for path finding | Manual BFS in JS | Cytoscape's built-in Dijkstra is tested, optimised, returns a traversable collection |

**Installation:**
```bash
cd dashboard && npm install cytoscape-fcose cytoscape-dagre
```

---

## Architecture Patterns

### Existing Structure (Do Not Restructure)
```
dashboard/src/
├── views/
│   ├── GraphView.svelte       # Extend in-place (already functional)
│   └── InvestigationView.svelte  # Add "Open in Graph" callback prop
├── lib/
│   └── api.ts                 # Add graph.caseGraph() and graph.global() methods
└── App.svelte                 # Wire navigation callbacks between views
backend/
├── api/
│   └── graph.py               # Add /graph/{investigation_id} + /graph/global endpoints
└── graph/
    └── builder.py             # Already has get_entity_subgraph() — reuse directly
```

### Pattern 1: fCoSE Plugin Registration (one-time setup)
**What:** Register layout plugins once at module level before Cytoscape init.
**When to use:** Before any `cytoscape({...})` call.
**Example:**
```typescript
// Source: https://github.com/iVis-at-Bilkent/cytoscape.js-fcose
import cytoscape from 'cytoscape'
import fcose from 'cytoscape-fcose'
import dagre from 'cytoscape-dagre'

// Register once at module top-level (not inside onMount — idempotent)
cytoscape.use(fcose)
cytoscape.use(dagre)
```

### Pattern 2: Risk-Scored Node Sizing
**What:** Map a `risk_score` attribute (0-100) onto node `width`/`height` via Cytoscape style function.
**When to use:** Nodes returned by `/api/graph/global` should carry `risk_score` from `attributes` JSON.
```typescript
// Source: Cytoscape.js official docs - https://js.cytoscape.org/#style
{
  selector: 'node',
  style: {
    'width': (ele: cytoscape.NodeSingular) => {
      const score = Number(ele.data('risk_score') ?? 0)
      return Math.max(20, Math.min(50, 20 + score * 0.3))
    },
    'height': (ele: cytoscape.NodeSingular) => {
      const score = Number(ele.data('risk_score') ?? 0)
      return Math.max(20, Math.min(50, 20 + score * 0.3))
    },
    'background-color': (ele: cytoscape.NodeSingular) => typeColors[ele.data('type')] ?? '#8b949e',
  }
}
```

### Pattern 3: Attack Path BFS Highlighting
**What:** Use Cytoscape's built-in Dijkstra to find shortest path, apply CSS class for visual highlighting.
**When to use:** When user selects a source + target node for "Show attack path".
```typescript
// Source: https://js.cytoscape.org/#collection/graph-manipulation
function highlightAttackPath(sourceId: string, targetId: string) {
  // Clear previous highlight
  cy!.elements().removeClass('attack-path-node attack-path-edge')

  const dijkstra = cy!.elements().dijkstra({
    root: cy!.$(`#${sourceId}`),
    directed: true,
  })
  const pathCollection = dijkstra.pathTo(cy!.$(`#${targetId}`))

  if (pathCollection.length > 0) {
    pathCollection.nodes().addClass('attack-path-node')
    pathCollection.edges().addClass('attack-path-edge')
    // Animate pulse on path nodes
    pathCollection.nodes().animate({
      style: { 'border-width': 4, 'border-color': '#f85149' },
      duration: 600,
    }).animate({
      style: { 'border-width': 2 },
      duration: 600,
    })
  }
}
```

CSS classes for highlighting:
```typescript
{
  selector: 'node.attack-path-node',
  style: {
    'border-width': 3,
    'border-color': '#f85149',
    'background-color': 'rgba(248, 81, 73, 0.25)',
  }
},
{
  selector: 'edge.attack-path-edge',
  style: {
    'width': 4,
    'line-color': '#f85149',
    'target-arrow-color': '#f85149',
  }
}
```

### Pattern 4: Graph ↔ Investigation Navigation
**What:** App.svelte lifts navigation state; views communicate via callback props.
**When to use:** Node click in GraphView → navigate to InvestigationView; "Open in Graph" from InvestigationView → navigate to GraphView with entity pre-selected.

App.svelte additions:
```typescript
// Source: existing App.svelte pattern — analogous to handleInvestigate()
let graphFocusEntityId = $state<string>('')

function handleOpenInGraph(entityId: string) {
  graphFocusEntityId = entityId
  currentView = 'graph'
}

function handleNavigateInvestigation(investigationId: string) {
  investigatingId = investigationId
  currentView = 'investigation'
}
```

GraphView.svelte receives `focusEntityId` prop and `onNavigateInvestigation` callback:
```typescript
let { focusEntityId = '', onNavigateInvestigation }: {
  focusEntityId?: string
  onNavigateInvestigation?: (id: string) => void
} = $props()

$effect(() => {
  if (focusEntityId && cy) {
    loadSubgraph(focusEntityId)
  }
})
```

InvestigationView.svelte receives `onOpenInGraph` callback prop.

### Pattern 5: fCoSE Layout Options for 100-500 Nodes
**What:** Replace basic `cose` layout with `fcose` for performance and aesthetics.
**When to use:** Any graph render over 20 nodes.
```typescript
// Source: https://github.com/iVis-at-Bilkent/cytoscape.js-fcose README
cy!.layout({
  name: 'fcose',
  quality: 'default',        // 'draft' for speed, 'default' for quality
  animate: false,            // disable animation for initial render speed
  randomize: true,
  nodeRepulsion: 4500,
  idealEdgeLength: 80,
  edgeElasticity: 0.45,
  padding: 40,
  nodeSeparation: 75,
} as any).run()
```

### Pattern 6: Backend — New API Endpoints (P15-T01)
**What:** Two thin endpoint additions to `backend/api/graph.py` reusing existing store methods.

`GET /api/graph/{investigation_id}`:
```python
@router.get("/{investigation_id}")
async def get_investigation_graph(investigation_id: str, request: Request) -> JSONResponse:
    """Return full entity graph for an investigation case (alias for /graph/case/{case_id})."""
    stores = request.app.state.stores
    # Reuse existing get_case_graph logic
    entities_raw = await asyncio.to_thread(stores.sqlite.get_entities_by_case, investigation_id)
    # ... same logic as get_case_graph()
```

`GET /api/graph/global`:
```python
@router.get("/global")
async def get_global_graph(
    request: Request,
    limit: int = Query(200, ge=1, le=500),
) -> JSONResponse:
    """Return a global graph of all entities up to limit, with inter-entity edges."""
    stores = request.app.state.stores
    # Fetch top N entities by created_at, then collect their edges
```

**IMPORTANT routing order:** Register `/global` before `/{investigation_id}` in the router to prevent `"global"` being matched as an investigation_id parameter.

### Anti-Patterns to Avoid
- **async onMount with return cleanup:** If `onMount` callback is async, the returned cleanup function will NOT be called automatically by Svelte. Keep the Cytoscape init synchronous in `onMount`.
- **Calling cy.layout().run() before elements are added:** Always `cy.add([...nodes, ...edges])` first, then run layout.
- **Re-initializing cy on every data reload:** Call `cy.elements().remove()` then `cy.add(...)` — do NOT destroy and recreate the Cytoscape instance on data changes. This causes canvas flicker.
- **Registering layout plugins inside onMount:** Register `cytoscape.use(fcose)` at module top-level, not inside lifecycle hooks, to avoid double-registration errors.
- **Overly complex CSS selectors on large graphs:** Each style function call is invoked per-element. Keep style functions lightweight (O(1), no loops).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Force-directed layout algorithm | Custom spring physics | `cytoscape-fcose` | fCoSE handles compound graphs, 400-node performance, constraint support |
| BFS/shortest path | Manual queue BFS in TypeScript | `cy.elements().dijkstra()` / `cy.elements().bfs()` | Built-in, returns traversable Cytoscape collection; handles weighted/directed edges |
| Graph rendering canvas | Raw Canvas 2D / WebGL | Cytoscape.js | Already integrated; handles zoom, pan, selection, events, export |
| Hierarchical attack chain layout | Manual position calculation | `cytoscape-dagre` | Proven dagre algorithm; handles complex DAGs |
| Node tooltip / detail panel | Custom tooltip library | Existing entity-panel sidebar in GraphView | Already built in GraphView.svelte |

**Key insight:** 90% of the required functionality is already scaffolded. Phase 15 is enhancement, not construction.

---

## Common Pitfalls

### Pitfall 1: Route Ordering — `/global` vs `/{investigation_id}`
**What goes wrong:** FastAPI matches `GET /api/graph/global` against `/{investigation_id}` first if declared first, passing `"global"` as the investigation_id parameter.
**Why it happens:** FastAPI routes are matched in declaration order; path parameters match any string.
**How to avoid:** Declare `GET /api/graph/global` BEFORE `GET /api/graph/{investigation_id}` in the router.
**Warning signs:** Backend returns 404 "investigation global not found" or empty graph when hitting /global.

### Pitfall 2: Cytoscape Container Sizing in Flex Layout
**What goes wrong:** Cytoscape canvas renders at 0x0 or incorrect size when the container div has no explicit dimensions.
**Why it happens:** Cytoscape reads the container's computed size at init time. If the parent is a flex container with `flex: 1`, the container may not have resolved size before `onMount` fires.
**How to avoid:** Set `width: 100%; height: 100%` on the `.cy-container` div and ensure the parent flex container has a fixed or percentage height. The existing `flex: 1` + `overflow: hidden` pattern in GraphView.svelte is correct. Call `cy.resize()` after any layout change that might resize the container.
**Warning signs:** Graph renders correctly on second navigation but not on first load.

### Pitfall 3: Dijkstra Requires Directed Graph Awareness
**What goes wrong:** `dijkstra` with `directed: true` finds no path when edges point the wrong direction for the attack scenario.
**Why it happens:** SQLite edges are stored directionally (source_id → target_id). Attack paths may need reverse traversal (e.g., going from detection back to initial access).
**How to avoid:** Use `directed: false` for general path exploration, or implement bidirectional BFS. Alternatively expose a UI toggle. For SOC use, `directed: false` is the safer default since analysts want to discover paths regardless of edge direction.
**Warning signs:** "No path found" when a visual path clearly exists in the graph.

### Pitfall 4: fCoSE Layout Plugin TypeScript Types
**What goes wrong:** TypeScript reports type errors when passing fCoSE layout options because `@types/cytoscape` doesn't include the plugin's layout options.
**Why it happens:** `cytoscape-fcose` does not ship its own `@types` definitions compatible with the core Cytoscape type system.
**How to avoid:** Cast layout options with `as any`: `cy.layout({ name: 'fcose', ... } as any)`. This is the documented workaround (already used in existing GraphView.svelte with `{ name: 'cose', ... } as any`).
**Warning signs:** TypeScript build errors on `cy.layout({ name: 'fcose', ... })`.

### Pitfall 5: GraphEntity `id` Field Shape Mismatch
**What goes wrong:** Backend `GraphEntity` (Pydantic model) uses `id`, `type`, `label`, `attributes` — but frontend `GraphEntity` interface in `api.ts` has dual fields (`id?`, `entity_id?`, `type?`, `entity_type?`, `label?`, `entity_name?`). New endpoints that return the Pydantic model directly will need the existing `normalizeEntity()` function in GraphView.svelte applied to responses.
**Why it happens:** The `api.ts` interface was built to accommodate multiple backend response shapes during iterative development.
**How to avoid:** New endpoints (`/graph/{investigation_id}` and `/graph/global`) should return the canonical Pydantic `GraphResponse.model_dump()` shape (`entities[].id`, `entities[].type`, `entities[].label`, `entities[].attributes`). The existing `normalizeEntity()` in GraphView.svelte handles this. Do NOT introduce a third shape.
**Warning signs:** Nodes render with empty labels or `undefined` IDs.

### Pitfall 6: `cy.animate()` Deprecation Risk
**What goes wrong:** Older animation patterns may not work as expected in Cytoscape 3.31+.
**Why it happens:** Cytoscape 3.x changed animation API slightly from 2.x.
**How to avoid:** Use `ele.animate({ style: {...}, duration: ms })` chained calls for pulsing. Alternatively use CSS class toggling with CSS transitions if animation proves problematic.

---

## Code Examples

Verified patterns from official sources:

### Cytoscape BFS with Path Selection
```typescript
// Source: https://js.cytoscape.org/#eles.bfs + animated-bfs demo
const bfs = cy!.elements().bfs({
  roots: cy!.$(`#${startEntityId}`),
  directed: false,
})
// bfs.path contains all traversed elements in BFS order
bfs.path.select()
```

### Cytoscape Dijkstra for Shortest Path
```typescript
// Source: https://js.cytoscape.org/#eles.dijkstra
const dijkstraResult = cy!.elements().dijkstra({
  root: cy!.$(`#${sourceId}`),
  directed: false,  // use false for attack path exploration
})
const path = dijkstraResult.pathTo(cy!.$(`#${targetId}`))
// path is a Cytoscape collection containing alternating nodes and edges
path.nodes().addClass('attack-path-node')
path.edges().addClass('attack-path-edge')
```

### Backend: SQLite Global Graph Query Pattern
```python
# Source: existing sqlite_store.py pattern
def get_global_entities(self, limit: int = 200) -> list[dict]:
    rows = self._conn.execute(
        "SELECT id, type, name, attributes, case_id, created_at "
        "FROM entities ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    # deserialize attributes JSON per existing pattern
```

### FastAPI Route Ordering (Critical)
```python
# Source: FastAPI docs - path operations evaluated in order
router = APIRouter(prefix="/graph", tags=["graph"])

# MUST come before /{investigation_id}
@router.get("/global")
async def get_global_graph(...): ...

@router.get("/case/{case_id}")
async def get_case_graph(...): ...

@router.get("/{investigation_id}")    # matches last
async def get_investigation_graph(...): ...
```

### GraphView prop interface for navigation
```typescript
// Source: existing App.svelte prop pattern (handleInvestigate callback)
let {
  focusEntityId = $bindable(''),
  onNavigateInvestigation = undefined,
}: {
  focusEntityId?: string
  onNavigateInvestigation?: (investigationId: string) => void
} = $props()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `cose` layout (built-in) | `fcose` plugin | 2020 (fcose stable) | 2x faster, better aesthetics at 100+ nodes |
| `beforeUpdate`/`afterUpdate` | `$effect` runes | Svelte 5 (2024) | Existing code uses onMount/onDestroy — valid in Svelte 5 runes mode |
| `writable()` stores | `$state()` runes | Svelte 5 (2024) | GraphView.svelte already uses `$state` correctly |
| Manual graph traversal | `cy.elements().dijkstra()` | Cytoscape 3.x | Built-in algorithm library covers BFS, Dijkstra, A* |

**Deprecated/outdated:**
- `cose-bilkent` npm package: still works but `cytoscape-fcose` is the newer, faster successor from the same research group.
- `svelte:store` / `writable()`: Not used in this codebase — correctly using runes.

---

## Open Questions

1. **Risk score availability in entity attributes**
   - What we know: `GraphEntity.attributes` is a free-form JSON dict. `backend/intelligence/` (Phase 9) adds `risk_score` to `detections` table.
   - What's unclear: Whether `risk_score` is stored on entities in `attributes` or only on detections.
   - Recommendation: During P15-T02, read `attributes.risk_score` if present; fall back to `0` for nodes without a score. The sizing function should gracefully handle absence.

2. **`/api/graph/global` performance at 200+ entities**
   - What we know: SQLite LIMIT 200 fetch is fast. The concern is frontend rendering — Cytoscape at 500 nodes approaches 20 FPS ceiling.
   - What's unclear: Actual entity counts in production data.
   - Recommendation: Default limit of 100 for global graph; expose a UI slider or `?limit=` param. Document the 500-node performance ceiling.

3. **MITRE ATT&CK tactic overlay implementation depth**
   - What we know: Phase description mentions "MITRE ATT&CK tactic overlays". The `attack_technique` entity type exists in schema.
   - What's unclear: Whether this means colour-coding by tactic (simpler) or a full ATT&CK Navigator-style matrix overlay (much more complex).
   - Recommendation: Implement tactic colour-coding on `attack_technique` nodes using their `attributes.tactic` field. Do NOT build a full ATT&CK Navigator matrix — that is out of scope for a single phase. A node border colour differentiating by tactic is sufficient for SOC utility.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x (uv run pytest) |
| Config file | pyproject.toml (pytest-asyncio mode: auto) |
| Quick run command | `uv run pytest tests/unit/test_graph_api.py -x -q` |
| Full suite command | `uv run pytest -q --tb=short` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P15-T01 | GET /api/graph/{investigation_id} returns entities+edges | unit | `uv run pytest tests/unit/test_graph_api.py::test_investigation_graph -x` | ❌ Wave 0 |
| P15-T01 | GET /api/graph/global returns up to limit entities | unit | `uv run pytest tests/unit/test_graph_api.py::test_global_graph -x` | ❌ Wave 0 |
| P15-T01 | /global route not shadowed by /{investigation_id} | unit | `uv run pytest tests/unit/test_graph_api.py::test_global_route_precedence -x` | ❌ Wave 0 |
| P15-T02 | fCoSE layout plugin registers without error | manual | `cd dashboard && npm run build` exits 0 | ❌ Wave 0 |
| P15-T03 | BFS path highlight — Dijkstra finds path between connected entities | unit (JS) | manual / Vitest if configured | manual-only |
| P15-T04 | Node click triggers onNavigateInvestigation callback | manual | manual browser test | manual-only |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_graph_api.py -x -q`
- **Per wave merge:** `uv run pytest -q --tb=short && cd dashboard && npm run build`
- **Phase gate:** Full suite green + npm build exits 0 before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_graph_api.py` — covers P15-T01 (3 test functions for new endpoints)
- [ ] Install layout plugins: `cd dashboard && npm install cytoscape-fcose cytoscape-dagre`

*(Frontend rendering tests P15-T02/T03/T04 are manual-only — no Vitest configured in this project)*

---

## Sources

### Primary (HIGH confidence)
- Cytoscape.js official docs — https://js.cytoscape.org/ — BFS, Dijkstra, style API, layout API
- Codebase read: `graph/builder.py` — existing BFS traversal implementation
- Codebase read: `backend/api/graph.py` — all 7 existing graph endpoints
- Codebase read: `dashboard/src/views/GraphView.svelte` — full existing stub implementation
- Codebase read: `backend/stores/sqlite_store.py` — entities/edges schema and query methods
- Codebase read: `dashboard/package.json` — cytoscape 3.31.0 confirmed installed
- Codebase read: `backend/models/event.py` — GraphEntity, GraphEdge, GraphResponse models

### Secondary (MEDIUM confidence)
- `cytoscape-fcose` npm/GitHub — version 2.2.0, MIT, fCoSE README confirms registration pattern
- `cytoscape-dagre` npm — version 2.5.0, `@types/cytoscape-dagre` 2.3.4 (updated October 2025)
- WebSearch — Svelte 5 onMount/onDestroy + runes mode: confirmed onMount/onDestroy work in runes-mode components
- WebSearch — fCoSE layout performance: confirmed 2x faster than cose; 286 nodes ~50ms render

### Tertiary (LOW confidence)
- WebSearch — Cytoscape 3.31 animate() API: no version-specific changelog found; general 3.x animate pattern assumed correct

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Cytoscape already installed; fCoSE/dagre npm versions confirmed
- Architecture: HIGH — codebase fully read; existing patterns documented
- Pitfalls: HIGH — route ordering, container sizing, normalizeEntity() all verified against actual code
- BFS/Dijkstra API: HIGH — official Cytoscape.js docs confirmed method signatures
- Svelte 5 lifecycle: HIGH — confirmed onMount/onDestroy valid in runes-mode components

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (stable library domain; Svelte 5/Cytoscape APIs stable)
