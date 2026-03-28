---
phase: 14-llmops-evaluation-investigation-ai-copilot
verified: 2026-03-28T00:00:00Z
status: passed
score: 19/19 automated must-haves verified
re_verification: false
human_verification:
  - test: "Navigate to InvestigationView in the browser and verify the two-panel layout renders"
    expected: "Left panel shows Evidence Timeline header and either timeline rows or 'No events found' message; right panel shows AI Copilot header with textarea and Send button"
    why_human: "Svelte component rendering, CSS grid layout, and panel visibility cannot be verified without a running browser"
  - test: "Type a question in the AI Copilot textarea and click Send"
    expected: "Tokens appear progressively in the chat panel (streaming, not all at once); blinking cursor visible during stream"
    why_human: "SSE streaming behaviour, progressive token render, and abort-controller interaction require live browser + running backend"
  - test: "Click the Stop button mid-stream"
    expected: "Stream halts immediately; isStreaming returns to false; partial response stays visible"
    why_human: "AbortController mid-stream cancellation cannot be verified statically"
  - test: "Reload the page and navigate back to the same investigation"
    expected: "Previous chat messages restored from GET /api/investigations/{id}/chat/history"
    why_human: "End-to-end SQLite persistence round-trip requires live services"
  - test: "Run uv run python scripts/eval_models.py --dry-run --limit 5 while the backend is running"
    expected: "No DuckDB lock error; prints markdown table with 4 rows (2 models x 2 prompt types); creates data/eval_results.jsonl with 20 entries"
    why_human: "Requires running backend holding DuckDB write lock to exercise the lock-bypass code path"
---

# Phase 14: LLMOps Evaluation, Investigation Timeline, and AI Copilot — Verification Report

**Phase Goal:** Implement LLMOps evaluation harness (foundation-sec:8b vs qwen3:14b), LLMOps telemetry layer (DuckDB llm_calls table + metrics KPI fields), investigation timeline API, and AI Copilot chat SSE endpoint with InvestigationView two-panel workbench in Svelte 5.
**Verified:** 2026-03-28
**Status:** human_needed — all automated checks pass; 5 items require live browser/service verification
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | EvalResult dataclass and score_response() exist in scripts/eval_models.py | VERIFIED | File is 368 lines; dataclass at line 47, function at line 64; all 8 unit tests pass |
| 2 | Eval harness runs TWO prompt types (triage + summarise) per row against both models | VERIFIED | `_PROMPT_TEMPLATES` dict with both keys; dual loop over models and prompt_types in main(); `prompt_type` field on EvalResult |
| 3 | --dry-run mode bypasses DuckDB entirely to avoid write-lock conflict | VERIFIED | Plan 06 gap closure applied; `if args.dry_run:` branch at line 273 generates `_DRY_RUN_ROW` tuples, no DuckDBStore init |
| 4 | llm_calls DDL exists in duckdb_store.py and initialise_schema() creates it | VERIFIED | `_CREATE_LLM_CALLS_TABLE` at line 72; `_CREATE_LLM_CALLS_INDEXES` at line 86; both executed in `initialise_schema()` at lines 141-142 |
| 5 | OllamaClient accepts optional duckdb_store and records every generate() and stream_generate() call | VERIFIED | `duckdb_store: Optional[DuckDBStore] = None` in `__init__`; `_write_telemetry()` called after generate(), stream_generate() success and in error paths |
| 6 | stream_generate_iter() accepts use_cybersec_model parameter | VERIFIED | Parameter present at line 551; `_effective_model` computed at line 561 |
| 7 | OllamaClient is wired with duckdb_store in main.py lifespan | VERIFIED | `duckdb_store=duckdb_store` at line 132 and 149 in main.py |
| 8 | GET /api/metrics/kpis returns avg_latency_ms_per_model, total_llm_calls, error_rate | VERIFIED | KpiSnapshot fields at lines 49-51 of metrics_service.py; `_compute_llm_kpis()` fetches from llm_calls table and populates all three fields |
| 9 | backend/api/timeline.py exports TimelineItem, merge_and_sort_timeline, router | VERIFIED | TimelineItem Pydantic model at line 34; merge_and_sort_timeline() function with 4-param signature (edge_rows/playbook_rows have None defaults); router registered in main.py at line 339 |
| 10 | GET /api/investigations/{id}/timeline fetches from DuckDB events + SQLite detections + SQLite graph edges | VERIFIED | `stores.duckdb.fetch_all(... FROM normalized_events WHERE case_id = ?)` at line 228; `asyncio.to_thread(stores.sqlite.get_detections_by_case, ...)` at line 239; `asyncio.to_thread(_get_edge_rows_sync, ...)` at line 247 |
| 11 | Timeline returns HTTP 200 with empty items list for unknown investigation_id (not 404) | VERIFIED | Endpoint returns `JSONResponse({"items": [...], "total": ...})` unconditionally; no 404 raise |
| 12 | playbook_rows always empty in Phase 14 with deferred comment | VERIFIED | `playbook_rows: list[dict] = []` at line 253 with comment "deferred to future phase" |
| 13 | backend/api/chat.py exports CHAT_MESSAGES_DDL, ChatMessage, router | VERIFIED | CHAT_MESSAGES_DDL constant at line 31; ChatMessage Pydantic model; router registered in main.py at line 346 |
| 14 | POST /api/investigations/{id}/chat streams SSE using stream_generate_iter with use_cybersec_model=True | VERIFIED | `ollama.stream_generate_iter(prompt, system=_COPILOT_SYSTEM, use_cybersec_model=True)` at line 156-158; StreamingResponse with `text/event-stream` |
| 15 | Chat exchanges persisted to SQLite chat_messages via insert_chat_message | VERIFIED | `asyncio.to_thread(stores.sqlite.insert_chat_message, ...)` at lines 149-153 (user) and 164-168 (assistant); sqlite_store.py has DDL at line 135, insert at line 725, get_chat_history at line 741 |
| 16 | InvestigationView.svelte has two panels (timeline left, copilot right) with correct Svelte 5 runes | VERIFIED | File is 235 lines; `.investigation-view` grid at 55%/45%; `timeline-panel` and `copilot-panel` divs; `$state()`, `$derived`, `$effect()` runes; no writable()/svelte:store |
| 17 | InvestigationView calls api.investigations.timeline(), chatStream(), chatHistory() | VERIFIED | All three calls found: line 30, 41, 55 of InvestigationView.svelte |
| 18 | api.ts has typed investigations namespace with timeline(), chatStream(), chatHistory() | VERIFIED | `chatStream:` found at line 252; TimelineResponse and ChatHistoryMessage interfaces defined |
| 19 | App.svelte wires investigatingId prop to InvestigationView as investigationId | VERIFIED | `<InvestigationView investigationId={investigatingId} />` at line 217; `investigatingId = $state<string>('')` at line 24 |

