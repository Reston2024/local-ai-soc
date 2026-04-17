---
phase: 45-agentic-investigation
verified: 2026-04-12T00:00:00Z
status: human_needed
score: 15/15 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 14/15
  gaps_closed:
    - "System prompt starts with /no_think — prompt_templates now loaded from smolagents defaults and system_prompt key overridden before passing to ToolCallingAgent"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Verify [Agent] tab renders and streams tool cards correctly"
    expected: "Summary and Agent tabs visible; clicking Agent starts investigation; trace cards appear per tool call; reasoning text streams; verdict section appears at completion"
    why_human: "SSE streaming, animation, card expand/collapse, and verdict display are visual/interactive behaviors that require a running Ollama + live frontend"
  - test: "Verify /no_think suppression works at runtime"
    expected: "qwen3:14b does not emit <think>...</think> tokens in its tool-call responses; agent follows the 6-step investigation strategy; verdict JSON is well-formed"
    why_human: "Requires live Ollama execution with qwen3:14b model and live event data"
---

# Phase 45: Agentic Investigation Verification Report

**Phase Goal:** Replace the pre-built investigation summary with a genuine agentic loop — the LLM calls tools, reasons about intermediate results, decides what to query next, and produces a chain-of-reasoning verdict. Analysts see the investigation steps, not just the conclusion. Uses smolagents with 6 tools wrapping existing DuckDB/Chroma/IOC endpoints. qwen3:14b via Ollama handles tool-calling reliably at this scope.
**Verified:** 2026-04-12
**Status:** human_needed (all automated checks pass; 2 items require live Ollama + frontend)
**Re-verification:** Yes — gap closed after initial gaps_found (14/15)

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | smolagents[litellm] is installed and importable | VERIFIED | pyproject.toml `smolagents[litellm]>=1.24.0`; imports in runner.py succeed |
| 2  | 6 Tool subclasses exist and are importable | VERIFIED | tools.py (429 lines): QueryEventsTool, GetEntityProfileTool, EnrichIpTool, SearchSigmaMatchesTool, GetGraphNeighborsTool, SearchSimilarIncidentsTool |
| 3  | Each tool's forward() is synchronous and returns a descriptive string | VERIFIED | All 6 `def forward()` non-async; all return strings |
| 4  | build_agent(stores) returns ToolCallingAgent with 6 tools + max_steps=10 | VERIFIED | runner.py: ToolCallingAgent with MAX_STEPS=10, 6 custom tools |
| 5  | run_investigation() is an async generator yielding SSE event dicts | VERIFIED | runner.py: `async def run_investigation(...)` yields tool_call, reasoning, verdict, limit, done, error |
| 6  | Agent respects max_steps=10 and 90s asyncio timeout | VERIFIED | MAX_STEPS enforced; deadline loop yields `limit/timeout` at 90s |
| 7  | System prompt starts with /no_think to suppress thinking tokens | VERIFIED | runner.py line 47: SYSTEM_PROMPT = `"""/no_think...`; lines 109-114 load smolagents default templates, override `system_prompt` key, pass full dict via `prompt_templates=_default_templates` to ToolCallingAgent |
| 8  | num_ctx=8192 passed to LiteLLMModel | VERIFIED | runner.py line 95: `num_ctx=8192` |
| 9  | POST /api/investigate/agentic returns text/event-stream with SSE events | VERIFIED | investigate.py line 356: `@router.post("/agentic")` returns `EventSourceResponse` |
| 10 | Endpoint accepts {detection_id: str} JSON body | VERIFIED | AgenticInvestigateRequest Pydantic model; route wired |
| 11 | Agent is built from request.app.state.stores on each request | VERIFIED | investigate.py line 376: `stores = request.app.state.stores` |
| 12 | test_agent_tools.py — 7 tests GREEN | VERIFIED | 7 PASSED |
| 13 | test_agent_runner.py — build_agent and max_steps GREEN | VERIFIED | test_build_agent PASSED, test_max_steps_limit PASSED, test_timeout_fires SKIPPED (expected) |
| 14 | test_agentic_api.py — 2 tests GREEN | VERIFIED | test_agentic_endpoint_exists PASSED, test_agentic_sse_content_type PASSED |
| 15 | InvestigationView has [Agent] tab, streaming trace cards, verdict section, confirm buttons | VERIFIED | activeTab $state at line 23; tabs at lines 359-360; verdict-section at line 514; btn-confirm-tp/btn-mark-fp at lines 523-524; runAgentic() call at line 186 |

**Score:** 15/15 truths verified

### Unit Test Suite

