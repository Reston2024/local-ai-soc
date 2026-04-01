---
phase: 20-schema-standardisation-ecs-ocsf
plan: "00"
subsystem: testing
tags: [pytest, tdd, ecs, ocsf, duckdb, pydantic, schema-migration]

# Dependency graph
requires:
  - phase: 19-identity-rbac
    provides: "Stable backend foundation — operators API, auth, RBAC all tested and passing"
provides:
  - "RED phase stubs: 19 failing tests across 3 files defining TDD contracts for Phase 20"
  - "test_normalized_event_ecs.py: 8 stubs for ECS fields, OCSF class_uid, backward compat"
  - "test_field_mapper.py: 6 stubs for FieldMapper pure function and source type mappings"
  - "test_duckdb_migration.py: 5 stubs for additive schema migration and db_meta table"
affects: [20-01, 20-02, 20-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "pytest.fail('NOT IMPLEMENTED') for RED stubs — ensures FAILED not ERROR at collection"
    - "Import guards: NormalizedEvent and DuckDBStore imported at module level (exist); FieldMapper imported inside test body (does not exist yet)"

key-files:
  created:
    - tests/unit/test_normalized_event_ecs.py
    - tests/unit/test_field_mapper.py
    - tests/unit/test_duckdb_migration.py
  modified: []

key-decisions:
  - "20-00: test_field_mapper.py has no module-level import of ingestion.field_mapper (does not exist); stubs call pytest.fail directly, deferring import to implementation phase"
  - "20-00: test_normalized_event_ecs.py and test_duckdb_migration.py import real modules at module level since NormalizedEvent and DuckDBStore already exist"

patterns-established:
  - "RED stub pattern: pytest.fail('NOT IMPLEMENTED') body, real imports where module exists, no @pytest.mark.skip"

requirements-completed: [P20-T01, P20-T02, P20-T03]

# Metrics
duration: 5min
completed: 2026-04-01
---

# Phase 20 Plan 00: Schema Standardisation ECS/OCSF — RED Phase Stubs Summary

**19 failing pytest stubs across three files establishing TDD contracts for ECS field additions, FieldMapper, and DuckDB additive schema migration**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-01T13:54:43Z
- **Completed:** 2026-04-01T13:59:00Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments

- Created 3 test stub files covering all Phase 20 production work contracts
- All 19 stubs produce FAILED (not ERROR) — pytest collection is clean with 0 errors
- NormalizedEvent and DuckDBStore imported at module level (both exist); FieldMapper deferred to test body level (module does not yet exist)
- Existing test suite unaffected

## Task Commits

Each task was committed atomically:

1. **Task 1: Write stub test files (RED phase)** - `8f10f02` (test)

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified

- `tests/unit/test_normalized_event_ecs.py` - 8 RED stubs for P20-T01 (ECS fields on NormalizedEvent, OCSF class_uid mapping, backward compat, to_duckdb_row extension)
- `tests/unit/test_field_mapper.py` - 6 RED stubs for P20-T02 (FieldMapper EVTX/ECS/network field mapping, passthrough for unknowns)
- `tests/unit/test_duckdb_migration.py` - 5 RED stubs for P20-T03 (db_meta table, 6 new ECS columns, idempotent migration, existing row safety, schema_version=20)

## Decisions Made

- test_field_mapper.py has no module-level import of `ingestion.field_mapper` since the module does not yet exist; all stubs call `pytest.fail("NOT IMPLEMENTED")` directly so there is no ImportError at collection time
- test_normalized_event_ecs.py imports `NormalizedEvent` at module level (module exists); this confirms the import contract is valid before production code is written

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- RED phase complete; 19 stubs ready to drive implementation in plans 20-01 through 20-03
- 20-01: Add 6 ECS fields + OCSF_CLASS_UID_MAP to NormalizedEvent (will turn test_normalized_event_ecs.py GREEN)
- 20-02: Create ingestion/field_mapper.py FieldMapper class (will turn test_field_mapper.py GREEN)
- 20-03: Add additive DuckDB migration + db_meta table (will turn test_duckdb_migration.py GREEN)

---
*Phase: 20-schema-standardisation-ecs-ocsf*
*Completed: 2026-04-01*

## Self-Check: PASSED

- FOUND: tests/unit/test_normalized_event_ecs.py
- FOUND: tests/unit/test_field_mapper.py
- FOUND: tests/unit/test_duckdb_migration.py
- FOUND: .planning/phases/20-schema-standardisation-ecs-ocsf/20-00-SUMMARY.md
- FOUND: commit 8f10f02
