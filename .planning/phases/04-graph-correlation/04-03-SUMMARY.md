---
phase: 04-graph-correlation
plan: "03"
subsystem: graph-correlation
tags: [graph, correlation, temporal, dns-chain, attack-paths, fastapi]
dependency_graph:
  requires: [04-02]
  provides: [temporal-correlation-engine, graph-correlate-endpoint]
  affects: [dashboard-threat-graph]
tech_stack:
  added: []
  patterns:
    - Union-Find attack path grouping extended with correlation edges
    - defaultdict-based grouping for DNS repeated query pattern
    - Temporal sliding window with per-event edge cap for proximity correlation
    - ISO timestamp sort + delta comparison for DNS-chain pattern
key_files:
  created: []
  modified:
    - backend/src/graph/builder.py
    - backend/src/api/routes.py
decisions:
  - "_correlate() returns list[GraphEdge] merged with base edges before attack_path grouping"
  - "Edge counter starts at 10000 to avoid collision with _extract_edges simple counters"
  - "Pattern 4 prefers ip node over host node when src_ip/dst_ip available in node map"
  - "investigation_thread resolved as first AttackPath containing any of target's primary entity nodes"
metrics:
  duration_seconds: 108
  completed_date: "2026-03-16"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 4 Plan 03: Correlation Engine + Full /graph/correlate Summary

**One-liner:** Temporal + entity correlation engine (_correlate with 4 patterns) wired into build_graph, plus full GET /graph/correlate returning investigation_thread and live graph.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add _correlate() to builder.py with 4 correlation patterns | 729e043 | backend/src/graph/builder.py |
| 2 | Replace GET /graph/correlate scaffold with full implementation | 123c821 | backend/src/api/routes.py |

## What Was Built

### _correlate() — 4 Correlation Patterns

Added to `backend/src/graph/builder.py`:

**Pattern 1 — Repeated DNS:** Groups events by `query` field; when >=2 dns/dns_query events share the same domain, emits `related_event` edges between their respective host nodes. Domain node must exist in graph. Capped at `MAX_PROXIMITY_EDGES_PER_EVENT` (10) per event.

**Pattern 2 — DNS → Connection Chain:** Sorts all events by timestamp. For each dns_query event, scans forward within `DNS_CHAIN_WINDOW_SEC` (60s) for a `connection` event on the same host with a `dst_ip`. Emits `related_event` edge from `domain:{query}` to `ip:{dst_ip}` when both nodes exist.

**Pattern 3 — Shared Entity Alerts:** Groups `alert_trigger` edges by their destination entity node. When >=2 alert nodes point to the same entity, emits `related_event` edges between alert nodes.

**Pattern 4 — Temporal Proximity:** Groups events by host; within each host's sorted event list, emits `related_event` edges for pairs within `PROXIMITY_WINDOW_SEC` (30s). Prefers ip nodes over host node. Capped at `MAX_PROXIMITY_EDGES_PER_EVENT` per event.

**Integration:** `build_graph()` now calls `_correlate(events, nodes, edges)` and merges correlation edges (`all_edges = edges + corr_edges`) before building attack paths and stats.

### GET /graph/correlate — Full Implementation

Replaced placeholder scaffold in `backend/src/api/routes.py`:

- Finds target event by `event_id`; returns 404 if not found
- Collects correlated events sharing `host`, `src_ip`, `dst_ip`, or `query` with target
- Collects correlated alerts whose `event_id` is in the correlated event set
- Builds full `GraphResponse` via `build_graph(all_events, correlated_alerts)`
- Resolves `investigation_thread` as the first `AttackPath` containing any of the target's entity nodes
- Returns: `event_id`, `correlated_event_count`, `correlated_alert_count`, `graph` (full GraphResponse), `investigation_thread` (AttackPath or null)

## Verification Results

```
backend/src/tests/test_phase4.py - 9 xpassed
  TestGraphModels::test_graphnode_has_new_fields        XPASS
  TestNodeExtraction::test_extract_nodes_emits_host_node XPASS
  TestEdgeExtraction::test_extract_edges_emits_connection_edge XPASS
  TestCorrelation::test_correlate_dns_chain             XPASS  ← was XFAIL before this plan
  TestAttackPaths::test_group_attack_paths_returns_list  XPASS
  TestGraphAPI::test_get_graph_has_attack_paths_and_stats XPASS
  TestAlertGraph::test_alert_trigger_edge_created        XPASS
  TestCorrelateRoute::test_get_graph_correlate_returns_200 XPASS
  TestCorrelateRoute::test_get_graph_correlate_unknown_returns_404 XPASS

Full suite: 41 passed, 9 xpassed — 0 failures, 0 errors
```

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| _correlate() returns list[GraphEdge] merged with base edges before attack_path grouping | Ensures attack paths see all edges including correlation ones |
| Edge counter starts at 10000 | Avoids ID collision with _extract_edges simple incremental counters |
| Pattern 4 prefers ip node over host node | More specific entity linkage when IP is available |
| investigation_thread resolved via first AttackPath with any target entity node | Simple lookup sufficient; full BFS not needed for endpoint |

## Self-Check: PASSED

- backend/src/graph/builder.py: FOUND
- backend/src/api/routes.py: FOUND
- Commit 729e043: FOUND
- Commit 123c821: FOUND
