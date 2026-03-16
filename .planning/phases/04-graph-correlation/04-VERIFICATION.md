---
phase: 04-graph-correlation
verified: 2026-03-16T00:00:00Z
status: passed
score: 7/7 must-haves verified
re_verification: false
human_verification:
  - test: "Open dashboard in browser, ingest 3-5 events with overlapping hosts/IPs, view /graph"
    expected: "ThreatGraph renders with attack-path-highlight border on path nodes, node detail panel opens on click showing evidence events"
    why_human: "Cytoscape rendering, CSS class application, and side panel interaction cannot be verified programmatically"
  - test: "POST two dns events with the same query field from different hosts, then GET /graph"
    expected: "related_event edge appears between the two host nodes"
    why_human: "End-to-end correlation output in live API response requires running server with real in-memory state"
---

# Phase 4: Graph + Correlation Verification Report

**Phase Goal:** Enhance existing graph builder to correlate multiple security events, reconstruct attack paths, produce richer /graph API response with attack_paths/stats/correlated edges, and enhance frontend graph visualization. No regressions on prior phases.
**Verified:** 2026-03-16
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                 | Status      | Evidence                                                                              |
|----|---------------------------------------------------------------------------------------|-------------|---------------------------------------------------------------------------------------|
| 1  | GraphNode has attributes, first_seen, last_seen, evidence fields                     | VERIFIED   | `backend/src/api/models.py` lines 46-52: all four fields present with correct types  |
| 2  | GraphEdge uses src and dst fields (not source/target)                                | VERIFIED   | `backend/src/api/models.py` lines 55-61: `src: str`, `dst: str` — no source/target  |
| 3  | GraphResponse has attack_paths and stats fields alongside nodes and edges             | VERIFIED   | `backend/src/api/models.py` lines 73-77: `attack_paths` + `stats` with Field defaults |
| 4  | GET /graph returns JSON with nodes, edges, attack_paths, stats keys                  | VERIFIED   | `backend/src/api/routes.py` line 112: `build_graph(_events, _alerts)` with GraphResponse model; TestGraphAPI XPASS |
| 5  | build_graph accepts both events and alerts arguments                                 | VERIFIED   | `backend/src/graph/builder.py` line 459: `def build_graph(events: list[dict], alerts: list[dict])` |
| 6  | _correlate() implements all 4 correlation patterns                                   | VERIFIED   | `backend/src/graph/builder.py` lines 306-452: Pattern 1 (repeated DNS), Pattern 2 (DNS→connection chain), Pattern 3 (shared entity alerts), Pattern 4 (temporal proximity) |
| 7  | GET /graph/correlate returns correlated events, alerts, graph, investigation_thread   | VERIFIED   | `backend/src/api/routes.py` lines 115-172: full implementation returning all 5 keys; 404 on unknown event_id |

**Score:** 7/7 truths verified

---

## Required Artifacts

| Artifact                                             | Expected                                                  | Status      | Details                                                                          |
|------------------------------------------------------|-----------------------------------------------------------|-------------|----------------------------------------------------------------------------------|
| `backend/src/api/models.py`                          | GraphNode, GraphEdge, AttackPath, GraphResponse           | VERIFIED   | All 4 classes present; AttackPath at lines 64-70; GraphResponse at lines 73-77  |
| `backend/src/graph/builder.py`                       | build_graph(events, alerts), _correlate, 4 patterns       | VERIFIED   | 477 lines; all functions present; _correlate at lines 306-452; build_graph at lines 459-476 |
| `backend/src/api/routes.py`                          | GET /graph + GET /graph/correlate full implementation     | VERIFIED   | Both routes present; /graph/correlate full (not scaffold) — investigation_thread present |
| `dashboard/src/components/graph/ThreatGraph.svelte`  | e.src/e.dst mapping, attack-path-highlight CSS class       | VERIFIED   | Lines 108-109: `source: e.src, target: e.dst`; line 66: `.attack-path-highlight` selector |
| `dashboard/src/lib/api.ts`                           | getGraph() returns attack_paths+stats, getGraphCorrelate() | VERIFIED  | Lines 185-193: `getGraph()` returns `Phase4GraphResponse`; `getGraphCorrelate()` exported |
| `backend/src/tests/test_phase4.py`                   | 8 test classes covering all features                      | VERIFIED   | 9 tests (TestCorrelateRoute has 2), all XPASS — 41 prior tests still pass       |

---

## Key Link Verification

| From                                        | To                                                   | Via                                          | Status      | Details                                                                      |
|---------------------------------------------|------------------------------------------------------|----------------------------------------------|-------------|------------------------------------------------------------------------------|
| `backend/src/api/routes.py`                 | `backend/src/graph/builder.py`                       | `build_graph(_events, _alerts)` call         | WIRED      | Line 112: `return build_graph(_events, _alerts)` — exactly matches locked pattern |
| `backend/src/graph/builder.py`              | `backend/src/api/routes.py`                          | `_correlate()` called inside `build_graph()` | WIRED      | Line 463: `corr_edges = _correlate(events, nodes, edges)` present            |
| `backend/src/api/routes.py`                 | `backend/src/graph/builder.py`                       | `/graph/correlate` calls `build_graph(all_events, ...)` | WIRED | Line 147: `graph = build_graph(all_events, correlated_alerts)` present      |
| `dashboard/src/components/graph/ThreatGraph.svelte` | `dashboard/src/lib/api.ts`                 | `getGraph()` call consuming attack_paths/stats | WIRED    | Line 76: `const data = await getGraph()`; lines 119-125: attack_paths consumed |
| `dashboard/src/lib/api.ts`                  | `backend/src/api/routes.py`                          | `getGraphCorrelate()` calling `/graph/correlate` | WIRED  | Lines 190-193: `fetch(`${BASE}/graph/correlate?event_id=...`)` present       |

