---
phase: 12-api-hardening-parser-coverage
plan: 01
subsystem: api
tags: [slowapi, rate-limiting, fastapi, middleware, security]

# Dependency graph
requires: []
provides:
  - "slowapi==0.1.9 Limiter singleton in backend/core/rate_limit.py (disabled when TESTING=1)"
  - "SlowAPIMiddleware + RateLimitExceeded handler wired in main.py create_app()"
  - "Per-endpoint limits: ingest/file 10/min, query/ask 30/min, detect/run 10/min"
  - "feature/phase-12-api-hardening branch established for all Phase 12 work"
affects: [12-02, 12-03, 12-04]

# Tech tracking
tech-stack:
  added: ["slowapi==0.1.9", "limits==5.8.0 (transitive)", "deprecated==1.3.1 (transitive)", "wrapt==2.1.2 (transitive)"]
  patterns: ["Limiter singleton in core/rate_limit.py imported by main.py and router files", "@limiter.limit above @router.post (required when from __future__ import annotations is used)", "TESTING=1 env var disables rate limiter for test suite"]

key-files:
  created:
    - "backend/core/rate_limit.py"
    - "tests/unit/test_rate_limiting.py"
  modified:
    - "backend/main.py"
    - "backend/api/ingest.py"
    - "backend/api/query.py"
    - "backend/api/detect.py"
    - "tests/conftest.py"
    - "pyproject.toml"
    - "uv.lock"

key-decisions:
  - "Decorator order must be @limiter.limit ABOVE @router.post when from __future__ import annotations is present in the module (annotations become ForwardRef strings; FastAPI can't resolve them from the slowapi wrapper context if @router.post runs second)"
  - "TESTING=1 env var guard added to conftest.py via os.environ.setdefault to prevent 429s in entire test suite"
  - "Limiter singleton at module level in backend/core/rate_limit.py, shared across main.py and all three router files"

patterns-established:
  - "Rate limiter disabled for tests: TESTING=1 in conftest.py + os.getenv check in rate_limit.py"
  - "Decorator order with __future__ annotations: @limiter.limit first (outermost in source) so FastAPI receives unwrapped function"

requirements-completed: [P12-T01, P12-T05]

# Metrics
duration: 5min
completed: 2026-03-27
---

# Phase 12 Plan 01: API Rate Limiting Summary

**slowapi==0.1.9 rate limiting on three expensive endpoints (ingest/file 10/min, query/ask 30/min, detect/run 10/min) with TESTING=1 guard and 4 unit tests covering limiter enable/disable and middleware registration**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-27T18:46:37Z
- **Completed:** 2026-03-27T18:51:37Z
- **Tasks:** 3 (Task 2 used TDD: RED + GREEN commits)
- **Files modified:** 7

## Accomplishments
- Created `backend/core/rate_limit.py` with Limiter singleton, auto-disabled when TESTING=1
- Wired SlowAPIMiddleware and RateLimitExceeded handler into main.py create_app()
- Applied @limiter.limit decorators to the three computationally expensive endpoints
- Created 4 unit tests (TDD) covering limiter state and middleware registration
- All 497 existing tests pass (zero regressions); coverage 71.99% (above 70% threshold)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create feature branch and add slowapi dependency** - `0f7de88` (chore)
2. **Task 2 RED: Add failing tests for rate limiting** - `043658c` (test)
3. **Task 2 GREEN: Implement rate limiter singleton and wire SlowAPIMiddleware** - `4058aab` (feat)
4. **Task 3: Apply per-endpoint rate limit decorators** - `00a88e0` (feat)

## Files Created/Modified
- `backend/core/rate_limit.py` - Limiter singleton (disabled when TESTING=1)
- `backend/main.py` - Added slowapi imports, app.state.limiter, SlowAPIMiddleware, RateLimitExceeded handler
- `backend/api/ingest.py` - @limiter.limit("10/minute") on POST /ingest/file
- `backend/api/query.py` - @limiter.limit("30/minute") on POST /query/ask
- `backend/api/detect.py` - @limiter.limit("10/minute") on POST /detect/run
- `tests/unit/test_rate_limiting.py` - 4 TDD unit tests for rate limiting
- `tests/conftest.py` - Added os.environ.setdefault("TESTING", "1") guard
- `pyproject.toml` - Added slowapi==0.1.9 to dependencies
- `uv.lock` - Updated with slowapi and transitive deps

## Decisions Made
- Limiter disabled via `enabled=os.getenv("TESTING") != "1"` check at module import time; conftest.py sets default before any imports
- Decorator order (`@limiter.limit` above `@router.post` in source) required because all three target files use `from __future__ import annotations`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed decorator order incompatible with `from __future__ import annotations`**
- **Found during:** Task 3 (Apply per-endpoint rate limit decorators)
- **Issue:** Plan specified `@router.post` FIRST (above) then `@limiter.limit` below it. With `from __future__ import annotations` active in all three router files, this causes annotations to become `ForwardRef` strings. FastAPI receives the slowapi-wrapped function and cannot resolve `ForwardRef('UploadFile')` — raises `FastAPIError: Invalid args for response field`. 104 tests failed.
- **Fix:** Reversed decorator order: `@limiter.limit` above `@router.post` in source (Python applies decorators bottom-up, so `@router.post` runs first on the raw function, then `@limiter.limit` wraps the route object, leaving FastAPI's registration unaffected).
- **Files modified:** `backend/api/ingest.py`, `backend/api/query.py`, `backend/api/detect.py`
- **Verification:** All 497 existing tests pass; `uv run pytest tests/ -q` zero failures
- **Committed in:** `00a88e0` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Auto-fix essential for correctness. No scope creep. The correct decorator order is documented in patterns-established for future plans in this phase.

## Issues Encountered
- `from __future__ import annotations` (PEP 563) makes function annotations lazy strings. The plan's stated decorator order silently breaks FastAPI's type resolution when the slowapi wrapper is interposed between the route registration and the original function. Fixed by reversing order.

## User Setup Required
None - no external service configuration required. Rate limiting takes effect automatically in production (no TESTING=1 set).

## Next Phase Readiness
- feature/phase-12-api-hardening branch ready for Phase 12 plans 02-04
- slowapi Limiter singleton available for any additional endpoints that need rate limiting
- Decorator order pattern documented: @limiter.limit ABOVE @router.post when from __future__ import annotations is present

## Self-Check: PASSED
- backend/core/rate_limit.py: FOUND
- tests/unit/test_rate_limiting.py: FOUND
- 12-01-SUMMARY.md: FOUND
- Commit 0f7de88 (Task 1): FOUND
- Commit 043658c (Task 2 RED): FOUND
- Commit 4058aab (Task 2 GREEN): FOUND
- Commit 00a88e0 (Task 3): FOUND

---
*Phase: 12-api-hardening-parser-coverage*
*Completed: 2026-03-27*
