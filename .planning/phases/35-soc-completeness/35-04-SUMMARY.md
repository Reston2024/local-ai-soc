---
plan: "35-04"
phase: 35-soc-completeness
status: complete
completed: "2026-04-10"
tests_added: 7
tests_total: 965
---

# Plan 35-04 Summary — Frontend: OverviewView + triage panel + telemetry endpoint

## What Was Built

**GET /api/telemetry/summary** (`backend/api/telemetry.py`):
- DuckDB 24h rollup: `event_type_counts` dict + `total_events` + `ioc_matches`
- SQLite 24h rollup: `total_detections` + `assets_count` + `top_rules` (top 5 by count)
- Graceful degradation: DuckDB and SQLite failures caught independently, return zeros

**OverviewView.svelte** (new landing dashboard):
- Default view — `currentView` in App.svelte changed from `'detections'` to `'overview'`
- Block 1: EVE type breakdown bar chart (proportional fill bars, last 24h)
- Block 2: Scorecard row — Total Events / Total Detections / IOC Matches / Assets
- Block 3: System health — API backend dot + Router/Firewall/GMKtec network device dots
- Block 4: Latest AI triage — severity summary + expand/collapse for full result text
- Block 5: Top detected rules table — rule name / count / severity badge
- 60s auto-refresh via `$effect()` with `setInterval` cleanup

**Triage panel in DetectionsView.svelte**:
- Collapsible panel at top of view (`triagePanelOpen` defaults to `true`)
- Polls `/api/triage/latest` every 15s
- "Run Triage Now" button — calls `POST /api/triage/run`, updates panel on completion
- Spinner while running (`triageRunning` state)
- Error state: `triageError` shown inline if `run()` throws (prevents unhandled rejections)

**App.svelte changes**:
- `type View` extended with `'overview'`
- `currentView` defaults to `'overview'`
- Overview added as first item in Monitor nav group with dashboard icon
- `<OverviewView healthStatus={...} networkDevices={...} />` routing block added

**api.ts extensions**:
- `TelemetrySummary`, `TriageResult`, `TriageRunResult` interfaces
- `api.telemetry.summary()` → `GET /api/telemetry/summary`
- `api.triage.latest()` → `GET /api/triage/latest`
- `api.triage.run()` → `POST /api/triage/run`

## Fixes Applied During Checkpoint

- Backend restart required to load Phase 35-03/35-04 routes (triage + telemetry routers)
- `OLLAMA_MODEL` changed to `llama3:latest` in `.env` (qwen3:14b not pulled)
- `OLLAMA_CYBERSEC_MODEL` code default fixed: `"llama3:latest"` → `"foundation-sec:8b"`
- `tests/unit/test_config.py` hardened: config defaults now tested with `_env_file=None` + `monkeypatch` to isolate from `.env` overrides
- `runTriageNow()` in DetectionsView: added `catch` block — shows inline `triageError` message instead of unhandled promise rejection

## Tests

- `tests/unit/test_telemetry_summary.py`: 4 tests — response shape, event_type_counts types, top_rules item shape, empty-data 200
- `tests/unit/test_config.py`: 3 tests — cybersec model default, override via env, OLLAMA_MODEL regression (all now `.env`-isolated)

## Requirements Satisfied

- P35-T05: GET /api/telemetry/summary endpoint ✓
- P35-T07: E2E smoke — Overview landing, triage panel, auto-triage worker verified ✓
