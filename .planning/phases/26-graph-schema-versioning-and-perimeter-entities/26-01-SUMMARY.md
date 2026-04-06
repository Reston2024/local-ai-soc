---
phase: 26-graph-schema-versioning-and-perimeter-entities
plan: "01"
subsystem: graph
tags: [schema, versioning, perimeter, sqlite, api]
dependency_graph:
  requires: ["26-00"]
  provides: ["26-02", "26-03", "26-04", "26-05"]
  affects: ["graph/schema.py", "backend/stores/sqlite_store.py", "backend/api/graph.py"]
tech_stack:
  added: []
  patterns: ["INSERT OR IGNORE + conditional UPDATE for idempotent version seeding", "route ordering guard — static routes before wildcard"]
key_files:
  created: []
  modified:
    - graph/schema.py
    - backend/stores/sqlite_store.py
    - backend/api/graph.py
decisions:
  - "firewall_zone and network_segment appended to ENTITY_TYPES; blocks/permits/traverses appended to EDGE_TYPES — strictly additive"
  - "two-step version seeding: INSERT OR IGNORE for pre-existing installs, conditional UPDATE for fresh installs"
  - "get_graph_schema_version() uses row[0] index (not row['value']) to handle both Row factory and tuple modes"
  - "GET /schema-version placed immediately before /{investigation_id} wildcard to avoid route capture"
metrics:
  duration: "~10 minutes"
  completed_date: "2026-04-06T17:41:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 3
requirements_satisfied: [P26-T01, P26-T02, P26-T04]
---

# Phase 26 Plan 01: Graph Schema Extension and Version Seeding Summary

**One-liner:** Perimeter entity/edge types added to graph schema; graph_schema_version auto-seeded in system_kv on startup with fresh-install detection.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend graph/schema.py with perimeter types | 8505861 | graph/schema.py |
| 2 | SQLiteStore version seeding + schema-version endpoint | 748ad00 | backend/stores/sqlite_store.py, backend/api/graph.py |

## What Was Built

### Task 1 — graph/schema.py (P26-T02)

ENTITY_TYPES extended from 11 to 13 types (strictly additive):
- `firewall_zone` — IPFire/netfilter zone (zone_name, zone_color, interface)
- `network_segment` — IP subnet/CIDR block (cidr, zone, description)

EDGE_TYPES extended from 12 to 15 types (strictly additive):
- `blocks` — firewall_zone blocks traffic to ip/network_segment
- `permits` — firewall_zone permits traffic to ip/network_segment
- `traverses` — traffic crossed a zone boundary

All 11 original entity types and 12 original edge types remain unchanged. The frozenset sentinels rebuild automatically at import time.

### Task 2 — sqlite_store.py + graph.py (P26-T01)

**SQLiteStore.__init__ version seeding (two-step):**
- Step 1: `INSERT OR IGNORE` seeds `graph_schema_version = 1.0.0` for pre-existing installs (no-op if key already exists)
- Step 2: If `entities` table is empty, `UPDATE` sets version to `2.0.0` (fresh install detection)

**`get_graph_schema_version()` helper:** Reads `graph_schema_version` from `system_kv`, returns `"1.0.0"` as fallback.

**GET /graph/schema-version endpoint:** Added before the `/{investigation_id}` wildcard route to prevent route capture. Returns `{"graph_schema_version": "<version>"}`.

## Verification Results

- `len(ENTITY_TYPES) == 13` — confirmed
- `len(EDGE_TYPES) == 15` — confirmed
- `is_valid_entity_type("firewall_zone")` — True
- `is_valid_entity_type("network_segment")` — True
- `is_valid_edge_type("blocks")`, `is_valid_edge_type("permits")`, `is_valid_edge_type("traverses")` — all True
- Fresh install returns version `2.0.0` — confirmed
- Pre-existing install returns version `1.0.0` — confirmed
- 28 graph API tests pass — confirmed
- 835 total unit tests pass, 0 regressions — confirmed

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

- [x] `graph/schema.py` modified — FOUND
- [x] `backend/stores/sqlite_store.py` modified — FOUND
- [x] `backend/api/graph.py` modified — FOUND
- [x] Commit 8505861 — FOUND (feat(26-01): extend graph schema)
- [x] Commit 748ad00 — FOUND (feat(26-01): add graph_schema_version seeding)

## Self-Check: PASSED
