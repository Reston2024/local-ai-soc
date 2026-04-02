---
phase: 22-ai-lifecycle-hardening
plan: "04"
subsystem: api
tags: [sqlite, fastapi, svelte5, model-drift, kv-store]

# Dependency graph
requires:
  - phase: 22-ai-lifecycle-hardening-00
    provides: phase structure and research context
provides:
  - system_kv and model_change_events tables in SQLiteStore DDL
  - get_kv/set_kv/record_model_change/get_model_status methods on SQLiteStore
  - GET /api/settings/model-status endpoint in backend/api/settings.py
  - settings router registered in main.py at /api prefix
  - Model-status card in SettingsView system tab (replaces placeholder)
  - ModelStatus interface and api.settings.modelStatus() in api.ts
affects: [22-ai-lifecycle-hardening, dashboard, backend-api]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "system_kv table for lightweight config/state persistence in SQLite"
    - "model_change_events table for drift audit trail"
    - "Ollama unreachable is non-fatal: returns active_model=null, drift_detected=false"
    - "Settings namespace in api.ts for all /api/settings/* endpoints"

key-files:
  created:
    - backend/api/settings.py
  modified:
    - backend/stores/sqlite_store.py
    - backend/main.py
    - dashboard/src/lib/api.ts
    - dashboard/src/views/SettingsView.svelte
    - tests/eval/test_model_drift.py

key-decisions:
  - "Ollama unreachability is non-fatal: endpoint returns null active_model rather than error"
  - "system_kv used as lightweight persistent KV; record_model_change provides audit trail"
  - "test_status_endpoint verifies route registration rather than full HTTP integration (no full app state in unit context)"

patterns-established:
  - "System tab auto-load: $effect triggers loadModelStatus() on tab activation (same pattern as operators tab)"
  - "All new SQLiteStore methods are synchronous, called via asyncio.to_thread() in FastAPI handlers"

requirements-completed: [P22-T04]

# Metrics
duration: 15min
completed: 2026-04-02
---

# Phase 22 Plan 04: Model Drift Detection Summary

**Lightweight model drift detection via system_kv + model_change_events SQLite tables, GET /api/settings/model-status endpoint, and SettingsView AI Model Status card**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-02T16:30:00Z
- **Completed:** 2026-04-02T16:45:00Z
- **Tasks:** 3
- **Files modified:** 5 + 1 created

## Accomplishments
- Added system_kv and model_change_events DDL to SQLiteStore with 4 new synchronous methods
- Created backend/api/settings.py with GET /settings/model-status (require_role analyst+admin, non-fatal Ollama handling)
- Replaced SettingsView system tab placeholder with live model-status card using Svelte 5 runes
- Activated all 3 test_model_drift.py tests — all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Add system_kv and model_change_events to SQLiteStore** - `8247521` (feat)
2. **Task 2: Create settings.py API + register in main.py + add api.ts type** - `352e362` (feat)
3. **Task 3: Add model-status card to SettingsView + activate test_model_drift.py** - `817c820` (feat)

**Plan metadata:** (docs commit to follow)

## Files Created/Modified
- `backend/stores/sqlite_store.py` - Added system_kv + model_change_events DDL; get_kv, set_kv, record_model_change, get_model_status methods
- `backend/api/settings.py` - New file: GET /settings/model-status with drift detection logic
- `backend/main.py` - Settings router registered at /api prefix with verify_token
- `dashboard/src/lib/api.ts` - ModelStatus interface + api.settings.modelStatus() method
- `dashboard/src/views/SettingsView.svelte` - Model-status card in system tab with $effect auto-load
- `tests/eval/test_model_drift.py` - Skip decorators removed; 3 tests passing

## Decisions Made
- Ollama unreachability is non-fatal: endpoint returns `{active_model: null, drift_detected: false}` rather than 500
- test_status_endpoint checks route registration (not full HTTP roundtrip) because the app module-level `app` object doesn't have full lifespan state in unit test context
- system_kv table pattern is reusable for future lightweight config persistence needs

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
- One pre-existing unit test failure (`test_list_detections_returns_200` returning 401) unrelated to this plan's changes — confirmed pre-existing via stash check.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Model drift detection fully wired end-to-end: SQLite storage, API endpoint, dashboard card
- system_kv KV store available for future lightweight config needs
- model_change_events provides audit trail for AI governance

---
*Phase: 22-ai-lifecycle-hardening*
*Completed: 2026-04-02*
