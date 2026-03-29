---
phase: 15-attack-graph-ui
verified: 2026-03-29T14:00:00Z
status: passed
score: 12/12 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "fCoSE force-directed layout visual spread"
    expected: "Nodes appear spread out in a natural force-directed layout (not in a tight circle), with larger nodes for higher risk_score entities"
    why_human: "Layout rendering and node sizing requires live Cytoscape.js in a browser — cannot verify CSS data-functions produce correct pixel dimensions programmatically"
  - test: "Two-click attack path highlighting"
    expected: "First node click sets path source (hint banner appears). Second node click triggers Dijkstra shortest path — thick red edges (#f85149) and red-bordered nodes appear along the path. 'Clear Path' button resets to full graph."
    why_human: "Cytoscape.js Dijkstra traversal and CSS class application require live browser DOM interaction"
  - test: "InvestigationView 'Open in Graph' -> GraphView focus"
    expected: "Clicking 'Open in Graph' in InvestigationView switches to Attack Graph view and loads the subgraph centred on the investigation entity"
    why_human: "Cross-view navigation state flow requires browser interaction with the Svelte 5 SPA"
  - test: "GraphView 'Investigate case' -> InvestigationView"
    expected: "Clicking a graph node that has a case_id attribute reveals 'Investigate case' button; clicking it switches to Investigation view for that case_id"
    why_human: "Conditional rendering based on live entity data attributes requires browser interaction"
---

# Phase 15: Attack Graph UI Verification Report

**Phase Goal:** Transform the stub Attack Graph view into a production interactive network graph using Cytoscape.js — rendering entities as nodes and relationships as edges, with risk-scored colouring, MITRE ATT&CK tactic overlays, attack path BFS highlighting, and bidirectional InvestigationView integration.

**Verified:** 2026-03-29
**Status:** PASSED (automated checks) + 4 items require human browser verification
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | GET /api/graph/global returns { entities, edges, total_entities, total_edges } with status 200 | VERIFIED | `@router.get("/global")` at line 142, `get_global_graph()` returns `GraphResponse.model_dump(mode="json")`; 28/28 graph API tests pass |
| 2  | GET /api/graph/{investigation_id} returns { case_id, entities, edges, total_entities } with status 200 | VERIFIED | `@router.get("/{investigation_id}")` at line 382, returns `{"case_id": investigation_id, **response.model_dump(mode="json")}`; TestPhase15NewEndpoints::test_investigation_graph passes |
| 3  | "global" string is not matched by /{investigation_id} — route ordering is correct | VERIFIED | Router order: `/global` (line 142) declared before `/entity/{entity_id}` (line 195), `/case/{case_id}` (line 328), and `/{investigation_id}` (line 382); test_global_route_precedence passes |
| 4  | Both endpoints read from SQLite graph store, not DuckDB | VERIFIED | `get_global_graph` queries `stores.sqlite._conn.execute(...)` and calls `stores.sqlite.get_edges_from()`; `get_investigation_graph` delegates to `stores.sqlite.get_entities_by_case()` |
| 5  | GraphView renders nodes sized proportionally to risk_score (20px min, 50px max) | VERIFIED | `buildCytoStyle()` lines 71-78: `'width': (ele: any) => Math.max(20, Math.min(50, 20 + score * 0.3))` — data function present and substantive |
| 6  | Entity type colours applied: user=blue/green, device=green, IP=orange, process=amber | VERIFIED | `typeColors` map at lines 43-55: host=#58a6ff (blue), user=#3fb950 (green), process=#d29922 (amber), ip=#ffa657 (orange), attack_technique=#ff6b6b |
| 7  | Layout uses fCoSE plugin at module level (not inside onMount) | VERIFIED | `cytoscape.use(fcose)` at line 8, `cytoscape.use(dagre)` at line 9 — before any `let` declarations; no remaining `name: 'cose'` references in GraphView.svelte |
| 8  | Two-click node tap triggers attack path highlighting with thick red edges | VERIFIED (code) | `highlightAttackPath()` function at lines 151-170 implements Dijkstra; two-click logic in `initCy()` tap handler lines 238-243; `attack-path-edge` CSS class sets `'width': 4, 'line-color': '#f85149'` |
| 9  | Attack path toggle switches between full-graph and attack-path-only views | VERIFIED (code) | `showPathOnly` state + `clearAttackPath()` function; template shows Clear Path button and Path-only toggle when `attackPathActive` is true |
| 10 | MITRE ATT&CK tactic shown as badge for attack_technique nodes | VERIFIED (code) | Template lines 340-344: conditionally renders `.tactic-badge` div when `entity.type === 'attack_technique'` and `attributes.tactic` exists |
| 11 | api.ts graph namespace has caseGraph() and global() methods | VERIFIED | `api.graph.caseGraph()` (lines 176-179) and `api.graph.global()` (lines 180-183) present and typed correctly in api.ts |
| 12 | Bidirectional Graph <-> InvestigationView navigation is wired | VERIFIED (code) | App.svelte: `graphFocusEntityId` state (line 25), `handleOpenInGraph()` (lines 33-36), `handleNavigateInvestigation()` (lines 38-41); `<InvestigationView onOpenInGraph={handleOpenInGraph}>` (lines 228-231); `<GraphView focusEntityId={graphFocusEntityId} onNavigateInvestigation={handleNavigateInvestigation}>` (lines 235-238); InvestigationView has `onOpenInGraph` prop and "Open in Graph" button (lines 7-11, 98-100) |

