---
phase: 03-detection-rag
plan: 01
subsystem: testing
tags: [pytest, sigma, opensearch, fastapi, wave0-stubs, tdd]

# Dependency graph
requires:
  - phase: 02-ingestion
    provides: NormalizedEvent model, routes.py with _store_event, opensearch_sink.try_index

provides:
  - 9 Phase 3 test stubs covering OpenSearch activation, /search endpoint, sigma loader, and sigma alert integration
  - Wave 0 TDD gate: 3 tests FAIL (search route absent), 1 PASS (try_index HTTP behavior), 5 SKIP (sigma_loader absent)

affects:
  - 03-02-PLAN.md
  - 03-03-PLAN.md

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "pytest.importorskip inside test methods (not at module level) allows partial skip without skipping entire file"
    - "patch.object(sink, '_get_client') pattern for mocking httpx client in opensearch_sink tests"

key-files:
  created:
    - backend/src/tests/test_phase3.py
  modified: []

key-decisions:
  - "pytest.importorskip called inside each test method instead of at module level so OpenSearch/search tests still collect and fail independently"
  - "TestOpenSearch P3-T8 PASSES immediately — try_index already does HTTP PUT when OPENSEARCH_URL is set; wave 0 validates this baseline"
  - "TestSearchRoute tests FAIL with 404 (correct stub behavior — /search route not yet implemented)"
  - "Sigma test classes (TestSigmaLoader, TestSigmaDetection, TestSigmaAlerts) all SKIP — sigma_loader module absent until Plan 03"

patterns-established:
  - "Wave 0 TDD stub pattern: importorskip per-method for absent modules, assert for absent routes"

requirements-completed:
  - FR-3.1
  - FR-3.2
  - FR-3.6

# Metrics
duration: 8min
completed: 2026-03-16
---

# Phase 3 Plan 01: Phase 3 Wave-0 Test Stubs Summary

**9 pytest stubs covering /search endpoint, try_index HTTP behavior, and Sigma rule integration — 3 fail (no route), 1 pass (OpenSearch baseline confirmed), 5 skip (sigma_loader absent)**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-16T05:54:11Z
- **Completed:** 2026-03-16T06:02:00Z
- **Tasks:** 1 (TDD stub task)
- **Files modified:** 1

## Accomplishments

- Created `backend/src/tests/test_phase3.py` with 9 test methods across 5 test classes
- Verified P3-T8 (try_index HTTP PUT when URL set) PASSES — establishes baseline before Plan 02 changes guard logic
- Verified P3-T1/P3-T2/P3-T2-variant (search route) correctly FAIL with 404 — clear implementation target for Plan 02
- Verified P3-T3/T4/T5/T6/T6-alias SKIP cleanly via pytest.importorskip — no errors when sigma_loader absent
- All 32 pre-existing tests (smoke_test.py + test_phase2.py) continue to pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Write test_phase3.py with 8 failing stubs** - `77843fa` (test)

**Plan metadata:** (docs commit follows)

_Note: TDD task — stub-only step (RED). GREEN will be delivered by Plans 02 and 03._

## Files Created/Modified

- `backend/src/tests/test_phase3.py` — 9 stub tests: TestOpenSearch, TestSearchRoute, TestSigmaLoader, TestSigmaDetection, TestSigmaAlerts

## Decisions Made

- `pytest.importorskip` is called inside each test method rather than at module level. This is necessary because placing it at module level (outside a class) causes the entire file to be skipped when the module is absent, defeating the purpose of having search-route tests fail independently.
- P3-T8 design: rather than a pure failing stub, the test verifies the CURRENT behavior of try_index (it already calls HTTP PUT when URL is set). The Phase 2 scaffold comment says "no-op if OPENSEARCH_URL unset" — the test confirms it IS active when URL is set. This is the correct baseline before Plan 02 removes any remaining guard logic.

## Deviations from Plan

None - plan executed exactly as written.

The only minor structural decision was using per-method `pytest.importorskip` rather than module-level, which aligns with the plan's note to "use try/except ImportError to skip tests gracefully" and produces the expected partial SKIP/FAIL outcome rather than a full file skip.

## Issues Encountered

Initial write used module-level `pytest.importorskip` outside a class, which caused the entire file to be skipped (0 collected, 1 skipped). Fixed by moving `importorskip` calls inside each test method.

## Next Phase Readiness

- Plan 02 (OpenSearch route + search endpoint): implement `GET /search?q=` → will make 3 FAIL tests pass
- Plan 03 (sigma_loader): implement `backend/src/detection/sigma_loader.py` → will make 5 SKIP tests run and eventually pass
- 32 existing tests unaffected — safe to continue

---
## Self-Check: PASSED

- `backend/src/tests/test_phase3.py` — FOUND
- commit `77843fa` — FOUND
- `.planning/phases/03-detection-rag/03-01-SUMMARY.md` — FOUND

---
*Phase: 03-detection-rag*
*Completed: 2026-03-16*
