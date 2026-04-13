---
phase: 45-agentic-investigation
plan: "04"
subsystem: api
tags: [fastapi, sse, smolagents, streaming, investigation, agentic]

# Dependency graph
requires:
  - phase: 45-03
    provides: build_agent() and run_investigation() async generator in runner.py
provides:
  - POST /api/investigate/agentic SSE endpoint that streams agentic investigation events
affects: [frontend investigation view, Phase 45 wave 4 frontend integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Deferred import of smolagents inside route handler (try/except) to avoid import-time failures
    - EventSourceResponse wrapping async generator that yields dicts with event/data keys
    - Stores accessed via request.app.state.stores — no injection needed

key-files:
  created: []
  modified:
    - backend/api/investigate.py
    - tests/unit/test_agentic_api.py

key-decisions:
  - "Deferred import of build_agent/run_investigation inside route handler with try/except prevents import-time failures when smolagents not installed"
  - "No asyncio.wait_for wrapper needed — run_investigation() handles deadline-polling timeout internally"
  - "Fixed test URL /agentic → /investigate/agentic to match router prefix (Rule 1 auto-fix)"

patterns-established:
  - "Agentic SSE route: EventSourceResponse(_event_generator()) where _event_generator is a local async def"

requirements-completed: [P45-T03, P45-T05]

# Metrics
duration: 8min
completed: 2026-04-13
---

# Phase 45 Plan 04: Agentic API SSE Endpoint Summary

**POST /api/investigate/agentic route added to investigate router — streams tool_call/reasoning/verdict/done events from smolagents ToolCallingAgent via EventSourceResponse**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-13T03:58:33Z
- **Completed:** 2026-04-13T04:06:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Added `AgenticInvestigateRequest` Pydantic model and `POST /agentic` route to existing investigate router
- Route builds agent from `request.app.state.stores` on each call, yields from `run_investigation()` async generator via `EventSourceResponse`
- Error handling for missing stores (AttributeError) and agent build failure (any Exception) — both yield SSE error event then close stream
- Both `test_agentic_endpoint_exists` and `test_agentic_sse_content_type` GREEN; 1092 total unit tests passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Add POST /agentic route to investigate.py** - `2f3369d` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `backend/api/investigate.py` - Added `EventSourceResponse`/`BaseModel` imports, `AgenticInvestigateRequest` model, `run_agentic_investigation()` route at `/agentic`
- `tests/unit/test_agentic_api.py` - Fixed test URL from `/agentic` to `/investigate/agentic` to match router prefix

## Decisions Made
- Deferred import of `build_agent`/`run_investigation` inside the route handler (inside `_event_generator`) using try/except — prevents import-time failure if smolagents not installed in a particular environment
- No additional `asyncio.wait_for` wrapping at this layer — `run_investigation()` already enforces the 90s deadline via deadline-polling

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test URL /agentic → /investigate/agentic**
- **Found during:** Task 1 (verification run)
- **Issue:** Test stub from Plan 45-01 called `client.post("/agentic", ...)` but the router has `prefix="/investigate"`, so the route resolves to `/investigate/agentic` in any app that includes the router. Resulted in 404 instead of 200/401/422.
- **Fix:** Updated the URL in `test_agentic_sse_content_type` from `/agentic` to `/investigate/agentic`
- **Files modified:** `tests/unit/test_agentic_api.py`
- **Verification:** Both tests pass GREEN after fix
- **Committed in:** `2f3369d` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test stub URL)
**Impact on plan:** Necessary for correctness — test was genuinely wrong. No scope creep.

## Issues Encountered
None beyond the test URL bug documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `POST /api/investigate/agentic` is live and accessible via the existing authenticated API path `/api/investigate/agentic`
- Ready for Phase 45 Wave 3 frontend integration (InvestigationView agentic panel)
- No blockers

---
*Phase: 45-agentic-investigation*
*Completed: 2026-04-13*
