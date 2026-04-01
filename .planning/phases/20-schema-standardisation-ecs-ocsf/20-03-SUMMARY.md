---
phase: 20-schema-standardisation-ecs-ocsf
plan: "03"
subsystem: database
tags: [duckdb, schema-migration, ecs, ocsf, tdd]

# Dependency graph
requires:
  - phase: 20-02
    provides: "loader.py _INSERT_SQL extended to 35 columns; _CREATE_EVENTS_TABLE already includes the 6 ECS columns for fresh DBs"
provides:
  - "db_meta table with schema_version='20' key in DuckDB"
  - "6 new ECS columns added via idempotent ALTER TABLE migration for existing databases"
  - "initialise_schema() is safe to re-run (try/except per column, ON CONFLICT for version upsert)"
affects: [ingestion/loader.py, backend/main.py, any code relying on normalized_events column set]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "DuckDB additive migration via try/except (no IF NOT EXISTS support)"
    - "db_meta key-value table for tracking schema version"
    - "ON CONFLICT DO UPDATE for idempotent version upserts"

key-files:
  created:
    - tests/unit/test_duckdb_migration.py
  modified:
    - backend/stores/duckdb_store.py

key-decisions:
  - "20-03: try/except per ALTER TABLE column is the correct DuckDB idempotency pattern — DuckDB does not support ADD COLUMN IF NOT EXISTS syntax"
  - "20-03: db_meta table uses TEXT PRIMARY KEY key + TEXT NOT NULL value — simple key-value store for schema metadata"
  - "20-03: schema_version stored as string '20' (not integer) for forward-compatibility with multi-part version strings"

patterns-established:
  - "DuckDB migration pattern: wrap each ALTER TABLE in try/except; log skipped columns at DEBUG level"
  - "Schema version tracking: db_meta table with ON CONFLICT DO UPDATE for idempotent upsert"

requirements-completed: [P20-T03]

# Metrics
duration: 8min
completed: 2026-04-01
---

# Phase 20 Plan 03: DuckDB ECS Schema Migration Summary

**db_meta version tracking table + 6 idempotent ALTER TABLE statements wired into initialise_schema() via try/except pattern**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-01T14:14:22Z
- **Completed:** 2026-04-01T14:17:08Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Added `db_meta` table (CREATE TABLE IF NOT EXISTS) with key/value schema for version tracking
- Upserted schema_version='20' using ON CONFLICT DO UPDATE so re-runs are idempotent
- Added 6 ECS ALTER TABLE statements for existing databases: `ocsf_class_uid`, `event_outcome`, `user_domain`, `process_executable`, `network_protocol`, `network_direction`
- Each ALTER TABLE wrapped in try/except (DuckDB has no ADD COLUMN IF NOT EXISTS)
- Implemented 5 TDD tests covering all migration guarantees: db_meta creation, column presence, idempotency, row preservation, and schema_version string type
- 5/5 tests GREEN, 0 regressions (pre-existing 81 unit failures unchanged from baseline of 86 before plan)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add db_meta table and ECS migration to initialise_schema()** - `5765e31` (feat)

Note: RED phase test stubs were committed in plan 20-00 (`8f10f02`).

## Files Created/Modified
- `backend/stores/duckdb_store.py` - Added `_CREATE_DB_META_TABLE`, `_INSERT_SCHEMA_VERSION`, `_ECS_MIGRATION_COLUMNS` constants; updated `initialise_schema()` with migration block
- `tests/unit/test_duckdb_migration.py` - Implemented all 5 async TDD tests (replaced stubs from 20-00)

## Decisions Made
- Used try/except (not IF NOT EXISTS) for ALTER TABLE idempotency — DuckDB does not support the IF NOT EXISTS column syntax
- Stored schema_version as string '20' not integer — TEXT type is more flexible for future multi-part versions
- db_meta uses a simple key TEXT PRIMARY KEY / value TEXT NOT NULL structure for broad reuse

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. The existing `_CREATE_EVENTS_TABLE` already includes the 6 ECS columns (added in plan 20-02), so `test_new_ecs_columns_added` passes both via CREATE TABLE (fresh DBs) and via ALTER TABLE (existing DBs that go through the migration path). The test verified column presence regardless of how they arrived.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- DuckDB schema migration is complete and idempotent
- Existing production databases will receive the 6 new ECS columns on next startup
- loader.py's extended _INSERT_SQL (plan 20-02) will no longer fail on existing databases
- Phase 20 remaining plans can proceed with confidence that all three layers (model, loader, DB) are aligned

---
*Phase: 20-schema-standardisation-ecs-ocsf*
*Completed: 2026-04-01*
