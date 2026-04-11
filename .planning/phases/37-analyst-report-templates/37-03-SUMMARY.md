---
phase: 37-analyst-report-templates
plan: "03"
subsystem: ui
tags: [svelte5, typescript, report-templates, dashboard, pdf]

requires:
  - phase: 37-01
    provides: "6 HTML builders + 3 POST template endpoints + GET /template/meta registered in main.py"
  - phase: 37-02
    provides: "PIR, TI Bulletin, Severity Ref POST endpoints; pydantic model for TI bulletin body"

provides:
  - "Report.type widened to string in api.ts (accepts all template type strings without TS error)"
  - "TemplateMeta interface exported from api.ts"
  - "api.reports.templateMeta() and generateTemplate() methods"
  - "ReportsView.svelte 5th Templates tab with 2x3 card grid (6 cards)"
  - "Each card: data badge, inline selector, Generate-to-Download swap (Card 6 single button)"
  - "App.svelte handleGenerateReport() + reportsInitialTab/CaseId/RunId state"
  - "Generate Report shortcut button in investigation view block (App.svelte)"
  - "PlaybooksView.svelte onGenerateReport prop + btn-shortcut on active run header"

affects: [reporting, analyst-workflow, investigation-to-report, playbook-to-report]

tech-stack:
  added: []
  patterns:
    - "Generate-to-Download swap: cardLastReport[type] drives conditional button rendering"
    - "Card 6 single-action pattern: generate + window.open in one click handler, no state swap"
    - "Props as initial state: initialTab/CaseId/RunId capture parent nav intent on mount"
    - "api.reports.generateTemplate() routes type string to correct POST path via typeToPath map"

key-files:
  created: []
  modified:
    - "dashboard/src/lib/api.ts — Report.type: string, TemplateMeta interface, templateMeta() and generateTemplate() methods"
    - "dashboard/src/views/ReportsView.svelte — 5th Templates tab, 2x3 card grid, 6 cards with badges/selectors/buttons"
    - "dashboard/src/App.svelte — handleGenerateReport(), reportsInitialTab/CaseId/RunId state, Generate Report shortcut in investigation block"
    - "dashboard/src/views/PlaybooksView.svelte — onGenerateReport prop, btn-shortcut on active run header"

key-decisions:
  - "Card 6 (Severity & Confidence Reference): single Download PDF button fires generate + window.open in one click — no Generate-to-Download swap state per plan spec"
  - "Generate Report shortcut in App.svelte wraps InvestigationView in a flex column div with a header bar — no InvestigationView.svelte modification needed"
  - "PlaybooksView shortcut button placed in header-right next to Cancel/Back — visible when activeRun is set"
  - "Svelte warnings about initialTab/CaseId/RunId as initial $state values are benign — they capture parent nav intent on mount, not reactive updates"
  - "typeBadgeClass() helper humanizes template type strings in the Reports tab list (badge-template class for all template_ prefixed types)"
  - "selectedCaseId shared between Card 2 (Incident Report) and Card 4 (PIR) — user selects case once, both cards use it"

patterns-established:
  - "Template card: data-badge + optional selector + Generate/Download button pair is the standard card structure"
  - "cardGenerating / cardLastReport dictionaries keyed by type string enable per-card independent state"

requirements-completed:
  - P37-T07
  - P37-T08

duration: 18min
completed: 2026-04-11
---

# Phase 37 Plan 03: Analyst Report Templates — Frontend Summary

**5th Templates tab in ReportsView with 2x3 card grid for all 6 template types; api.ts extended with TemplateMeta interface + generateTemplate(); shortcut buttons in investigation view and PlaybooksView**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-04-11T~11:30Z
- **Completed:** 2026-04-11T~11:48Z
- **Tasks:** 2 auto tasks + 1 checkpoint (auto-approved)
- **Files modified:** 4

## Accomplishments

- Widened Report.type from `'investigation' | 'executive'` to `string` and exported TemplateMeta interface
- Added api.reports.templateMeta() and generateTemplate() with type-to-path routing for all 6 template types
- ReportsView.svelte: 5th "Templates" tab with 2x3 card grid — each card has data badge, optional inline selector, Generate-to-Download PDF swap (Card 6 is single-action Download PDF)
- App.svelte: handleGenerateReport() navigates to Reports > Templates with case/run pre-selected; Generate Report shortcut button on InvestigationView panel; ReportsView receives initialTab/CaseId/RunId props
- PlaybooksView: onGenerateReport prop + btn-shortcut button on active run header routes to Reports > Templates with run pre-selected

## Task Commits

1. **Task 1: api.ts — Report.type, TemplateMeta, templateMeta/generateTemplate** - `d756789` (feat)
2. **Task 2: ReportsView + App.svelte + PlaybooksView frontend** - `28bf1b3` (feat)
3. **Task 3: human-verify checkpoint** - auto-approved (auto_advance=true)

## Files Created/Modified

- `dashboard/src/lib/api.ts` — Report.type widened, TemplateMeta interface, templateMeta() and generateTemplate() methods added to api.reports
- `dashboard/src/views/ReportsView.svelte` — full rewrite adding 5th Templates tab with 2x3 grid, 6 cards, CSS; reports list badge humanization
- `dashboard/src/App.svelte` — handleGenerateReport(), 3 initial-state vars, ReportsView props, Generate Report shortcut button in investigation block, onGenerateReport passed to PlaybooksView
- `dashboard/src/views/PlaybooksView.svelte` — onGenerateReport prop, btn-shortcut in header-right, CSS

## Decisions Made

- Card 6 (Severity & Confidence Reference): single "Download PDF" button that generates and immediately opens PDF — no Generate-to-Download swap state as specified in key_decisions
- Generate Report shortcut in App.svelte wraps InvestigationView in a flex-column div with header bar — keeps InvestigationView.svelte untouched as required
- PlaybooksView shortcut visible only when activeRun is set and onGenerateReport prop is provided (both conditions required)
- selectedCaseId is shared between the Incident Report card and PIR card — acceptable since both use case_id and the dropdowns show the relevant subset

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 6 template endpoints are now accessible from the dashboard via the Templates tab
- Generate-to-Download flow is functional; generated templates appear in the main Reports list
- Shortcut navigation from InvestigationsView and PlaybooksView routes to pre-selected template cards
- Phase 37 plans 01, 02, 03 all complete — Phase 37 COMPLETE

---
*Phase: 37-analyst-report-templates*
*Completed: 2026-04-11*
