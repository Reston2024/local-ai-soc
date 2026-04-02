---
phase: 22-ai-lifecycle-hardening
plan: 09
subsystem: ai-lifecycle
tags: [ollama, model-drift, llm-audit, sqlite, async]

# Dependency graph
requires:
  - phase: 22-ai-lifecycle-hardening
    provides: SQLiteStore.get_kv/set_kv/record_model_change and system_kv table from plan 04
provides:
  - _check_model_drift() private async method on OllamaClient (hot-path drift check)
  - WARNING log on every generate()/stream_generate() call when active model differs from last_known_model
affects: [ollama_client, ai-lifecycle, llm-audit]

# Tech tracking
tech-stack:
  added: []
  patterns: [non-fatal async SQLite read via asyncio.to_thread on every LLM hot path]

key-files:
  created: []
  modified:
    - backend/services/ollama_client.py

key-decisions:
  - "22-09: _check_model_drift() placed between _write_telemetry() and generate() — same section as existing private helpers"
  - "22-09: Hot-path uses SQLite get_kv read (cheap) rather than list_models() HTTP call — only seeds on first-ever call when no last_known exists"
  - "22-09: Non-fatal contract: all exceptions caught and logged at DEBUG level so LLM call always proceeds"

patterns-established:
  - "Drift check pattern: read last_known from SQLite, compare, log WARNING on mismatch, seed on first call"

requirements-completed:
  - P22-T04

# Metrics
duration: 5min
completed: 2026-04-02
---

# Phase 22 Plan 09: Model Drift Hot-Path Detection Summary

**OllamaClient._check_model_drift() wired into generate() and stream_generate() — WARNING logged on every LLM call when active model differs from SQLite last_known_model**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-02T17:38:44Z
- **Completed:** 2026-04-02T17:43:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Added `_check_model_drift(effective_model)` private async method to OllamaClient
- Method reads `last_known_model` from SQLite `system_kv` table via `asyncio.to_thread()` on every call
- Seeds `last_known_model` on first call (no warning, debug log only)
- Logs `WARNING "Model drift detected on LLM call"` when active model differs from last_known
- Both `generate()` and `stream_generate()` call `_check_model_drift()` before the HTTP request to Ollama
- Fully non-fatal: all exceptions swallowed with debug log — LLM call always proceeds
- 803 tests pass, 18/18 eval tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Add _check_model_drift() and call it from generate() and stream_generate()** - `b48a2c3` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `backend/services/ollama_client.py` - Added `_check_model_drift()` method (42 lines) + 2 call sites in generate() and stream_generate()

## Decisions Made

- Used cheap SQLite `get_kv` read on every hot-path call instead of `list_models()` HTTP round-trip — avoids performance impact on each LLM call
- Non-fatal exception handling matches existing `record_llm_provenance` pattern already in the file
- Method placed in new "Model drift detection" section between telemetry helpers and text generation section for clarity

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- P22-T04 hot-path drift detection complete
- Settings endpoint `/api/settings/model-status` continues to serve as the authoritative record-writer (unchanged)
- Drift WARNING now fires on every generate()/stream_generate() call — analysts can see it in logs without visiting Settings

---
*Phase: 22-ai-lifecycle-hardening*
*Completed: 2026-04-02*
