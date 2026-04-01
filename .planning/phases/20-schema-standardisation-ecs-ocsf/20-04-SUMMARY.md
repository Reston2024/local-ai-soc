---
phase: 20-schema-standardisation-ecs-ocsf
plan: "04"
subsystem: detections
tags: [sigma, ecs, field-mapping, smoke-tests]
dependency_graph:
  requires: [20-01, 20-02]
  provides: [ECS-dotted-path Sigma field translation, Windows domain field mappings]
  affects: [detections/matcher.py]
tech_stack:
  added: []
  patterns: [SIGMA_FIELD_MAP extension, smoke test assertions]
key_files:
  created:
    - tests/sigma_smoke/test_ecs_field_map.py
  modified:
    - detections/field_map.py
decisions:
  - "22 new entries added purely additively — no existing entry touched; ECS dotted-path keys coexist with PascalCase Windows keys"
  - "INTEGER_COLUMNS deliberately unchanged — network_protocol, event_outcome, user_domain, process_executable, network_direction are TEXT and must not appear there"
metrics:
  duration: "~2 minutes"
  completed_date: "2026-04-01"
  tasks_completed: 2
  files_changed: 2
---

# Phase 20 Plan 04: Extend SIGMA_FIELD_MAP with ECS dotted-path and Windows domain entries Summary

Extended SIGMA_FIELD_MAP in detections/field_map.py with 22 new entries — 18 ECS dotted-path names (pySigma ECS pipeline compatibility) and 4 Windows domain/outcome names — plus 7 new smoke tests confirming correctness and INTEGER_COLUMNS integrity.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add ECS and Windows domain entries to SIGMA_FIELD_MAP | 8bf4d6a | detections/field_map.py |
| 2 | Add ECS field mapping smoke tests | 3eee23f | tests/sigma_smoke/test_ecs_field_map.py |

## What Was Built

### Task 1 — SIGMA_FIELD_MAP extension

Added two comment-delimited sections at the end of the map in `detections/field_map.py`:

**ECS dotted-path entries (18):**
- `process.*` — process_name, process_id, command_line, process_executable, parent_process_name, parent_process_id
- `user.*` — username, user_domain
- `host.hostname` — hostname
- `source.*` / `destination.*` — src_ip, src_port, dst_ip, dst_port, domain
- `file.*` — file_path, file_hash_sha256
- `network.protocol` — network_protocol
- `dns.question.name` — domain

**Windows Sigma field name entries (4):**
- EventOutcome → event_outcome
- SubjectDomainName → user_domain
- TargetDomainName → user_domain
- DomainName → user_domain

INTEGER_COLUMNS unchanged — the new TEXT columns (network_protocol, event_outcome, user_domain, process_executable, network_direction) are correctly excluded.

### Task 2 — ECS smoke tests

Created `tests/sigma_smoke/test_ecs_field_map.py` with 7 test functions:
- test_ecs_process_fields
- test_ecs_user_fields
- test_ecs_network_fields
- test_ecs_file_fields
- test_windows_domain_fields
- test_original_entries_unchanged (regression guard)
- test_new_text_columns_not_in_integer_columns

## Verification Results

- sigma_smoke suite: 29 passed, 1 skipped (pre-existing skip — no regressions)
- All 7 new smoke tests pass
- All 22 original tests pass unchanged
- SIGMA_FIELD_MAP total: 52 entries (30 original + 22 new)

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- detections/field_map.py — FOUND, contains "process.name"
- tests/sigma_smoke/test_ecs_field_map.py — FOUND, contains "test_new_text_columns_not_in_integer_columns"
- Commit 8bf4d6a — FOUND
- Commit 3eee23f — FOUND
