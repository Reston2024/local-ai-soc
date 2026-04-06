---
phase: 24-recommendation-artifact-store
plan: "01"
subsystem: database
tags: [duckdb, schema-migration, recommendations, ddl]

# Dependency graph
requires:
  - phase: 23-collector-pipeline
    provides: DuckDB single-writer store pattern with execute_write and initialise_schema()
provides:
  - recommendations DuckDB table with all artifact fields, PRIMARY KEY, BOOLEAN/TEXT defaults
  - recommendation_dispatch_log DuckDB table for dispatch audit trail
  - idx_recommendations_case_id and idx_recommendations_status indexes
affects: [24-02, 24-03, 24-04, 24-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CREATE TABLE IF NOT EXISTS in initialise_schema() — additive idempotent migration pattern"
    - "FK constraints omitted (DuckDB 1.3 does not enforce them) — referential integrity at app layer"

key-files:
  created: []
  modified:
    - backend/stores/duckdb_store.py
    - tests/unit/test_duckdb_migration.py

key-decisions:
  - "FK omitted on recommendation_dispatch_log.recommendation_id — DuckDB 1.3 does not enforce FOREIGN KEY constraints; integrity enforced at application layer"
  - "Two indexes created: idx_recommendations_case_id and idx_recommendations_status — primary query patterns for the approval API"

patterns-established:
  - "Phase 24 DDL block inserted between _INSERT_SCHEMA_VERSION and _ECS_MIGRATION_COLUMNS loop — clean additive migration insertion point"

requirements-completed: [P24-T01]

# Metrics
duration: 2min
completed: 2026-04-06
---

# Phase 24 Plan 01: DuckDB Recommendation Schema Summary

**recommendations and recommendation_dispatch_log tables added to DuckDB via CREATE TABLE IF NOT EXISTS in initialise_schema(), with case_id and status indexes**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-06T13:12:36Z
- **Completed:** 2026-04-06T13:14:30Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments

- `_CREATE_RECOMMENDATIONS_TABLE` DDL constant with all 21 artifact fields, PRIMARY KEY, and defaults (analyst_approved=FALSE, status='draft')
- `_CREATE_DISPATCH_LOG_TABLE` DDL constant for dispatch audit trail (log_id, recommendation_id, dispatched_at, http_status, response_body, failure_taxonomy)
- Two indexes: idx_recommendations_case_id and idx_recommendations_status
- All 29 targeted tests pass (test_duckdb_migration.py + test_duckdb_store.py)
- 5 new TDD tests verify table presence, column defaults, PK constraint, and idempotency

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for recommendations/dispatch_log tables** - `fb8e53c` (test)
2. **Task 1 GREEN: Add DDL constants and initialise_schema() calls** - `e40dc01` (feat)

_Note: TDD task has two commits (test RED → feat GREEN)_

## Files Created/Modified

- `backend/stores/duckdb_store.py` - Added 4 DDL constants + 4 execute_write calls in initialise_schema()
- `tests/unit/test_duckdb_migration.py` - Added 5 new tests for Phase 24 tables

## Decisions Made

- FK constraint omitted on dispatch_log.recommendation_id — DuckDB 1.3 does not enforce FOREIGN KEY at runtime; referential integrity enforced at application layer per plan specification
- Two indexes created for the primary API query patterns (filter by case_id, filter by status)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing failures in `tests/unit/test_recommendation_model.py` (16 tests) are from Plan 24-02 stubs activated before their implementation. These are out of scope for Plan 24-01 and were already failing before this plan's changes. The plan-specified verification command (`test_duckdb_migration.py tests/unit/test_duckdb_store.py`) passes with 29/29 green.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- DuckDB persistence layer ready for Phase 24-02 (RecommendationArtifact Pydantic model)
- Both tables are idempotent — app startup will create them on any fresh database
- Indexes in place for the API query patterns in 24-03 and 24-04

---
*Phase: 24-recommendation-artifact-store*
*Completed: 2026-04-06*
