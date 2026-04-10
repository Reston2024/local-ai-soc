---
phase: 35-soc-completeness
plan: "35-03"
subsystem: api
tags: [fastapi, ollama, triage, background-worker, asyncio, sqlite, pytest]

requires:
  - phase: 35-02
    provides: triage_results DDL, save_triage_result(), get_latest_triage(), triaged_at migration
  - phase: 35-01
    provides: explain endpoint, Zeek field map, prompts/triage.py build_prompt()
provides:
  - POST /api/triage/run — on-demand AI triage of untriaged detections, returns run summary
  - GET /api/triage/latest — most recent triage result row
  - _run_triage() helper — core triage logic callable from endpoint and background worker
  - _auto_triage_loop() — 60s background poll worker registered in main.py lifespan
  - 7 unit tests (test_triage_api.py x4, test_triage_worker.py x3)
affects:
  - 35-04
  - frontend triage views
  - main.py lifespan worker registration

tech-stack:
  added: []
  patterns:
    - "_run_triage() decoupled from HTTP layer — callable from both POST endpoint and background worker"
    - "Background worker uses asyncio.CancelledError re-raise pattern for clean shutdown"
    - "asyncio.sleep patched in tests for fast iteration (no real 60s waits)"

key-files:
  created:
    - backend/api/triage.py
    - tests/unit/test_triage_api.py
    - tests/unit/test_triage_worker.py
  modified:
    - backend/main.py

key-decisions:
  - "_run_triage() is a standalone async function (not a method) — both endpoint and background worker call it identically"
  - "Model name read from getattr(ollama_client, 'model', 'ollama') — graceful fallback if client has no .model attribute"
  - "severity_summary is first non-empty line of LLM result (truncated to 200 chars) — fast parse, no parsing errors"
  - "Triage worker registered inside try/except in lifespan — non-fatal if import fails (graceful degradation)"
  - "triaged_at stored as ISO-8601 UTC string (same format as created_at) — consistent timestamp style throughout detections table"

patterns-established:
  - "Background worker pattern: while True + try/except Exception + CancelledError re-raise + asyncio.sleep(N)"
  - "TDD pattern: write stub test importing unexistent module → confirm ImportError RED → implement → GREEN"

requirements-completed:
  - P35-T09
  - P35-T10

duration: 18min
completed: 2026-04-10
---

# Phase 35 Plan 03: Triage API endpoint + background worker Summary

**AI triage loop: POST /api/triage/run + GET /api/triage/latest + 60s background worker calling Ollama via _run_triage() helper**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-04-10T18:54:44Z
- **Completed:** 2026-04-10T19:12:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Implemented `backend/api/triage.py` with POST /run (on-demand triage), GET /latest (most recent result), `_run_triage()` helper (core logic), and `_auto_triage_loop()` (60s background poll)
- Wired triage router and auto-triage worker into `main.py` lifespan using the established try/except pattern
- 7 unit tests: 4 for API endpoints (run-with-detections, run-empty, latest-with-result, latest-empty) + 3 for worker (calls _run_triage, survives errors, exits on CancelledError)

## Task Commits

Each task was committed atomically:

1. **Task 1: POST /api/triage/run + GET /api/triage/latest + _run_triage** - `ca417d9` (feat)
2. **Task 2: Worker tests + _auto_triage_loop + main.py wiring** - `8c103a7` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `backend/api/triage.py` - POST /triage/run, GET /triage/latest, _run_triage(), _auto_triage_loop()
- `tests/unit/test_triage_api.py` - 4 tests for endpoint behavior via _run_triage() + get_triage_latest()
- `tests/unit/test_triage_worker.py` - 3 tests for background worker loop (calls, error handling, cancellation)
- `backend/main.py` - Auto-triage worker registration in lifespan + triage router mount at /api/triage

## Decisions Made
- `_run_triage()` decoupled from HTTP layer — both the POST endpoint and background worker call it identically, avoiding code duplication and HTTP overhead in the worker
- Model name read with `getattr(ollama_client, 'model', 'ollama')` — graceful fallback when client has no `.model` attribute
- `severity_summary` derived from first non-empty LLM response line truncated to 200 chars — simple, fast, no regex parsing errors
- Triage router and worker both wrapped in try/except in main.py — graceful degradation if import fails

## Deviations from Plan

None — plan executed exactly as written. `_auto_triage_loop()` was included in Task 1's implementation (triage.py) as it logically belongs there, and Task 2 added the tests and main.py wiring as planned.

## Issues Encountered

One pre-existing test failure (`tests/unit/test_config.py::test_cybersec_model_default`) was present before this plan's work — OLLAMA_CYBERSEC_MODEL default value mismatch. This is out of scope and was logged but not fixed. All 962 other unit tests pass.

## User Setup Required

None — no external service configuration required. Triage calls the existing Ollama client already configured via `OLLAMA_BASE_URL`.

## Next Phase Readiness
- Triage API complete: POST /api/triage/run and GET /api/triage/latest are live
- Auto-triage worker runs every 60s on event loop start, calls Ollama directly
- Phase 35 Plan 04 can now wire the frontend TriageView to call these endpoints
- Pre-existing test_config.py failure should be investigated in a future plan

---
*Phase: 35-soc-completeness*
*Completed: 2026-04-10*
