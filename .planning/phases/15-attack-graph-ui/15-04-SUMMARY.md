---
phase: 15-attack-graph-ui
plan: "04"
subsystem: dashboard
tags: [svelte5, graph, navigation, investigation, cytoscape]
dependency_graph:
  requires: [15-02, 15-03]
  provides: [bidirectional-graph-investigation-navigation]
  affects: [dashboard/src/App.svelte, dashboard/src/views/GraphView.svelte, dashboard/src/views/InvestigationView.svelte]
tech_stack:
  added: []
  patterns: [svelte5-props, svelte5-bindable, svelte5-effect, prop-callbacks]
key_files:
  created: []
  modified:
    - dashboard/src/App.svelte
    - dashboard/src/views/GraphView.svelte
    - dashboard/src/views/InvestigationView.svelte
decisions:
  - "focusEntityId uses $bindable('') to allow two-way binding from App parent"
  - "Investigate case button conditioned on both onNavigateInvestigation presence and case_id attribute — safe for standalone GraphView use"
  - "'Open in Graph' passes investigationId as entityId — the same ID used by GET /api/graph/{investigation_id}"
  - "header-actions flex container added to InvestigationView timeline panel header for multiple button layout"
metrics:
  duration_seconds: 92
  completed_date: "2026-03-29"
  tasks_completed: 3
  files_modified: 3
---

# Phase 15 Plan 04: Graph-Investigation Bidirectional Navigation Summary

Wired full Graph ↔ InvestigationView bidirectional navigation: "Open in Graph" button in InvestigationView launches GraphView centred on the investigation entity; clicking a graph node with a case_id shows an "Investigate case" button that switches to InvestigationView for that case.

## What Was Built

### Task 1 — GraphView Props and Navigation Effect (commit def627d)

Added `$props()` declaration to `GraphView.svelte` with two new props:
- `focusEntityId?: string` (with `$bindable('')`) — when set, triggers `loadSubgraph()` via `$effect`
- `onNavigateInvestigation?: (investigationId: string) => void` — callback invoked by "Investigate case" button

Added `$effect(() => { if (focusEntityId && cy) loadSubgraph(focusEntityId) })` after attack path state declarations.

Added "Investigate case" button in the entity panel, conditionally rendered when `onNavigateInvestigation` is provided and the selected entity has a `case_id` in its `attributes` or `properties`. The button calls `onNavigateInvestigation(String(caseId))`.

### Task 2 — App.svelte State Lift and InvestigationView Button (commit 40932e6)

**App.svelte:**
- Added `let graphFocusEntityId = $state<string>('')`
- Added `handleOpenInGraph(entityId)` → sets `graphFocusEntityId`, switches view to `'graph'`
- Added `handleNavigateInvestigation(investigationId)` → sets `investigatingId`, switches view to `'investigation'`
- Updated `<InvestigationView>` binding to pass `onOpenInGraph={handleOpenInGraph}`
- Updated `<GraphView>` binding to pass `focusEntityId={graphFocusEntityId}` and `onNavigateInvestigation={handleNavigateInvestigation}`

**InvestigationView.svelte:**
- Extended `$props()` to include `onOpenInGraph?: (entityId: string) => void`
- Added "Open in Graph" button in the timeline panel header, visible when `onOpenInGraph` is provided and `investigationId` is non-empty
- Added `.header-actions` flex container style for multi-button header layout

### Task 3 — Human Verify (auto-approved, auto_advance: true)

Navigation wiring verified by build success. Both `npm run build` passes exit 0 with no TypeScript errors.

## Verification

- `npm run build` exits 0 (both tasks)
- `uv run pytest tests/unit/ -q` — 589 passed, 1 skipped, 16 xpassed

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED
