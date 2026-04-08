---
phase: 28-dashboard-integration-fixes
plan: "03"
subsystem: dashboard
tags: [api-client, typescript, pagination, field-names, integration-fix]
dependency_graph:
  requires: [28-02]
  provides: [correct-events-pagination, correct-normalized-event-types]
  affects: [dashboard/src/views/EventsView.svelte]
tech_stack:
  added: []
  patterns: [offset-to-page-translation, backend-shape-matching]
key_files:
  modified:
    - dashboard/src/lib/api.ts
decisions:
  - "INT-05: Translate offset/limit to 1-indexed page/page_size inside api.events.list() — callers (EventsView.svelte) unchanged, function signature kept the same"
  - "INT-06: raw_event typed as string | null (not Record<string,unknown>) matching backend Optional[str] — views needing structured access should JSON.parse at display time"
  - "Pre-existing svelte-check errors in GraphView.svelte, InvestigationPanel.svelte, ProvenanceView.svelte are out-of-scope and logged as deferred items"
metrics:
  duration: "~8 minutes"
  completed_date: "2026-04-08T15:34:37Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 1
---

# Phase 28 Plan 03: Dashboard API Client Integration Fixes (INT-05, INT-06) Summary

**One-liner:** Pagination translation (offset→page) and NormalizedEvent field renames (process_pid→process_id, raw_data→raw_event) in api.ts to match backend shape.

## What Was Built

Fixed two LOW-severity integration gaps in `dashboard/src/lib/api.ts`:

**INT-05 — Pagination translation:**
- `api.events.list()` previously sent `?offset=N&limit=N` which the backend ignores
- Now computes `page = Math.floor(offset / limit) + 1` and sends `?page=N&page_size=N`
- `EventsListResponse` interface updated: `offset`/`limit` removed, `page`/`page_size`/`has_next` added
- Function signature unchanged — `EventsView.svelte` needs no modification

**INT-06 — NormalizedEvent field renames:**
- `process_pid: number | null` → `process_id: number | null` (backend: `process_id: Optional[int]`)
- `raw_data: Record<string, unknown>` → `raw_event: string | null` (backend: `raw_event: Optional[str]`)

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix pagination translation in api.ts (INT-05) | 96d5dde | dashboard/src/lib/api.ts |
| 2 | Fix NormalizedEvent field names in api.ts (INT-06) | d039a40 | dashboard/src/lib/api.ts |

## Verification Results

All spot checks pass:
- `Math.floor(offset / limit) + 1` present at line 339
- `process_pid` and `raw_data` — 0 matches in `dashboard/src/`
- `process_id: number | null` at line 17, `raw_event: string | null` at line 20
- `has_next: boolean` at line 30 in `EventsListResponse`

svelte-check: 10 pre-existing errors (GraphView.svelte cytoscape types, InvestigationPanel.svelte, ProvenanceView.svelte) — unchanged before and after this plan. 0 new errors introduced.

## Deviations from Plan

### Out-of-Scope Issues Noted

Pre-existing svelte-check errors in files not touched by this plan:
- `GraphView.svelte`: cytoscape-fcose/cytoscape-dagre missing type declarations, `hide`/`show` method types, oncynodetap event
- `InvestigationPanel.svelte`: NodeSingular PropertyValue type mismatch
- `ProvenanceView.svelte`: provenance function union type cast

These are logged but not fixed per the scope boundary rule (not caused by this plan's changes).

## Self-Check

Files verified:
- `dashboard/src/lib/api.ts`: FOUND and contains all required changes

Commits verified:
- 96d5dde: FOUND (Task 1 — pagination translation)
- d039a40: FOUND (Task 2 — field renames)

## Self-Check: PASSED
