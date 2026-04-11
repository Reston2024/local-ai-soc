---
phase: 36-zeek-full-telemetry
plan: "03"
subsystem: frontend-chips + sigma-field-map
tags: [zeek, eventsview, sigma, field-map, chips]
dependency_graph:
  requires: [36-01, 36-02]
  provides: [zeek-ui-chips, zeek-sigma-fields]
  affects: [EventsView.svelte, detections/field_map.py]
tech_stack:
  added: []
  patterns: [zeek-event-type-chips, sigma-ecs-field-mapping]
key_files:
  created: []
  modified:
    - dashboard/src/views/EventsView.svelte
    - detections/field_map.py
decisions:
  - "Added zeek.conn.orig_bytes and zeek.conn.resp_bytes mappings (17 total vs 15 planned) to satisfy test_integer_columns_are_subset_of_field_map_values assertion"
  - "Pre-existing failures from incomplete 36-01/36-02 plans left in place — 14 failures pre-existed this plan (zeek_normalizers, malcolm_collector, normalized_event tests)"
metrics:
  duration: "~12 minutes"
  completed: "2026-04-10"
  tasks_completed: 2
  tasks_total: 3
  files_modified: 2
---

# Phase 36 Plan 03: Zeek UI Chips + Sigma Field Map Summary

Closed the loop between the Phase 36 backend pipeline and the analyst-facing UI layer. Fixed broken ZEEK_CHIPS filter chips in EventsView (two chips had wrong event_type values returning zero results) and updated the Sigma field map with 17 Zeek ECS field mappings for detection rule authoring.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix ZEEK_CHIPS in EventsView.svelte | d92e52b | dashboard/src/views/EventsView.svelte |
| 2 | Update Sigma field_map.py + bump FIELD_MAP_VERSION to 22 | 0547a01 | detections/field_map.py |
| 3 | Smoke test DuckDB Zeek event_type coverage | SKIP | Skipped — 36-02 normalizers landed post-36-03 execution; requires backend restart + poll cycle. SPAN confirmed live (412,158 Malcolm docs). Run after next collector poll. |

## What Was Built

**Task 1 — EventsView.svelte ZEEK_CHIPS fix:**
- Removed broken `value: 'auth'` chip (no normalizer produces event_type='auth')
- Changed `value: 'smb'` → `value: 'smb_files'` (matches actual normalizer output)
- Added 6 new chips: Kerberos (kerberos_tgs_request), NTLM (ntlm_auth), RDP (rdp), Weird (weird), Notice (notice) — dropping one duplicate
- Final chip count: 12 chips with correct event_type values
- Updated divider label from "Phase 36" → "Zeek" with active SPAN port title text
- EventsView.svelte compiles without TypeScript errors

**Task 2 — field_map.py Zeek ECS mappings:**
- Added 17 Zeek ECS field mappings (15 planned + 2 for conn.orig_bytes/conn.resp_bytes)
- FIELD_MAP_VERSION bumped 21 → 22
- INTEGER_COLUMNS expanded: added conn_orig_bytes, conn_resp_bytes, ssh_version
- All 50 matcher + zeek_fields unit tests pass

## Smoke Test — Task 3 (Pending)

Task 3 is a `checkpoint:human-action` gate requiring live Malcolm traffic. To run:

```python
import duckdb
con = duckdb.connect("data/events.duckdb")
result = con.execute("""
    SELECT event_type, count(*) as cnt
    FROM normalized_events
    WHERE source_type = 'zeek'
      AND event_type IN (
        'conn', 'weird', 'http', 'ssl', 'x509', 'files', 'notice',
        'kerberos_tgs_request', 'ntlm_auth', 'ssh', 'smb_mapping',
        'smb_files', 'rdp', 'dhcp', 'dns_query'
      )
    GROUP BY event_type
    ORDER BY cnt DESC
""").fetchall()
print(result)
```

Expected: 15+ distinct rows (P36-T12 requirement). Minimum acceptable: 3+ event_types with cnt > 0.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added conn.orig_bytes and conn.resp_bytes ECS field mappings**
- **Found during:** Task 2 verification
- **Issue:** test_integer_columns_are_subset_of_field_map_values asserts every INTEGER_COLUMN must have a corresponding SIGMA_FIELD_MAP entry. The plan listed conn_orig_bytes and conn_resp_bytes as INTEGER_COLUMNS but omitted their ECS field mappings.
- **Fix:** Added `zeek.conn.orig_bytes` → `conn_orig_bytes` and `zeek.conn.resp_bytes` → `conn_resp_bytes` to SIGMA_FIELD_MAP. Total Zeek mappings: 17 (vs 15 planned).
- **Files modified:** detections/field_map.py
- **Commit:** 0547a01

### Pre-existing Failures (Out of Scope)

14 unit test failures exist from incomplete Phase 36 plans 01 and 02 work:
- tests/unit/test_zeek_normalizers.py — 11 failures (normalizers not yet implemented)
- tests/unit/test_normalized_event.py — 1 failure
- tests/unit/test_normalized_event_ecs.py — 1 failure
- tests/unit/test_malcolm_collector.py — 1 failure (new cursor keys)

These were present before this plan executed (confirmed via git stash). Logged to deferred-items for Phase 36 cleanup.

## Verification Results

```
field_map OK — 17 Zeek mappings, version=22
INTEGER_COLUMNS=['conn_orig_bytes', 'conn_resp_bytes', 'dst_port', 'parent_process_id', 'process_id', 'src_port', 'ssh_version']
```

```
tests/unit/test_matcher.py: 42 passed
tests/unit/test_zeek_fields.py: 8 passed
Total: 50 passed (field-map relevant tests)
```

## Self-Check: PASSED

- dashboard/src/views/EventsView.svelte: FOUND
- detections/field_map.py: FOUND
- Commit d92e52b (Task 1): FOUND
- Commit 0547a01 (Task 2): FOUND
