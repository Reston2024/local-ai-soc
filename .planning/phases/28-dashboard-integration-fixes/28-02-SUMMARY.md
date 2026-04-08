---
phase: 28-dashboard-integration-fixes
plan: "02"
subsystem: dashboard
tags: [api, sse, events, typescript, svelte, bug-fix]
dependency_graph:
  requires: []
  provides: [INT-01-fixed, INT-02-fixed]
  affects: [dashboard/src/lib/api.ts, dashboard/src/views/EventsView.svelte]
tech_stack:
  added: []
  patterns: [SSE-stream-via-fetch, typed-response-generics]
key_files:
  modified:
    - dashboard/src/lib/api.ts
    - dashboard/src/views/EventsView.svelte
decisions:
  - "SSE field names msg.token and msg.done already matched backend format — no SSE loop rewrite needed"
  - "Pre-existing svelte-check errors in GraphView/InvestigationPanel/ProvenanceView are out of scope (10 pre-existing errors remain)"
metrics:
  duration: "~8 minutes"
  completed: "2026-04-07"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 2
requirements:
  - P28-T01
  - P28-T02
---

# Phase 28 Plan 02: Dashboard Integration Fixes (INT-01 & INT-02) Summary

**One-liner:** Fixed SSE URL (`/api/query/ask` -> `/api/query/ask/stream`) and event search response mapping (`res.results.map(r => r.event)` -> `res.events`) to restore RAG Q&A and event search flows.

## What Was Built

Two targeted fixes to restore the two primary dashboard user flows that were broken due to API contract mismatches:

**INT-01 (Task 1):** `api.query.ask()` was POSTing to `/api/query/ask` (a JSON endpoint) but attempting to read the response as an SSE stream. The SSE streaming endpoint is `/api/query/ask/stream`. Fixed by changing the fetch URL on line 404 of `api.ts`. The existing SSE parsing loop correctly reads `msg.token` and `msg.done` — matching the backend's emission format — so no loop changes were needed.

**INT-02 (Task 2):** `EventsView.svelte` called `res.results.map(r => r.event)` but the backend `/api/events/search` returns `{ events: [...], total: N, query: "..." }`. Fixed by: (1) updating the `events.search()` return type generic in `api.ts` from `{ results: Array<{ event: NormalizedEvent; score: number }> }` to `{ events: NormalizedEvent[]; total: number; query: string }`, and (2) updating `EventsView.svelte` line 33 to read `res.events` directly.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix SSE URL in api.ts (INT-01) | d25fd0a | dashboard/src/lib/api.ts |
| 2 | Fix event search return type and EventsView mapping (INT-02) | dd591f0 | dashboard/src/lib/api.ts, dashboard/src/views/EventsView.svelte |

## Verification

- `grep -n "query/ask/stream" dashboard/src/lib/api.ts` → 1 match on line 404
- `grep -n "res\.events" dashboard/src/views/EventsView.svelte` → 2 matches (lines 18, 33)
- `grep -n "res\.results" dashboard/src/views/EventsView.svelte` → 0 matches
- `svelte-check` → 0 errors in `api.ts` and `EventsView.svelte`; 10 pre-existing errors in unrelated files (GraphView, InvestigationPanel, ProvenanceView) are out of scope

## Deviations from Plan

None — plan executed exactly as written. SSE field names (`msg.token`, `msg.done`) already matched the backend streaming format, so no SSE loop field name updates were required.

## Self-Check: PASSED

- [x] `dashboard/src/lib/api.ts` — modified, contains `/api/query/ask/stream` and `events: NormalizedEvent[]`
- [x] `dashboard/src/views/EventsView.svelte` — modified, contains `res.events`, no `res.results`
- [x] Commit d25fd0a — exists (Task 1)
- [x] Commit dd591f0 — exists (Task 2)
