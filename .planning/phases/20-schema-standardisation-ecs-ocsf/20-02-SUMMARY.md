---
phase: 20-schema-standardisation-ecs-ocsf
plan: "02"
subsystem: ingestion
tags: [ecs, ocsf, field-mapper, duckdb, parsers, normalization]

# Dependency graph
requires:
  - phase: 20-01
    provides: NormalizedEvent with 6 new ECS fields, to_duckdb_row() returning 35-element tuple

provides:
  - ingestion/field_mapper.py with FieldMapper class and 26-entry _FIELD_VARIANTS mapping
  - loader.py _INSERT_SQL with 35 columns/placeholders (6 new ECS columns added)
  - All four parsers (EVTX, JSON, CSV, osquery) call FieldMapper.map() before NormalizedEvent construction
  - duckdb_store.py _CREATE_EVENTS_TABLE updated to include 6 new ECS/OCSF columns

affects:
  - 20-03-schema-migration (ALTER TABLE migration for existing databases)
  - Any future parser additions must call FieldMapper.map() per established pattern

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FieldMapper singleton pattern: module-level _field_mapper = FieldMapper() in each parser (no per-call allocation)"
    - "ECS dotted-path translation: process.name -> process_name via _FIELD_VARIANTS dict before NormalizedEvent construction"
    - "Pure mapper module: field_mapper.py has no I/O, no logging, no backend imports"

key-files:
  created:
    - ingestion/field_mapper.py
    - tests/unit/test_field_mapper.py
  modified:
    - ingestion/loader.py
    - backend/stores/duckdb_store.py
    - ingestion/parsers/evtx_parser.py
    - ingestion/parsers/json_parser.py
    - ingestion/parsers/csv_parser.py
    - ingestion/parsers/osquery_parser.py

key-decisions:
  - "Added 6 new ECS columns to _CREATE_EVENTS_TABLE in duckdb_store.py alongside _INSERT_SQL update — fresh schema creation now matches INSERT; ALTER TABLE for existing databases deferred to plan 20-03"
  - "FieldMapper runs BEFORE existing parser field-extraction frozensets — augments rather than replaces the existing key-variant logic; EVTX PascalCase keys not in _FIELD_VARIANTS (handled by parser-level extraction)"
  - "raw_str captured BEFORE _field_mapper.map() call in json_parser and csv_parser — raw_event preserves original source format with dotted-path keys intact"

patterns-established:
  - "Parser FieldMapper wiring pattern: import + module-level singleton + single .map() call on raw dict before NormalizedEvent construction"

requirements-completed: [P20-T02]

# Metrics
duration: 25min
completed: 2026-04-01
---

# Phase 20 Plan 02: FieldMapper Utility + Loader and Parser ECS Wiring Summary

**FieldMapper pure utility with 26 ECS dotted-path mappings wired into all four ingestion parsers; loader.py _INSERT_SQL extended to 35 columns matching NormalizedEvent.to_duckdb_row()**

## Performance

- **Duration:** 25 min
- **Started:** 2026-04-01T14:05:00Z
- **Completed:** 2026-04-01T14:30:00Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Created `ingestion/field_mapper.py` with `FieldMapper` class mapping 26 ECS dotted-path keys (e.g., `process.name` -> `process_name`, `user.domain` -> `user_domain`) to NormalizedEvent snake_case field names
- Extended loader.py `_INSERT_SQL` from 29 to 35 columns/placeholders to include `ocsf_class_uid`, `event_outcome`, `user_domain`, `process_executable`, `network_protocol`, `network_direction`
- Wired `_field_mapper.map()` into all four parsers (EVTX, JSON, CSV, osquery) as a module-level singleton — ECS dotted-path keys in raw events now translate automatically before NormalizedEvent construction
- 6/6 test_field_mapper.py tests GREEN; 11/11 loader tests GREEN; no new test failures

## Task Commits

Each task was committed atomically:

1. **Task 1: Create ingestion/field_mapper.py** - `14aacc9` (feat)
2. **Task 2: Update loader.py _INSERT_SQL for 6 new ECS columns** - `ac83fe1` (feat)
3. **Task 3: Wire FieldMapper into all four parsers** - `3bade5e` (feat)

## Files Created/Modified

