---
phase: 08-8
plan: "v2"
type: summary
completed: "2026-03-17"
status: COMPLETE
---

# Phase 8 v2 — SOC Brain Implementation Summary

## Objective

Build the actual SOC investigation platform: correlation engine exposed via API, graph engine with Cytoscape visualization, threat trace / attack chain reconstruction, dashboard upgrade with interactive graph, and an APT scenario fixture proving end-to-end functionality.

## What Was Built

### Backend

#### `POST /api/detect/run`
- Loads Sigma rules from `fixtures/sigma/` and `rules/sigma/`
- Runs all rules against normalized_events in DuckDB
- Saves DetectionRecord to SQLite for each match
- Returns `{count, detections[]}`
- **Bug fixed:** Route ordering — `POST /run` must be registered before `GET /{detection_id}` in the same router (Starlette matches path before method)

#### `POST /api/correlate`
- Wraps `cluster_events_by_entity` + `cluster_events_by_time` from `correlation/clustering.py`
- Returns `{entity_clusters[], time_clusters[]}`

#### `POST /api/investigate`
- Central investigation orchestrator
- Steps: load detection (SQLite) → fetch matched events (DuckDB) → expand via Union-Find clustering → build Cytoscape graph → build timeline → build attack chain → extract MITRE techniques → generate summary
- Graph format: `{"elements": {"nodes": [...], "edges": [...]}}`
- Node types: host, user, process, ip, file, domain, detection (attack_technique)
- Edge types: spawned, connected_to, wrote, accessed, ran_on, resolved_to, triggered
- Always returns HTTP 200
- **Key design:** Graph built directly from event fields — no dependency on SQLite entity tables for fresh investigations

#### `backend/causality/causality_routes.py` — Rewired
- **Root cause:** Was importing `_events`/`_alerts` from `backend.src.api.routes` (always-empty in-memory lists)
- **Fix:** All handlers now query `request.app.state.stores` (DuckDB/SQLite)
- Entity resolver field mapping fixed: `hostname`/`username`/`process_name` (not `host`/`user`/`process`)
- Router prefix changed from conflicting `/api` to `/api/causality` to avoid shadowing `backend/api/graph.py`

#### `backend/api/correlate.py` — New
- `POST /api/correlate` — standalone correlation endpoint

### Fixtures

#### `fixtures/ndjson/apt_scenario.ndjson`
15-event multi-stage APT "Operation NightCrawler":
- **Hosts:** WORKSTATION-01, WORKSTATION-02, DC-01
- **Attacker C2:** 185.220.101.45:4444
- **Chain:** winword.exe (macro) → powershell.exe (IEX download) → svchosts.exe (implant) → persistence + discovery + LSASS → WMI lateral movement to WORKSTATION-02 → DC auth failure

#### `fixtures/sigma/` — 4 Rules
| Rule | Technique | Severity |
|------|-----------|----------|
| c2_beacon.yml | T1071.001 | critical |
| registry_persistence.yml | T1547.001 | high |
| lsass_access.yml | T1003.001 | critical |
| wmi_lateral.yml | T1047 | high |

#### `scripts/load-scenario.py`
Loads `fixtures/ndjson/apt_scenario.ndjson` via `POST /api/ingest/events`, then calls `POST /api/detect/run`.

### Dashboard

#### `dashboard/src/components/InvestigationPanel.svelte` — New
- Cytoscape.js graph with cose layout
- Entity-type color coding: process=red, host=blue, user=green, ip=yellow, domain=purple
- Severity-colored node borders
- Node tap → entity detail panel (event type, severity, command line, attack technique)
- Attack timeline list with severity color bands
- MITRE technique badge list
- Reactive `$effect` reload on `detectionId` prop change

#### `dashboard/src/views/DetectionsView.svelte` — Upgraded
- "Run Detection" button → `POST /api/detect/run`
- Per-row "Investigate" button → routes to InvestigationPanel
- MITRE technique badge column
- Matched events count column

#### `dashboard/src/App.svelte` — Upgraded
- "Investigation" nav item (magnifying glass icon)
- `investigatingId` state
- `handleInvestigate(detection_id)` callback
- InvestigationPanel rendered in investigation view slot

