---
phase: 15-attack-graph-ui
plan: 03
subsystem: ui
tags: [cytoscape, fcose, dagre, svelte5, attack-graph, mitre, dijkstra]

# Dependency graph
requires:
  - phase: 15-attack-graph-ui plan 01
    provides: cytoscape-fcose and cytoscape-dagre npm packages installed, xfail stubs for graph API endpoints

provides:
  - fCoSE force-directed layout replacing basic cose in GraphView.svelte
  - Risk-scored node sizing driven by risk_score attribute (20-50px range)
  - Two-click Dijkstra attack path highlighting with red edge/node styling
  - attack-path-node / attack-path-edge CSS classes with clear/toggle controls
  - MITRE ATT&CK tactic badge for attack_technique nodes in entity panel
  - api.graph.caseGraph(caseId) and api.graph.global(limit) typed methods in api.ts

affects: [15-04, graph-navigation, attack-path-analysis]

# Tech tracking
tech-stack:
  added: [cytoscape-fcose (module-level registration), cytoscape-dagre (module-level registration)]
  patterns:
    - "cytoscape plugins registered at module scope with cytoscape.use() — not inside onMount"
    - "Dijkstra path highlighting via two-click tap handler (first=source, second=target+highlight)"
    - "Risk scoring via cytoscape data functions (ele.data()) instead of fixed pixel sizes"

key-files:
  created: []
  modified:
    - dashboard/src/views/GraphView.svelte
    - dashboard/src/lib/api.ts

key-decisions:
  - "15-03: fCoSE layout options nodeRepulsion:4500 / idealEdgeLength:80 / edgeElasticity:0.45 / nodeSeparation:75 per plan spec — provides SOC-appropriate spread"
  - "15-03: Two-click attack path with pathSource state — avoids modal dialogs; clear visual hint shown between first and second click"
  - "15-03: directed:false in Dijkstra for SOC exploration — lateral movement paths often traverse undirected relationships"

patterns-established:
  - "Attack path: pathSource state cleared on clearAttackPath(); showPathOnly toggled via onchange hiding non-path elements"
  - "MITRE tactic badge rendered conditionally only when entity type is attack_technique and tactic attribute exists"

requirements-completed: [P15-T02, P15-T03]

# Metrics
duration: 12min
completed: 2026-03-29
---

# Phase 15 Plan 03: Attack Graph Visual Core Summary

**fCoSE force-directed layout with risk-scored nodes, two-click Dijkstra attack path highlighting, MITRE tactic overlay, and api.graph.caseGraph()/global() typed methods**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-29T12:47:35Z
- **Completed:** 2026-03-29T12:59:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Replaced basic cose layout with fCoSE (cytoscape-fcose registered at module level) — nodes now spread with force-directed physics matching SOC topology expectations
- Risk-scored node sizing: width/height driven by `risk_score` attribute data function (20px min, 50px max) so high-risk entities visually stand out
- Two-click Dijkstra attack path: first node tap sets source (shows hint banner), second tap computes shortest path via `cy.elements().dijkstra()` and applies red `attack-path-node` / `attack-path-edge` CSS classes with animate pulse
- MITRE ATT&CK tactic badge rendered in entity panel for `attack_technique` node type when `tactic` attribute is present
- `api.graph.caseGraph()` and `api.graph.global()` typed methods added to api.ts graph namespace

## Task Commits

1. **Task 1: Add api.graph.caseGraph() and api.graph.global() to api.ts** - `a8de2a7` (feat)
2. **Task 2: Enhance GraphView.svelte with fCoSE layout, risk scoring, and attack path highlighting** - `7742f47` (feat)

## Files Created/Modified

- `dashboard/src/lib/api.ts` - Added caseGraph(caseId) and global(limit) typed methods to graph namespace
- `dashboard/src/views/GraphView.svelte` - fCoSE layout, risk-scored sizing, Dijkstra attack path, MITRE tactic badge, path clear/toggle controls

## Decisions Made

- fCoSE layout options follow plan spec: nodeRepulsion:4500, idealEdgeLength:80, edgeElasticity:0.45, nodeSeparation:75 — chosen to give SOC-appropriate node spread without clutter
- `directed: false` in Dijkstra per plan spec — lateral movement paths often traverse non-directed entity relationships
- Two-click selection mechanism using `pathSource` state variable rather than a modal dialog — lower friction for analysts scanning graphs

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — cytoscape-fcose and cytoscape-dagre were already in package.json from Phase 15 Plan 01. Build succeeded on first attempt for both tasks.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- GraphView.svelte now exposes full attack path API through tap events — Plan 04 can wire case/global navigation on top
- Props interface for caseId / globalMode not yet added to GraphView — Plan 04 will add these as Svelte props
- All success criteria from 15-03 met: fCoSE registered at module level, risk-scored sizing, attack-path CSS classes, no remaining `name: 'cose'` references, api.ts has both new graph methods

---
*Phase: 15-attack-graph-ui*
*Completed: 2026-03-29*
