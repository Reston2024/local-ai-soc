---
phase: 25-receipt-ingestion-and-case-state-propagation
plan: "01"
subsystem: database
tags: [duckdb, ddl, json-schema, receipts, notifications, failure-taxonomy]

# Dependency graph
requires:
  - phase: 24-recommendation-artifact-store
    provides: recommendations and dispatch_log DDL patterns to mirror
  - phase: 25-00
    provides: stub test files (test_receipt_transitions.py, test_receipt_api.py, test_notifications_api.py)
provides:
  - execution_receipts table DDL + 3 indexes in duckdb_store.py
  - notifications table DDL + 1 index in duckdb_store.py
  - contracts/execution-receipt.schema.json Draft 2020-12 stub (version 1.0.0-stub)
affects: [25-02, 25-03, 25-04, receipt-ingestion-api, case-state-propagation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "DDL constants defined as module-level strings before DuckDBStore class, then called in initialise_schema() at end of method"
    - "Indexes grouped in list (_CREATE_EXECUTION_RECEIPTS_INDEXES) for iteration in initialise_schema()"
    - "JSON Schema contracts in contracts/ directory mirroring recommendation.schema.json structure"

key-files:
  created:
    - contracts/execution-receipt.schema.json
  modified:
    - backend/stores/duckdb_store.py

key-decisions:
  - "25-01: failure_taxonomy enum has exactly 5 values per ADR-032: applied, noop_already_present, validation_failed, expired_rejected, rolled_back"
  - "25-01: execution_receipts indexes on recommendation_id, case_id, and failure_taxonomy — primary query patterns for Wave 2 API"
  - "25-01: notifications index on status only — primary query is pending notifications poll"

patterns-established:
  - "Phase 25 DDL block: separate section in duckdb_store.py mirroring Phase 24 structure"
  - "receipt schema version pinned to 1.0.0-stub — frozen until canonical firewall repo ships"

requirements-completed: [P25-T01, P25-T03, P25-T04]

# Metrics
duration: 7min
completed: 2026-04-06
---

# Phase 25 Plan 01: Receipt Ingestion DDL and Schema Stub Summary

**DuckDB execution_receipts and notifications tables with 4 indexes, plus JSON Schema Draft 2020-12 stub for firewall receipt validation**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-04-06T16:28:00Z
- **Completed:** 2026-04-06T16:35:10Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `execution_receipts` table (9 columns, 3 indexes) and `notifications` table (6 columns, 1 index) to duckdb_store.py
- All new DDL called at end of `initialise_schema()` — tables created at app startup, idempotent via IF NOT EXISTS
- Created `contracts/execution-receipt.schema.json` — valid Draft 2020-12 with pinned version 1.0.0-stub and 5-value failure_taxonomy enum
- Full pytest suite: 885 passed, 19 skipped (17 are Phase 25 stubs), 0 errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Add execution_receipts and notifications DDL to duckdb_store.py** - `f1f7a04` (feat)
2. **Task 2: Create contracts/execution-receipt.schema.json stub** - `76e39e7` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `backend/stores/duckdb_store.py` - Added Phase 25 DDL constants block (_CREATE_EXECUTION_RECEIPTS_TABLE, _CREATE_EXECUTION_RECEIPTS_INDEXES, _CREATE_NOTIFICATIONS_TABLE, _CREATE_NOTIFICATIONS_INDEX) and initialise_schema() calls
- `contracts/execution-receipt.schema.json` - JSON Schema Draft 2020-12 stub: version 1.0.0-stub, failure_taxonomy enum (5 values), 6 required fields, additionalProperties: false

## Decisions Made
- failure_taxonomy enum exactly matches ADR-032: `applied`, `noop_already_present`, `validation_failed`, `expired_rejected`, `rolled_back`
- Three execution_receipts indexes (recommendation_id, case_id, failure_taxonomy) cover all anticipated Wave 2 query patterns
- Single notifications index on status — the only column queried in polling patterns
- Schema version pinned to `1.0.0-stub` to signal that canonical ownership belongs to the firewall repo

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Wave 2 plans (25-02, 25-03, 25-04) now have their DuckDB persistence layer and JSON Schema validation contract
- `initialise_schema()` will create both tables on next app startup
- contracts/execution-receipt.schema.json available for `_SCHEMA_PATH.read_text()` at module import time in backend/models/receipt.py (to be created in 25-02)

---
*Phase: 25-receipt-ingestion-and-case-state-propagation*
*Completed: 2026-04-06*
