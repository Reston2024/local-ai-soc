---
phase: 28-dashboard-integration-fixes
verified: 2026-04-07T00:00:00Z
status: human_needed
score: 6/6 must-haves verified
re_verification: false
human_verification:
  - test: "Settings view renders in browser"
    expected: "Clicking 'Settings' in the nav bar renders the SettingsView — operator management, key rotation, TOTP, and model-status sections should be visible"
    why_human: "App.svelte routing and SettingsView wiring is verified statically, but whether SettingsView.svelte itself renders without runtime errors (API calls, missing data, Svelte 5 rune issues) requires a browser run"
  - test: "RAG query returns streamed tokens, not empty"
    expected: "Typing a question in QueryView and clicking Ask streams tokens back and shows a non-empty answer"
    why_human: "api.ts now calls /api/query/ask/stream and reads msg.token; cannot verify actual SSE stream behavior without a live backend"
  - test: "Event search populates table from res.events"
    expected: "Typing a search term in EventsView and pressing Enter populates the events table with results (not a crash)"
    why_human: "EventsView.svelte now reads res.events correctly, but end-to-end behavior depends on live Chroma embeddings"
  - test: "Ingest progress bar updates beyond 0%"
    expected: "After uploading a file, the IngestView progress bar shows events_processed / events_total advancing above 0%"
    why_human: "The /api/ingest/status/{id} route exists and maps loaded/parsed correctly, but background job timing and polling behavior require a browser test"
  - test: "Event pagination advances past page 1"
    expected: "Clicking 'Next' in EventsView loads the next page of events (not the same first page)"
    why_human: "api.events.list() now translates offset/limit to page/page_size — requires live backend with >50 events to confirm pagination works"
---

# Phase 28: Dashboard Integration Fixes — Verification Report

**Phase Goal:** Close the 6 dashboard-backend contract mismatches found in the v1.0 milestone audit. The RAG query flow returns empty answers (wrong endpoint), event search crashes (shape mismatch), SettingsView is unreachable (not routed), ingest progress always shows 0%, pagination always returns page 1, and TS field names are wrong. All 6 are UI/api.ts fixes with no backend schema changes required.
**Verified:** 2026-04-07
**Status:** human_needed — all 6 automated gaps closed; 5 items require live browser verification
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | api.query.ask() POSTs to /api/query/ask/stream (SSE endpoint) | VERIFIED | api.ts line 408: `fetch('/api/query/ask/stream', ...)`; SSE loop reads `msg.token` and `msg.done` matching backend format |
| 2 | SSE stream tokens received by QueryView — no more empty-string answers | HUMAN NEEDED | URL is correct; live stream behavior requires browser test |
| 3 | api.events.search() return type is `{ events: NormalizedEvent[]; total: number; query: string }` | VERIFIED | api.ts line 348: `request<{ events: NormalizedEvent[]; total: number; query: string }>` |
| 4 | EventsView.svelte reads res.events, not res.results.map(r => r.event) | VERIFIED | EventsView.svelte lines 18 and 33 both assign `events = res.events`; no `res.results` anywhere in dashboard/src |
| 5 | App.svelte imports SettingsView, View type includes 'settings', nav item exists, render branch exists | VERIFIED | All 4 additions confirmed: import line 19, type union line 24, nav item line 132, render branch line 274 |
| 6 | SettingsView renders when navigating (human gate) | HUMAN NEEDED | Static wiring complete; visual confirmation requires browser |
| 7 | api.events.list() translates offset/limit to page/page_size | VERIFIED | api.ts line 339: `Math.floor(offset / limit) + 1` with `q.set('page', ...)` and `q.set('page_size', ...)` |
| 8 | EventsListResponse has page, page_size, has_next (not offset/limit) | VERIFIED | api.ts lines 25-31: interface has `page: number; page_size: number; has_next: boolean` |
| 9 | NormalizedEvent has process_id (not process_pid) and raw_event: string | null (not raw_data) | VERIFIED | api.ts lines 17 and 20: `process_id: number \| null` and `raw_event: string \| null`; no occurrences of `process_pid` or `raw_data` anywhere in dashboard/src |
| 10 | GET /api/ingest/status/{job_id} route exists and returns dashboard-compatible shape | VERIFIED | backend/api/ingest.py lines 359-383: `@router.get("/status/{job_id}")` returns events_processed, events_total, filename, started_at, completed_at |
| 11 | _set_job stores filename kwarg | VERIFIED | ingestion/loader.py lines 120-141: `filename: str = ""` kwarg, stored as `"filename": filename` in _JOBS dict |
| 12 | ingest.py passes filename= to _set_job at upload time | VERIFIED | backend/api/ingest.py line 288: `_set_job(job_id, "queued", filename=filename)` |
| 13 | TestJobStatusCompat test class exists and covers 404 + shape check | VERIFIED | tests/unit/test_ingest_api.py lines 222-243: class with both test methods, checking all required keys |

