---
plan: 43-04
phase: 43
subsystem: frontend
tags: [svelte, typescript, correlation, detections-view]
requires: [43-03]
provides: [corr-filter-chip, corr-type-badge, corr-expand-panel]
affects: [dashboard/src/lib/api.ts, dashboard/src/views/DetectionsView.svelte]
tech_stack_added: []
tech_stack_patterns: [svelte5-runes, derived-filtering]
key_files_created: []
key_files_modified:
  - dashboard/src/lib/api.ts
  - dashboard/src/views/DetectionsView.svelte
decisions:
  - displayDetections derived from typeFilter rune so severity filter and type filter compose independently
  - corrBadgeLabel branches on rule_id prefix to map corr-portscan/bruteforce/beacon/chain to display labels
  - Expand panel branches on rule_id.startsWith('corr-') — corr rows show event ID pills, others keep CAR panel intact
metrics:
  duration_minutes: 5
  tasks_completed: 2
  tasks_total: 2
  files_changed: 2
  completed_date: "2026-04-12T19:12:36Z"
requirements_satisfied: [P43-T06]
---

# Phase 43 Plan 04: Frontend — CORR filter chip, correlation badge, expand-to-events UI Summary

Correlation detection surfacing in DetectionsView: CORR/ANOMALY/SIGMA filter chips, per-row correlation type badges (PORT_SCAN/BRUTE_FORCE/BEACON/CHAIN), and expand panel showing matched_event_ids as monospace pills for corr-* rows while preserving CAR analytics for all others.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Extend Detection interface + CORR filter chips and type badges | 71a50a5 | api.ts, DetectionsView.svelte |
| 2 | Correlation expand panel showing matched event IDs | 1969e0a | DetectionsView.svelte |

## What Was Built

### Task 1 — Detection interface extension + CORR filter chips + type badges

**api.ts Detection interface:** Two optional fields added:
- `correlation_type?: string` — 'PORT_SCAN' | 'BRUTE_FORCE' | 'BEACON' | 'CHAIN'
- `matched_event_count?: number` — convenience count for row badge

**DetectionsView.svelte additions:**
- `typeFilter` rune (`'' | 'CORR' | 'ANOMALY' | 'SIGMA'`) alongside existing `severityFilter`
- `displayDetections` derived list — filters by `rule_id` prefix for CORR/ANOMALY, inverse for SIGMA, passthrough for ''
- `corrCount` derived — count of `corr-*` detections for chip badge
- `corrBadgeLabel()` helper — maps rule_id prefix to display string
- Four filter chips (All / CORR / ANOMALY / SIGMA) inserted after the severity select in kpi-bar actions
- `{#each displayDetections}` replaces `{#each detections}` in the table body
- Inline `corr-type-badge` span rendered after `rule_name` on corr-* rows

**CSS added:** `.type-filter-chips`, `.chip` base + hover + active variants, `.chip-corr/anomaly/sigma` active colors, `.corr-type-badge` base + `.corr-badge-port-scan/brute-force/beacon/chain` variants

### Task 2 — Correlation expand panel

Existing expand section branched on `d.rule_id?.startsWith('corr-')`:
- **Correlation branch:** `corr-expand-panel` with header (label + event count), flex-wrap list of `corr-event-id` code pills from `d.matched_event_ids`, empty state text, and optional `d.explanation` shown below
- **Non-correlation branch:** CAR analytics panel preserved exactly as written in Phase 39 — no changes to existing markup

**CSS added:** `.corr-expand-panel`, `.corr-expand-header`, `.corr-expand-label`, `.corr-expand-count`, `.corr-event-id-list`, `.corr-event-id`, `.corr-no-events`, `.corr-explanation`

## Verification

- TypeScript: `npx tsc --noEmit` — 0 errors both tasks
- Unit tests: 1067 passed, 3 skipped, 9 xfailed, 7 xpassed — no regressions

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `dashboard/src/lib/api.ts` — modified, correlation_type + matched_event_count fields present
- `dashboard/src/views/DetectionsView.svelte` — modified, typeFilter/displayDetections/corrCount/corrBadgeLabel/chips/badges/expand-panel all in place
- Commits 71a50a5 and 1969e0a exist in git log
