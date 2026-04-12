---
phase: 44
plan: 44-04
subsystem: frontend
tags: [svelte, feedback, verdicts, kpi, ux]
depends_on:
  requires: [44-03]
  provides: [analyst-feedback-ui]
  affects: [DetectionsView, InvestigationView, OverviewView]
tech-stack:
  added: []
  patterns: [svelte5-runes, $state, $derived, $effect, typed-api-client]
key-files:
  created: []
  modified:
    - dashboard/src/views/DetectionsView.svelte
    - dashboard/src/views/InvestigationView.svelte
    - dashboard/src/views/OverviewView.svelte
decisions:
  - Verdict buttons placed in expand panel (both corr and CAR branches) per CONTEXT.md
  - verdictFilter composes with typeFilter via IIFE-wrapped $derived
  - OverviewView adds kpis $state via api.metrics.kpis() in load() Promise.all with graceful .catch(() => null) — no separate polling loop needed
  - feedback-kpi-row uses auto-fit minmax(90px, 1fr) to handle conditional 4th vs 5th tile
  - Classifier Accuracy tile hidden until training_samples >= 10 per CONTEXT.md decision
metrics:
  duration_seconds: 300
  completed_date: "2026-04-12"
  tasks_completed: 3
  files_modified: 3
---

# Phase 44 Plan 04: Wave 3 — Frontend verdict buttons, similar cases, feedback KPIs Summary

Analyst feedback UI wired across three Svelte views: verdict TP/FP buttons + toast in DetectionsView, similar confirmed cases section in InvestigationView, and 5 feedback KPI tiles in OverviewView. TypeScript compiles clean, 1081 unit tests green.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 44-04-01 | DetectionsView — verdict buttons, Unreviewed chip, badge, toast | b4d8aae | dashboard/src/views/DetectionsView.svelte |
| 44-04-02 | InvestigationView — Similar Confirmed Cases section | ffceb48 | dashboard/src/views/InvestigationView.svelte |
| 44-04-03 | OverviewView — 5 feedback KPI cards | 421bf4b | dashboard/src/views/OverviewView.svelte |

## What Was Built

### DetectionsView.svelte
- `verdicts` Map rune + `verdictFilter` boolean rune
- `displayDetections` $derived now uses IIFE to compose typeFilter and verdictFilter
- `showToast()` + `submitVerdict()` helpers; verdicts Map initialized from `d.verdict` fields on each `load()` call
- Unreviewed filter chip with `chip-unreviewed` active style added alongside CORR/ANOMALY/SIGMA chips
- Verdict badge (TP green / FP red) on each collapsed detection row (rule-name cell)
- TP/FP ghost buttons in both expand panel branches: corr panel and CAR/sigma panel
- Fixed-position toast notification (3s auto-dismiss via setTimeout)

### InvestigationView.svelte
- `SimilarCase` type imported from api.ts
- `similarCases $state<SimilarCase[]>([])` rune
- `$effect` triggers on investigationId change, passes rule_id/rule_name from investigationResult.detection to api.feedback.similar()
- Conditional Similar Confirmed Cases section renders below CAR Analytics inside timeline-panel
- Shows verdict badge, rule name, similarity %, optional summary per case card

### OverviewView.svelte
- `KpiSnapshot` type imported from api.ts
- `kpis $state<KpiSnapshot | null>(null)` rune
- `api.metrics.kpis()` added to `load()` Promise.all with `.catch(() => null)` — uses existing 60s poll from setInterval
- 5 new scorecard tiles: Verdicts Given, TP Rate, FP Rate, Classifier Accuracy (conditional), Training Samples
- Classifier Accuracy tile conditionally rendered only when `training_samples >= 10`
- `feedback-kpi-row` uses `auto-fit minmax(90px, 1fr)` for flexible column count

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing functionality] OverviewView missing kpis state**
- **Found during:** Task 44-04-03
- **Issue:** Plan assumed kpis variable already existed in OverviewView, but the view only used `summary` (TelemetrySummary)
- **Fix:** Added KpiSnapshot import, `kpis $state`, and `api.metrics.kpis()` to existing `load()` Promise.all with graceful fallback
- **Files modified:** dashboard/src/views/OverviewView.svelte

**2. [Rule 1 - Bug] OverviewView scorecard uses tile-value/tile-label, not kpi-value/kpi-label**
- **Found during:** Task 44-04-03
- **Issue:** Plan said "kpi-label, kpi-value already exist" but the actual CSS classes are `tile-value` and `tile-label`
- **Fix:** Used correct existing CSS class names throughout new feedback KPI tiles
- **Files modified:** dashboard/src/views/OverviewView.svelte

## Verification

- TypeScript: 0 errors across all three files (`npx tsc --noEmit`)
- Unit tests: 1081 passed, 0 regressions (`uv run pytest tests/unit/ -q`)
- DetectionsView: submitVerdict, verdictFilter, verdict-badge, verdict-toast all confirmed present
- InvestigationView: similarCases rune and "Similar Confirmed" section confirmed present
- OverviewView: verdicts_given, tp_rate, training_samples tiles confirmed present

## Self-Check: PASSED