**Score:** 11/11 automated truths verified; 2 deferred to human verification (live browser behavior)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `dashboard/src/lib/api.ts` | SSE URL fix, search return type, pagination translation, EventsListResponse, NormalizedEvent field renames | VERIFIED | All 6 mutations confirmed by grep |
| `dashboard/src/views/EventsView.svelte` | Reads res.events from both list and search responses | VERIFIED | Lines 18 and 33 both use `res.events` |
| `dashboard/src/App.svelte` | SettingsView import, View type, nav item, render branch | VERIFIED | All 4 additions present |
| `backend/api/ingest.py` | GET /status/{job_id} compat route | VERIFIED | Lines 359-383 implement the route with correct shape mapping |
| `ingestion/loader.py` | _set_job accepts and stores filename kwarg | VERIFIED | Lines 120-141 |
| `tests/unit/test_ingest_api.py` | TestJobStatusCompat class | VERIFIED | Lines 222-243 |
| `dashboard/src/views/SettingsView.svelte` | Exists (no modifications required) | VERIFIED | File exists at expected path |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| api.ts query.ask() | /api/query/ask/stream | fetch() call | VERIFIED | Line 408 — correct SSE endpoint |
| api.ts query.ask() SSE reader | msg.token / msg.done | JSON.parse of data: lines | VERIFIED | Lines 427-429 — matches backend stream format |
| EventsView.svelte search() | api.events.search() return | res.events | VERIFIED | Line 33 — `events = res.events` |
| EventsView.svelte load() | api.events.list() return | res.events | VERIFIED | Line 18 — `events = res.events` |
| App.svelte nav click | SettingsView render | currentView === 'settings' | VERIFIED | Line 274 — `{:else if currentView === 'settings'}<SettingsView />` |
| api.ts events.list() | GET /api/events?page=N&page_size=N | Math.floor(offset / limit) + 1 | VERIFIED | Lines 338-344 — offset/limit translated before fetch |
| backend/api/ingest.py upload_file() | _set_job with filename | _set_job(job_id, "queued", filename=filename) | VERIFIED | Line 288 — filename passed at upload time |
| backend/api/ingest.py GET /status/{job_id} | get_job_status() | result.get("loaded") -> events_processed | VERIFIED | Lines 372-382 — correct field mapping |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status |
|-------------|------------|-------------|--------|
| P28-T04 | 28-01 | Ingest progress always shows 0% — /status/{id} route missing | SATISFIED |
| P28-T01 | 28-02 | RAG query empty answers — wrong SSE endpoint in api.ts | SATISFIED |
| P28-T02 | 28-02 | Event search crashes — shape mismatch res.results vs res.events | SATISFIED |
| P28-T05 | 28-03 | Pagination always returns page 1 — offset/limit not translated | SATISFIED |
| P28-T06 | 28-03 | TS field names wrong — process_pid/raw_data vs process_id/raw_event | SATISFIED |
| P28-T03 | 28-04 | SettingsView unreachable — not wired into App.svelte nav | SATISFIED |

