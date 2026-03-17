---
phase: 07-threat-hunting-case-management
plan: "00"
subsystem: investigation
tags: [tdd, wave-0, stubs, sqlite, fastapi, phase7]
dependency_graph:
  requires: []
  provides:
    - backend/investigation/ package (6 stub modules)
    - backend/src/tests/test_phase7.py (16 xfail stubs)
    - SQLiteStore investigation_cases/case_artifacts/case_tags DDL
  affects:
    - backend/stores/sqlite_store.py
tech_stack:
  added: []
  patterns:
    - xfail stub pattern (strict=False) matching Phase 6 baseline
    - NotImplementedError stubs for incremental TDD implementation
    - SQLite DDL extension without modifying existing tables
key_files:
  created:
    - backend/investigation/__init__.py
    - backend/investigation/case_manager.py
    - backend/investigation/hunt_engine.py
    - backend/investigation/timeline_builder.py
    - backend/investigation/artifact_store.py
    - backend/investigation/tagging.py
    - backend/investigation/investigation_routes.py
    - backend/src/tests/test_phase7.py
  modified:
    - backend/stores/sqlite_store.py
decisions:
  - "investigation_cases table name avoids conflict with existing 'cases' table"
  - "strict=False on all Phase 7 xfail stubs — xpass acceptable before implementation"
  - "SQLiteStore stub methods raise NotImplementedError — Plan 01 will implement"
metrics:
  duration: "2 minutes"
  completed_date: "2026-03-17"
  tasks_completed: 2
  files_created: 8
  files_modified: 1
---

# Phase 7 Plan 00: Wave 0 TDD Red Baseline Summary

**One-liner:** Phase 7 Wave 0 red baseline — 16 xfail stubs in test_phase7.py, investigation/ package with 6 NotImplementedError stubs, SQLiteStore DDL extended with investigation_cases/case_artifacts/case_tags tables.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create backend/investigation/ package + extend SQLiteStore DDL | 7227556 | 7 new + 1 modified |
| 2 | Write test_phase7.py with 16 xfail stubs (P7-T01 through P7-T16) | b3d2e3d | 1 new |

## What Was Built

### backend/investigation/ Package

Seven files establishing the Phase 7 investigation module skeleton:

- `__init__.py` — Package marker (empty)
- `case_manager.py` — `CaseManager` class with 4 stub methods: `create_investigation_case`, `get_investigation_case`, `list_investigation_cases`, `update_investigation_case`
- `hunt_engine.py` — `HUNT_TEMPLATES: dict = {}` + async `execute_hunt` stub
- `timeline_builder.py` — async `build_timeline` stub
- `artifact_store.py` — async `save_artifact` stub
- `tagging.py` — `add_tag`, `remove_tag`, `list_tags` stubs
- `investigation_routes.py` — `investigation_router = APIRouter(prefix="/api", tags=["investigation"])`

### SQLiteStore DDL Extension

Three new tables appended to `_DDL` (existing tables untouched):
- `investigation_cases` — 12 columns including case_status, related_alerts, analyst_notes
- `case_artifacts` — 8 columns with FK to investigation_cases
- `case_tags` — 4 columns with UNIQUE(case_id, tag) constraint + FK

Three new indexes: `idx_inv_cases_status`, `idx_artifacts_case`, `idx_tags_case`

Six stub methods added to SQLiteStore class: `create_investigation_case`, `get_investigation_case`, `list_investigation_cases`, `update_investigation_case`, `insert_artifact`, `get_artifacts_by_case`

### test_phase7.py (16 xfail stubs)

| Test Class | Tests | Plans |
|------------|-------|-------|
| TestCaseManager | 3 (P7-T01, T02, T03) | Plan 01 |
| TestCaseAPI | 4 (P7-T04, T05, T06, T07) | Plan 01 |
| TestHuntEngine | 2 (P7-T08, T09) | Plan 02 |
| TestHuntAPI | 2 (P7-T10, T11) | Plan 02 |
| TestTimelineBuilder | 1 (P7-T12) | Plan 03 |
| TestTimelineAPI | 1 (P7-T13) | Plan 03 |
| TestArtifactStore | 1 (P7-T14) | Plan 03 |
| TestArtifactAPI | 1 (P7-T15) | Plan 03 |
| test_dashboard_build | 1 (P7-T16) | Plan 04 |

## Verification Results

```
uv run pytest backend/src/tests/test_phase7.py -v
16 xfailed in 0.43s

uv run pytest backend/src/tests/ -v
41 passed, 17 xfailed, 42 xpassed in 0.58s
```

No regressions. All 41 existing tests still pass.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- [x] backend/investigation/__init__.py exists
- [x] backend/investigation/case_manager.py exists
- [x] backend/investigation/hunt_engine.py exists
- [x] backend/investigation/timeline_builder.py exists
- [x] backend/investigation/artifact_store.py exists
- [x] backend/investigation/tagging.py exists
- [x] backend/investigation/investigation_routes.py exists
- [x] backend/src/tests/test_phase7.py exists (16 test methods)
- [x] SQLiteStore._DDL contains investigation_cases, case_artifacts, case_tags
- [x] All 16 tests XFAIL (not ERROR)
- [x] 41 regression tests pass (no new failures)
- [x] Commit 7227556 exists (Task 1)
- [x] Commit b3d2e3d exists (Task 2)
