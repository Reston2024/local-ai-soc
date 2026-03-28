---
phase: 14
plan: 05
subsystem: investigation-copilot
tags: [chat, sse, streaming, svelte5, sqlite, foundation-sec, investigation]
dependency_graph:
  requires: [14-03, 14-04]
  provides: [chat-backend, investigation-view]
  affects: [dashboard, backend-api, sqlite-store]
tech_stack:
  added: []
  patterns:
    - SSE streaming via FastAPI StreamingResponse (reuse of query.py pattern)
    - asyncio.to_thread for SQLite chat_messages persistence
    - Svelte 5 runes ($state, $effect, $props) for two-panel workbench
    - AbortController for stop-stream client-side cancellation
key_files:
  created:
    - backend/api/chat.py
    - dashboard/src/views/InvestigationView.svelte
  modified:
    - backend/stores/sqlite_store.py
    - backend/main.py
    - dashboard/src/lib/api.ts
    - dashboard/src/App.svelte
decisions:
  - "Used try/except ImportError pattern for chat_router registration in main.py — consistent with all other deferred routers"
  - "App.svelte investigation view replaced InvestigationPanel with InvestigationView (new workbench replaces old stub panel)"
  - "asyncio.create_task for persisting assistant response — non-blocking, stream completes first"
  - "_build_investigation_context() calls merge_and_sort_timeline() directly (not via HTTP) to avoid internal round-trip"
metrics:
  duration_minutes: 12
  completed_date: "2026-03-28"
  tasks_completed: 2
  tasks_total: 3
  files_created: 2
  files_modified: 4
---

# Phase 14 Plan 05: AI Copilot Chat Backend + InvestigationView Workbench Summary

**One-liner:** Foundation-sec:8b SSE chat endpoint with SQLite persistence and two-panel Svelte 5 investigation workbench (timeline left, AI Copilot right).

## What Was Built

### Task 1: Chat Backend (TDD — RED then GREEN)

**backend/api/chat.py** — New module providing:
- `CHAT_MESSAGES_DDL`: SQLite DDL constant (also used by test contract)
- `ChatMessage` pydantic model with `investigation_id`, `role`, `content`
- `ChatRequest` model with `question` and `context_limit`
- `_build_investigation_context()`: async helper that calls `merge_and_sort_timeline()` directly from `backend.api.timeline` to build a text block of recent evidence
- `POST /api/investigations/{id}/chat`: SSE endpoint streaming foundation-sec:8b tokens; persists user question before streaming, assistant response after via `asyncio.create_task`
- `GET /api/investigations/{id}/chat/history`: returns stored messages for an investigation, oldest first

**backend/stores/sqlite_store.py** — Extended with:
- `chat_messages` DDL table appended to `_DDL` (applied on store init)
- `idx_chat_inv` index on `investigation_id`
- `insert_chat_message(investigation_id, role, content)` sync method
- `get_chat_history(investigation_id, limit=50)` sync method

**backend/main.py** — chat_router registered using deferred try/except pattern after timeline_router.

### Task 2: Frontend (InvestigationView + api.ts)

**dashboard/src/lib/api.ts** — Extended with:
- `TimelineItem`, `TimelineResponse`, `ChatHistoryMessage` TypeScript interfaces
- `api.investigations.timeline(investigationId)` — GET timeline
- `api.investigations.chatHistory(investigationId)` — GET chat history
- `api.investigations.chatStream(id, question, onToken, onDone, signal?)` — SSE streaming with AbortSignal support

**dashboard/src/views/InvestigationView.svelte** — New component (Svelte 5 runes):
- Two-column grid: Evidence Timeline (55%) + AI Copilot (45%)
- Timeline panel: severity-coloured dots (critical/high/medium/low/info), ISO timestamps, type/MITRE/tactic badges, entity labels
- Copilot panel: streaming token display with cursor blink, Send/Stop button swap, chat history loaded on mount
- `$effect()` triggers timeline + history load when `investigationId` changes

**dashboard/src/App.svelte** — Added `InvestigationView` import; replaced `InvestigationPanel` with `<InvestigationView investigationId={investigatingId} />` in investigation view slot.

## Deviations from Plan

None — plan executed exactly as written.

## Tests

All 3 `test_investigation_chat.py` tests pass (CHAT_MESSAGES_DDL contract, column names, ChatMessage instantiation). Full unit suite: 584 passed, 1 skipped, 0 failures.

## Decisions Made

1. Deferred try/except pattern for chat_router in main.py — consistent with all other routes in the codebase.
2. App.svelte investigation view replaced InvestigationPanel with InvestigationView — the new component is the production workbench.
3. `asyncio.create_task` for assistant response persistence — keeps SSE stream non-blocking.
4. `_build_investigation_context()` calls `merge_and_sort_timeline()` directly — avoids unnecessary HTTP internal round-trip.

## Self-Check: PASSED

- FOUND: backend/api/chat.py
- FOUND: backend/stores/sqlite_store.py
- FOUND: dashboard/src/views/InvestigationView.svelte
- FOUND: dashboard/src/lib/api.ts
- FOUND: commit 4886a9d (Task 1)
- FOUND: commit e6e46e7 (Task 2)