---

## Anti-Patterns Found

No blockers or warnings found in any of the modified files. No TODO/FIXME/placeholder comments. No stub return values. No empty implementations. All handlers are wired to real logic.

---

## Human Verification Required

### 1. Settings View Renders in Browser

**Test:** Start the dashboard dev server (`cd dashboard && npm run dev`), open the browser, click "Settings" in the nav sidebar under "Platform"
**Expected:** SettingsView renders — should show operator management table, key rotation controls, TOTP section, and model-status
**Why human:** Static wiring is confirmed (import, type, nav item, render branch all present), but runtime rendering of SettingsView.svelte (which makes multiple API calls for operators, model status) requires live browser verification

### 2. RAG Query Returns Streamed Tokens

**Test:** Navigate to "AI Query" view, type a question, click Ask
**Expected:** Tokens stream in progressively; final answer is non-empty
**Why human:** The SSE URL fix is verified, and the token/done field names match the backend format, but actual streaming behavior depends on a live Ollama + backend environment

### 3. Event Search Populates Table

**Test:** Navigate to "Events" view, type a search query, press Enter
**Expected:** Events table populates with matching results (no crash, no empty-string error)
**Why human:** res.events fix is verified; end-to-end search depends on Chroma embeddings being populated

### 4. Ingest Progress Bar Advances

**Test:** Navigate to "Ingest" view, upload a CSV file, observe progress bar
**Expected:** Progress bar shows events_processed / events_total > 0% as file is processed
**Why human:** /api/ingest/status/{id} route and field mapping are verified; background job polling behavior and timing require live observation

### 5. Event Pagination Past Page 1

**Test:** Ensure >50 events are ingested, navigate to "Events" view, click "Next" button
**Expected:** Page 2 of events loads (different rows than page 1)
**Why human:** Math.floor(offset / limit) + 1 translation is verified; requires live backend with sufficient data to confirm pagination works end-to-end

---

## Summary

All 6 dashboard-backend contract mismatches from the v1.0 audit are closed at the code level:

- **P28-T01 (RAG empty answers):** `api.ts` now calls `/api/query/ask/stream` and reads `msg.token`/`msg.done` matching the backend SSE format.
- **P28-T02 (event search crash):** `api.events.search()` return type updated to `{ events: NormalizedEvent[] }` and `EventsView.svelte` reads `res.events` at both list and search call sites.
- **P28-T03 (SettingsView unreachable):** `App.svelte` has the import, `'settings'` in the View type union, a gear-icon nav item in the Platform group, and the `{:else if currentView === 'settings'}` render branch.
- **P28-T04 (ingest progress 0%):** `GET /api/ingest/status/{job_id}` compat route added to `backend/api/ingest.py`; maps `result.loaded -> events_processed` and `result.parsed -> events_total`; `_set_job` stores `filename` kwarg; `api.ts` `ingest.status()` calls the correct endpoint.
- **P28-T05 (pagination stuck page 1):** `api.events.list()` translates `offset`/`limit` to `page`/`page_size` using `Math.floor(offset / limit) + 1`; `EventsListResponse` interface updated to `page`, `page_size`, `has_next`.
- **P28-T06 (wrong TS field names):** `NormalizedEvent` interface corrected to `process_id: number | null` and `raw_event: string | null`; no occurrences of `process_pid` or `raw_data` remain in `dashboard/src/`.

No backend schema changes were required — all fixes are in `api.ts`, `EventsView.svelte`, `App.svelte`, `backend/api/ingest.py`, `ingestion/loader.py`, and the test file.

The 5 human verification items are behavioral confirmations against a live environment; the static code evidence is complete and consistent across all artifacts.

---

_Verified: 2026-04-07_
_Verifier: Claude (gsd-verifier)_