**Score:** 19/19 automated truths verified

---

### Required Artifacts

| Artifact | Min Lines | Actual Lines | Status | Key Exports |
|----------|-----------|--------------|--------|-------------|
| `scripts/eval_models.py` | 120 | 368 | VERIFIED | EvalResult, score_response, main |
| `scripts/__init__.py` | — | exists | VERIFIED | Enables test imports |
| `backend/stores/duckdb_store.py` | — | exists | VERIFIED | llm_calls DDL in initialise_schema |
| `backend/services/ollama_client.py` | — | exists | VERIFIED | _write_telemetry, duckdb_store param, use_cybersec_model |
| `backend/api/metrics.py` + `metrics_service.py` | — | exists | VERIFIED | avg_latency_ms_per_model, total_llm_calls, error_rate |
| `backend/api/timeline.py` | 100 | 259 | VERIFIED | router, TimelineItem, merge_and_sort_timeline |
| `backend/api/chat.py` | 100 | 190 | VERIFIED | router, ChatMessage, CHAT_MESSAGES_DDL |
| `backend/stores/sqlite_store.py` | — | exists | VERIFIED | chat_messages DDL, insert_chat_message, get_chat_history |
| `dashboard/src/views/InvestigationView.svelte` | 150 | 235 | VERIFIED | Two-panel layout, Svelte 5 runes |
| `dashboard/src/lib/api.ts` | — | exists | VERIFIED | investigations.timeline, chatStream, chatHistory |
| `tests/unit/test_eval_models.py` | 30 | exists | VERIFIED | 8 tests, all pass |
| `tests/unit/test_investigation_timeline.py` | 30 | exists | VERIFIED | 3 tests, all pass |
| `tests/unit/test_investigation_chat.py` | 30 | exists | VERIFIED | 3 tests, all pass |

---

### Key Link Verification

| From | To | Via | Status | Evidence |
|------|----|-----|--------|----------|
| `scripts/eval_models.py` | `backend/stores/duckdb_store.py` | `fetch_all()` on normalized_events | WIRED | `DuckDBStore(settings.DATA_DIR)` + `fetch_all(sql, [args.limit])` in non-dry-run path |
| `backend/services/ollama_client.py` | `backend/stores/duckdb_store.py` | `execute_write()` into llm_calls | WIRED | `INSERT OR IGNORE INTO llm_calls` in `_write_telemetry()`; called after every generate/stream |
| `backend/api/metrics.py` | `backend/services/metrics_service.py` | KpiSnapshot fields and _compute_llm_kpis() | WIRED | `from backend.services.metrics_service import KpiSnapshot, MetricsService`; llm_calls aggregates in KpiSnapshot |
| `backend/api/timeline.py` | `backend/stores/duckdb_store.py` | `fetch_all()` normalized_events WHERE case_id | WIRED | `stores.duckdb.fetch_all(... FROM normalized_events WHERE case_id = ?)` |
| `backend/api/timeline.py` | `backend/stores/sqlite_store.py` | `asyncio.to_thread(get_detections_by_case)` | WIRED | `asyncio.to_thread(stores.sqlite.get_detections_by_case, investigation_id)` |
| `backend/api/timeline.py` | `backend/stores/sqlite_store.py` | `asyncio.to_thread(_get_edge_rows_sync)` for graph edges | WIRED | `asyncio.to_thread(_get_edge_rows_sync, stores.sqlite, entity_names)` |
| `backend/main.py` | `backend/api/timeline.py` | `timeline_router` include_router | WIRED | `from backend.api.timeline import router as timeline_router`; `app.include_router(timeline_router, ...)` |
| `backend/api/chat.py` | `backend/services/ollama_client.py` | `stream_generate_iter(..., use_cybersec_model=True)` | WIRED | `ollama.stream_generate_iter(prompt, system=_COPILOT_SYSTEM, use_cybersec_model=True)` |
| `backend/api/chat.py` | `backend/stores/sqlite_store.py` | `asyncio.to_thread(insert_chat_message)` | WIRED | `asyncio.to_thread(stores.sqlite.insert_chat_message, ...)` for both user and assistant turns |
| `backend/main.py` | `backend/api/chat.py` | `chat_router` include_router | WIRED | `from backend.api.chat import router as chat_router`; `app.include_router(chat_router, ...)` |
| `dashboard/src/views/InvestigationView.svelte` | `dashboard/src/lib/api.ts` | `api.investigations.timeline()` + `chatStream()` on mount/send | WIRED | Lines 30, 41, 55 in InvestigationView.svelte |
| `dashboard/src/App.svelte` | `dashboard/src/views/InvestigationView.svelte` | `investigationId={investigatingId}` prop | WIRED | `<InvestigationView investigationId={investigatingId} />` at line 217 |

