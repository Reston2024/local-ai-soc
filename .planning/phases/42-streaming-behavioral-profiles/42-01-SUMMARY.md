---
phase: 42-streaming-behavioral-profiles
plan: "01"
subsystem: testing
tags: [anomaly-detection, river-ml, halfspacetrees, tdd, wave0-stubs, duckdb, fastapi]

requires:
  - phase: 41-threat-map-overhaul
    provides: 1044 passing unit tests as baseline — stubs must not break them

provides:
  - Wave 0 RED stubs for AnomalyScorer (8 stubs, all SKIP until Plan 42-02)
  - Wave 0 RED stubs for anomaly API (6 stubs: 5 SKIP + 1 RED FAIL)
  - test_anomaly_score_in_duckdb immediately fails RED (correct — anomaly_score not yet in _ECS_MIGRATION_COLUMNS)

affects:
  - 42-02-PLAN (AnomalyScorer implementation must satisfy all 8 scorer stubs)
  - 42-03-PLAN (anomaly API must satisfy 5 API stubs + synthetic detection stub)
  - backend/stores/duckdb_store.py (must add anomaly_score to _ECS_MIGRATION_COLUMNS)

tech-stack:
  added: []
  patterns:
    - "skipif-importerror guard at module level (pytestmark) — stubs SKIP not ERROR when source absent"
    - "Per-decorator @_skip_api on individual tests alongside module pytestmark — allows mixing SKIP and RED FAIL in same file"
    - "Async test for DuckDB schema check uses store.start_write_worker() + await store.initialise_schema() pattern (consistent with test_duckdb_store.py)"

key-files:
  created:
    - tests/unit/test_anomaly_scorer.py
    - tests/unit/test_anomaly_api.py
  modified: []

key-decisions:
  - "test_anomaly_score_in_duckdb uses async def (not asyncio.get_event_loop().run_until_complete) — consistent with pytest-asyncio auto mode used throughout codebase"
  - "Per-test @_skip_api decorator (not module pytestmark) for API stubs — allows test_anomaly_score_in_duckdb to run RED without being blocked by router import guard"
  - "entity_key returns (subnet_str, process_str) 2-tuple — plan stub asserts tuple length=2 and both string components"
  - "test_learn_updates_model uses 2 independent AnomalyScorer instances — avoids state pollution between before/after score measurement"

requirements-completed:
  - P42-T01
  - P42-T02
  - P42-T03
  - P42-T04
  - P42-T05
  - P42-T06

duration: 8min
completed: "2026-04-12"
---

# Phase 42 Plan 01: Streaming Behavioral Profiles — Wave 0 TDD Stubs Summary

**8 AnomalyScorer stubs (all SKIP) + 6 anomaly API stubs (5 SKIP, 1 RED FAIL on missing anomaly_score column), establishing contracts for Plans 42-02 and 42-03**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-12T13:30:00Z
- **Completed:** 2026-04-12T13:38:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `tests/unit/test_anomaly_scorer.py` with 8 Wave 0 stubs covering score_one, learn_one, entity_key (with /24 subnet extraction and None-IP fallback), model persistence (save/load roundtrip), model directory creation, high-anomaly threshold validation, and fresh model default score
- Created `tests/unit/test_anomaly_api.py` with 6 Wave 0 stubs: list anomalies, threshold filter, entity profile, score trend, DuckDB schema check (RED FAIL), and synthetic detection creation
- 1044 existing unit tests unaffected; test_anomaly_score_in_duckdb fails RED as intended (anomaly_score column not yet in schema)

## Task Commits

Each task was committed atomically:

1. **Task 1: AnomalyScorer unit test stubs** - `0821795` (test)
2. **Task 2: Anomaly API test stubs** - `c900d0e` (test)

**Plan metadata:** see final docs commit

## Files Created/Modified

- `tests/unit/test_anomaly_scorer.py` — 8 stubs with real assertion bodies for AnomalyScorer, all SKIP via module-level pytestmark skipif guard
- `tests/unit/test_anomaly_api.py` — 6 stubs: 5 API stubs skip via per-test @_skip_api decorator; test_anomaly_score_in_duckdb runs immediately and FAILS RED

## Decisions Made

- Used per-test `@_skip_api` decorator rather than module-level `pytestmark` for `test_anomaly_api.py` — allows `test_anomaly_score_in_duckdb` to execute immediately (DuckDB IS available) and fail RED while the 5 API stubs skip cleanly
- Used `async def` for `test_anomaly_score_in_duckdb` with `store.start_write_worker()` + `await store.initialise_schema()` — consistent with pytest-asyncio auto mode and existing `test_duckdb_store.py` fixture pattern
- Stub bodies contain real assertions (not `pytest.skip()`) — stubs go RED when module exists but behavior is wrong, consistent with Nyquist compliance requirement

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 42-02 (AnomalyScorer implementation): 8 scorer stubs define the complete contract — implement `backend/services/anomaly/scorer.py` with `AnomalyScorer` class and `entity_key()` function; all 8 tests must transition from SKIP to PASS
- Plan 42-03 (anomaly API): 5 API stubs + 1 synthetic detection stub define endpoints — implement `backend/api/anomaly.py` router; also add `anomaly_score FLOAT` to `_ECS_MIGRATION_COLUMNS` in `duckdb_store.py` to fix the RED FAIL

---
*Phase: 42-streaming-behavioral-profiles*
*Completed: 2026-04-12*

## Self-Check: PASSED

- `tests/unit/test_anomaly_scorer.py` — FOUND
- `tests/unit/test_anomaly_api.py` — FOUND
- Task 1 commit `0821795` — verified in git log
- Task 2 commit `c900d0e` — verified in git log
- 1044 existing tests pass, 1 RED FAIL (test_anomaly_score_in_duckdb), 16 skipped (8+5+3 pre-existing)
