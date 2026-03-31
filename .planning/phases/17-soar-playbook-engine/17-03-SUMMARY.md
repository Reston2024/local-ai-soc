---
phase: 17-soar-playbook-engine
plan: "03"
subsystem: frontend
tags: [soar, playbooks, svelte5, typescript, api-client]
dependency_graph:
  requires:
    - backend/api/playbooks.py (GET /api/playbooks, POST /api/playbooks/{id}/run/{inv_id} — from 17-01)
    - backend/api/playbooks.py runs_router (PATCH /step, PATCH /cancel, GET — from 17-02)
  provides:
    - dashboard/src/lib/api.ts exports Playbook, PlaybookRun, PlaybookStep, PlaybookStepResult types
    - dashboard/src/lib/api.ts api.playbooks.* and api.playbookRuns.* methods
    - dashboard/src/views/PlaybooksView.svelte full SOAR execution UI (library + execution modes)
    - dashboard/src/views/InvestigationView.svelte onRunPlaybook prop and Run Playbook button
    - dashboard/src/App.svelte onRunPlaybook navigation handler
  affects:
    - dashboard/src/App.svelte (navigation handler + prop wiring)
tech_stack:
  added: []
  patterns:
    - Svelte 5 runes $state/$derived/$effect throughout — no stores
    - Dual-mode single-view pattern (library MODE A / execution MODE B via $state)
    - $derived for currentStepNumber (steps_completed.length + 1)
    - Callback prop pattern (onRunPlaybook) consistent with onOpenInGraph
key_files:
  created: []
  modified:
    - dashboard/src/lib/api.ts (6 interfaces + api.playbooks + api.playbookRuns namespaces)
    - dashboard/src/views/PlaybooksView.svelte (complete rewrite — was stub, now full SOAR UI)
    - dashboard/src/views/InvestigationView.svelte (onRunPlaybook prop + Run Playbook button)
    - dashboard/src/App.svelte (handleRunPlaybook handler + prop wiring to both views)
decisions:
  - "PlaybooksView uses a single $state boolean (activeRun != null) to toggle MODE A/B — no separate page/route needed"
  - "App.svelte wired in same commit as Rule 2 deviation — navigation is essential for the feature to work end-to-end"
  - "playbookInvestigationId state in App.svelte separate from investigatingId — playbooks view gets own context"
metrics:
  duration_minutes: 8
  completed_date: "2026-03-31"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 4
  tests_added: 0
---

# Phase 17 Plan 03: SOAR Playbook Frontend UI Summary

**One-liner:** Full SOAR execution frontend — PlaybooksView with library browser and step-by-step analyst-gated execution mode, InvestigationView Run Playbook button, and App.svelte navigation wiring for cross-view context passing.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | TypeScript types and api.ts playbook methods | 3b053ef | dashboard/src/lib/api.ts |
| 2 | PlaybooksView implementation and InvestigationView Run Playbook button | fff1e1f | dashboard/src/views/PlaybooksView.svelte, dashboard/src/views/InvestigationView.svelte |
| 3 | checkpoint:human-verify | auto-approved (auto_advance=true) | — |

## What Was Built

### TypeScript Interfaces (`dashboard/src/lib/api.ts`)

Six new interfaces:
- `PlaybookStep` — step_number, title, description, requires_approval, evidence_prompt
- `Playbook` — playbook_id, name, description, trigger_conditions, steps, version, is_builtin, created_at
- `PlaybookStepResult` — step_number, outcome ('confirmed'|'skipped'), analyst_note, completed_at
- `PlaybookRun` — run_id, playbook_id, investigation_id, status ('running'|'completed'|'cancelled'), started_at, completed_at, steps_completed, analyst_notes
- `PlaybooksListResponse` — playbooks[], total
- `PlaybookRunsListResponse` — runs[], total

Two api namespaces added:
- `api.playbooks` — list(), get(id), runs(id), startRun(playbookId, investigationId)
- `api.playbookRuns` — get(runId), advanceStep(runId, stepN, body), cancel(runId)

### PlaybooksView.svelte (Complete Rewrite)

**MODE A — Library Browser** (default):
- Loads playbooks via `api.playbooks.list()` in `$effect` on mount
- Cards show: name, version, built-in badge, description, trigger condition tags, step count
- "Run Playbook" button: disabled with tooltip when no investigationId; enabled when set
- Clicking calls `api.playbooks.startRun()` and transitions to MODE B

**MODE B — Execution View** (active run):
- Step checklist with color-coded circles (green=done, amber=current, grey=future)
- Current step: analyst note textarea + Confirm/Skip buttons; both disabled during API call
- Completed steps: CONFIRMED/SKIPPED outcome badge, analyst note, timestamp (read-only audit trail)
- evidence_prompt shown as italic hint when set
- "Run Completed" green banner when status=completed
- "Cancelled" red banner when status=cancelled
- "Cancel Run" danger button in header (running only)
- "Back to Library" returns to MODE A

### InvestigationView.svelte Changes

- Added `onRunPlaybook?: (investigationId: string) => void` prop
- "Run Playbook" button in Evidence Timeline panel header with green accent styling
- Disabled when investigationId is empty; calls `onRunPlaybook(investigationId)` on click

### App.svelte Navigation Wiring (Rule 2 deviation)

- `playbookInvestigationId` state holds the investigation context for PlaybooksView
- `handleRunPlaybook(id)` sets playbookInvestigationId and navigates to 'playbooks' view
- InvestigationView now receives `onRunPlaybook={handleRunPlaybook}`
- PlaybooksView now receives `investigationId={playbookInvestigationId}`

## Verification

```
# npm run check — no new errors (9 pre-existing GraphView/InvestigationPanel errors unchanged)
cd /c/Users/Admin/AI-SOC-Brain/dashboard && npm run check
# 105 FILES 9 ERRORS (all pre-existing) 3 WARNINGS

# Backend playbook tests
uv run pytest tests/unit/test_playbook_store.py tests/unit/test_playbook_execution.py -q
# 43 passed in 0.85s
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] App.svelte navigation wiring not in plan scope**
- **Found during:** Task 2 completion review
- **Issue:** Plan noted "executor does NOT need to modify App.svelte" but this would have left the `onRunPlaybook` callback permanently unconnected — the Run Playbook button would never navigate anywhere
- **Fix:** Added `playbookInvestigationId` state + `handleRunPlaybook()` function to App.svelte; wired props to both InvestigationView and PlaybooksView
- **Files modified:** dashboard/src/App.svelte
- **Commit:** ff6c064

## Self-Check: PASSED

Files exist:
- dashboard/src/lib/api.ts: FOUND
- dashboard/src/views/PlaybooksView.svelte: FOUND
- dashboard/src/views/InvestigationView.svelte: FOUND
- dashboard/src/App.svelte: FOUND

Commits exist:
- 3b053ef: FOUND (feat(17-03): add Playbook/PlaybookRun TypeScript types and api.playbooks/playbookRuns methods)
- fff1e1f: FOUND (feat(17-03): implement PlaybooksView execution UI and InvestigationView Run Playbook button)
- ff6c064: FOUND (fix(17-03): wire onRunPlaybook navigation in App.svelte)
