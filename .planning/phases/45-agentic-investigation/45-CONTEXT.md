# Phase 45: Agentic Investigation - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the pre-built investigation summary with a genuine agentic loop — the LLM calls tools, reasons about intermediate results, decides what to query next, and produces a chain-of-reasoning verdict. Analysts see the investigation steps, not just the conclusion. Uses smolagents ToolCallingAgent with qwen3:14b via Ollama, 6 read-only tools, SSE streaming, max 10 tool calls / 90s timeout.

This phase adds an [Agent] tab to InvestigationView. The existing [Summary] tab and all existing investigation infrastructure remain unchanged.

</domain>

<decisions>
## Implementation Decisions

### Trigger & Coexistence
- InvestigationView gets a **second tab: [Summary] [Agent]**. Existing static summary (events, graph, timeline, CAR analytics, similar cases) stays on [Summary] tab — zero disruption to current workflow.
- Agent runs **on demand only** — clicking the [Agent] tab triggers the run. Opening an investigation never auto-starts the agent.
- After a run completes, the result is **cached in memory** (keyed by detection_id). Re-opening the same investigation shows the previous result without re-running.
- **Empty state** (before first run): clean panel with a `Run agentic investigation ▶` button and a one-line description ("The AI agent will query events, enrich IPs, and reason step-by-step to a verdict"). Nothing else.

### Step Rendering
- Each tool call is a **collapsible trace card**. Collapsed = tool icon + name + 1-line outcome summary (e.g. `🔍 query_events — 12 events found on WINDEV01`). Expand to see full arguments + formatted result.
- Results inside expanded cards are shown as **formatted summaries**, not raw JSON (e.g. "12 events found — 3 process_create, 7 network_connection, 2 auth_failure").
- **While the agent is running between tool calls**: the LLM's chain-of-thought reasoning streams in as text between step cards. Analysts can read the model's live reasoning as it decides what to call next. Completed cards stack above; reasoning text flows below the last card.
- Tool call budget counter visible in the Agent tab header during a run: **`3/10 calls used`** (subtle, not a progress bar).

### Final Verdict Format
- A **distinct Verdict section** is pinned at the bottom of the Agent panel — always visible once the agent completes (does not require scrolling).
- Verdict section contains:
  1. **TP/FP recommendation badge** — visually prominent (green for TP, red for FP)
  2. **Confidence percentage** (e.g. "87% confident")
  3. **2–3 sentence narrative** explaining the agent's reasoning
  4. **Confirm buttons**: `✓ Confirm TP` and `✗ Mark FP` — clicking either fires the same `submitVerdict()` flow as Phase 44 (verdict persists to SQLite, fires async ML update). The agentic verdict is a suggestion; analyst confirms or overrides.

### Failure & Timeout UX
- **90s timeout or 10-call limit hit**: all completed step cards remain visible. A yellow warning banner appears above the Verdict section: `"Agent stopped — hit [10-call limit / 90s timeout]. Partial investigation shown."` No data is discarded.
- **Ollama unavailable or model error mid-run**: the in-progress step card shows an inline error message. A `Retry ↺` button on that card restarts the agent from scratch (full re-run, not partial resume). Completed steps remain visible above.
- **Retry from error** always starts a fresh run — no partial resume. Cached result is cleared on retry.

### Claude's Discretion
- Exact SSE event format (step cards vs reasoning text vs verdict)
- smolagents tool registration syntax and LiteLLM/Ollama adapter config
- Exact icons per tool (🔍 query_events, 🌐 enrich_ip, 🕸️ get_graph_neighbors, etc.)
- Agent tab CSS layout (how reasoning text flows between cards)
- Exact LLM prompt/system message structure for verdict generation
- Whether to cache results in SQLite or memory-only (memory-only acceptable for Phase 45)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `dashboard/src/views/InvestigationView.svelte` (480 lines) — existing investigation UI; add [Agent] tab alongside [Summary] without touching existing content. SSE streaming pattern already exists via `api.investigations.chatStream()`.
- `backend/api/investigations.py` — `chatStream()` SSE pattern is the model for `POST /api/investigate/agentic` streaming. Reuse the same EventSourceResponse / async generator approach.
- `backend/api/investigate.py` — `POST /api/investigate` is the existing static endpoint. New `POST /api/investigate/agentic` is a sibling route (same router prefix `/investigate`).
- `backend/api/feedback.py` — Phase 44 `submitVerdict()` logic lives here. Verdict confirm buttons in the Agent tab call the same `POST /api/feedback` endpoint — no duplication.
- `backend/stores/duckdb_store.py`, `chroma_store.py`, `sqlite_store.py` — all stores accessible via `request.app.state.stores`; all 6 agent tools wrap these.
- `backend/services/ollama_client.py` — existing Ollama HTTP client for LLM calls; smolagents LiteLLM adapter will use same Ollama base URL from settings.

### Established Patterns
- Svelte 5 runes: `$state`, `$derived`, `$effect` — no stores
- Relative imports in Svelte (not `$lib` alias)
- `asyncio.to_thread()` for all blocking I/O in backend
- SSE streaming: `EventSourceResponse` from `sse_starlette` (used in `investigations.py`)
- `api.ts` typed client pattern — all new API calls need typed interfaces + functions in `src/lib/api.ts`
- Fire-and-forget async pattern for non-critical background work (Phase 44 ML updates)

### Integration Points
- `dashboard/src/lib/api.ts` — add `AgentStep`, `AgentReasoning`, `AgentVerdict`, `AgentRunResult` interfaces + `api.investigate.runAgentic(detection_id)` streaming method
- `backend/api/investigate.py` — add `POST /api/investigate/agentic` route to existing investigate router
- `backend/services/` — new `agent/` subdirectory: `tools.py` (6 tool definitions) + `runner.py` (smolagents ToolCallingAgent setup + run loop)
- `backend/main.py` — no new router mounting needed if agentic route is on existing investigate router

</code_context>

<specifics>
## Specific Ideas

- The [Agent] tab sits next to [Summary] — zero disruption is a hard requirement. Analysts who prefer the existing workflow should never be forced into agentic mode.
- Streaming reasoning text between tool call cards is the key differentiator — analysts should see the model "thinking" ("I found 12 events; now I'll check if any IPs are known malicious..."). This makes the investigation legible, not a black box.
- The Verdict section's confirm buttons directly tie into the Phase 44 feedback loop — agent-recommended verdicts that get analyst confirmation become training samples immediately.
- The `3/10 calls used` counter makes the resource budget legible without being alarming. Analysts working with AI need to understand there's a cap.

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope.

</deferred>

---

*Phase: 45-agentic-investigation*
*Context gathered: 2026-04-12*
