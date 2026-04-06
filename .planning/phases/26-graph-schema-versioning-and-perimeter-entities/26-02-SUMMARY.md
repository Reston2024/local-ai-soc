---
phase: 26-graph-schema-versioning-and-perimeter-entities
plan: "02"
subsystem: ingestion/graph
tags: [perimeter, ipfire, entity-extraction, graph, loader]
dependency_graph:
  requires:
    - 26-01  # graph schema versioning groundwork
  provides:
    - extract_perimeter_entities() function in entity_extractor.py
    - IPFire syslog perimeter edge emission in loader._write_graph()
  affects:
    - ingestion/loader.py
    - ingestion/entity_extractor.py
    - backend/stores/sqlite_store.py (read-only; method names confirmed)
tech_stack:
  added: []
  patterns:
    - Pure extraction function with (entities, edges) return shape
    - Comma-separated string tags parsing (matching NormalizedEvent.tags format)
    - Conditional wiring in _sync_write_graph() for source_type == ipfire_syslog
key_files:
  created:
    - tests/unit/test_loader_ipfire_pipeline.py
  modified:
    - ingestion/entity_extractor.py
    - ingestion/loader.py
decisions:
  - "Tags are comma-separated strings in NormalizedEvent.tags (not a list), so extract_perimeter_entities() splits on comma before scanning for zone: prefix"
  - "Used get_edges_from(entity_id, depth=1) in tests instead of non-existent get_edges_for_entity(); no new SQLiteStore methods added"
  - "ingested_at is a required field on NormalizedEvent; tests populate it explicitly"
metrics:
  duration: "~20 minutes"
  completed: 2026-04-06
  tasks_completed: 4
  files_modified: 3
  tests_added: 3
---

# Phase 26 Plan 02: Perimeter Entity Extraction Summary

**One-liner:** IPFire syslog events now emit `firewall_zone` + `ip` entities and `blocks`/`traverses`/`permits` edges to SQLite via a pure `extract_perimeter_entities()` function wired into `loader._write_graph()`.

## What Was Built

### Task 1: extract_perimeter_entities() (ingestion/entity_extractor.py)

Appended a new function after the existing `extract_entities_and_edges()` — no existing code modified.

Key behaviors:
- Returns `([], [])` for non-IPFire events and events without `dst_ip` (safe to call unconditionally)
- Parses `event.tags` as a comma-separated string (e.g. `"in:red0,zone:red"`) to extract the `zone:*` label
- Produces a `firewall_zone` entity with `zone_color` in uppercase (RED, GREEN, BLUE, ORANGE)
- Produces a destination `ip` entity
- Edge type selection: `failure` -> `blocks`; `success` + both IPs -> `traverses`; `success` + dst only -> `permits`
- Only emits an edge when zone is known (zone tag present in event.tags)

### Task 2: Loader wiring (ingestion/loader.py)

- Updated import: `from ingestion.entity_extractor import extract_entities_and_edges, extract_perimeter_entities`
- Added conditional block inside `_sync_write_graph()`'s per-event `try:` after the existing edge loop:
  - Calls `extract_perimeter_entities(event)` for `source_type == "ipfire_syslog"` only
  - Writes perimeter entities via `sqlite.upsert_entity()` and edges via `sqlite.insert_edge()`
  - Increments `local_edges` for each new edge (matching existing pattern)

### Task 3: Pipeline tests (tests/unit/test_loader_ipfire_pipeline.py)

Three async tests using real `SQLiteStore` (tmp_path) with mocked DuckDB and Chroma:

1. `test_loader_ipfire_drop_produces_blocks_edge` — DROP event (event_outcome=failure) -> `blocks` edge from `firewall_zone:red` in SQLite
2. `test_loader_ipfire_forward_produces_traverses_edge` — FORWARDFW event (both IPs, success) -> `traverses` edge from `firewall_zone:green`
3. `test_loader_non_ipfire_no_firewall_zone_entity` — Windows EVTX event -> no `firewall_zone:red` entity in SQLite

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tags are comma-separated strings, not lists**
- **Found during:** Task 3 (test failure)
- **Issue:** The plan template showed `tags=["zone:red"]` (a list) but `NormalizedEvent.tags` is `Optional[str]` — a comma-separated string matching the DuckDB schema. Iterating `event.tags or []` on a string produces individual characters.
- **Fix:** Changed `extract_perimeter_entities()` to split `event.tags` on commas before scanning for the `zone:` prefix. Tests pass `",".join(tags)` to the model constructor.
- **Files modified:** `ingestion/entity_extractor.py`, `tests/unit/test_loader_ipfire_pipeline.py`
- **Commit:** 6c5b0e3

**2. [Rule 1 - Bug] NormalizedEvent requires ingested_at**
- **Found during:** Task 3 (validation error)
- **Issue:** `ingested_at` is a required field on `NormalizedEvent` but was omitted in the plan's test template.
- **Fix:** Added `ingested_at=datetime(2026, 1, 1, tzinfo=timezone.utc)` to all test event constructors.
- **Files modified:** `tests/unit/test_loader_ipfire_pipeline.py`
- **Commit:** 533bf8f

**3. [Rule 3 - Adaptation] SQLiteStore has no get_edges_for_entity()**
- **Found during:** Task 3 planning (pre-emptive check)
- **Issue:** Plan template used `sqlite.get_edges_for_entity(entity_id)` which does not exist. SQLiteStore provides `get_edges_from(entity_id, depth)` and `get_edges_to(entity_id)`.
- **Fix:** Tests use `sqlite.get_edges_from("firewall_zone:red", depth=1)` — which returns outbound edges from the firewall zone source entity.
- **Files modified:** `tests/unit/test_loader_ipfire_pipeline.py`
- **Commit:** 533bf8f

## Verification Results

```
uv run pytest tests/unit/test_entity_extractor.py tests/unit/test_entity_extractor_ecs.py -x -q
-> 21 passed (no regressions)

uv run pytest tests/unit/test_loader_ipfire_pipeline.py -x -v
-> 3 passed

uv run pytest tests/unit/ -x -q
-> 838 passed, 13 skipped, 9 xfailed, 7 xpassed, 0 failures
```

## Commits

- `6c5b0e3` — feat(26-02): add extract_perimeter_entities() and wire into loader._write_graph()
- `533bf8f` — test(26-02): add pipeline tests for IPFire perimeter edge emission

## Self-Check: PASSED

- `ingestion/entity_extractor.py` modified — confirmed present
- `ingestion/loader.py` modified — confirmed present
- `tests/unit/test_loader_ipfire_pipeline.py` created — confirmed present
- Commits 6c5b0e3 and 533bf8f — confirmed in git log
