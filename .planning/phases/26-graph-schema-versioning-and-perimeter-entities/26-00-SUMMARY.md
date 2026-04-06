---
phase: 26-graph-schema-versioning-and-perimeter-entities
plan: "00"
subsystem: graph-schema-testing
tags: [testing, graph, schema, versioning, tdd, wave-0, stubs]
dependency_graph:
  requires: []
  provides:
    - tests/unit/test_graph_schema.py (7 wave-0 stubs for P26-T02, T03, T04)
    - tests/unit/test_graph_versioning.py (5 wave-0 stubs for P26-T01, T04)
  affects:
    - graph/schema.py (targeted by schema stub assertions)
    - backend/stores/sqlite_store.py (targeted by versioning stub assertions)
    - ingestion/entity_extractor.py (forward-declared in perimeter entity stubs)
tech_stack:
  added: []
  patterns:
    - pytestmark module-level skip for wave-0 stubs (same as phase 25)
    - forward-declared imports wrapped in try/except inside test bodies
    - _build_app helper replicated from test_graph_api.py for endpoint stub
key_files:
  created:
    - tests/unit/test_graph_schema.py
    - tests/unit/test_graph_versioning.py
  modified: []
decisions:
  - "26-00: pytestmark module-level skip used (not per-test) — single decorator activates all 12 stubs in plan 26-05"
  - "26-00: extract_perimeter_entities import wrapped in try/except inside test body to avoid module-level ImportError breaking skip mechanism"
  - "26-00: test_preexisting_install_gets_version_1 bootstraps schema via first SQLiteStore then injects row directly via sqlite3 — avoids coupling stub to not-yet-implemented seeding logic"
  - "26-00: test_system_kv_not_clobbered uses INSERT OR REPLACE to pre-set key, then re-opens store — verifies INSERT OR IGNORE semantics without assuming system_kv table exists before SQLiteStore init"
metrics:
  duration_minutes: 8
  completed_date: "2026-04-06"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 26 Plan 00: Graph Schema Versioning — Wave-0 Test Stubs Summary

Wave-0 Nyquist compliance stubs for graph schema versioning and perimeter entity extraction — 12 skipped tests covering all 4 phase requirements before any production code is written.

## What Was Built

Two pre-skipped test stub files that define the complete automated test surface for phase 26:

- `tests/unit/test_graph_schema.py` — 7 stubs targeting graph/schema.py constants (P26-T02, P26-T03, P26-T04)
- `tests/unit/test_graph_versioning.py` — 5 stubs targeting SQLiteStore versioning + API endpoint (P26-T01, P26-T04)

All 12 tests collect and show as SKIPPED. Full unit suite: 901 passed, 14 skipped, 0 failures.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create test_graph_schema.py stubs (P26-T02, T03, T04) | 3717eee | tests/unit/test_graph_schema.py |
| 2 | Create test_graph_versioning.py stubs (P26-T01, T04) | 63d1aea | tests/unit/test_graph_versioning.py |

## Requirement Coverage

| Requirement | Stub Functions |
|-------------|----------------|
| P26-T01 | test_fresh_install_gets_version_2, test_preexisting_install_gets_version_1, test_schema_version_endpoint |
| P26-T02 | test_firewall_zone_in_entity_types, test_network_segment_in_entity_types |
| P26-T03 | test_new_edge_types_present, test_extract_perimeter_entities_blocks, test_extract_perimeter_entities_permits |
| P26-T04 | test_pre_existing_entity_types_preserved, test_pre_existing_edge_types_preserved, test_system_kv_not_clobbered, test_no_columns_removed |

## Decisions Made

- pytestmark module-level skip used (not per-test) — single decorator activates all 12 stubs in plan 26-05
- extract_perimeter_entities import wrapped in try/except inside test body to avoid module-level ImportError breaking skip mechanism
- test_preexisting_install_gets_version_1 bootstraps schema via first SQLiteStore then injects row directly via sqlite3
- test_system_kv_not_clobbered uses INSERT OR REPLACE to pre-set key, then re-opens store to verify INSERT OR IGNORE semantics

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- tests/unit/test_graph_schema.py: FOUND (167 lines, 7 stubs, all SKIPPED)
- tests/unit/test_graph_versioning.py: FOUND (186 lines, 5 stubs, all SKIPPED)
- Commit 3717eee: test_graph_schema.py stubs
- Commit 63d1aea: test_graph_versioning.py stubs
- Full suite: 901 passed, 0 failures