**Result: 1092 passed, 4 skipped, 9 xfailed, 7 xpassed in 32.11s** — no regressions introduced by the gap fix.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/services/agent/__init__.py` | Package init | VERIFIED | Exists |
| `backend/services/agent/tools.py` | 6 Tool subclasses, min 200 lines | VERIFIED | 429 lines, all 6 classes |
| `backend/services/agent/runner.py` | build_agent + run_investigation + SYSTEM_PROMPT injected, min 120 lines | VERIFIED | 274 lines; SYSTEM_PROMPT at line 47 starts with `/no_think`; injected via `prompt_templates` at line 120 |
| `backend/api/investigate.py` | POST /agentic route | VERIFIED | Line 356, full SSE generator |
| `dashboard/src/lib/api.ts` | AgentStep/Reasoning/Verdict/Limit/RunResult + runAgentic() | VERIFIED | All 5 interfaces + runAgentic() present |
| `dashboard/src/views/InvestigationView.svelte` | [Summary][Agent] tabs, streaming trace, verdict section | VERIFIED | Full implementation present |
| `tests/unit/test_agent_tools.py` | 6 tool tests, min 80 lines | VERIFIED | 105 lines, 7 tests |
| `tests/unit/test_agent_runner.py` | 3 tests, min 50 lines | VERIFIED | 56 lines, 3 tests |
| `tests/unit/test_agentic_api.py` | 2 tests, min 40 lines | VERIFIED | 42 lines, 2 tests |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| backend/services/agent/tools.py | DuckDB store | `duckdb.connect(db_path, read_only=True)` | VERIFIED | Used in QueryEventsTool, GetEntityProfileTool |
| backend/services/agent/tools.py | SQLite store | `_sqlite_read(sqlite_path)` context manager | VERIFIED | Used in EnrichIpTool, SearchSigmaMatchesTool, GetGraphNeighborsTool |
| backend/services/agent/tools.py | Chroma store | `chromadb.PersistentClient(path=chroma_path)` | VERIFIED | Used in SearchSimilarIncidentsTool |
| backend/services/agent/runner.py | tools.py | instantiates all 6 Tool classes | VERIFIED | Lines 98-105 |
| backend/services/agent/runner.py | smolagents.ToolCallingAgent | LiteLLMModel + prompt_templates | VERIFIED | Lines 91-121; prompt_templates carries /no_think system_prompt |
| backend/api/investigate.py | backend/services/agent/runner.py | imports build_agent, run_investigation | VERIFIED | Line 382 |
| dashboard/src/views/InvestigationView.svelte | dashboard/src/lib/api.ts | api.investigations.runAgentic() | VERIFIED | Line 186 |
| dashboard/src/lib/api.ts | POST /api/investigate/agentic | fetch SSE reader | VERIFIED | api.ts fetch call to `/api/investigate/agentic` |
| dashboard/src/views/InvestigationView.svelte | api.feedback.submit() | confirmVerdict() | VERIFIED | Line 234 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| P45-T01 | 45-01, 45-02 | 6 Tool subclasses wrapping DuckDB/SQLite/Chroma | SATISFIED | tools.py with 6 Tool subclasses; all tests GREEN |
| P45-T02 | 45-01, 45-03 | build_agent + run_investigation async generator | SATISFIED | runner.py both functions verified; tests GREEN |
| P45-T03 | 45-01, 45-04 | POST /api/investigate/agentic SSE endpoint | SATISFIED | investigate.py /agentic route verified; tests GREEN |
| P45-T04 | 45-05 | [Agent] tab UI with streaming trace cards and verdict | SATISFIED | InvestigationView.svelte full implementation |
| P45-T05 | 45-01, 45-03, 45-04, 45-05 | End-to-end: agent runs with /no_think, analyst sees steps, confirms verdict | SATISFIED | All components wired; system_prompt now injected with /no_think via prompt_templates |

### Anti-Patterns Found

None. The SYSTEM_PROMPT unused-constant anti-pattern from initial verification is resolved.

### Human Verification Required

#### 1. Agent Tab Streaming UI

**Test:** Navigate to a detection in the dashboard, click [Agent] tab, click "Run agentic investigation"
**Expected:** Call counter appears, trace cards populate per tool call with expand/collapse, reasoning text shown between cards, Verdict section appears on completion with TP/FP badge + confidence + narrative + Confirm buttons
**Why human:** SSE streaming, animation, interactive expand/collapse, and visual layout cannot be verified programmatically

#### 2. /no_think Suppression at Runtime

**Test:** After injecting SYSTEM_PROMPT via prompt_templates, run an investigation against a detection with live Ollama qwen3:14b
**Expected:** Agent reasoning does not include `<think>...</think>` blocks; agent follows the 6-step investigation strategy in the system prompt; verdict JSON is well-formed
**Why human:** Requires live Ollama + live event data; model behavior can only be assessed at runtime

### Re-verification Summary

The sole gap from initial verification is closed:

- **Gap was:** `SYSTEM_PROMPT` defined at runner.py:47 but never passed to `ToolCallingAgent` — agent ran with no `/no_think` directive and no investigation guidance.
- **Fix applied:** Lines 109-120 now load the full smolagents default `toolcalling_agent.yaml` template (satisfying the 4-key requirement: `system_prompt`, `planning`, `managed_agent`, `final_answer`), override only the `system_prompt` key with `SYSTEM_PROMPT` (which starts with `/no_think`), and pass the merged dict via `prompt_templates=_default_templates`.
- **No regressions:** 1092 unit tests pass, same count as before the fix.

---

_Verified: 2026-04-12_
_Verifier: Claude (gsd-verifier)_
