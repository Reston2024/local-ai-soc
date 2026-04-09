---
phase: 31-malcolm-full-telemetry
plan: "03"
subsystem: ingestion-collector, dashboard-ui, configuration
tags: [malcolm, ubuntu-normalizer, event-filtering, svelte5, api-client]
dependency_graph:
  requires: [31-01, 31-02]
  provides: [ubuntu-poll-source, event-type-filter-chips, api-event-type-param]
  affects: [dashboard/EventsView, ingestion/jobs/malcolm_collector, backend/core/config]
tech_stack:
  added: []
  patterns:
    - Svelte 5 $effect() for reactive chip-driven data fetching
    - Line-count cursor tracking for NDJSON append-only file polling
    - Disabled beta chip pattern for upcoming telemetry (Phase 36 preview)
key_files:
  created: []
  modified:
    - backend/core/config.py
    - ingestion/jobs/malcolm_collector.py
    - dashboard/src/lib/api.ts
    - dashboard/src/views/EventsView.svelte
    - tests/unit/test_malcolm_collector.py
decisions:
  - "Empty UBUNTU_NORMALIZER_URL disables the Ubuntu poll silently — no error, returns []"
  - "Line-count cursor (not byte offset) tracks Ubuntu NDJSON append-only file position"
  - "ZEEK_CHIPS are disabled/dashed in UI — Phase 36 preview with tooltip explaining wait"
  - "$effect() replaces onMount(load) — handles both initial load and reactive chip re-fetch"
metrics:
  duration_seconds: 185
  tasks_completed: 4
  files_modified: 5
  completed_date: "2026-04-09"
requirements: [P31-T09, P31-T10, P31-T12]
---

# Phase 31 Plan 03: Ubuntu Poll + EventsView Filter Chips Summary

Ubuntu normalization poll source wired into MalcolmCollector with NDJSON line-count cursor, UBUNTU_NORMALIZER_URL setting added, api.ts events.list() extended with event_type param, and EventsView gets a horizontal chip filter row (7 active + 8 beta Zeek chips).

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 0 | TDD RED — failing Ubuntu poll test | a483cc3 | tests/unit/test_malcolm_collector.py |
| 1 | Settings + Ubuntu poll in MalcolmCollector (GREEN) | 18dc519 | backend/core/config.py, ingestion/jobs/malcolm_collector.py, tests/unit/test_malcolm_collector.py |
| 2 | api.ts event_type param + EventsView chips | 0b189a0 | dashboard/src/lib/api.ts, dashboard/src/views/EventsView.svelte |
| 3 | Beta Zeek telemetry chips (Phase 36 preview) | 0b189a0 | dashboard/src/views/EventsView.svelte |
| CP | Checkpoint auto-approved (auto_advance=true) | — | — |

## What Was Built

**backend/core/config.py:** Added `UBUNTU_NORMALIZER_URL: str = ""` and `UBUNTU_NORMALIZER_POLL_INTERVAL: int = 60` to Settings. Empty string = Ubuntu poll disabled by default.

**ingestion/jobs/malcolm_collector.py:**
- `__init__` accepts `ubuntu_normalizer_url: str = ""` and sets `self._ubuntu_normalizer_url`, `self._ubuntu_ingested`
- `_poll_ubuntu_normalizer()`: async method — returns `[]` immediately when URL is empty; otherwise polls `{url}/normalized/latest`, parses NDJSON, tracks line-count cursor in SQLite KV key `malcolm.ubuntu_normalized.last_line_count`, routes `ipfire_syslog` source_type via `_normalize_syslog()`, builds generic `NormalizedEvent` for other types
- `_poll_and_ingest()` calls `_poll_ubuntu_normalizer()` before the heartbeat
- `status()` now includes `ubuntu_ingested` count
- Also added `_interval_sec` alias for test compatibility

**dashboard/src/lib/api.ts:** `events.list()` params now includes `event_type?: string` — passed as `URLSearchParams` `event_type` key when non-empty.

**dashboard/src/views/EventsView.svelte:**
- `CHIPS` array: All | Alert | TLS | DNS | File | Anomaly | Syslog
- `ZEEK_CHIPS` array: Connection | HTTP | SSL | SMB | Auth | SSH | SMTP | DHCP (disabled/dashed, Phase 36)
- `selectedChip = $state('')` drives chip active state
- `$effect()` replaces `onMount(load)` — re-fetches on chip change, resets offset to 0
- Chip row inserted between `.view-header` and `{#if error}` block
- CSS: `.chip-row`, `.chip`, `.chip-active`, `.chip-divider`, `.chip-beta`, `.chip-beta:hover`

## Verification Results

```
uv run pytest tests/unit/test_malcolm_collector.py -x -q  →  11 passed
uv run pytest tests/unit/ -x -q  →  882 passed, 1 skipped, 9 xfailed, 7 xpassed
settings.UBUNTU_NORMALIZER_URL == ''  → Settings OK
grep event_type dashboard/src/lib/api.ts  → 3 matches (interface + param type + URLSearchParams)
grep -c "ZEEK_CHIPS|chip-beta|chip-divider" dashboard/src/views/EventsView.svelte → 7
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added _interval_sec alias for test compatibility**
- **Found during:** Task 1
- **Issue:** `test_malcolm_collector_backoff_on_failure` uses `getattr(collector, "_interval_sec", 30)` — existing attribute was `_interval` only
- **Fix:** Added `self._interval_sec = interval_sec` alias alongside existing `self._interval`
- **Files modified:** ingestion/jobs/malcolm_collector.py
- **Commit:** 18dc519

**2. [Rule 1 - Implementation merge] Tasks 2 and 3 committed together**
- Both tasks modified only `EventsView.svelte` — committed as single logical unit since ZEEK_CHIPS were written in the same Write operation as the active chips
- No behavior change — all acceptance criteria for both tasks are met

## Self-Check: PASSED
