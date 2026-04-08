---
phase: 30-final-security-and-human-sign-off
plan: 01
subsystem: api
tags: [sigma, detection, fastapi, tdd, guard]

# Dependency graph
requires:
  - phase: detections
    provides: SigmaMatcher with load_rules_dir and run_all
provides:
  - HTTPException(422) guard in POST /api/detect/run when 0 Sigma rules are loaded
  - rules/sigma/ directory with operator README and example rule skeleton
  - Unit tests confirming the guard behaviour (RED/GREEN TDD)
affects: [operators deploying detect endpoint, future detection phases]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD RED/GREEN: write failing test first, then implement guard to pass it"
    - "Module-level import of SigmaMatcher to enable unittest.mock.patch at backend.api.detect.SigmaMatcher"

key-files:
  created:
    - tests/unit/test_sigma_guard.py
    - rules/sigma/README.md
  modified:
    - backend/api/detect.py

key-decisions:
  - "Move SigmaMatcher import from function body to module level so it can be patched at backend.api.detect.SigmaMatcher in tests"
  - "Return HTTP 422 (Unprocessable Entity) rather than 200 with empty list to clearly signal misconfiguration vs clean environment"

patterns-established:
  - "0-rule guard pattern: check loaded count after rules loop, raise 422 with descriptive detail before proceeding"

requirements-completed:
  - P30-T03

# Metrics
duration: 8min
completed: 2026-04-08
---

# Phase 30 Plan 01: Sigma 0-Rule Guard Summary

**HTTPException(422) guard added to POST /api/detect/run preventing silent 0-detection failures when rules/sigma/ is empty or missing**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-08T21:02:58Z
- **Completed:** 2026-04-08T21:10:30Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- TDD RED phase: wrote two failing tests for the 0-rule guard before implementation
- TDD GREEN phase: moved SigmaMatcher import to module level, added `if loaded == 0: raise HTTPException(422, ...)` guard with structured warning log
- Created `rules/sigma/README.md` with operator guidance, modifier table, and example rule skeleton
- Full unit suite (871 tests) passes with 0 regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing test for 0-rule guard** - `3a6d9cd` (test)
2. **Task 2: Add 0-rule guard to run_detection and create rules/sigma/README.md** - `9073755` (feat)
3. **Task 3: Full unit suite regression check** - (no files changed — verification only)

_Note: TDD tasks have two commits (test RED → feat GREEN)_

## Files Created/Modified
- `backend/api/detect.py` - Moved SigmaMatcher import to module level; added 0-rule guard raising HTTPException(422)
- `tests/unit/test_sigma_guard.py` - Two unit tests: no-rules → 422, with-rules → 200
- `rules/sigma/README.md` - Operator guidance for placing Sigma .yml rules, example skeleton, modifier table

## Decisions Made
- Moved `SigmaMatcher` import from inside `run_detection()` to module level so `unittest.mock.patch("backend.api.detect.SigmaMatcher")` works in tests. This is the idiomatic Python mock pattern — patch where the name is used, not where it's defined.
- HTTP 422 (Unprocessable Entity) chosen over 200 empty list because 422 clearly signals "this request cannot be processed due to a configuration problem" rather than "no threats found".

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SigmaMatcher import moved to module level for patchability**
- **Found during:** Task 1 (RED phase test run)
- **Issue:** SigmaMatcher was imported inside `run_detection()` function body; `patch("backend.api.detect.SigmaMatcher")` raised AttributeError because the name didn't exist at module scope
- **Fix:** Moved `from detections.matcher import SigmaMatcher` to the module-level imports in detect.py; removed local import from inside the function
- **Files modified:** backend/api/detect.py
- **Verification:** Both tests pass in GREEN phase; 871 unit tests pass
- **Committed in:** 9073755 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug preventing test infrastructure from working)
**Impact on plan:** Required moving one import line; no architectural change, no scope creep.

## Issues Encountered
None beyond the import location fix documented above.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- 0-rule guard is live; operators who deploy with an empty `rules/sigma/` will now receive a clear HTTP 422 instead of a misleading empty detections list
- `rules/sigma/README.md` provides operator onboarding for adding production Sigma rules
- Ready for Phase 30 Plan 02 (Caddy digest verification) or human sign-off checkpoint

---
*Phase: 30-final-security-and-human-sign-off*
*Completed: 2026-04-08*
