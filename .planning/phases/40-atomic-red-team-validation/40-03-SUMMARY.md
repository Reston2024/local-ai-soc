---
phase: 40-atomic-red-team-validation
plan: "03"
subsystem: api
tags: [fastapi, sqlite, atomics, sigma, detection-validation]

# Dependency graph
requires:
  - phase: 40-atomic-red-team-validation
    provides: AtomicsStore with save_validation_result, Wave 0 TDD stubs with _VALIDATE_AVAILABLE guard

provides:
  - POST /api/atomics/validate endpoint with 5-minute detection window check and result persistence

affects: [40-atomic-red-team-validation, frontend-atomics-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - asyncio.to_thread for synchronous SQLite detection queries inside async FastAPI handler
    - hasattr(row, "keys") guard for sqlite3.Row vs plain tuple row access
    - 3-way technique matching: exact + LIKE parent.% + parent exact

key-files:
  created: []
  modified:
    - backend/api/atomics.py

key-decisions:
  - "_check_detection_sync uses hasattr(row, 'keys') guard — handles both sqlite3.Row (row_factory set) and plain tuple rows; row['id'] vs row[0]"
  - "sqlite_store._conn fallback to atomics_store._conn in validate_atomic — consistent with get_atomics handler pattern, enables test isolation"
  - "VALIDATION_WINDOW_SECONDS=300 as module-level constant — makes window configurable without changing function signatures"
  - "3-way technique matching (exact T1059.001, LIKE T1059.%, parent T1059) from RESEARCH.md Pattern 3 Pitfall 5 — covers sub-technique and parent-technique detections"

patterns-established:
  - "Detection window query: cutoff_iso = (now - timedelta(seconds=N)).strftime('%Y-%m-%dT%H:%M:%S') for ISO-8601 string comparison"

requirements-completed:
  - P40-T05
  - P40-T06

# Metrics
duration: 8min
completed: 2026-04-12
---

# Phase 40 Plan 03: POST /api/atomics/validate endpoint — 5-minute window detection check with persistence

**POST /api/atomics/validate closes the ART simulation loop: checks detections table for a matching technique within 5 minutes and persists pass/fail verdict to atomics_validation_results**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-12T~08:30:00Z
- **Completed:** 2026-04-12T~08:38:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Added POST /api/atomics/validate to existing backend/api/atomics.py router
- Implemented ValidateRequest Pydantic model and _check_detection_sync() helper with 3-way technique matching
- All 3 test_atomics_api.py tests now PASS (test_get_atomics_returns_200, test_validate_pass, test_validate_fail)
- All 8 Phase 40 unit tests pass (5 store + 3 API); 1028 total unit tests green

## Task Commits

Each task was committed atomically:

1. **Task 1: POST /api/atomics/validate endpoint** - `b4aabc3` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `backend/api/atomics.py` — Added ValidateRequest model, _check_detection_sync() helper, POST /api/atomics/validate handler, datetime/timedelta/timezone imports, pydantic BaseModel import, VALIDATION_WINDOW_SECONDS constant

## Decisions Made

- **_check_detection_sync uses hasattr(row, "keys") guard** — handles both sqlite3.Row (row_factory set) and plain tuple rows; row["id"] vs row[0] fallback
- **sqlite_store._conn fallback to atomics_store._conn** — consistent with get_atomics handler pattern, enables test isolation without lifespan
- **VALIDATION_WINDOW_SECONDS=300 as module-level constant** — makes window size readable and configurable
- **3-way technique matching** — exact (T1059.001), LIKE (T1059.%), parent exact (T1059) from RESEARCH.md Pattern 3 to cover all detection storage variants

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 8 Phase 40 unit tests pass
- POST /api/atomics/validate endpoint is live and tested
- ART simulation loop is complete: analyst runs atomic test → clicks Validate → backend confirms detection fired
- Ready for Phase 40 frontend integration (AtomicsView validate button wiring)

---
*Phase: 40-atomic-red-team-validation*
*Completed: 2026-04-12*
