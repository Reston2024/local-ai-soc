---
phase: 18-reporting-compliance
plan: "03"
subsystem: database
tags: [duckdb, apscheduler, kpi, trends, analytics, time-series]

# Dependency graph
requires:
  - phase: 18-reporting-compliance
    provides: "MetricsService.compute_all_kpis(), SQLiteStore, DuckDBStore patterns"

provides:
  - "daily_kpi_snapshots DuckDB table with DATE PRIMARY KEY and upsert method"
  - "GET /api/analytics/trends endpoint for time-series KPI retrieval"
  - "APScheduler midnight cron job writing daily KPI snapshots"
  - "SQLiteStore.list_investigations() and list_detections() helpers"

affects: [ReportingView trend charts, compliance evidence, any consumer of /api/analytics/trends]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "DuckDB ON CONFLICT (col) DO UPDATE SET EXCLUDED.col upsert pattern"
    - "APScheduler AsyncIOScheduler cron job wired in FastAPI lifespan"
    - "Graceful table-not-exist fallback on analytics endpoints"

key-files:
  created:
    - tests/unit/test_kpi_snapshots.py
  modified:
    - backend/stores/duckdb_store.py
    - backend/api/analytics.py
    - backend/main.py
    - backend/stores/sqlite_store.py

key-decisions:
  - "Used DuckDB ON CONFLICT DO UPDATE (not INSERT OR REPLACE which DuckDB does not support)"
  - "APScheduler midnight job placed in main.py lifespan (not lazy-started in endpoint handler) for reliable cron scheduling"
  - "Trends endpoint caps days at 365 to prevent unbounded queries"
  - "Single-metric response returns {metric, data:[]} shape; multi-metric returns keyed dict for consistent dashboard consumption"

patterns-established:
  - "KPI snapshot upsert: upsert_daily_kpi_snapshot() via execute_write() with ON CONFLICT DO UPDATE"
  - "Trends query: fetch_all() with formatted (validated int) days — safe since days is never user-controlled string"

requirements-completed: [P18-T03]

# Metrics
duration: 4min
completed: 2026-03-31
---

# Phase 18 Plan 03: KPI Trend History Summary

**DuckDB daily_kpi_snapshots table with ON CONFLICT upsert, APScheduler midnight snapshot job, and GET /api/analytics/trends endpoint for single and multi-metric time-series retrieval**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-31T18:55:39Z
- **Completed:** 2026-03-31T18:59:34Z
- **Tasks:** 2
- **Files modified:** 4 (+ 1 created)

## Accomplishments
- Added `daily_kpi_snapshots` DuckDB table with DDL in `duckdb_store.py`, created during `initialise_schema()`
- Added `upsert_daily_kpi_snapshot()` using DuckDB-correct `ON CONFLICT (snapshot_date) DO UPDATE SET` syntax
- Added `GET /api/analytics/trends` endpoint supporting single and comma-separated multi-metric requests with 400 validation on unknown metrics
- Wired `AsyncIOScheduler` midnight cron job in FastAPI lifespan startup/shutdown
- Added `list_investigations()` and `list_detections()` count helpers to `SQLiteStore`

## Task Commits

Each task was committed atomically:

1. **Task 1: RED tests** - `7817564` (test)
2. **Task 1: DDL and upsert method** - `c964280` (feat)
3. **Task 2: Trends endpoint and APScheduler** - `9352dcd` (feat)

**Plan metadata:** TBD (docs: complete plan)

## Files Created/Modified
- `tests/unit/test_kpi_snapshots.py` - 3 unit tests: schema_created, upsert_insert, upsert_replace
- `backend/stores/duckdb_store.py` - Added `_CREATE_KPI_SNAPSHOTS_TABLE` DDL, schema init call, and `upsert_daily_kpi_snapshot()` method
- `backend/api/analytics.py` - Added `METRIC_COLUMNS` mapping and `GET /api/analytics/trends` endpoint
- `backend/main.py` - Added APScheduler midnight cron job, `_take_daily_kpi_snapshot()` function, lifespan start/stop
- `backend/stores/sqlite_store.py` - Added `list_investigations()` and `list_detections()` helpers

## Decisions Made
- Used DuckDB's `ON CONFLICT (snapshot_date) DO UPDATE SET EXCLUDED.*` syntax — `INSERT OR REPLACE` is not valid DuckDB SQL
- Midnight cron job lives in `main.py` lifespan (not lazy-started in endpoint handler) so it runs even if the trends endpoint is never called
- Days parameter capped at 365 at the FastAPI query layer to prevent excessive queries
- Single-metric returns `{"metric": "mttd", "data": [...]}` while multi-metric returns `{"mttd": [...], "mttr": [...]}` to match dashboard expectations

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added list_investigations() and list_detections() to SQLiteStore**
- **Found during:** Task 2 (APScheduler midnight job)
- **Issue:** `stores.sqlite.list_investigations` and `stores.sqlite.list_detections` were referenced in the snapshot job but did not exist on `SQLiteStore`
- **Fix:** Added both as minimal count-query methods in `backend/stores/sqlite_store.py`
- **Files modified:** backend/stores/sqlite_store.py
- **Verification:** Import and main.py startup succeed without errors
- **Committed in:** 9352dcd (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Required for snapshot job correctness. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `daily_kpi_snapshots` table will be populated at midnight by the running server
- `GET /api/analytics/trends?metric=mttd,mttr,mttc&days=30` ready for ReportingView trend charts
- Compliance evidence pipeline has historical KPI storage foundation

---
*Phase: 18-reporting-compliance*
*Completed: 2026-03-31*

## Self-Check: PASSED

- FOUND: tests/unit/test_kpi_snapshots.py
- FOUND: backend/stores/duckdb_store.py
- FOUND: backend/api/analytics.py
- FOUND: backend/main.py
- FOUND: .planning/phases/18-reporting-compliance/18-03-SUMMARY.md
- Commits 7817564, c964280, 9352dcd, 24cbeb8 verified in git log
