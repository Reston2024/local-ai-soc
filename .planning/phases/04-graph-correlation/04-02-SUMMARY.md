---
phase: 04-graph-correlation
plan: 02
subsystem: graph
tags: [graph, builder, models, pydantic, cytoscape, svelte, tdd, attack-paths, union-find]

# Dependency graph
requires:
  - phase: 04-graph-correlation
    plan: 01
    provides: xfail test stubs for Phase 4 graph features
provides:
  - Full Phase 4 Pydantic graph schema (GraphNode, GraphEdge, AttackPath, GraphResponse)
  - build_graph(events, alerts) with node/edge extraction and Union-Find attack path grouping
  - GET /graph endpoint returning {nodes, edges, attack_paths, stats}
  - GET /graph/correlate scaffold endpoint
  - ThreatGraph.svelte Cytoscape component with attack-path highlighting and node detail panel
affects: [04-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Union-Find (path-compressed) for connected-component attack path grouping
    - _get_or_create_node helper with ISO string min/max for first_seen/last_seen tracking
    - e.src/e.dst Cytoscape mapping (backend schema propagated to frontend)
    - Svelte 5 $state(null) for selectedNode side panel

key-files:
  created:
    - dashboard/src/components/graph/ThreatGraph.svelte
  modified:
    - backend/src/api/models.py
    - backend/src/graph/builder.py
    - backend/src/api/routes.py
    - dashboard/src/lib/api.ts
    - backend/src/tests/test_phase4.py

key-decisions:
  - "GraphEdge uses src/dst fields (not source/target) — schema locked in CONTEXT.md"
  - "Union-Find path compression on node IDs (not event IDs) for attack path grouping"
  - "SEVERITY_RANK dict for max-severity computation across connected components"
  - "_get_or_create_node merges evidence lists and updates ISO string timestamps in place"
  - "ThreatGraph.svelte created in dashboard/src/components/graph/ (plan said frontend/ — deviation resolved per actual project layout)"
  - "getGraph()/getGraphCorrelate() added as module-level exports in api.ts alongside api object"

requirements-completed:
  - FR-4.1

# Metrics
duration: 7min
completed: 2026-03-16
---

# Phase 4 Plan 02: Graph Builder + Models + ThreatGraph Summary

**Full Phase 4 graph schema with Union-Find attack path grouping, src/dst edge rename, and Cytoscape ThreatGraph component with attack-path highlighting**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-03-16T07:15:23Z
- **Completed:** 2026-03-16T07:22:30Z
- **Tasks:** 2
- **Files modified:** 5 (4 modified, 1 created)

## Accomplishments

- Replaced stub GraphNode/GraphEdge/GraphResponse Pydantic models with full Phase 4 schema
- Added AttackPath model with node_ids, edge_ids, severity, first_event, last_event
- Rewrote builder.py: _extract_nodes (host/ip/domain/alert/user/process), _extract_edges (connection/dns_query/alert_trigger), _group_attack_paths (Union-Find per connected component), build_graph(events, alerts)
- Updated GET /graph route to pass _alerts; added GET /graph/correlate scaffold
- Created ThreatGraph.svelte with e.src/e.dst Cytoscape mapping, attack-path-highlight CSS class, $state(null) selectedNode, evidence list + attributes in side panel
- Added Phase4GraphResponse interface, getGraph(), getGraphCorrelate() to api.ts
- All 41 prior regression tests still pass; 8 Phase 4 stubs now xpassed; TestCorrelation correctly stays xfail (Plan 03)

## Task Commits

1. **Task 1: Replace Pydantic models + rewrite builder.py** - `d75204b` (feat)
2. **Task 2: Update routes.py, ThreatGraph.svelte, and api.ts** - `452e75a` (feat)

## Files Created/Modified

- `backend/src/api/models.py` - GraphNode (attributes/first_seen/last_seen/evidence), GraphEdge (src/dst), AttackPath, GraphResponse (attack_paths/stats)
- `backend/src/graph/builder.py` - Full builder with _extract_nodes, _extract_edges, _group_attack_paths, build_graph(events, alerts)
- `backend/src/api/routes.py` - AttackPath import, build_graph(_events, _alerts), GET /graph/correlate scaffold
- `dashboard/src/lib/api.ts` - Phase4GraphResponse interface, getGraph(), getGraphCorrelate()
- `dashboard/src/components/graph/ThreatGraph.svelte` - New Cytoscape component with src/dst mapping, attack-path-highlight, node detail panel
- `backend/src/tests/test_phase4.py` - Auto-fixed: .source -> .src on edge assertion (Rule 1)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_phase4.py edge field reference**
- **Found during:** Task 1 verification
- **Issue:** TestEdgeExtraction line 89 asserted `response.edges[0].source is not None` but GraphEdge was renamed to use `src` field — test would fail
- **Fix:** Changed `.source` to `.src` in the assertion
- **Files modified:** `backend/src/tests/test_phase4.py`
- **Commit:** `d75204b`

**2. [Rule 3 - Blocking] Fixed routes.py build_graph call breaks smoke_test**
- **Found during:** Task 1 regression suite
- **Issue:** `build_graph(_events)` call was TypeError after signature changed to require `alerts` argument; smoke_test::test_graph_returns_nodes_and_edges failed
- **Fix:** Updated call to `build_graph(_events, _alerts)` in routes.py
- **Files modified:** `backend/src/api/routes.py`
- **Commit:** `d75204b`

**3. [Path deviation] ThreatGraph.svelte placed in dashboard/ not frontend/**
- **Found during:** Task 2 start
- **Issue:** Plan references `frontend/src/components/graph/ThreatGraph.svelte` but project uses `dashboard/` as the SPA root
- **Fix:** Created at `dashboard/src/components/graph/ThreatGraph.svelte` (correct project layout)
- No code change needed; purely a path resolution

## Issues Encountered

None beyond the auto-fixed items above.

## Self-Check: PASSED
- `backend/src/api/models.py` — FOUND
- `backend/src/graph/builder.py` — FOUND
- `backend/src/api/routes.py` — FOUND
- `dashboard/src/lib/api.ts` — FOUND
- `dashboard/src/components/graph/ThreatGraph.svelte` — FOUND
- Commit `d75204b` — FOUND
- Commit `452e75a` — FOUND
