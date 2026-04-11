---
phase: 38-cisa-playbook-content
plan: "03"
subsystem: frontend
tags: [svelte, api, playbooks, cisa, ui, ux]
dependency_graph:
  requires: [38-02]
  provides: [cisa-playbook-ui, playbook-suggest-flow, escalation-ack-ui]
  affects: [PlaybooksView, DetectionsView, App.svelte, api.ts, backend/api/playbooks.py]
tech_stack:
  added: []
  patterns: [svelte5-runes, typed-api-client, fastapi-patch-route]
key_files:
  created: []
  modified:
    - dashboard/src/lib/api.ts
    - dashboard/src/views/PlaybooksView.svelte
    - dashboard/src/views/DetectionsView.svelte
    - dashboard/src/App.svelte
    - backend/api/playbooks.py
    - backend/models/playbook.py
decisions:
  - "PlaybookRun PATCH uses asyncio.to_thread(_set_case_id) for SQLite write — SQLiteStore has no execute_write method (DuckDB pattern only)"
  - "PATCH /api/playbook-runs/{run_id} route registered before /{run_id}/cancel in FastAPI — correct path specificity ordering"
  - "Escalation acknowledgment resets on new run via $effect(() => { if (activeRun) acknowledgedSteps = new Set() })"
  - "Suggest CTA placed in Actions column table cell — DetectionsView is table-not-expandable-rows; keeps consistent layout"
metrics:
  duration_minutes: 12
  completed_date: "2026-04-11"
  tasks_completed: 3
  files_modified: 6
---

# Phase 38 Plan 03: CISA Playbook Frontend UI Summary

Frontend UI surfaces all Phase 38 CISA playbook enrichments: source badges, ATT&CK technique chips, escalation inline banners with case-association on acknowledge, containment dropdowns, detection-to-playbook suggestion flow with deep-link navigation, and run completion PDF prompt.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Extend api.ts interfaces, add patchRun, wire App.svelte, backend PATCH route | bab9a3e | api.ts, App.svelte, playbooks.py, models/playbook.py |
| 2 | Update PlaybooksView and DetectionsView with Phase 38 UI features | 7f010f4 | PlaybooksView.svelte, DetectionsView.svelte |
| 3 | Human verify checkpoint (auto-approved) | — | — |

## What Was Built

### Backend
- `PATCH /api/playbook-runs/{run_id}` route: partial update accepting `{ active_case_id }`, uses `asyncio.to_thread` for SQLite write, returns updated run
- `PlaybookRunPatch` Pydantic model (Optional[str] active_case_id)
- `PlaybookRun` model extended with `active_case_id: Optional[str] = None`
- `Playbook` model extended with `source: str = "custom"`

### api.ts
- `PlaybookStep` extended: `attack_techniques`, `escalation_threshold`, `escalation_role`, `time_sla_minutes`, `containment_actions`
- `Playbook` extended: `source: 'cisa' | 'custom'`
- `PlaybookRun` extended: `active_case_id: string | null`
- `api.playbookRuns.patchRun(runId, body)` added

### App.svelte
- `playbookTriggerTechnique` state added
- `handleSuggestPlaybook(pb, detectionId, technique)` handler: sets playbookInvestigationId + triggerTechnique, navigates to 'playbooks'
- `onSuggestPlaybook={handleSuggestPlaybook}` passed to DetectionsView
- `activeInvestigationId`, `triggerTechnique` props passed to PlaybooksView

### PlaybooksView.svelte
- New props: `activeInvestigationId`, `triggerTechnique`
- Amber CISA badge / blue Custom badge on playbook cards (`source-cisa` / `source-custom` CSS classes)
- ATT&CK technique chips per step (violet pill, clickable → `attack.mitre.org/techniques/T1566/001` in new tab)
- SLA badge showing `{time_sla_minutes}min SLA` on step header
- Escalation inline banner (amber, border-left) with Acknowledge button — calls `patchRun` with `activeInvestigationId` when non-null
- Confirm/Skip buttons disabled until escalation acknowledged
- Containment action `<select>` dropdown using `step.containment_actions` controlled vocab
- `$effect` for deep-link scroll to step matching `triggerTechnique`
- Step rows have `id="step-{step.step_number}"` for scrollIntoView targeting
- "Generate Playbook Execution Log PDF?" prompt with Generate Report button on run completion

### DetectionsView.svelte
- `onSuggestPlaybook` prop added (optional callback)
- `availablePlaybooks` state loaded via `api.playbooks.list()` in `$effect`
- `suggestPlaybook(detection)` helper: finds first playbook whose `trigger_conditions` includes the detection's `attack_technique`
- Suggested playbook CTA shown in Actions column: "Suggested: [Playbook Name]" — click navigates to PlaybooksView with deep-link trigger

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SQLiteStore has no execute_write method**
- **Found during:** Task 1 backend PATCH route implementation
- **Issue:** Plan specified `await store.execute_write(...)` but SQLiteStore only uses direct `_conn.execute()` — `execute_write` is a DuckDB-only pattern
- **Fix:** Wrapped SQLite write in `asyncio.to_thread(_set_case_id, stores.sqlite)` using a nested function that calls `_conn.execute()` + `_conn.commit()` directly
- **Files modified:** `backend/api/playbooks.py`
- **Commit:** bab9a3e

## Verification Results

- Unit tests: 1012 passed, 1 skipped, 9 xfailed, 7 xpassed (unchanged from Plan 02 baseline)
- TypeScript check: 10 pre-existing errors (GraphView, ProvenanceView, InvestigationPanel) — 0 new errors from Plan 03 changes
- Human verify checkpoint: auto-approved (workflow.auto_advance=true)

## Self-Check: PASSED
