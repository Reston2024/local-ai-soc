---
phase: 15-attack-graph-ui
plan: 02
subsystem: api
tags: [fastapi, graph, sqlite, endpoints, investigation]

# Dependency graph
requires:
  - phase: 15-01
    provides: xfail stubs for GET /api/graph/{investigation_id} and GET /api/graph/global
provides:
  - GET /api/graph/global endpoint returning global entity graph with limit parameter
  - GET /api/graph/{investigation_id} endpoint returning per-investigation entity graph
  - Route ordering guaranteeing 'global' is never caught by /{investigation_id} path param
affects: [15-03, frontend AttackGraphView, dashboard graph panel]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Route ordering: literal path segments (/global) must be declared before path-param routes (/{id}) in FastAPI"
    - "GET /graph/{id} as alias for GET /graph/case/{id} — same logic, different URL shape for frontend"

key-files:
  created: []
  modified:
    - backend/api/graph.py
    - tests/unit/test_graph_api.py

key-decisions:
  - "15-02: GET /graph/global inserted before GET /graph/entity/{entity_id} so 'global' is never treated as an entity_id or investigation_id"
  - "15-02: GET /graph/{investigation_id} declared last (after /case/{case_id}) so it catches all unmatched strings"

patterns-established:
  - "Global graph endpoint queries entities table directly via raw SQL with LIMIT, same pattern as list_entities()"
  - "Investigation graph endpoint delegates to get_entities_by_case() + _fetch_edges() helper — mirrors get_case_graph() exactly"

requirements-completed: [P15-T01]

# Metrics
duration: 1min
completed: 2026-03-29
---

# Phase 15 Plan 02: Graph API Endpoints Summary

**Two new FastAPI routes — GET /api/graph/global (bounded entity scan) and GET /api/graph/{investigation_id} (per-case alias) — turn three strict xfail stubs green with correct route-precedence ordering**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-29T12:47:28Z
- **Completed:** 2026-03-29T12:49:01Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Added GET /api/graph/global: queries SQLite entities table with LIMIT, collects internal edges, returns GraphResponse shape
- Added GET /api/graph/{investigation_id}: alias for /graph/case/{id} via get_entities_by_case() + edge deduplication
- Correct FastAPI route ordering: /global declared before any path-param routes, /{investigation_id} declared last
- Removed strict=True xfail marks from all 3 TestPhase15NewEndpoints tests — 28/28 graph API tests now pass
- Full unit suite: 589 passed, 0 failures, no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add GET /api/graph/global and GET /api/graph/{investigation_id}** - `66fbbab` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `backend/api/graph.py` - Added get_global_graph() and get_investigation_graph() route handlers with correct declaration order
- `tests/unit/test_graph_api.py` - Removed @pytest.mark.xfail decorators from TestPhase15NewEndpoints (3 tests)

## Decisions Made
- GET /global placed before GET /entity/{entity_id} to prevent FastAPI routing 'global' as an entity_id
- GET /{investigation_id} placed last in router declaration order so it acts as a catch-all for unmatched strings
- Both handlers follow the existing get_case_graph() pattern for consistency (asyncio.to_thread, GraphResponse.from_stores)

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- GET /api/graph/global and GET /api/graph/{investigation_id} are live and tested
- Plan 03 (frontend AttackGraphView) can now call both endpoints for real graph data
- No blockers

---
*Phase: 15-attack-graph-ui*
*Completed: 2026-03-29*
