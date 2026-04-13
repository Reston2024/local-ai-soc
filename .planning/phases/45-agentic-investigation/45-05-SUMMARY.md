---
phase: 45-agentic-investigation
plan: 05
subsystem: ui
tags: [svelte5, typescript, sse, streaming, agentic, investigation]

# Dependency graph
requires:
  - phase: 45-04
    provides: POST /api/investigate/agentic SSE endpoint with tool_call/reasoning/verdict/limit/done events
  - phase: 44-analyst-feedback
    provides: api.feedback.submit() for verdict confirmation buttons

provides:
  - AgentStep, AgentReasoning, AgentVerdict, AgentLimit, AgentRunResult TypeScript interfaces in api.ts
  - api.investigations.runAgentic() SSE streaming client
  - [Summary][Agent] tabs on InvestigationView copilot panel
  - Collapsible trace cards per tool call with expand/collapse
  - Streaming reasoning text between cards (live italic text with indigo border)
  - X/10 calls counter during run, yellow limit/timeout warning banner
  - Error card with Retry button (clears cache, full re-run)
  - Verdict section: TP/FP badge + confidence % + narrative + Confirm buttons
  - Module-level agentCache Map keyed by detection_id (persists across mounts)

affects: [45-agentic-investigation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - SSE dispatch-by-shape: each event type has a unique key (call_number=tool_call, text=reasoning, verdict=verdict, reason=limit, message=error)
    - Module-level Svelte cache: Map declared in <script module> persists across component re-mounts
    - Tab pattern: activeTab $state rune with {#if}/{:else} — existing content zero-disruption

key-files:
  created: []
  modified:
    - dashboard/src/lib/api.ts
    - dashboard/src/views/InvestigationView.svelte

key-decisions:
  - "45-05: api.investigations.runAgentic() added to investigations group (not investigate) to avoid conflict with existing api.investigate() function"
  - "45-05: agentCache declared in <script module lang='ts'> for cross-mount persistence — import uses _AgentRunResult alias to avoid naming collision"
  - "45-05: verdict-badge-agent class used for agent tab verdict badge to avoid CSS collision with existing verdict-badge used in Similar Cases section"
  - "45-05: Agent tab auto-starts on first click if no cached result; subsequent clicks show cache immediately"

patterns-established:
  - "SSE dispatch-by-shape pattern: parse JSON from data: lines, dispatch to callback by checking for unique keys in parsed object"
  - "Module-level cache in Svelte 5: use <script module lang='ts'> block for state shared across component instances"

requirements-completed: [P45-T04, P45-T05]

# Metrics
duration: 25min
completed: 2026-04-13
---

# Phase 45 Plan 05: Agentic Investigation UI Summary

**[Summary][Agent] tab UI with SSE streaming trace cards, reasoning text, call counter, and TP/FP verdict section wired to Phase 44 feedback loop**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-04-13T04:10:00Z
- **Completed:** 2026-04-13T04:35:00Z
- **Tasks:** 2 auto + 1 checkpoint (auto-approved, auto_advance=true)
- **Files modified:** 2

## Accomplishments
- 5 Phase 45 TypeScript interfaces added to api.ts (AgentStep, AgentReasoning, AgentVerdict, AgentLimit, AgentRunResult)
- api.investigations.runAgentic() SSE streaming client added — buffers incomplete lines, dispatches by data shape
- InvestigationView gets [Summary][Agent] tabs — existing AI Copilot content 100% unchanged in summary tab
- Agent panel: empty state, trace cards with collapsible details (arguments JSON + result), live reasoning text, call counter, limit banner, error+retry, pinned verdict with Confirm buttons

## Task Commits

1. **Task 1: Add AgentStep/AgentVerdict interfaces + investigations.runAgentic()** - `120dc1f` (feat)
2. **Task 2: Add [Agent] tab to InvestigationView.svelte** - `f96c0bf` (feat)

## Files Created/Modified
- `dashboard/src/lib/api.ts` - 5 Phase 45 interfaces + api.investigations.runAgentic() SSE client (88 lines added)
- `dashboard/src/views/InvestigationView.svelte` - [Summary][Agent] tabs, Agent panel with all UX states, 283 lines added (zero disruption to Summary tab)

## Decisions Made
- **api.investigations.runAgentic vs api.investigate.runAgentic**: Plan specified `api.investigate.runAgentic()` but `api.investigate` is already a standalone function (calls `POST /api/investigate`). Converting it to a group would break 2 existing callers (InvestigationView.svelte, InvestigationPanel.svelte). Added `runAgentic` to the existing `investigations` group instead — fully functional, no breakage, TypeScript clean.
- **verdict-badge-agent CSS class**: Phase 44 already has `.verdict-badge` for Similar Cases badges. Used `.verdict-badge-agent` for the Agent tab's verdict badge to avoid cascade conflicts.
- **Module-level cache via `<script module>`**: Svelte 5's `<script module lang="ts">` block provides module scope. Used `_AgentRunResult` import alias to avoid TypeScript name collision with the instance-scope import.
- **Auto-start behavior**: Clicking [Agent] tab starts agent automatically if no cached result exists and nothing is running — matches CONTEXT.md design ("clicking the [Agent] tab triggers the run").

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Used `investigations` group instead of `investigate` group for runAgentic**
- **Found during:** Task 1 (api.ts modification)
- **Issue:** Plan specified `api.investigate.runAgentic()` but `api.investigate` is a bare function, not a group. Adding `.runAgentic` as a property would require TypeScript declaration merging or function-as-object hacks.
- **Fix:** Added `runAgentic` to the existing `api.investigations` group. Updated InvestigationView call to `api.investigations.runAgentic()`.
- **Files modified:** dashboard/src/lib/api.ts, dashboard/src/views/InvestigationView.svelte
- **Verification:** TypeScript 0 errors, no existing callers broken
- **Committed in:** 120dc1f (Task 1), f96c0bf (Task 2)

**2. [Rule 1 - Bug] Fixed deprecated `context="module"` syntax**
- **Found during:** Task 2 (svelte-check run)
- **Issue:** `<script context="module">` is deprecated in Svelte 5; warns on compile.
- **Fix:** Changed to `<script module lang="ts">` per Svelte 5 spec.
- **Files modified:** dashboard/src/views/InvestigationView.svelte
- **Verification:** svelte-check no longer reports InvestigationView deprecation warning
- **Committed in:** f96c0bf (Task 2)

---

**Total deviations:** 2 auto-fixed (1 structural adaptation, 1 Svelte 5 deprecation fix)
**Impact on plan:** Both necessary for correct TypeScript and Svelte 5 compatibility. No scope creep.

## Issues Encountered
None — plan executed cleanly. All pre-existing svelte-check errors (GraphView cytoscape types, ProvenanceView type cast) are unrelated to Phase 45 scope.

## User Setup Required
None — frontend-only changes, no new environment variables or external services.

## Next Phase Readiness
Phase 45 agentic investigation is fully wired end-to-end:
- Backend: smolagents tools (Plan 02), runner + SSE bridge (Plan 03), FastAPI SSE endpoint (Plan 04)
- Frontend: api.ts client + InvestigationView [Agent] tab (Plan 05)
- Manual verification checkpoint: open http://localhost:5173, navigate to a detection, click [Agent] tab

---
*Phase: 45-agentic-investigation*
*Completed: 2026-04-13*