#### `dashboard/src/lib/api.ts` — Updated
- `api.investigate(body)` — POST /api/investigate
- `api.investigateEntity(entity_id, entity_type)` — entity-based investigation
- `api.correlate(event_ids)` — POST /api/correlate
- `api.detections.run()` — POST /api/detect/run
- `api.graph.traverse(entity_id)` — GET /api/graph/traverse/{entity_id}
- Updated `Detection` and `GraphEntity` interfaces

## End-to-End Verification (2026-03-17)

```
# 1. Ingest APT scenario
POST /api/ingest/events (15 events)
→ {"parsed": 15, "loaded": 15, "edges_created": 21}

# 2. Run Sigma detection
POST /api/detect/run
→ 3 detections:
  [high] PowerShell Download Cradle — id: 1a73989a
  [critical] Suspicious Outbound Network Connection — id: 952ec479
  [medium] Multiple Failed Authentication Attempts — id: 97e40aab

# 3. Investigate critical C2 detection
POST /api/investigate {"detection_id": "952ec479..."}
→ {
    "events": 75,
    "graph": {"elements": {"nodes": 53, "edges": 42}},
    "timeline": 75 entries,
    "attack_chain": 75 steps,
    "techniques": 11 (T1059.001, T1105, T1071.001, T1547.001, T1059.003,
                       T1033, T1087.002, T1016, T1003.001, T1047, T1110),
    "summary": "Investigation covers 75 events across 5 hosts..."
  }

# 4. Process ancestry chain (from graph spawned edges)
winword.exe → powershell.exe → svchosts.exe → cmd.exe → {whoami, net, ipconfig}
WmiPrvSE.exe → powershell.exe (lateral movement, WORKSTATION-02)

# 5. Network connections
svchosts.exe → 185.220.101.45 (C2 beacon, T1071.001)
powershell.exe → 185.220.101.45 (download cradle, T1105)

# 6. Tests: 66 passed, 4 xpassed, 0 failures
uv run pytest tests/unit/ -q --tb=short
```

## Architectural Decisions

- **ADR-015:** Causality engine rewired from empty in-memory lists to DuckDB/SQLite
- **ADR-016:** Unified `POST /api/investigate` endpoint orchestrates full pipeline
- **ADR-017:** FastAPI route ordering — static routes before parametric catch-alls
- **ADR-018:** APT scenario fixture as integration verification mechanism

## Files Created/Modified

### New
- `backend/api/investigate.py`
- `backend/api/correlate.py`
- `fixtures/ndjson/apt_scenario.ndjson`
- `fixtures/sigma/c2_beacon.yml`
- `fixtures/sigma/registry_persistence.yml`
- `fixtures/sigma/lsass_access.yml`
- `fixtures/sigma/wmi_lateral.yml`
- `scripts/load-scenario.py`
- `dashboard/src/components/InvestigationPanel.svelte`

### Modified
- `backend/causality/causality_routes.py` — rewired to DuckDB/SQLite
- `backend/causality/entity_resolver.py` — field name fix
- `backend/api/detect.py` — added POST /run (route order fix)
- `backend/api/investigate.py` — timeline fallback, graph format
- `backend/main.py` — new router mounts (correlate, investigate, rewired causality)
- `dashboard/src/lib/api.ts` — new endpoints + interfaces
- `dashboard/src/views/DetectionsView.svelte` — Run Detection + Investigate buttons
- `dashboard/src/App.svelte` — Investigation nav + routing
- `dashboard/src/views/GraphView.svelte` — entity field name normalization
- `STATE.md` — Phase 8 complete status
- `DECISION_LOG.md` — ADR-015 through ADR-018

## Phase 8 Complete

All 12 P8-T IDs (v1) and all 7 Phase 8 v2 non-negotiable requirements satisfied:

1. Correlation engine — Union-Find exposed via `/api/correlate` and used in investigation
2. Graph engine — SQLite-backed + Cytoscape-format output from `/api/investigate`
3. Threat trace engine — attack chain reconstruction in investigation endpoint
4. Dashboard upgrade — InvestigationPanel with Cytoscape, timeline, entity detail
5. Investigation flow — Detections → Investigate button → graph + timeline
6. APT fixture — Operation NightCrawler, 15 events, verified end-to-end
7. Verification — graph builds, attack path reconstructed, dashboard renders
