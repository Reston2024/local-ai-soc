---
phase: 52-thehive-case-management-integration
plan: "04"
subsystem: ui
tags: [svelte5, typescript, thehive, case-management, dashboard]

# Dependency graph
requires:
  - phase: 52-03
    provides: TheHive pipeline wiring — thehive_case_num/status persisted on detections table
provides:
  - TheHive case badge (#N · status) on detection rows in DetectionsView
  - "Open in TheHive" deep-link button in expanded detection panel
  - TheHive case badge + button in InvestigationView Evidence Timeline header
  - thehive_case_id/num/status fields on Detection TypeScript interface
affects:
  - phase 53 (future frontend components can reuse badge CSS pattern)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "THEHIVE_CASE_URL constant hardcoded as 192.168.1.22:9000 — config constant per CONTEXT.md decision"
    - "Duplicate CSS classes across Svelte components (badge-thehive) — idiomatic Svelte scoping, no shared stylesheet"
    - "thehiveBadgeClass/thehiveBadgeLabel helper functions duplicated per component — Svelte scoping makes sharing non-trivial"

key-files:
  created: []
  modified:
    - dashboard/src/lib/api.ts
    - dashboard/src/views/DetectionsView.svelte
    - dashboard/src/views/InvestigationView.svelte

key-decisions:
  - "THEHIVE_URL hardcoded as http://192.168.1.22:9000 in both components — per CONTEXT.md decision, no settings endpoint needed"
  - "TheHive badge placed on collapsed row AND in expanded panel for both corr and CAR paths — max visibility without intrusion"
  - "investigationResult.detection type extended inline (not new interface) — detection sub-object is already typed ad-hoc; adding thehive fields inline avoids proliferating small interfaces"
  - "ThehiveHeaderBadge placed between <h2> and .header-actions in panel-header — consistent with panel-header flex layout, badge stays near title"

patterns-established:
  - "Badge status → color mapping: New/InProgress=amber (#92400e), Resolved/TruePositive=green (#065f46), FalsePositive=red (#7f1d1d)"
  - "Open in TheHive button uses window.open(_blank) with non-null assertion on case_num — safe because wrapped in {#if d.thehive_case_num}"

requirements-completed:
  - REQ-52-05

# Metrics
duration: 8min
completed: 2026-04-16
---

# Phase 52 Plan 04: TheHive Frontend Integration Summary

**TheHive case badge (#N · status) and "Open in TheHive" deep-link added to detection rows and investigation header, with amber/green/red status coloring and TypeScript clean build**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-16T15:20:00Z
- **Completed:** 2026-04-16T15:25:31Z
- **Tasks:** 2 auto + 1 checkpoint (auto-approved)
- **Files modified:** 3

## Accomplishments
- Detection interface in api.ts gains `thehive_case_id`, `thehive_case_num`, `thehive_status` — backend thehive columns now surfaced to frontend
- DetectionsView shows `#N · status` amber badge on collapsed rows; expanded panel shows badge + "Open in TheHive" button deep-linking to `http://192.168.1.22:9000/cases/{N}` in both corr and CAR expand panels
- InvestigationView Evidence Timeline header shows case badge + "Open in TheHive" button when `investigationResult.detection.thehive_case_num` is set
- TypeScript 0 errors, 1181 unit tests passing (pre-existing test_metrics_api failure unaffected)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend Detection interface and DetectionsView with case badge and button** - `1599a46` (feat)
2. **Task 2: Add TheHive case badge and button to InvestigationView header** - `cd58f5b` (feat)
3. **Checkpoint: auto-approved** (auto_advance=true, TypeScript clean)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `dashboard/src/lib/api.ts` — Added `thehive_case_id`, `thehive_case_num`, `thehive_status` to Detection interface
- `dashboard/src/views/DetectionsView.svelte` — THEHIVE_CASE_URL constant, thehiveBadgeClass/Label helpers, case badge on rows, button in expanded panels, CSS
- `dashboard/src/views/InvestigationView.svelte` — Same helpers, detection type extended, case badge + button in Evidence Timeline header, CSS

## Decisions Made
- THEHIVE_URL hardcoded as `http://192.168.1.22:9000` in both components per CONTEXT.md decision — no settings endpoint needed
- `investigationResult.detection` type extended inline with thehive fields rather than creating a new interface — avoids proliferating small ad-hoc interfaces
- TheHive badge placed in both the corr panel and CAR panel expand paths — ensures all detection types show the button regardless of detection source
- `thehive-header-badge` placed between `<h2>` and `.header-actions` in InvestigationView panel-header — fits naturally in flex row layout

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `test_metrics_api.py::test_endpoint_accessible_at_api_metrics_kpis` pre-existing failure confirmed via `git stash` — out of scope, not caused by this plan's changes.

## User Setup Required
Live badge testing requires TheHive deployed on GMKtec:
```
docker compose -f infra/docker-compose.thehive.yml up -d
```
Then High/Critical detections will auto-create cases (Phase 52-03 pipeline) and badges will appear.

## Next Phase Readiness
- Phase 52 frontend complete — analyst workflow loop closed: detections with TheHive cases show live status badge and one-click navigation
- Phase 53 (Network Privacy Monitoring) can begin independently

---
*Phase: 52-thehive-case-management-integration*
*Completed: 2026-04-16*
