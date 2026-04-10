---
phase: 35-soc-completeness
plan: "35-01"
title: "Broken flow fixes + quick wins"
subsystem: backend-api, detections, dashboard
tags: [explain, timeline, field-map, zeek, frontend, tdd]
dependency_graph:
  requires: []
  provides: [explain-structured-error, playbook-timeline-rows, zeek-field-map-entries]
  affects: [backend/api/explain.py, backend/api/timeline.py, detections/field_map.py, dashboard]
tech_stack:
  added: []
  patterns: [early-return guard, asyncio.to_thread fallback, TDD wave-0 stubs]
key_files:
  created:
    - tests/unit/test_explain.py
    - tests/unit/test_field_map.py
    - tests/unit/test_timeline_merge_playbooks.py
  modified:
    - backend/api/explain.py
    - backend/api/timeline.py
    - detections/field_map.py
    - dashboard/src/App.svelte
    - dashboard/src/views/EventsView.svelte
decisions:
  - "explain.py early return uses structured ExplainResponse (not exception) so frontend always gets parseable JSON"
  - "_fetch_playbook_rows is module-level (not nested) for unit-testability; falls back silently when table absent"
  - "ZEEK_CHIPS now fully active (no disabled/chip-beta) — managed switch arrived and SPAN port confirmed active"
  - "4 Intelligence nav items lose beta tag; Playbooks and Recommendations retain beta"
  - "FIELD_MAP_VERSION bumped 20→21 to track the new Zeek ECS entries"
metrics:
  duration_minutes: 4
  completed_date: "2026-04-10"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 5
---

# Phase 35 Plan 01: Broken Flow Fixes + Quick Wins Summary

**One-liner:** Structured early-return in explain.py + playbook_runs timeline wiring + Zeek ECS field-map entries + ZEEK_CHIPS and nav beta-flag cleanup.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wave 0 test stubs + explain.py early return + field_map Zeek entries | 4623c2a | test_explain.py, test_field_map.py, explain.py, field_map.py |
| 2 | Wire playbook_runs into timeline + frontend quick wins | 1c511f5 | test_timeline_merge_playbooks.py, timeline.py, App.svelte, EventsView.svelte |

## What Was Built

### Task 1: explain.py early return + field_map Zeek entries

**explain.py** — Added early return guard in `_run_explanation()` after the investigation assembly block. When `investigation == {}` (detection not found in store), the function now returns a structured `ExplainResponse` with `what_happened="No investigation context found for detection_id: {det_id}"` instead of proceeding to `build_evidence_context()` and crashing or returning garbage to the frontend.

**detections/field_map.py** — Added three Zeek/ECS dotted-field aliases that Sigma rules use when matching against Zeek-sourced events:
- `dns.query.name` → `dns_query`
- `http.user_agent` → `http_user_agent`
- `tls.client.ja3` → `tls_ja3`

`FIELD_MAP_VERSION` bumped from `"20"` to `"21"`.

### Task 2: Timeline playbook wiring + frontend fixes

**backend/api/timeline.py** — Two changes:
1. `merge_and_sort_timeline()` — replaced the "intentionally unused" comment with a real loop that produces `TimelineItem(item_type="playbook", title="Playbook: {name} — {status}", ...)` entries from `playbook_rows` dicts.
2. `get_investigation_timeline()` — replaced `playbook_rows: list[dict] = []` stub with a real `asyncio.to_thread()` call to `_fetch_playbook_rows(conn, investigation_id)` which executes `SELECT ... FROM playbook_runs JOIN playbooks ... WHERE investigation_id = ?`. Safe fallback on `OperationalError` when table absent.

**dashboard/src/App.svelte** — Removed `beta: true` from the four Intelligence group nav items: Threat Intel, ATT&CK Coverage, Hunting, Threat Map. Playbooks and Recommendations retain `beta: true`.

**dashboard/src/views/EventsView.svelte** — Removed `disabled` attribute and `chip-beta` class from the `{#each ZEEK_CHIPS}` render block. Chips are now fully interactive (no greyed/dashed state). The `chip-beta` CSS rule left in place harmlessly.

## Test Results

| File | Tests | Result |
|------|-------|--------|
| tests/unit/test_explain.py | 2 | PASS |
| tests/unit/test_field_map.py | 3 | PASS |
| tests/unit/test_timeline_merge_playbooks.py | 4 | PASS |
| tests/unit/ (full suite) | 953 passed, 1 pre-existing failure | PASS |

The pre-existing failure (`test_config.py::test_cybersec_model_default`) was present before this plan and is unrelated to these changes.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- tests/unit/test_explain.py: EXISTS and passes
- tests/unit/test_field_map.py: EXISTS and passes
- tests/unit/test_timeline_merge_playbooks.py: EXISTS and passes
- backend/api/explain.py: contains "No investigation context found"
- detections/field_map.py: contains dns_query, http_user_agent, tls_ja3
- backend/api/timeline.py: contains "Playbook:" in merge loop
- Commits 4623c2a and 1c511f5: verified in git log
