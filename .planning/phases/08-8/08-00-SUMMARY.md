---
phase: 08-8
plan: "00"
subsystem: testing
tags: [pytest, xfail, tdd, osquery, integration-tests, wave-0]

# Dependency graph
requires:
  - phase: 07-7
    provides: existing test infrastructure and pytest-asyncio auto mode
provides:
  - Fixed pagination field assertions in test_backend_health.py (page/page_size/has_next)
  - Fixed detect API URL in test_backend_health.py (/api/detect not /api/detections)
  - OsqueryCollector stub module importable without error
  - 4 xfail unit stubs for P8-T01..P8-T04 (tests/unit/test_osquery_collector.py)
  - 1 xfail integration stub for P8-T08 (tests/integration/test_osquery_pipeline.py)
  - Clean green baseline: 0 failures before any Wave 1 implementation lands
affects: [08-01, 08-02, 08-03, 08-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "xfail stubs with strict=False allow Wave 1 to drive tests to XPASS without changing test infrastructure"
    - "OsqueryCollector stub exposes _ingest_new_lines() as the primary unit-testable method"

key-files:
  created:
    - ingestion/osquery_collector.py
    - tests/unit/test_osquery_collector.py
    - tests/integration/test_osquery_pipeline.py
  modified:
    - tests/integration/test_backend_health.py

key-decisions:
  - "Expose _ingest_new_lines() as stub method on OsqueryCollector so unit tests can call it directly without needing the full run() loop"
  - "Use xfail(strict=False) so tests become XPASS (not XFAIL ERROR) when Wave 1 implements the collector"

patterns-established:
  - "Wave 0 TDD baseline: create all test stubs before any implementation, establish 0-failure green baseline"

requirements-completed:
  - P8-T01
  - P8-T02
  - P8-T03
  - P8-T08
  - P8-T06
  - P8-T07

# Metrics
duration: 2min
completed: 2026-03-17
---

# Phase 8 Plan 00: Wave 0 TDD Baseline Summary

**Fixed 4 failing integration test assertions (pagination fields + detect URL) and created OsqueryCollector stub with 5 xfail test stubs establishing clean 0-failure baseline for Phase 8**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-17T18:37:46Z
- **Completed:** 2026-03-17T18:39:56Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Fixed `test_backend_health.py`: replaced `offset`/`limit` with `page`/`page_size`/`has_next` in pagination assertions, changed `limit=5` param to `page_size=5`, fixed both `TestDetectionsAPI` tests to use `/api/detect` instead of `/api/detections`
- Created `ingestion/osquery_collector.py` stub with `OsqueryCollector` class exposing `run()`, `_ingest_new_lines()`, and `status()` — importable without error, all methods raise `NotImplementedError`
- Created `tests/unit/test_osquery_collector.py` with 4 xfail stubs covering P8-T01 (reads_lines), P8-T02 (missing_log_graceful), P8-T03 (uses_write_queue), P8-T04 (disabled_no_start)
- Created `tests/integration/test_osquery_pipeline.py` with 1 xfail stub for P8-T08 (mock NDJSON lines to DuckDB write queue)
- Full suite: 102 passed, 1 skipped, 6 xfailed — 0 failures

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix 4 failing integration tests in test_backend_health.py** - `c092200` (fix)
2. **Task 2: Create OsqueryCollector stub + 4 xfail unit stubs** - `2bf4c96` (test)
3. **Task 3: Create xfail integration stub for osquery pipeline** - `e545c55` (test)

**Plan metadata:** (docs commit — pending)

## Files Created/Modified
- `tests/integration/test_backend_health.py` - Fixed 4 assertions: pagination fields (page/page_size/has_next), limit param (page_size=5), detect URL (/api/detect); added TestTelemetryAPI xfail stub
- `ingestion/osquery_collector.py` - OsqueryCollector stub with run(), _ingest_new_lines(), status() skeleton
- `tests/unit/test_osquery_collector.py` - 4 xfail unit stubs for P8-T01..P8-T04
- `tests/integration/test_osquery_pipeline.py` - 1 xfail integration stub for P8-T08

## Decisions Made
- Expose `_ingest_new_lines()` as a stub method (raising NotImplementedError) on OsqueryCollector so tests can directly invoke it without the full polling loop — this matches the plan's test structure and allows clean unit testing in Wave 1
- Use `xfail(strict=False)` throughout: when Wave 1 implements the collector, tests will show as XPASS without requiring any changes to the test files

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — backend was running during Task 1 verification, so the integration tests ran live and confirmed 12 passed + 1 xfailed rather than being skipped.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Clean green baseline established: 102 passed, 6 xfailed, 0 failures
- `ingestion/osquery_collector.py` stub is importable — Wave 1 (08-01) can implement `_ingest_new_lines()` to drive all 5 xfail stubs to XPASS
- `Settings` class does not yet have `OSQUERY_ENABLED` field — Wave 1 must add it to drive P8-T04 to XPASS

---
*Phase: 08-8*
*Completed: 2026-03-17*

## Self-Check: PASSED

- FOUND: `ingestion/osquery_collector.py`
- FOUND: `tests/unit/test_osquery_collector.py`
- FOUND: `tests/integration/test_osquery_pipeline.py`
- FOUND: `.planning/phases/08-8/08-00-SUMMARY.md`
- Commits verified: `c092200`, `2bf4c96`, `e545c55`
- Full suite: 102 passed, 1 skipped, 6 xfailed — 0 failures
