---
phase: 04-graph-correlation
plan: 01
subsystem: testing
tags: [pytest, xfail, tdd, graph, correlation, attack-paths]

# Dependency graph
requires:
  - phase: 03-detection-rag
    provides: test_phase3.py patterns and xfail conventions established
provides:
  - Phase 4 red baseline — 9 xfail tests across 8 classes covering graph models, node/edge extraction, correlation, attack paths, graph API, alert edges, and correlate route
affects: [04-02, 04-03]

# Tech tracking
tech-stack:
  added: []
  patterns: [xfail stub pattern — all stubs strict=False so xpass doesn't fail suite, pytest.importorskip inside methods to prevent import errors on absent modules]

key-files:
  created:
    - backend/src/tests/test_phase4.py
  modified: []

key-decisions:
  - "pytest.importorskip inside test methods (not module-level) keeps file importable when graph.builder absent"
  - "strict=False on all xfail markers so xpass (e.g. 404-already-working route) doesn't break the suite"
  - "9 tests in 8 classes — TestCorrelateRoute has 2 methods covering known-200 and unknown-404"

patterns-established:
  - "Wave-1 stub file: minimal module-level imports (pytest, TestClient, app only); heavy imports inside methods via importorskip"

requirements-completed:
  - FR-4.1
  - FR-4.5

# Metrics
duration: 1min
completed: 2026-03-16
---

# Phase 4 Plan 01: Graph + Correlation Test Stubs Summary

**9-test xfail red baseline for Phase 4 graph builder, temporal correlation, attack-path grouping, and correlate route — all stubs clean against unmodified codebase**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-16T07:11:15Z
- **Completed:** 2026-03-16T07:12:25Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Created test_phase4.py with 8 test classes and 9 test methods, all xfail(strict=False)
- File imports cleanly against current codebase (no graph.builder or models changes needed)
- 41 prior regression tests still pass; new stubs add xfail count but do not fail suite
- TestCorrelateRoute.test_get_graph_correlate_unknown_returns_404 is xpassed (404 already returned for unknown route) — strict=False handles this correctly

## Task Commits

1. **Task 1: Create test_phase4.py with 8 xfail stub classes** - `650781f` (test)

**Plan metadata:** (docs commit pending)

## Files Created/Modified
- `backend/src/tests/test_phase4.py` - 8 test classes, 9 xfail stubs for Phase 4 graph, correlation, attack-paths, alert-edge, and correlate route features

## Decisions Made
- `pytest.importorskip` inside test methods (not module-level) so the file imports cleanly when `backend.src.graph.builder` is absent — same pattern as Phase 3 sigma_loader tests
- `strict=False` on all xfail decorators allows xpass without breaking the suite (one test already passes because `/graph/correlate` returns 404 for an unknown route before the endpoint is implemented)
- TestCorrelateRoute contains 2 methods to cover both 200 (known event) and 404 (unknown event) paths as specified in the plan

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Red baseline established: all 9 Phase 4 stubs are xfail (or xpass where already correct)
- Plan 02 can now flip TestGraphModels, TestNodeExtraction, TestEdgeExtraction, TestAttackPaths, TestGraphAPI stubs to passing by extending GraphNode and implementing graph.builder
- Plan 03 can flip TestCorrelation, TestAlertGraph, TestCorrelateRoute stubs by adding temporal correlation and alert-trigger edge logic

---
*Phase: 04-graph-correlation*
*Completed: 2026-03-16*

## Self-Check: PASSED
- `backend/src/tests/test_phase4.py` — FOUND
- Commit `650781f` — FOUND
