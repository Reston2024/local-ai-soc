---
phase: 43-sigma-v2-correlation-rules
plan: "01"
subsystem: testing
tags: [tdd, pytest, correlation-engine, wave-0, stubs]

# Dependency graph
requires:
  - phase: 42-streaming-behavioral-profiles
    provides: AnomalyScorer TDD Wave 0 stub pattern with per-test @_skip decorator

provides:
  - Wave 0 TDD stub file test_correlation_engine.py (1 RED + 8 SKIP)
  - Locked module contract: detections.correlation_engine.CorrelationEngine
  - Defined behavioral contracts for port scan, brute force, beaconing, chain, dedup, YAML loading, ingest hook

affects:
  - 43-02 (implements CorrelationEngine — turns RED GREEN)
  - 43-03 (implements chain detection and YAML loading)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-test @_skip decorator (not module-level pytestmark) lets one RED test run while all stubs skip cleanly"

key-files:
  created:
    - tests/unit/test_correlation_engine.py
  modified: []

key-decisions:
  - "Per-test @_skip decorator pattern (not pytestmark) so test_correlation_engine_module_exists runs RED while 8 behavioral stubs skip cleanly — same pattern as Phase 42 test_anomaly_scorer.py"

patterns-established:
  - "Wave 0 stub pattern: _skip = pytest.mark.skip(...) at module level, apply @_skip to all stubs, leave RED import test undecorated"

requirements-completed: [P43-T01, P43-T02, P43-T03, P43-T04, P43-T05]

# Metrics
duration: 5min
completed: 2026-04-12
---

# Phase 43 Plan 01: TDD Wave 0 Stubs — Correlation Engine Test Contracts Summary

**Wave 0 TDD stub file for correlation engine: 1 RED import failure + 8 SKIP behavioral contracts covering port scan, brute force, beaconing, chain detection, dedup, YAML loading, and ingest hook wiring**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-12T17:35:00Z
- **Completed:** 2026-04-12T17:40:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Created `tests/unit/test_correlation_engine.py` with exact Phase 42 stub pattern
- 1 RED test (`test_correlation_engine_module_exists`) fails with `ModuleNotFoundError` locking the `detections.correlation_engine.CorrelationEngine` import contract
- 8 behavioral stubs skip cleanly with `@_skip` decorator covering all P43-T01 through P43-T05 requirements
- 1058 previously passing unit tests unaffected

## Task Commits

Each task was committed atomically:

1. **Task 1: Write TDD stub file for correlation engine** - `7b70b7e` (test)

## Files Created/Modified
- `tests/unit/test_correlation_engine.py` - Wave 0 stub file: 1 RED import test + 8 skip stubs for correlation engine behavioral contracts

## Decisions Made
- Used per-test `@_skip = pytest.mark.skip(...)` decorator rather than module-level `pytestmark` — this is the established Phase 42 pattern that allows the RED import test to run while all behavioral stubs skip cleanly

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Wave 0 contracts locked — Plan 43-02 can now implement `detections/correlation_engine.py` to turn the RED import test GREEN
- Behavioral stubs (8 SKIP) define the exact method signatures and return types Plan 43-02/43-03 must satisfy
- All 1058 existing tests remain green, safe baseline for implementation

---
*Phase: 43-sigma-v2-correlation-rules*
*Completed: 2026-04-12*
