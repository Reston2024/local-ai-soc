---
phase: "06"
plan: "05"
subsystem: frontend-dashboard
tags: [svelte5, cytoscape, dagre, attack-graph, investigation-panel, mitre-attck, timeline-filter]
dependency_graph:
  requires: ["06-04"]
  provides: ["AttackChain.svelte", "InvestigationPanel.svelte", "api.ts Phase 6 types"]
  affects: ["frontend/src/components/graph", "frontend/src/components/panels", "frontend/src/lib/api.ts"]
tech_stack:
  added: ["cytoscape-dagre@^2.5.0"]
  patterns:
    - "Svelte 5 runes ($state, $derived, $effect, $props — single call per component)"
    - "Cytoscape.js dagre layout (rankDir: TB) for directed attack-graph DAG"
    - "Attack-path highlighting via data('attackPath') CSS selector override"
    - "e.src/e.dst -> Cytoscape source/target mapping (GraphEdge schema)"
key_files:
  created:
    - frontend/src/components/graph/AttackChain.svelte
    - frontend/src/components/panels/InvestigationPanel.svelte
  modified:
    - frontend/src/lib/api.ts
    - frontend/package.json
    - frontend/package-lock.json
decisions:
  - "cytoscape.use(dagre) called at module level — safe to call multiple times, no guard needed"
  - "$props() called once per component with all props merged (Svelte 5 constraint)"
  - "timeFrom/timeTo state lives in InvestigationPanel; parent notified via onFilterApplied callback"
  - "TestDashboardBuild remains XFAIL(strict=False) — npm subprocess can't resolve npm in test runner PATH; actual build verified separately"
metrics:
  duration_seconds: 239
  completed_date: "2026-03-17"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 3
---

# Phase 6 Plan 05: Dashboard Components — AttackChain + InvestigationPanel Summary

**One-liner:** Svelte 5 attack-graph visualization with cytoscape-dagre layout, orange attack-path highlighting, and investigation sidebar with MITRE techniques, AI summary button, and datetime-local timeline filter.

## Tasks Completed

| # | Task | Commit | Key Files |
|---|------|--------|-----------|
| 1 | Install cytoscape-dagre and extend api.ts | 53865ef | frontend/package.json, frontend/src/lib/api.ts |
| 2 | Create AttackChain.svelte and InvestigationPanel.svelte | 3001155 | frontend/src/components/graph/AttackChain.svelte, frontend/src/components/panels/InvestigationPanel.svelte |

## What Was Built

### Task 1: cytoscape-dagre + api.ts Phase 6 extensions

Installed `cytoscape-dagre@^2.5.0` into frontend dependencies. Extended `api.ts` with the full Phase 6 type surface:

- `CausalityGraphNode`, `CausalityGraphEdge` (src/dst not source/target), `AttackPath`, `MitreTechnique` interfaces
- `CausalityGraphResponse`, `InvestigationQueryRequest/Response`, `InvestigationSummaryResponse` interfaces
- `getAttackGraph(alertId, opts?)` — GET /api/graph/{id}?from=&to= with optional time-range params
- `getAttackChain(alertId)` — GET /api/attack_chain/{id}
- `investigationQuery(params)` — POST /api/query
- `getInvestigationSummary(alertId)` — POST /api/investigate/{id}/summary

All causality endpoints use `/api/` prefix per CONTEXT.md locked decision.

### Task 2: AttackChain.svelte

Cytoscape.js attack-graph component using the dagre layout plugin:

- Registers `cytoscape.use(dagre)` at module level (safe to call multiple times)
- Calls `getAttackGraph(alertId)` on mount and whenever `alertId` changes (`$effect`)
- Maps `edge.src -> source`, `edge.dst -> target` for Cytoscape (GraphEdge schema uses src/dst)
- dagre layout: `{ name: 'dagre', rankDir: 'TB', nodeSep: 50, rankSep: 80 }`
- `highlightAttackPaths()` marks attack-path nodes/edges via `data('attackPath', true)`
- CSS selectors: `node[attackPath]` → orange (`#f97316`) border; `edge[attackPath]` → orange line, width 3
- 7-color `NODE_COLORS` map: host/ip/alert/user/domain/process/file
- `onNodeSelect` prop callback fires on node tap
- `loading` and `error` states with overlay display
- Full Svelte 5 runes: `$props()`, `$state()`, `$effect()`

### Task 2: InvestigationPanel.svelte

Investigation sidebar panel:

- Score badge with dynamic color: red >60, yellow 30-60, green <30
- Timeline range display (firstEvent to lastEvent)
- **Timeline filter** (locked CONTEXT.md capability): `timeFrom`/`timeTo` datetime-local inputs, Apply Filter button calls `getAttackGraph` with ?from/to params and emits `onFilterApplied` callback, Clear button resets state
- MITRE ATT&CK techniques list: technique-id (monospace blue), name, tactic badge
- AI Summary section: "Generate Summary" button calls `getInvestigationSummary(alertId)`, loading/error/result states
- Single `$props()` call with all 6 props merged (Svelte 5 constraint)
- Full Svelte 5 runes throughout

## Verification Results

- `npm run build` exits 0 (vite 6.4.1, 684 modules, 1.30s)
- Full test suite: 41 passed + 42 xpassed + 1 xfailed (strict=False) — no regressions
- Phase 6 tests: 15/16 XPASS; 1 XFAIL (TestDashboardBuild, strict=False — npm not on PATH in subprocess)

## Deviations from Plan

None — plan executed exactly as written. The single $props() merge mentioned in the plan's implementation note was applied correctly.

## Self-Check: PASSED

- frontend/src/components/graph/AttackChain.svelte: FOUND
- frontend/src/components/panels/InvestigationPanel.svelte: FOUND
- frontend/src/lib/api.ts: FOUND (modified)
- Commit 53865ef: FOUND (Task 1)
- Commit 3001155: FOUND (Task 2)
