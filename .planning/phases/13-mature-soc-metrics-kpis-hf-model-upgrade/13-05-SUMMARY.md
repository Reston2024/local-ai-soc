---
phase: 13-mature-soc-metrics-kpis-hf-model-upgrade
plan: "05"
subsystem: dashboard
tags: [svelte, kpi, dashboard, live-data, assets-view, detections-view]
dependency_graph:
  requires: [13-04]
  provides: [live-kpi-polling, live-assets-view]
  affects: [dashboard/src/lib/api.ts, dashboard/src/views/DetectionsView.svelte, dashboard/src/views/AssetsView.svelte]
tech_stack:
  added: []
  patterns: [svelte5-runes, $derived, $effect-polling, api-typed-client]
key_files:
  created: []
  modified:
    - dashboard/src/lib/api.ts
    - dashboard/src/views/DetectionsView.svelte
    - dashboard/src/views/AssetsView.svelte
decisions:
  - "KPI polling via $effect + setInterval(60_000) with cleanup return — matches Svelte 5 rune lifecycle pattern"
  - "AssetsView: $derived ingestionSources and coverageCategories computed from reactive $state — no manual refresh needed"
  - "FP Rate displayed as percentage (value * 100) matching backend ratio 0-1 storage"
  - "AssetsView pipeline health: overall healthData.status drives source row status; per-component map available for future drill-down"
metrics:
  duration: "~2 minutes"
  completed_date: "2026-03-27"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 3
requirements_satisfied: [P13-T06, P13-T07]
---

# Phase 13 Plan 05: Dashboard Live KPI and Asset Wiring Summary

**One-liner:** Live KPI polling (MTTD/MTTR/MTTC/FP Rate/Active Rules/24h Alerts) wired to /api/metrics/kpis with 60s auto-refresh; AssetsView wired to entity graph counts, source event volumes, and /api/health pipeline status.

## What Was Built

### Task 1 — KpiSnapshot types and api.metrics.kpis() (commit: 53cda7b)

Added to `dashboard/src/lib/api.ts`:

- `KpiValue` interface: `{ label, value, unit, trend: 'up'|'down'|'flat' }` — matches backend KpiValue Pydantic model
- `KpiSnapshot` interface: 9 KpiValue fields + `computed_at` string — matches backend KpiSnapshot.model_dump shape
- `api.metrics.kpis()` in the api object after the `ingest` section — calls `GET /api/metrics/kpis`
- No existing interfaces or functions modified

### Task 2 — DetectionsView + AssetsView wired to live data (commit: c871ac1)

**DetectionsView.svelte:**
- Replaced `mttd`/`mttr` string stubs and static `activeCases` with `kpis: $state<KpiSnapshot | null>(null)` reactive state
- Added `loadKpis()` function using `api.metrics.kpis()` with error isolation (stale data preserved on transient failures)
- `onMount` now runs `Promise.all([load(), checkIngestion(), loadKpis()])`
- `$effect` starts `setInterval(loadKpis, 60_000)` with cleanup on component destroy
- KPI bar ops-group now shows 8 stats: MTTD, MTTR, MTTC, FP Rate, Active Rules, Active Cases, 24h Alerts, Total
- `lastUpdated` reflects `kpis.computed_at` when KPIs available
- Graceful degradation: shows `—` for all KPI values when `kpis` is null or fetch fails

**AssetsView.svelte:**
- Full replacement from static stub to live reactive implementation
- `api.health()` — drives per-source pipeline status (online/offline/error) — satisfies P13-T07
- `api.graph.entities({ limit: 1000 })` — entity type counts for coverage grid (host/user/process/file/network)
- `api.events.list({ limit: 500 })` — source_type counts for ingestion volume display
- `$derived coverageCategories` computed from `entityCounts` reactive state
- `$derived ingestionSources` computed from `sourceCounts + healthData` reactive state
- Added HF SIEM Seed source row; Cloud (AWS/Azure) remains `planned`
- Status color map: active=cyan, ready=green, error=red, planned=grey
- Loading/error states handled — `loading` and `error` $state with graceful fallback

## Verification

```
npm run build    # exits 0, no TypeScript errors
grep "api.metrics.kpis" DetectionsView.svelte    # hit
grep "api.graph.entities" AssetsView.svelte      # hit
grep "api.health" AssetsView.svelte              # hit
grep "KpiSnapshot" api.ts                        # hit
grep "setInterval" DetectionsView.svelte         # hit
```

All 6 verification checks passed.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

- [x] `dashboard/src/lib/api.ts` — modified
- [x] `dashboard/src/views/DetectionsView.svelte` — modified
- [x] `dashboard/src/views/AssetsView.svelte` — modified
- [x] commit 53cda7b exists (Task 1)
- [x] commit c871ac1 exists (Task 2)

## Self-Check: PASSED
