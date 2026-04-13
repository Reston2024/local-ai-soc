---
phase: 45-agentic-investigation
plan: 03
subsystem: api
tags: [smolagents, litellm, ollama, sse, threading, async, agent, qwen3]

# Dependency graph
requires:
  - phase: 45-02
    provides: 6 smolagents Tool subclasses (QueryEventsTool, GetEntityProfileTool, EnrichIpTool, SearchSigmaMatchesTool, GetGraphNeighborsTool, SearchSimilarIncidentsTool)
provides:
  - build_agent(stores) returning ToolCallingAgent with 6 tools wired to LiteLLMModel(ollama_chat/qwen3:14b, num_ctx=8192)
  - run_investigation(agent, task) async generator yielding SSE-compatible event dicts
  - SYSTEM_PROMPT constant starting with /no_think
affects: [45-04-agentic-api, 45-05-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - threading.Thread + queue.Queue bridge for synchronous smolagents → async FastAPI SSE
    - Deadline-polling pattern for asyncio timeout without wait_for (compatible with async generator)
    - Defensive getattr access for smolagents step attributes (API varies by version)

key-files:
  created:
    - backend/services/agent/runner.py
  modified:
    - tests/unit/test_agent_runner.py

key-decisions:
  - "agent.tools dict has 7 entries (6 custom + built-in final_answer) — test updated to assert == 7"
  - "Deadline-polling used for timeout (not asyncio.wait_for) since async generators cannot be wrapped with wait_for"
  - "num_ctx=8192 passed to LiteLLMModel as kwarg — prevents silent tool-call JSON truncation at default 2048"
  - "System prompt starts with /no_think to suppress qwen3 thinking tokens mid tool-call"

patterns-established:
  - "SSE bridge pattern: threading.Thread(_run_sync) + queue.Queue + async poll loop with 0.1s drain timeout"
  - "Final answer extraction: check agent.memory.steps in reverse for FinalAnswerStep after generator exhausts"

requirements-completed: [P45-T02, P45-T05]

# Metrics
duration: 3min
completed: 2026-04-13
---

# Phase 45 Plan 03: Agent Runner Summary

**smolagents ToolCallingAgent wired to ollama_chat/qwen3:14b with threading bridge converting synchronous generator to FastAPI async SSE stream**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-13T03:32:09Z
- **Completed:** 2026-04-13T03:35:43Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Implemented `backend/services/agent/runner.py` with `build_agent()` and `run_investigation()` async generator
- `build_agent(stores)` constructs ToolCallingAgent with 6 investigation tools, max_steps=10, LiteLLMModel with num_ctx=8192
- `run_investigation()` bridges synchronous smolagents via threading.Thread + queue.Queue, yielding tool_call/reasoning/verdict/limit/done/error SSE events
- SYSTEM_PROMPT starts with `/no_think` to suppress qwen3 thinking tokens
- test_build_agent and test_max_steps_limit GREEN; 1090 unit tests passing (up from 1088)

## Task Commits

1. **Task 1: Implement runner.py — build_agent() and run_investigation() async generator** - `35a2d70` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `backend/services/agent/runner.py` - ToolCallingAgent factory + async SSE bridge (153 lines)
- `tests/unit/test_agent_runner.py` - Fixed len assertion from 6 to 7 (6 custom + final_answer)

## Decisions Made
- `agent.tools` dict includes built-in `final_answer` tool making len == 7, not 6 — test corrected
- Deadline-polling approach used for timeout enforcement (not `asyncio.wait_for`) because async generators cannot be wrapped with `wait_for` directly
- `queue.Queue.get(timeout=0.1)` in `run_in_executor` drains events without busy-waiting; `asyncio.sleep(0)` yields control on empty queue

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_agent_runner.py assertion: len(agent.tools) == 6 → 7**
- **Found during:** Task 1 (implementing runner.py and verifying tests)
- **Issue:** smolagents `_setup_tools()` always calls `self.tools.setdefault("final_answer", FinalAnswerTool())` — 6 custom tools produces a 7-entry dict. Test stub asserted `== 6` which would always fail.
- **Fix:** Updated assertion to `== 7` with explanatory comment
- **Files modified:** tests/unit/test_agent_runner.py
- **Verification:** test_build_agent passes
- **Committed in:** 35a2d70 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test stub)
**Impact on plan:** Necessary correctness fix. The 6-tool intent is preserved — the assertion now correctly reflects the actual smolagents API behavior.

## Issues Encountered
None beyond the test stub assertion fix.

## User Setup Required
None — no external service configuration required. Ollama must be running for integration tests (test_timeout_fires is SKIP until live execution).

## Next Phase Readiness
- `build_agent(stores)` and `run_investigation(agent, task)` are ready for Plan 45-04 (SSE endpoint)
- SSE event shapes (tool_call, reasoning, verdict, limit, done, error) match Plan 04 endpoint contract
- SYSTEM_PROMPT, MAX_STEPS=10, DEFAULT_TIMEOUT=90.0 constants exported from runner.py

---
*Phase: 45-agentic-investigation*
*Completed: 2026-04-13*
