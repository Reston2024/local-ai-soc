---
phase: 15-attack-graph-ui
plan: 01
subsystem: testing
tags: [pytest, xfail, cytoscape, npm, graph, tdd]

# Dependency graph
requires: []
provides:
  - Three xfail(strict=True) test stubs for P15 graph endpoints in TestPhase15NewEndpoints
  - cytoscape-fcose@2.2.0 and cytoscape-dagre@2.5.0 in dashboard/node_modules and package.json
affects:
  - 15-02-PLAN (implements the xfail endpoints to turn XFAIL -> XPASS)
  - 15-03-PLAN (imports cytoscape-fcose and cytoscape-dagre layout plugins)

# Tech tracking
tech-stack:
  added: [cytoscape-fcose@2.2.0, cytoscape-dagre@2.5.0]
  patterns: [wave-0 xfail stubs before implementation, strict=True xfail for mandatory unblock]

key-files:
  created: []
  modified:
    - tests/unit/test_graph_api.py
    - dashboard/package.json
    - dashboard/package-lock.json

key-decisions:
  - "strict=True on all xfail marks so XPASS signals Plan 02 succeeded and stubs need removal"
  - "No @types packages needed for cytoscape plugins — existing codebase uses 'as any' cast for layout options"

patterns-established:
  - "Wave-0 xfail pattern: write strict xfail stubs before endpoint implementation to enforce RED state"

requirements-completed: [P15-T01, P15-T02]

# Metrics
duration: 5min
completed: 2026-03-29
---

# Phase 15 Plan 01: Attack Graph UI Wave-0 Setup Summary

**Three strict xfail test stubs for new graph endpoints plus cytoscape-fcose@2.2.0 and cytoscape-dagre@2.5.0 installed in dashboard**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-29T12:44:18Z
- **Completed:** 2026-03-29T12:49:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Appended `TestPhase15NewEndpoints` class with 3 xfail(strict=True) methods to tests/unit/test_graph_api.py
- All 25 pre-existing graph API tests remain green; 3 new tests show XFAIL (not ERROR)
- Installed cytoscape-fcose@2.2.0 and cytoscape-dagre@2.5.0 via npm — both present in node_modules and package.json
- npm run build exits 0 with new packages present

## Task Commits

Each task was committed atomically:

1. **Task 1: Add xfail stubs for new graph endpoints** - `6869568` (test)
2. **Task 2: Install cytoscape-fcose and cytoscape-dagre npm packages** - `7d556f0` (chore)

## Files Created/Modified
- `tests/unit/test_graph_api.py` - Appended TestPhase15NewEndpoints with 3 strict xfail methods
- `dashboard/package.json` - Added cytoscape-fcose@^2.2.0 and cytoscape-dagre@^2.5.0 to dependencies
- `dashboard/package-lock.json` - Updated lockfile with 7 new transitive packages

## Decisions Made
- Used `strict=True` on all xfail marks — once Plan 02 implements the endpoints correctly they become XPASS, signaling stubs should be removed
- No TypeScript `@types` packages added — existing codebase uses `as any` cast for layout options (confirmed in GraphView.svelte)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 02 executor has clear failing tests to satisfy: TestPhase15NewEndpoints::test_investigation_graph, test_global_graph, test_global_route_precedence
- Plan 03 executor has cytoscape-fcose and cytoscape-dagre available in node_modules — no additional npm install needed

---
*Phase: 15-attack-graph-ui*
*Completed: 2026-03-29*
