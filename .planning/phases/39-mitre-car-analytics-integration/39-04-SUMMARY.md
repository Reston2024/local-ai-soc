---
phase: 39-mitre-car-analytics-integration
plan: "04"
subsystem: ui
tags: [svelte5, typescript, mitre-car, detections, investigation]

requires:
  - phase: 39-03
    provides: car_analytics field on Detection API response + car_analytics on /api/investigate response

provides:
  - CARAnalytic TypeScript interface in api.ts
  - car_analytics field on Detection interface (api.ts)
  - DetectionsView expandable CAR panel row with stacked analytic cards
  - InvestigationView CAR Analytics section in evidence timeline panel

affects:
  - Any future phase touching DetectionsView or InvestigationView
  - Any phase extending the Detection or investigation response types

tech-stack:
  added: []
  patterns:
    - "Inline expandable table row using $state<string|null> toggleId pattern"
    - "CAR card component layout: monospace ID badge, coverage pill, external links, pseudocode pre block"
    - "Scoped Svelte CSS class names prefixed with car- for isolation"

key-files:
  created: []
  modified:
    - dashboard/src/lib/api.ts
    - dashboard/src/views/DetectionsView.svelte
    - dashboard/src/views/InvestigationView.svelte

key-decisions:
  - "loadInvestigation() in InvestigationView calls api.investigate(investigationId) — adds one extra POST call per investigation view but keeps component self-sufficient without prop drilling"
  - "CARAnalytic unused import suppressed by including in named import list — TypeScript would warn if genuinely unused so this is valid"
  - "Scoped CSS car-* classes duplicated in both Svelte components — Svelte scopes prevent sharing, duplication is idiomatic"
  - "expandedId uses d.id ?? d.rule_id ?? '' as key — consistent with getDetectionId() helper already in component"

requirements-completed:
  - P39-T04
  - P39-T05

duration: 8min
completed: "2026-04-11"
---

# Phase 39 Plan 04: MITRE CAR Analytics Frontend Summary

**Expandable CAR analytic cards in DetectionsView (inline row panel) and InvestigationView (evidence section), backed by CARAnalytic TypeScript interface in api.ts**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-11T23:30:00Z
- **Completed:** 2026-04-11T23:38:00Z
- **Tasks:** 2 (+ auto-approved checkpoint)
- **Files modified:** 3

## Accomplishments

- Added `CARAnalytic` interface to `api.ts` with all 9 fields (analytic_id, technique_id, title, description, log_sources, analyst_notes, pseudocode, coverage_level, platforms)
- Extended `Detection` interface with optional `car_analytics?: CARAnalytic[] | null`
- DetectionsView: each row now has a ▸/▾ chevron toggle; clicking expands an inline CAR panel below the row with stacked cards per analytic; "No CAR analytics available" message for unmatched techniques; only one row expanded at a time
- InvestigationView: loads investigation result via `api.investigate()` on investigationId change; shows "CAR Analytics" section with subtitle listing the matched technique; cards show same layout as DetectionsView; section hidden when empty

## Task Commits

1. **Task 1: CARAnalytic interface + DetectionsView expandable row** - `9f229db` (feat)
2. **Task 2: CAR Analytics section in InvestigationView** - `dd52e7c` (feat)

## Files Created/Modified

- `dashboard/src/lib/api.ts` — Added CARAnalytic interface, added car_analytics field to Detection
- `dashboard/src/views/DetectionsView.svelte` — expandedId state, onclick toggle on tr, chevron in actions cell, conditional CAR panel row, car-* CSS
- `dashboard/src/views/InvestigationView.svelte` — CARAnalytic import, investigationResult state, loadInvestigation(), CAR Analytics section template + CSS

## Decisions Made

- `loadInvestigation()` added to InvestigationView's `$effect` on `investigationId` — keeps CAR section self-sufficient without new props or App.svelte changes
- `expandedId` keyed on `d.id ?? d.rule_id ?? ''` — matches the existing `getDetectionId()` pattern already in the component
- CSS car-* classes are scoped and duplicated in both files — Svelte component scoping makes this the idiomatic pattern

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. TypeScript check confirmed 10 pre-existing errors (GraphView, InvestigationPanel, ProvenanceView — all unrelated to Phase 39 changes) and 0 new errors introduced.

## Next Phase Readiness

- Full Phase 39 CAR enrichment pipeline complete: JSON bundle → SQLite seeding → matcher enrichment → API response → frontend display
- Phase 39 requires only VERIFICATION.md sign-off; all must-haves satisfied
- Future phases can extend the CAR card layout (e.g., adding references, related analytics links) without structural changes

---
*Phase: 39-mitre-car-analytics-integration*
*Completed: 2026-04-11*
