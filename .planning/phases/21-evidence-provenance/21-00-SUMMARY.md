---
phase: 21-evidence-provenance
plan: "00"
subsystem: testing
tags: [pydantic, provenance, sqlite, sigma, pytest, tdd, red-state]

# Dependency graph
requires:
  - phase: 20-schema-standardisation
    provides: field_map.py ECS/OCSF column mappings that FIELD_MAP_VERSION tracks
provides:
  - backend/models/provenance.py with 4 Pydantic BaseModel classes as interface contracts
  - 16 failing RED test stubs across 5 test files for all P21 requirements
  - FIELD_MAP_VERSION = "20" constant in detections/field_map.py
affects:
  - 21-01-PLAN (ingest provenance implementation — turns RED stubs GREEN)
  - 21-02-PLAN (detection provenance implementation)
  - 21-03-PLAN (LLM audit provenance implementation)
  - 21-04-PLAN (playbook run provenance implementation)
  - 21-05-PLAN (provenance API endpoints)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "pytest.fail('NOT IMPLEMENTED') RED stub pattern for Nyquist compliance"
    - "Pydantic BaseModel with str/Optional[str]/list[str] only for SQLite-backed records"

key-files:
  created:
    - backend/models/provenance.py
    - tests/unit/test_ingest_provenance.py
    - tests/unit/test_detection_provenance.py
    - tests/unit/test_llm_provenance.py
    - tests/unit/test_playbook_provenance.py
    - tests/unit/test_provenance_api.py
  modified:
    - detections/field_map.py

key-decisions:
  - "FIELD_MAP_VERSION = '20' placed before SIGMA_FIELD_MAP dict in field_map.py — matching the phase (20) that last updated the field map"
  - "All provenance Pydantic models use str/Optional[str]/list[str] only — no datetime or complex types — to ensure trivial SQLite serialization"
  - "test_provenance_api.py imports all 4 model classes to ensure collection-level import errors surface before any stub test body runs"

patterns-established:
  - "RED stub pattern: import the model class at module level, call pytest.fail in test body — import errors = collection error, body fail = FAIL"
  - "Provenance models as Wave 0 interface contracts: downstream Wave 1-2 plans implement against these types without codebase exploration"

requirements-completed:
  - P21-T01
  - P21-T02
  - P21-T03
  - P21-T04
  - P21-T05

# Metrics
duration: 2min
completed: 2026-04-02
---

# Phase 21 Plan 00: Evidence Provenance — RED Stubs and Interface Contracts Summary

**4 Pydantic provenance models + FIELD_MAP_VERSION constant + 16 pytest RED stubs covering all 5 P21 requirement areas**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-02T12:31:04Z
- **Completed:** 2026-04-02T12:33:29Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Created `backend/models/provenance.py` with `IngestProvenanceRecord`, `DetectionProvenanceRecord`, `LlmProvenanceRecord`, and `PlaybookProvenanceRecord` Pydantic BaseModel classes — these are the interface contracts all Wave 1/2 plans implement against
- Added `FIELD_MAP_VERSION = "20"` to `detections/field_map.py` immediately before `SIGMA_FIELD_MAP` — enables detection provenance records to capture which field translation version was active when a rule fired
- Created 5 test stub files (16 total functions) all in FAIL state (`pytest.fail("NOT IMPLEMENTED")`) — 0 errors, confirming model imports resolve cleanly at collection time

## Task Commits

Each task was committed atomically:

1. **Task 1: Pydantic provenance models and FIELD_MAP_VERSION** - `c367d05` (feat)
2. **Task 2: 16 failing RED test stubs** - `32ee473` (test)

## Files Created/Modified

- `backend/models/provenance.py` - 4 Pydantic BaseModel classes for SQLite provenance record types
- `detections/field_map.py` - Added FIELD_MAP_VERSION = "20" module-level constant
- `tests/unit/test_ingest_provenance.py` - 5 stubs for P21-T01 (ingest provenance)
- `tests/unit/test_detection_provenance.py` - 3 stubs for P21-T02 (detection provenance)
- `tests/unit/test_llm_provenance.py` - 4 stubs for P21-T03 (LLM audit provenance)
- `tests/unit/test_playbook_provenance.py` - 3 stubs for P21-T04 (playbook run provenance)
- `tests/unit/test_provenance_api.py` - 1 stub for P21-T05 (provenance API auth enforcement)

## Decisions Made

- `FIELD_MAP_VERSION = "20"` — value matches Phase 20 (ECS extension), which was the last phase to modify the field map
- All Pydantic fields use `str`, `Optional[str]`, or `list[str]` only — no `datetime` objects — so serialization to/from DuckDB/SQLite strings is trivial and needs no custom validators
- `test_provenance_api.py` imports all 4 model classes so any future import regression in provenance.py surfaces as a collection error, not a false FAIL

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 5 P21 requirement areas have concrete FAIL tests to turn GREEN
- `backend/models/provenance.py` provides typed interface contracts for Wave 1 (plans 01-04) and Wave 2 (plan 05) executors
- `FIELD_MAP_VERSION` ready for import by detection provenance implementation (plan 21-02)
- No blockers — proceed to Wave 1 plans in any order

---
*Phase: 21-evidence-provenance*
*Completed: 2026-04-02*