---

### Requirements Coverage

REQUIREMENTS.md contains no P14 entries (no formal requirement IDs in the file). Requirements P14-T01 through P14-T04 are plan-internal identifiers only. Coverage is assessed from plan must_haves:

| Plan Requirement | Description | Status |
|-----------------|-------------|--------|
| P14-T01 | LLMOps evaluation harness: eval_models.py with EvalResult, score_response, dual-prompt main | SATISFIED — scripts/eval_models.py 368 lines; gap-closure Plan 06 applied for dry-run DuckDB bypass |
| P14-T02 | LLMOps telemetry: llm_calls DDL, OllamaClient telemetry hook, KPI extension | SATISFIED — all three components verified wired |
| P14-T03 | Investigation timeline API: GET endpoint, TimelineItem, merge_and_sort_timeline | SATISFIED — backend/api/timeline.py 259 lines, all 3 unit tests pass |
| P14-T04 | AI Copilot SSE endpoint + InvestigationView two-panel workbench | SATISFIED (automated) — chat.py, sqlite_store methods, InvestigationView.svelte all verified; streaming/stop/persistence require human check |

---

### Anti-Patterns Found

No blockers found. The following were reviewed and are legitimate:

| File | Pattern | Classification | Notes |
|------|---------|----------------|-------|
| `scripts/eval_models.py` | "placeholder" in comments | INFO | Describes dry-run placeholder rows — intentional behaviour |
| `backend/api/timeline.py` | `placeholders` variable | INFO | SQL parameterization helper — not a stub |
| `dashboard/src/views/InvestigationView.svelte` | `placeholder=` attribute | INFO | HTML textarea placeholder text — not a stub |
| `backend/api/timeline.py` | playbook_rows always `[]` | INFO | Explicitly deferred by design; comment in code notes future-phase implementation |

---

### Human Verification Required

#### 1. Two-Panel Layout Renders

**Test:** Start backend + `npm run dev`, navigate to InvestigationView
**Expected:** Left panel "Evidence Timeline" and right panel "AI Copilot" visible side by side in a 55%/45% grid
**Why human:** CSS grid rendering and component mount cannot be verified statically

#### 2. AI Copilot Streams Tokens Progressively

**Test:** Type "What is the most suspicious event here?" in the copilot textarea and click Send (backend must be running with Ollama)
**Expected:** Individual tokens appear one at a time with blinking cursor; not a single full response dump
**Why human:** SSE streaming token-by-token behaviour requires live browser + running Ollama

#### 3. Stop Button Halts Stream

**Test:** Start a stream and click Stop mid-stream
**Expected:** Stream halts; partial response stays visible; Send button returns
**Why human:** AbortController mid-stream abort requires live browser interaction

#### 4. Chat History Persists Across Page Reload

**Test:** Send a message, reload the page, navigate back to same investigation
**Expected:** Previous messages reload from GET /api/investigations/{id}/chat/history
**Why human:** End-to-end SQLite persistence round-trip requires live services

#### 5. Eval Harness Dry-Run With Backend Running

**Test:** Start backend, then run `uv run python scripts/eval_models.py --dry-run --limit 5` in a second terminal
**Expected:** No DuckDB lock IOException; table with 4 rows printed; data/eval_results.jsonl created with 20 entries
**Why human:** Requires the specific race condition of a running backend holding the DuckDB write lock

---

### Test Suite Result

```
586 passed, 1 skipped, 16 xpassed, 6 warnings in 11.20s
```

All 16 phase-14 specific unit tests pass (test_eval_models.py: 8, test_investigation_timeline.py: 3, test_investigation_chat.py: 3, test_timeline_builder.py: 2). No regressions in the broader suite.

---

_Verified: 2026-03-28_
_Verifier: Claude (gsd-verifier)_
