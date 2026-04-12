---
phase: 40-atomic-red-team-validation
plan: "02"
subsystem: api
tags: [sqlite, atomic-red-team, fastapi, tdd, coverage]

# Dependency graph
requires:
  - phase: 40-01
    provides: Wave 0 TDD stubs (test_atomics_store.py, test_atomics_api.py) + atomics.json bundle

provides:
  - AtomicsStore class with DDL, bulk_insert, list_techniques, get_tests_for_technique, save_validation_result, get_validation_results
  - seed_atomics() async idempotent startup seed from data/atomics.json
  - GET /api/atomics returning grouped techniques with three-tier coverage and per-test invoke strings
  - AtomicsStore wired in main.py lifespan (7e block), router registered

affects: [40-03, 40-04, atomics-validation, art-catalog-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - AtomicsStore mirrors CARStore exactly (sqlite3.Connection param, executescript DDL, bulk_insert OR IGNORE)
    - Coverage fallback: sqlite_store._conn → atomics_store._conn (graceful test/degradation)
    - Test auth bypass via dependency_overrides[verify_token] (consistent with all other unit tests)
    - _VALIDATE_AVAILABLE guard separates Plan 02 (GET) from Plan 03 (POST validate) test activation

key-files:
  created:
    - backend/services/atomics/atomics_store.py
    - backend/api/atomics.py
  modified:
    - backend/main.py
    - tests/unit/test_atomics_api.py

key-decisions:
  - "AtomicsStore uses sqlite_store._conn fallback to atomics_store._conn in get_atomics handler — allows test isolation without lifespan"
  - "test_atomics_api.py refactored: SimpleNamespace for sqlite_store, dependency_overrides for auth, _VALIDATE_AVAILABLE guard for Plan 03 stubs"
  - "test_validate_pass/fail use _VALIDATE_AVAILABLE (route presence check) not _AVAILABLE — separate Plan 02/03 activation cleanly"
  - "detections table created in _make_conn() — prevents OperationalError crash in test_validate_pass setup before assert"

patterns-established:
  - "AtomicsStore: sqlite3.Connection passed directly, not SQLiteStore wrapper — testable with :memory: conn"
  - "_make_authed_app() helper pattern: create_app() + inject state + dependency_overrides + TestClient"

requirements-completed: [P40-T01, P40-T02]

# Metrics
duration: 25min
completed: 2026-04-12
---

# Phase 40 Plan 02: AtomicsStore + GET /api/atomics Summary

**AtomicsStore SQLite CRUD (DDL, bulk_insert, validation persistence) + GET /api/atomics catalog endpoint returning 220 techniques with three-tier coverage badges and Invoke-AtomicTest command strings**

## Performance

- **Duration:** 25 min
- **Started:** 2026-04-12T08:00:00Z
- **Completed:** 2026-04-12T08:25:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- AtomicsStore class: DDL (atomics + atomics_validation_results tables + index), bulk_insert (INSERT OR IGNORE, 13 columns), atomic_count, list_techniques, get_tests_for_technique, save_validation_result, get_validation_results — all 5 unit tests PASS
- GET /api/atomics: parallel asyncio.gather for techniques/tests/validations, three-tier coverage (validated > detected > none), per-test invoke strings (Invoke-AtomicTest, -CheckPrereqs, -Cleanup), supported_platforms deserialized, elevation_required cast to bool
- AtomicsStore wired in main.py lifespan block 7e after CARStore; atomics router registered with try/except safety pattern
- Full unit suite: 1026 passed, 3 skipped, no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: AtomicsStore class and seed_atomics()** - `f820885` (feat)
2. **Task 2: main.py wiring + GET /api/atomics endpoint** - `dd5a18f` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `backend/services/atomics/atomics_store.py` - AtomicsStore DDL + CRUD + seed_atomics()
- `backend/api/atomics.py` - GET /api/atomics router with coverage computation
- `backend/main.py` - AtomicsStore init in lifespan (7e block) + router registration
- `tests/unit/test_atomics_api.py` - Fixed test setup: SimpleNamespace, auth override, detections DDL, _VALIDATE_AVAILABLE guard

## Decisions Made
- `sqlite_store._conn` fallback to `atomics_store._conn` in get_atomics handler — tests don't run lifespan, so sqlite_store may not exist; fallback uses same conn as in-memory test db
- `test_atomics_api.py` stubs had broken setup: `app.state.sqlite_store._conn = conn` fails when sqlite_store not on app.state; fixed to `SimpleNamespace(_conn=conn)` assignment
- `_VALIDATE_AVAILABLE` guard checks for route presence in router.routes — activate validate tests only when Plan 03 registers POST /api/atomics/validate

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_atomics_api.py broken state setup**
- **Found during:** Task 2 (API test GREEN phase)
- **Issue:** `app.state.sqlite_store._conn = conn` fails with AttributeError because sqlite_store isn't set (lifespan doesn't run in TestClient). Test also used `"Bearer test"` token without auth dependency override.
- **Fix:** Added `_make_authed_app()` helper using `SimpleNamespace(_conn=conn)` for sqlite_store, `dependency_overrides[verify_token]` for auth bypass. Added `_VALIDATE_AVAILABLE` guard to skip Plan 03 validate stubs cleanly.
- **Files modified:** tests/unit/test_atomics_api.py
- **Verification:** test_get_atomics_returns_200 PASS; test_validate_pass/fail SKIP (not ERROR)
- **Committed in:** dd5a18f (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test fixture)
**Impact on plan:** Required to make test_get_atomics_returns_200 pass. No scope creep.

## Issues Encountered
- Test stub (from Plan 01) used incorrect state initialization pattern — fixed inline as part of Task 2 implementation

## Next Phase Readiness
- AtomicsStore fully operational, seed_atomics() wired at startup
- GET /api/atomics returns full ART catalog with coverage; ready for Plan 03 validate endpoint
- test_validate_pass and test_validate_fail skip cleanly, will activate automatically when Plan 03 adds POST /api/atomics/validate

---
*Phase: 40-atomic-red-team-validation*
*Completed: 2026-04-12*