- `ingestion/field_mapper.py` — FieldMapper class with `_FIELD_VARIANTS` dict (26 ECS entries) and `.map()` pure function
- `tests/unit/test_field_mapper.py` — 6 unit tests (importability, EVTX passthrough, ECS dotted, network fields, unknown passthrough, new ECS fields)
- `ingestion/loader.py` — `_INSERT_SQL` extended to 35 columns; `[:29]` backward-compat slice removed
- `backend/stores/duckdb_store.py` — `_CREATE_EVENTS_TABLE` updated to include 6 new ECS/OCSF columns
- `ingestion/parsers/evtx_parser.py` — FieldMapper import + singleton; `.map()` applied to `flat_data` after EventData flatten
- `ingestion/parsers/json_parser.py` — FieldMapper import + singleton; `.map()` applied to `record` in `_record_to_event()`
- `ingestion/parsers/csv_parser.py` — FieldMapper import + singleton; `.map()` applied to `row` in `_row_to_event()`
- `ingestion/parsers/osquery_parser.py` — FieldMapper import + singleton; `.map()` applied to `columns` in `_columns_to_event()`

## Decisions Made

- **duckdb_store.py schema update**: Adding the 6 new columns to `_CREATE_EVENTS_TABLE` alongside the `_INSERT_SQL` change ensures consistency — fresh schema creation (used in unit tests) matches the INSERT. The ALTER TABLE for existing production databases is deferred to plan 20-03 as originally designed.
- **raw_str captured before .map()**: In JSON and CSV parsers, `raw_str = json.dumps(record, ...)` is captured before `_field_mapper.map()` is applied — this preserves the original source representation in `raw_event` (dotted-path keys remain in the raw JSON).
- **FieldMapper augments, not replaces**: Existing frozenset-based key-variant logic in parsers is kept intact. FieldMapper runs first to catch ECS dotted-path keys; existing logic remains as a safety net for vendor-specific aliases.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added 6 new ECS columns to _CREATE_EVENTS_TABLE in duckdb_store.py**
- **Found during:** Task 2 (Update loader.py _INSERT_SQL for 6 new ECS columns)
- **Issue:** Updating `_INSERT_SQL` to 35 columns while leaving `_CREATE_EVENTS_TABLE` at 29 columns caused 4 unit test failures in `test_loader.py` ("Table does not have a column with name ocsf_class_uid"). Tests create fresh DuckDB schemas using `initialise_schema()`.
- **Fix:** Added 6 new columns to `_CREATE_EVENTS_TABLE` DDL in `backend/stores/duckdb_store.py`; ALTER TABLE for existing databases remains in plan 20-03.
- **Files modified:** `backend/stores/duckdb_store.py`
- **Verification:** 11/11 loader tests passed after fix; `_INSERT_SQL.count('?') == 35` confirmed
- **Committed in:** `ac83fe1` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Essential correctness fix — plan stated both schema update AND INSERT change are plan 20-02 scope; the DDL change was the missing half. No scope creep.

## Issues Encountered

The plan's original `loader.py` had a comment saying "they will be added in plan 20-02 together with an ALTER TABLE" — confirming the schema DDL change was always intended for this plan. The deviation was simply that `duckdb_store.py` was not listed in the plan's `files_modified` front-matter.

## Next Phase Readiness

- Plan 20-03 (ALTER TABLE migration) can proceed: `_CREATE_EVENTS_TABLE` in duckdb_store.py already has the 6 new columns, and the production migration script only needs to handle existing databases via ALTER TABLE ADD COLUMN IF NOT EXISTS
- FieldMapper is importable and functional; any future parsers should follow the established pattern (import + module-level singleton + `.map()` before NormalizedEvent construction)

## Self-Check: PASSED

- ingestion/field_mapper.py: FOUND
- tests/unit/test_field_mapper.py: FOUND
- 20-02-SUMMARY.md: FOUND
- commit 14aacc9 (Task 1): FOUND
- commit ac83fe1 (Task 2): FOUND
- commit 3bade5e (Task 3): FOUND
- _INSERT_SQL placeholder count == 35: VERIFIED

---
*Phase: 20-schema-standardisation-ecs-ocsf*
*Completed: 2026-04-01*
