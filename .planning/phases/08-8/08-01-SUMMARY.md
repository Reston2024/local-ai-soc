---
phase: 08-8
plan: "01"
subsystem: ingestion
tags: [osquery, live-telemetry, asyncio, duckdb, config]

# Dependency graph
requires:
  - phase: 03-detection-rag
    provides: DuckDB write queue pattern (execute_write)
  - phase: 08-8
    provides: OsqueryCollector stub and xfail test scaffolding
provides:
  - Full OsqueryCollector implementation with asyncio log-tailing loop
  - OSQUERY_ENABLED/OSQUERY_LOG_PATH/OSQUERY_POLL_INTERVAL config fields
  - Conditional collector startup/shutdown wired into main.py lifespan
affects: [08-8, backend-lifespan, live-telemetry]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "asyncio.to_thread() for all blocking file I/O in async context"
    - "Collector writes exclusively via store.execute_write() (DuckDB write queue)"
    - "OSQUERY_ENABLED defaults False so backend starts without osquery installed"
    - "Lifespan conditional startup pattern for optional background collectors"

key-files:
  created: []
  modified:
    - ingestion/osquery_collector.py
    - backend/core/config.py
    - backend/main.py

key-decisions:
  - "OSQUERY_ENABLED defaults to False — backend starts cleanly without osquery installed"
  - "to_duckdb_row() returns tuple; _build_row() wraps with list() for execute_write compatibility"
  - "PermissionError in _read_new_lines() caught and stored in _error with icacls fix hint"
  - "OsqueryCollector imported inside lifespan if-block to allow graceful ImportError fallback"

patterns-established:
  - "Optional background collector pattern: conditional start in lifespan, cancel on shutdown"
  - "Blocking file I/O in async context always wrapped in asyncio.to_thread()"

requirements-completed: []

# Metrics
duration: 1min
completed: 2026-03-17
---

# Phase 8 Plan 01: OsqueryCollector Live Telemetry Summary

**Asyncio log-tailing OsqueryCollector with DuckDB write-queue ingestion, gated by OSQUERY_ENABLED=False default in Settings**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-17T13:02:57Z
- **Completed:** 2026-03-17T13:04:03Z
- **Tasks:** 3 (Task 1, Task 2, Task 2b)
- **Files modified:** 3

## Accomplishments
- Replaced OsqueryCollector stub with full asyncio tail-and-ingest polling loop
- Added 3 osquery config fields to Settings (OSQUERY_ENABLED, OSQUERY_LOG_PATH, OSQUERY_POLL_INTERVAL)
- Wired conditional collector startup and clean cancellation into main.py lifespan
- Drove P8-T01, T02, T03, T04, T08 from xfail to XPASS; full suite 102 passed 0 failures

## Task Commits

Each task was committed atomically:

1. **Tasks 1+2+2b: OsqueryCollector implementation + config + lifespan wiring** - `d623cb0` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `ingestion/osquery_collector.py` - Full OsqueryCollector replacing stub: run(), _ingest_new_lines(), _read_new_lines(), _build_row(), status()
- `backend/core/config.py` - Added OSQUERY_ENABLED, OSQUERY_LOG_PATH, OSQUERY_POLL_INTERVAL fields
- `backend/main.py` - Conditional collector startup in lifespan step 8, osquery_task cancellation in shutdown

## Decisions Made
- OSQUERY_ENABLED defaults to False so the backend starts without osquery installed on the host
- `_build_row()` calls `list(evt.to_duckdb_row())` since `to_duckdb_row()` returns a tuple but `execute_write` expects `list[Any]`
- PermissionError in `_read_new_lines()` is caught gracefully and stored in `_error` (not re-raised) with an actionable `icacls` fix hint in the message
- Collector imported inside the lifespan `if` block with an `ImportError` try/except for graceful degradation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected _build_row() return type from list to list(tuple)**
- **Found during:** Task 1 (implementing _build_row)
- **Issue:** Plan showed `_build_row` returning a list but noted `to_duckdb_row()` — inspection of event.py showed `to_duckdb_row()` returns a `tuple`, while `execute_write` expects `Optional[list[Any]]`
- **Fix:** Added `list(evt.to_duckdb_row())` conversion in the happy path, and the fallback also returns a list literal
- **Files modified:** ingestion/osquery_collector.py
- **Verification:** All 5 xfail tests become XPASS
- **Committed in:** d623cb0

---

**Total deviations:** 1 auto-fixed (1 type correction bug)
**Impact on plan:** Necessary for DuckDB write queue compatibility. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. OSQUERY_ENABLED defaults to False; to enable, set `OSQUERY_ENABLED=True` in `.env` and ensure osquery is installed with log file accessible.

## Next Phase Readiness
- OsqueryCollector live telemetry foundation complete
- Ready for remaining Phase 8 plans (wave 2+)
- To use: set `OSQUERY_ENABLED=True` and `OSQUERY_LOG_PATH` in `.env`, grant `Users:R` on osquery log directory

---
*Phase: 08-8*
*Completed: 2026-03-17*

## Self-Check: PASSED
