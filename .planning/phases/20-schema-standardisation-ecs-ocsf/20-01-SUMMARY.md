---
phase: 20-schema-standardisation-ecs-ocsf
plan: "01"
subsystem: database
tags: [pydantic, ecs, ocsf, normalized-event, duckdb, schema]

# Dependency graph
requires:
  - phase: 20-00
    provides: "stub test file tests/unit/test_normalized_event_ecs.py with NOT IMPLEMENTED stubs"
provides:
  - "NormalizedEvent extended with 6 new Optional ECS/OCSF fields (ocsf_class_uid, event_outcome, user_domain, process_executable, network_protocol, network_direction)"
  - "OCSF_CLASS_UID_MAP dict mapping 28 event_type strings to OCSF integer class UIDs"
  - "to_duckdb_row() returning 35-element tuple; new fields at positions 29-34"
  - "loader.py backward-compat slice [:29] — existing 29-column INSERT SQL unaffected"
affects:
  - 20-02-DuckDB-schema-migration
  - 20-03-FieldMapper
  - ingestion/loader.py
  - detections/field_map.py
  - backend/api/ingest.py

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Backward-compatible model extension: append new fields at tuple end, slice in caller until DB migration"
    - "OCSF class_uid lookup dict at module level, exported in __all__"

key-files:
  created: []
  modified:
    - backend/models/event.py
    - ingestion/loader.py
    - tests/unit/test_normalized_event_ecs.py

key-decisions:
  - "Appended 6 new ECS fields at end of to_duckdb_row() tuple (positions 29-34) to keep positions 0-28 stable for loader.py until plan 20-02 DB migration"
  - "loader.py slices to_duckdb_row()[:29] so existing 29-column INSERT SQL remains valid — zero loader regression"
  - "OCSF_CLASS_UID_MAP placed before NormalizedEvent class so it can be imported independently"
  - "Registry events mapped to OCSF class 1001 (File System Activity) per OCSF v1 convention"

patterns-established:
  - "Backward-compat slice pattern: caller uses row[:N] until DB schema migration adds the N new columns"

requirements-completed: [P20-T01]

# Metrics
duration: 15min
completed: 2026-04-01
---

# Phase 20 Plan 01: ECS-Aligned NormalizedEvent Extension Summary

**NormalizedEvent extended with 6 Optional ECS/OCSF fields and OCSF_CLASS_UID_MAP (28 event_type -> integer class_uid), backward-compatible via loader [:29] slice until plan 20-02 DB migration**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-01T14:00:00Z
- **Completed:** 2026-04-01T14:15:00Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 3

## Accomplishments

- Extended NormalizedEvent with 6 new Optional fields (ocsf_class_uid, event_outcome, user_domain, process_executable, network_protocol, network_direction) — all default None, zero breakage to existing callers
- Added OCSF_CLASS_UID_MAP dict with 28 entries mapping Sysmon/Windows event_type strings to OCSF v1 integer class UIDs
- Updated to_duckdb_row() to return a 35-element tuple with new ECS fields at positions 29-34
- Fixed backward-compatibility in loader.py by slicing tuple to [:29] so existing INSERT SQL is unaffected until plan 20-02

## Task Commits

1. **RED: ECS test stubs replaced with real assertions** - `5a1ef4e` (test)
2. **GREEN: NormalizedEvent + OCSF_CLASS_UID_MAP + loader fix** - `31ed790` (feat)

## Files Created/Modified

- `backend/models/event.py` - Added OCSF_CLASS_UID_MAP (28 entries), 6 new Optional fields, extended to_duckdb_row() to 35 elements, updated __all__
- `ingestion/loader.py` - Added [:29] slice on to_duckdb_row() for backward-compat with existing INSERT SQL
- `tests/unit/test_normalized_event_ecs.py` - Replaced 8 NOT IMPLEMENTED stubs with real test assertions

## Decisions Made

- **Backward-compat slice in loader.py:** to_duckdb_row() now returns 35 elements but loader.py's INSERT SQL only has 29 placeholders. Rather than modifying loader.py's SQL (plan 20-02's job), the call site slices `row[:29]`. This keeps the loader working unchanged until the DB ALTER TABLE in plan 20-02.
- **OCSF registry mapping:** Registry events (registry_event, registry_value_set) map to OCSF class 1001 (File System Activity) per OCSF v1 — no dedicated registry class exists in OCSF v1.
- **Field order:** ocsf_class_uid first (integer, most useful for analytics), followed by string metadata fields (event_outcome, user_domain, process_executable, network_protocol, network_direction).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed loader.py parameter count mismatch**
- **Found during:** Task 1 (GREEN phase — running full test suite)
- **Issue:** to_duckdb_row() extended to 35 elements but loader.py passes the full tuple to a 29-placeholder INSERT SQL, causing DuckDB "Parameter argument/count mismatch" errors for positions 30-35
- **Fix:** Sliced the row to `[:29]` at the call site in loader.py with an explanatory comment referencing plan 20-02
- **Files modified:** `ingestion/loader.py`
- **Verification:** `uv run pytest tests/unit/test_loader.py -v` — 11/11 pass; full suite shows 0 new regressions vs pre-change baseline (101 pre-existing failures unchanged)
- **Committed in:** 31ed790 (feat(20-01) commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug caused by my own change)
**Impact on plan:** Essential fix for backward-compatibility. The plan stated "loader.py _INSERT_SQL is NOT modified in this plan" — the fix honors that constraint while preventing the mismatch.

## Issues Encountered

- Full test suite showed 101 failures. Verified via git stash comparison that all 101 are pre-existing from earlier phases (Phase 19 RBAC auth guard causes 401 on test_ingest_api.py, test_graph_api.py; stub tests in test_field_mapper.py). Zero new failures introduced.

## Next Phase Readiness

- backend/models/event.py is the canonical model with all 6 ECS fields — plan 20-02 can now run `ALTER TABLE normalized_events ADD COLUMN ...` for each new field and update loader.py _INSERT_SQL to include positions 29-34
- OCSF_CLASS_UID_MAP is importable from `backend.models.event` — plan 20-03 FieldMapper can reference it directly
- All 8 test_normalized_event_ecs.py tests pass GREEN, no regressions

---
*Phase: 20-schema-standardisation-ecs-ocsf*
*Completed: 2026-04-01*

## Self-Check: PASSED

- `backend/models/event.py` — FOUND
- `ingestion/loader.py` — FOUND
- `tests/unit/test_normalized_event_ecs.py` — FOUND
- `.planning/phases/20-schema-standardisation-ecs-ocsf/20-01-SUMMARY.md` — FOUND
- Commit `5a1ef4e` (test RED) — FOUND
- Commit `31ed790` (feat GREEN) — FOUND