---

## Requirements Coverage

| Requirement | Source Plans | Description                                         | Status         | Evidence                                                                                     |
|-------------|-------------|-----------------------------------------------------|----------------|----------------------------------------------------------------------------------------------|
| FR-4.1      | 01, 02, 03  | Graph query service — traversal, richer graph data  | SATISFIED     | build_graph with _extract_nodes/_extract_edges/_group_attack_paths; GET /graph returns full GraphResponse |
| FR-4.5      | 01, 03      | GET /graph/correlate?event_id={id} — correlated events, detections, investigation thread | SATISFIED | Full implementation in routes.py lines 115-172; returns correlated_event_count, correlated_alert_count, graph, investigation_thread |
| FR-4.2      | (deferred)  | Graph entity/path API endpoints                     | DEFERRED      | Explicitly deferred to Phase 5 per CONTEXT.md — not a gap                                    |
| FR-4.3      | (deferred)  | Event clustering service                            | DEFERRED      | Explicitly deferred to Phase 5 per CONTEXT.md — not a gap                                    |
| FR-4.4      | (deferred)  | Alert aggregation into investigation threads        | DEFERRED      | Explicitly deferred to Phase 5 per CONTEXT.md — not a gap                                    |

---

## Anti-Patterns Found

| File                                    | Line    | Pattern                                          | Severity | Impact                                                                                |
|-----------------------------------------|---------|--------------------------------------------------|----------|---------------------------------------------------------------------------------------|
| `backend/src/tests/test_phase4.py`      | 21,38,68,99,139,178,195,222,239 | `@pytest.mark.xfail(strict=False, ...)` on all 9 tests that now XPASS | Info | Tests pass (XPASS) so test suite is green. The xfail markers were not removed after implementation. No functional impact — `strict=False` means xpass is not a test failure. |
| `frontend/src/components/graph/ThreatGraph.svelte` | 27 | Still uses `e.source, e.target` (old field names) | Warning | This file is in `frontend/` (Wave 1 legacy SPA, not production). The production component in `dashboard/` is correctly updated. No runtime impact. |
| `frontend/src/lib/api.ts`               | 29    | `getGraph()` return type still `{ nodes: any[]; edges: any[] }` — missing attack_paths/stats | Warning | Same as above — this is the legacy `frontend/` SPA. Production `dashboard/src/lib/api.ts` is fully updated. No runtime impact. |

---

## Note on Two Frontend Directories

The project has two Svelte SPA directories:

- `frontend/` — Wave 1 legacy SPA (`ai-soc-wave1-frontend`). Not served in production. Plans referenced `frontend/` but this was a naming mismatch.
- `dashboard/` — Production SPA (`ai-soc-brain-dashboard`). Served by Caddy from `/srv/dashboard` (confirmed in `config/caddy/Caddyfile` line 51). All Phase 4 frontend changes were correctly applied here.

The executor documented this deviation in `04-02-SUMMARY.md`: "ThreatGraph.svelte placed in dashboard/ not frontend/ — correct project layout". The production implementation is complete and correct.

---

## Human Verification Required

### 1. Attack Path Highlighting in Dashboard

**Test:** Start the backend, ingest 4+ events: two dns events to the same domain from different hosts, a connection event on the same host as one of the dns events within 60s, and one more connection event with shared IP.
**Expected:** ThreatGraph renders attack-path-highlight gold border on nodes belonging to connected components; clicking a node opens the side panel showing evidence event IDs; closing works.
**Why human:** Cytoscape `addClass` execution, visual CSS rendering, and click interaction require a live browser.

### 2. Investigation Thread Response

**Test:** POST an event, capture its `id`, then `GET /graph/correlate?event_id={id}` and POST additional events sharing the same `host` field.
**Expected:** Response includes `investigation_thread` as a non-null `AttackPath` object once correlated events exist, or `null` when the event has no shared entities with others.
**Why human:** The in-memory store resets between test runs; meaningful correlation requires a running server with multiple related events.

---

## Gaps Summary

None. All phase goals are achieved in the codebase:

- Backend models fully updated with Phase 4 schema (GraphNode, GraphEdge, AttackPath, GraphResponse)
- builder.py implements all 4 correlation patterns inside `_correlate()`, integrated into `build_graph()`
- GET /graph returns the full enriched response
- GET /graph/correlate returns correlated subgraph with investigation_thread
- dashboard frontend maps e.src/e.dst correctly, highlights attack paths, shows node details
- dashboard api.ts exports getGraph() and getGraphCorrelate() with correct types
- All 41 prior tests pass; all 9 Phase 4 tests XPASS (implementation complete)
- FR-4.1 and FR-4.5 satisfied; FR-4.2/4.3/4.4 correctly deferred to Phase 5

The two warning-level anti-patterns (legacy `frontend/` files not updated) have no runtime impact as `dashboard/` is the production frontend served by Caddy.

---

_Verified: 2026-03-16_
_Verifier: Claude (gsd-verifier)_
