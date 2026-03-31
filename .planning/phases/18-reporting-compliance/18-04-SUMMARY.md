---
phase: 18-reporting-compliance
plan: "04"
subsystem: api
tags: [compliance, nist-csf, thehive, zip-export, fastapi, asyncio]

# Dependency graph
requires:
  - phase: 18-reporting-compliance
    provides: reports router (backend/api/reports.py), SQLite reports/investigation_cases/playbook_runs tables
  - phase: 18-reporting-compliance
    provides: daily_kpi_snapshots DuckDB table (plan 18-03)
provides:
  - GET /api/reports/compliance?framework=nist-csf — downloadable ZIP with 6 NIST CSF 2.0 evidence files + summary.html
  - GET /api/reports/compliance?framework=thehive — downloadable ZIP with TheHive Alert/Case JSON records
  - 400 response for unknown framework values
affects: [compliance-ui, audit-readiness, security-reporting]

# Tech tracking
tech-stack:
  added: [zipfile (stdlib), io.BytesIO (stdlib)]
  patterns:
    - asyncio.gather for parallel SQLite queries (detections + investigations + playbook_runs + reports_list)
    - graceful DuckDB exception fallback for optional daily_kpi_snapshots table
    - in-memory ZIP construction using io.BytesIO (no temp files)

key-files:
  created:
    - tests/unit/test_compliance_export.py
  modified:
    - backend/api/reports.py

key-decisions:
  - "Used asyncio.gather to run the four SQLite queries in parallel for nist-csf path"
  - "TheHive description field reads analyst_notes (not description column, which is not used in evidence export)"
  - "Graceful exception catch around DuckDB daily_kpi_snapshots query — table may not exist on fresh installs"
  - "Added 6 extra tests (beyond the 3 required) to cover empty-DB edge case and analyst_notes correctness"

patterns-established:
  - "In-memory ZIP pattern: io.BytesIO + zipfile.ZipFile, seek(0), read() — no temp files needed"

requirements-completed: [P18-T04]

# Metrics
duration: 3min
completed: 2026-03-31
---

# Phase 18 Plan 04: Compliance Evidence Export Summary

**GET /api/reports/compliance producing NIST CSF 2.0 ZIP (6 evidence JSON + summary.html) and TheHive Alert/Case ZIP, with graceful empty-database handling**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-31T19:02:24Z
- **Completed:** 2026-03-31T19:06:20Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Added `GET /api/reports/compliance` to the existing reports router supporting `nist-csf` and `thehive` frameworks
- NIST CSF 2.0 path: gathers evidence from SQLite (detections, investigations, playbook_runs, reports) and DuckDB (kpi_snapshots), builds a ZIP with `nist-csf/{function}.json` for all 6 CSF functions (GOVERN/IDENTIFY/PROTECT/DETECT/RESPOND/RECOVER) plus `summary.html`
- TheHive path: maps investigations to TheHive Alert/Case format using `analyst_notes` as description content (not the `description` column), builds a ZIP with `thehive/alerts.json` and `thehive/cases.json`
- Unknown framework returns HTTP 400 with descriptive error listing supported values
- Added `_severity_to_int` helper and imported `io`, `zipfile`, `Query` — all from stdlib/existing fastapi deps
- 6 unit tests pass (covers all 3 required paths plus empty-DB edge cases and analyst_notes correctness)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add GET /api/reports/compliance endpoint** - `2b44590` (feat)

**Plan metadata:** (included in final metadata commit below)

## Files Created/Modified

- `backend/api/reports.py` — appended `get_compliance_export` route with nist-csf and thehive paths, `_severity_to_int` helper; added `io`, `zipfile`, `Query` imports
- `tests/unit/test_compliance_export.py` — 6 unit tests using real SQLiteStore + mocked DuckDB; patches `backend.core.auth.settings` for auth token

## Decisions Made

- Used `asyncio.gather` for the four parallel SQLite queries in the nist-csf path (detections, investigations, playbook_runs, reports_list) rather than sequential `asyncio.to_thread` calls — reduces wall time when DB has data
- TheHive `description` uses `inv.get("analyst_notes", "") or ""` — the plan explicitly notes that `investigation_cases` has no `description` column intended for evidence export
- DuckDB `daily_kpi_snapshots` query wrapped in try/except with fallback to `[]` — consistent with the pattern established in plan 18-01's executive report endpoint
- Wrote 6 tests instead of the 3 minimum to ensure empty-DB validity and analyst_notes correctness are explicitly verified

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added Authorization header to tests**
- **Found during:** Task 1 (running tests — all returned 401)
- **Issue:** The `create_app()` factory mounts auth middleware that requires `Authorization: Bearer <token>`; the plan's test spec did not mention auth headers
- **Fix:** Added `_AUTH_TOKEN` constant, `_AUTH_HEADERS` dict, patched `backend.core.auth.settings.AUTH_TOKEN` in the `client` fixture, and passed headers in all test requests
- **Files modified:** tests/unit/test_compliance_export.py
- **Verification:** All 6 tests pass after fix
- **Committed in:** 2b44590 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Necessary for test correctness — the auth pattern is consistent with `test_metrics_api.py` and other tests in the project. No scope creep.

## Issues Encountered

None beyond the auth header deviation documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 4 plans in phase 18 are complete (18-01 through 18-04)
- Phase 18 compliance reporting fully implemented: MITRE ATT&CK heatmap, KPI trend snapshots, PDF report generation, and compliance evidence export
- Ready for phase transition / milestone completion review

## Self-Check: PASSED

- `backend/api/reports.py` — FOUND
- `tests/unit/test_compliance_export.py` — FOUND
- Commit `2b44590` — FOUND

---
*Phase: 18-reporting-compliance*
*Completed: 2026-03-31*