**Score:** 12/12 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/unit/test_graph_api.py` | Wave 0 xfail stubs (now passing) for P15-T01 | VERIFIED | `TestPhase15NewEndpoints` class at line 261 with 3 passing tests; 28/28 graph API tests pass; no xfail markers remain |
| `dashboard/package.json` | cytoscape-fcose@^2.2.0 and cytoscape-dagre@^2.5.0 in dependencies | VERIFIED | Both packages listed under `"dependencies"` in package.json; node_modules directories confirmed present |
| `backend/api/graph.py` | GET /api/graph/global and GET /api/graph/{investigation_id} endpoints | VERIFIED | Both handlers implemented at lines 142 and 382 respectively; 467 lines, substantive implementations |
| `dashboard/src/views/GraphView.svelte` | fCoSE layout, risk-scored nodes, attack path highlighting, path toggle, MITRE tactic border; min 350 lines | VERIFIED | 458 lines; all required features present — fcose/dagre registered at module level, risk-scored sizing, Dijkstra path highlighting, attack path CSS classes, MITRE tactic badge |
| `dashboard/src/lib/api.ts` | api.graph.caseGraph() and api.graph.global() typed methods | VERIFIED | Both methods present at lines 176-183 with correct return types |
| `dashboard/src/App.svelte` | graphFocusEntityId state, handleOpenInGraph, handleNavigateInvestigation callbacks, updated view bindings | VERIFIED | All three items at lines 25, 33-36, 38-41; InvestigationView and GraphView bindings updated |
| `dashboard/src/views/InvestigationView.svelte` | onOpenInGraph prop and "Open in Graph" button wired to entity_id | VERIFIED | Prop declared at line 7-11; button rendered at lines 98-100 inside `.header-actions` |
| `dashboard/src/views/GraphView.svelte` | focusEntityId prop, onNavigateInvestigation prop, $effect for focus, "Investigate case" button | VERIFIED | $props() at lines 11-17; $effect at lines 35-39; "Investigate case" button at lines 363-369 |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `cytoscape.use(fcose)` | module-level registration | Import + use before onMount | VERIFIED | Lines 4-9: imports then `cytoscape.use(fcose)` / `cytoscape.use(dagre)` at module scope before `$props()` |
| GraphView node tap handler | `highlightAttackPath(pathSource, data.id)` | Two-click selection via `pathSource` state | VERIFIED | Lines 238-243: `if (!pathSource) pathSource = data.id; else if (pathSource !== data.id) { pathTarget = data.id; highlightAttackPath(pathSource, data.id) }` |
| `cy.elements().dijkstra()` | `attack-path-node / attack-path-edge` CSS classes | `pathCollection.nodes().addClass / edges().addClass` | VERIFIED | Lines 152-169: `dijkstra({root, directed: false})`, `pathTo()`, `addClass('attack-path-node')`, `addClass('attack-path-edge')` |
| InvestigationView "Open in Graph" button | App.svelte `handleOpenInGraph(entityId)` | `onOpenInGraph` prop callback | VERIFIED | InvestigationView passes `investigationId` to `onOpenInGraph?.(investigationId)`; App.svelte binds `onOpenInGraph={handleOpenInGraph}` |
| App.svelte `handleOpenInGraph` | GraphView `focusEntityId` prop | `graphFocusEntityId` $state passed as prop | VERIFIED | `graphFocusEntityId = entityId; currentView = 'graph'`; `<GraphView focusEntityId={graphFocusEntityId}>` |
| GraphView node tap | App.svelte `handleNavigateInvestigation` | `onNavigateInvestigation` prop callback | VERIFIED | "Investigate case" button in entity panel calls `onNavigateInvestigation(String(caseId))`; App.svelte binds `onNavigateInvestigation={handleNavigateInvestigation}` |
| GET /api/graph/global | sqlite.entities table | `asyncio.to_thread` SELECT with LIMIT | VERIFIED | `_list_global()` uses `stores.sqlite._conn.execute("SELECT ... FROM entities ORDER BY created_at DESC LIMIT ?")` |
| GET /api/graph/{investigation_id} | sqlite.get_entities_by_case() | `asyncio.to_thread` | VERIFIED | `await asyncio.to_thread(stores.sqlite.get_entities_by_case, investigation_id)` at line 390 |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| P15-T01 | 15-02-PLAN | Graph data API extension — GET /api/graph/{investigation_id} and GET /api/graph/global from SQLite store | SATISFIED | Both endpoints implemented in graph.py; 28/28 unit tests pass; route ordering correct (global before path-param) |
| P15-T02 | 15-03-PLAN | Cytoscape.js component — fCoSE/hierarchical layout, risk-scored node sizing, entity type colours, edge labels, hover tooltips | SATISFIED | GraphView.svelte 458 lines; fCoSE at module level; risk-scored width/height via data functions; typeColors map; edge `edge_type` labels; entity panel on tap |
| P15-T03 | 15-03-PLAN | Attack path highlighting — BFS/Dijkstra from source to target, thick red edges, toggle between full and path-only view | SATISFIED | `highlightAttackPath()` with Dijkstra; `attack-path-node` / `attack-path-edge` CSS classes; `showPathOnly` toggle; `clearAttackPath()` |
| P15-T04 | 15-04-PLAN | Graph <-> Investigation integration — node click navigates to InvestigationView; "Open in Graph" button launches GraphView centred on entity | SATISFIED | Full bidirectional wiring in App.svelte; `focusEntityId` prop + `$effect` in GraphView; "Open in Graph" button in InvestigationView; "Investigate case" button in GraphView entity panel |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `dashboard/src/views/GraphView.svelte` | 8-9 | `cytoscape.use(fcose/dagre)` registered inside `<script>` tag of Svelte component — these run once per module load, not per component instance | Info | Safe: Svelte modules execute once; idempotent for cytoscape.use(). No functional issue. |
| `dashboard/src/App.svelte` | All | No anti-patterns found | — | — |
| `backend/api/graph.py` | 119 | `import json as _json` inside nested function `_list_global` | Info | Minor style issue; functionally correct since Python caches imports. Not a blocker. |

No blockers or warnings found.

---

## Human Verification Required

### 1. fCoSE Force-Directed Layout and Risk-Scored Node Sizing

**Test:** Open http://localhost:5173, navigate to "Attack Graph". Ingest sample events or use existing entities. Observe the graph.
**Expected:** Nodes spread out naturally in a force-directed layout (not in a tight circle). Entities with higher `risk_score` attributes should appear visually larger (up to 50px) compared to baseline entities (20px minimum).
**Why human:** Cytoscape.js layout physics and CSS data-function sizing require live browser rendering to verify visually.

### 2. Two-Click Attack Path Highlighting

**Test:** In Attack Graph view with at least 2 connected nodes, click one node. Observe the hint banner. Click a second connected node.
**Expected:** After first click, a hint banner shows "Click target node to highlight path from {id}...". After second click, thick red edges (#f85149) and red-bordered nodes appear along the shortest Dijkstra path. "Clear Path" and "Path only" controls appear in the toolbar. Clicking "Clear Path" resets the graph to normal.
**Why human:** Cytoscape.js Dijkstra traversal and addClass/animate calls require live browser DOM.

### 3. InvestigationView "Open in Graph" Navigation

**Test:** Navigate to "Investigation" view. If an active investigation exists, click the "Open in Graph" button in the timeline panel header.
**Expected:** The view switches to "Attack Graph" and the graph loads centred on the investigation's entity (via `loadSubgraph(focusEntityId)` triggered by the `$effect`).
**Why human:** Cross-view Svelte 5 state propagation and $effect reactivity require live browser SPA interaction.

### 4. GraphView "Investigate case" Navigation

**Test:** In Attack Graph view, click a node that belongs to an investigation (has `case_id` in its attributes or properties). Observe the entity panel on the right.
**Expected:** The entity panel shows an "Investigate case" button (only when `case_id` attribute is present). Clicking it switches to "Investigation" view for that case_id.
**Why human:** Conditional rendering based on live entity attribute data and callback invocation require browser interaction.

---

## Build and Test Evidence

- `npm run build` exits 0 (441 modules, no TypeScript errors; chunk size warning is non-blocking)
- `uv run pytest tests/unit/test_graph_api.py` — 28 passed in 1.48s
- `uv run pytest tests/unit/` — 589 passed, 1 skipped, 16 xpassed in 8.05s (no regressions)
- `cytoscape-fcose@2.2.0` and `cytoscape-dagre@2.5.0` present in `dashboard/node_modules/`

---

## Summary

All 12 must-haves verified. The phase goal is achieved at the code level:

- **P15-T01 (API):** GET /api/graph/global and GET /api/graph/{investigation_id} are fully implemented in backend/api/graph.py with correct FastAPI route ordering. All 28 graph API unit tests pass. Both endpoints read from SQLite store via asyncio.to_thread.

- **P15-T02 (Cytoscape component):** GraphView.svelte is a 458-line production component. cytoscape-fcose is registered at module scope (lines 8-9). Nodes use data-function sizing driven by risk_score (20-50px). Entity type colours match requirements. Edge labels display edge_type. Entity panel renders on node tap.

- **P15-T03 (Attack path):** highlightAttackPath() implements Dijkstra with directed:false. Two-click tap handler wired. attack-path-node and attack-path-edge CSS classes defined with thick red (#f85149) styling. showPathOnly toggle and clearAttackPath() function present. No remaining `name: 'cose'` references.

- **P15-T04 (Navigation wiring):** Complete bidirectional wiring in App.svelte. graphFocusEntityId state lifted. InvestigationView has "Open in Graph" button. GraphView has focusEntityId prop with $effect, and "Investigate case" button in entity panel. All key_links verified as connected.

4 items flagged for human browser verification (visual rendering, live interaction flows).

---

_Verified: 2026-03-29_
_Verifier: Claude (gsd-verifier)_
