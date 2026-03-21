# AI-SOC-Brain Codebase Audit — Phase 8 v2

**Analysis Date:** 2026-03-17
**Branch:** feature/ai-soc-phase3-detection

---

## 1. Correlation Engine

### EXISTS

`correlation/clustering.py` — 378 lines — **fully implemented**, not a stub.

Two real clustering strategies:

**`cluster_events_by_entity()`** — Union-Find algorithm over `normalized_events` DuckDB rows. Derives entity IDs from `hostname`, `username`, `process_name+process_id`, `dst_ip`, `domain` fields. Path-compressed Union-Find merges events sharing at least one entity. Returns `EventCluster` objects with `cluster_id`, `events`, `shared_entities`, `cluster_type="shared_entity"`, `relatedness_score` (Jaccard-style overlap ratio), and `time_range`.

**`cluster_events_by_time()`** — Sliding window over `(hostname, timestamp)` order. Groups events where gap from window-start exceeds `window_minutes` (default 5). Emits clusters with ≥2 events.

**`EventCluster` dataclass:**
```python
cluster_id: str
events: list[str]          # event_id values
shared_entities: list[str] # entity IDs
cluster_type: str          # "shared_entity" | "temporal"
relatedness_score: float   # 0.0–1.0
time_range: tuple[datetime, datetime] | None
```

`correlation/__init__.py` — exists but likely empty.

### GAPS

- No API endpoint exposes clustering results. Both functions exist as library code only — no `/api/correlate` or `/api/cluster` route exists in `backend/api/`.
- No auto-trigger: clustering is never called on ingest or on demand.
- No persistence: cluster results are ephemeral (in-memory only, not saved to SQLite).
- No frontend panel displays cluster results.

---

## 2. Graph Engine

### EXISTS

**`graph/schema.py`** — 62 lines — defines `ENTITY_TYPES` and `EDGE_TYPES` constants with validation helpers.

Node types (11): `host`, `user`, `process`, `file`, `network_connection`, `domain`, `ip`, `detection`, `artifact`, `incident`, `attack_technique`

Edge types (12): `executed_by`, `ran_on`, `accessed`, `connected_to`, `resolved_to`, `triggered`, `maps_to`, `part_of`, `spawned`, `wrote`, `logged_into`, `related_to`

**`graph/builder.py`** — 222 lines — `get_entity_subgraph()` and `get_entity_neighbours()` — real bidirectional BFS using SQLite recursive CTEs. Supports depth/max_nodes caps, entity type filtering, deduplication of edges. Wraps synchronous SQLite calls in `asyncio.to_thread()`.

**`backend/stores/sqlite_store.py`** — 641 lines — full graph persistence implementation.

SQLite graph schema:
```sql
-- entities: nodes
entities (id TEXT PK, type TEXT, name TEXT, attributes TEXT JSON,
          case_id TEXT, created_at TEXT)
-- edges: directed relationships
edges (id INTEGER PK AUTOINCREMENT, source_type TEXT, source_id TEXT,
       edge_type TEXT, target_type TEXT, target_id TEXT,
       properties TEXT JSON, created_at TEXT,
       UNIQUE(source_id, edge_type, target_id))
```

`get_edges_from()` uses recursive CTE (WITH RECURSIVE) for multi-hop traversal up to a given depth. `get_edges_to()` does reverse lookup. `get_neighbours()` returns (outbound, inbound) tuples.

**`backend/api/graph.py`** — 359 lines — REST API for the graph:
- `POST /api/graph/entity` — create/upsert entity
- `GET  /api/graph/entity/{entity_id}` — entity + neighbours
- `GET  /api/graph/entities` — list all entities (type filter)
- `POST /api/graph/edge` — create directed edge
- `GET  /api/graph/traverse/{entity_id}` — multi-hop BFS (depth param)
- `GET  /api/graph/case/{case_id}` — full case entity graph
- `DELETE /api/graph/entity/{entity_id}` — remove entity + edges

**There is also a SECOND, older graph engine** at `backend/src/graph/builder.py` used by the causality module. It is Cytoscape-compatible and builds `GraphNode`/`GraphEdge`/`AttackPath` Pydantic objects from in-memory event dicts. This is what `causality_routes.py` calls via `from backend.src.graph.builder import build_graph`.

### GAPS

- Graph in SQLite is populated by `ingestion/entity_extractor.py` (via the ingest pipeline), but `backend/api/graph.py` exposes only manual CRUD — there is no auto-enrichment endpoint.
- The two graph engines (`graph/builder.py` BFS vs `backend/src/graph/builder.py` in-memory builder) are architecturally separate and not reconciled.
- No graph visualization linked to the main `backend/api/graph.py` endpoints — frontend only calls the old `backend/src` causality graph.

---

## 3. Data Model (NormalizedEvent)

### EXISTS

**`backend/models/event.py`** — 275 lines.

**`NormalizedEvent` fields** (29 columns):
```
event_id, timestamp, ingested_at, source_type, source_file
hostname, username
process_name, process_id, parent_process_name, parent_process_id
file_path, file_hash_sha256, command_line
src_ip, src_port, dst_ip, dst_port, domain, url
event_type, severity, confidence, detection_source
attack_technique, attack_tactic
raw_event, tags, case_id
```

`to_duckdb_row()` returns a 29-tuple in the exact column order above (used for parameterized INSERTs).

`to_embedding_text()` produces a compact pipe-separated string for Chroma vector embedding.

`from_duckdb_row(row, columns)` reconstructs from a DuckDB row.

**DuckDB schema** (`backend/stores/duckdb_store.py`):

```sql
CREATE TABLE normalized_events (
    event_id TEXT PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    ingested_at TIMESTAMP NOT NULL,
    -- ... 26 more columns matching NormalizedEvent fields exactly
    case_id TEXT
)
```

Indexes: `idx_events_timestamp`, `idx_events_hostname`, `idx_events_process`, `idx_events_case_id`.

**SQLite tables** (`backend/stores/sqlite_store.py`):
- `cases` — simple case containers (id, name, description, status, created_at)
- `entities` — graph nodes
- `edges` — graph directed edges with UNIQUE constraint on (source_id, edge_type, target_id)
- `detections` — detection/alert records with JSON `matched_event_ids`
- `investigation_cases` — richer case model with JSON array fields (related_alerts, related_entities, timeline_events, tags, artifacts)
- `case_artifacts` — artifact file metadata linked to investigation_cases
- `case_tags` — normalized tags table

Note: There are **two case tables**: `cases` (simple) and `investigation_cases` (rich). The investigation API uses `investigation_cases`.

**Other models in `event.py`:**
- `DetectionRecord` — rule_id, rule_name, severity, matched_event_ids[], attack_technique, attack_tactic, explanation, case_id
- `GraphEntity` — id, type, name, attributes dict, case_id
- `GraphEdge` — id, source_type, source_id, edge_type, target_type, target_id, properties dict
- `GraphResponse` — entities[], edges[], root_entity_id, depth, total_entities, total_edges
- `EventListResponse` — paginated events response
- `EventSearchRequest` — query + filters

### GAPS

- `NormalizedEvent` has no `parent_process_id` in the embedding text (only process_name and command_line are included).
- No `process_path` or `process_hash` field — only `file_path` and `file_hash_sha256` (file-centric, not process-centric).
- No `severity_score` numeric field — severity is a string enum only.

---

## 4. Current API Endpoints

### EXISTS

All routes mounted under `/api` prefix in `backend/main.py`.

**Core routers (always mounted):**

| Router file | Prefix | Endpoints |
|---|---|---|
| `backend/api/health.py` | `/health` | `GET /health` |
| `backend/api/events.py` | `/api/events` | `GET /api/events`, `GET /api/events/search`, `GET /api/events/{event_id}` |
| `backend/api/ingest.py` | `/api/ingest` | `POST /api/ingest/event`, `POST /api/ingest/events`, `POST /api/ingest/file`, `POST /api/ingest/upload` (legacy), `GET /api/ingest/jobs/{job_id}` |
| `backend/api/query.py` | `/api/query` | `POST /api/query/semantic`, `POST /api/query/ask`, `POST /api/query/ask/stream` |
| `backend/api/detect.py` | `/api/detect` | `GET /api/detect`, `GET /api/detect/case/{case_id}`, `POST /api/detect`, `GET /api/detect/{detection_id}` |
| `backend/api/graph.py` | `/api/graph` | `POST /api/graph/entity`, `GET /api/graph/entity/{entity_id}`, `GET /api/graph/entities`, `POST /api/graph/edge`, `GET /api/graph/traverse/{entity_id}`, `GET /api/graph/case/{case_id}`, `DELETE /api/graph/entity/{entity_id}` |
| `backend/api/export.py` | `/api/export` | `GET /api/export/events/csv`, `GET /api/export/events/json`, `GET /api/export/case/{case_id}/bundle` |

**Deferred routers (graceful degradation — mounted if module available):**

| Router file | Prefix | Endpoints |
|---|---|---|
| `backend/causality/causality_routes.py` | `/api` | `GET /api/graph/{alert_id}`, `GET /api/entity/{entity_id}`, `GET /api/attack_chain/{alert_id}`, `POST /api/query`, `POST /api/investigate/{alert_id}/summary` |
| `backend/investigation/investigation_routes.py` | `/api` | `POST /api/cases`, `GET /api/cases`, `GET /api/cases/{case_id}`, `PATCH /api/cases/{case_id}`, `GET /api/cases/{case_id}/timeline`, `POST /api/cases/{case_id}/artifacts`, `GET /api/hunt/templates`, `POST /api/hunt` |
| `backend/api/telemetry.py` | `/api/telemetry` | `GET /api/telemetry/osquery/status` |

**CRITICAL CONFLICT:** `causality_routes.py` mounts `GET /api/graph/{alert_id}` — this shadows `backend/api/graph.py`'s router which also has routes under `/api/graph`. FastAPI resolves by first-registered router wins.

### GAPS

- No `POST /api/detect/run` endpoint to trigger Sigma rule matching on demand.
- No `POST /api/correlate` to run clustering.
- No sigma-based detection endpoint — `SigmaMatcher` exists in `detections/matcher.py` but is not wired into any API route.
- `GET /api/detect` only reads from the SQLite `detections` table; it does not run live detection.
- `/api/graph/{alert_id}` in causality_routes reads from an in-memory `_events`/`_alerts` list in `backend/src/api/routes.py` — not from DuckDB/SQLite.

---

## 5. Dashboard / Frontend

### EXISTS

Two parallel frontend codebases exist: `frontend/` (active) and `dashboard/` (legacy/parallel).

**`frontend/` (active — used by main.py static serving):**

`main.py` serves `dashboard/dist` at `/app`, NOT `frontend/dist`. This means `frontend/` is the dev environment while `dashboard/` is what gets built and served.

**`frontend/src/lib/api.ts`** — 372 lines — typed API client with:
- Phase 1: `getHealth()`, `getEvents()`, `getTimeline()`, `getGraph()`, `getAlerts()`, `loadFixtures()`
- Phase 2: `postIngest()`, `ingestSyslog()`, `openEventStream()` (SSE)
- Phase 5: `getThreats()`, `AlertItem` interface with `threat_score` and `attack_tags`
- Phase 6: `getAttackGraph()`, `getAttackChain()`, `investigationQuery()`, `getInvestigationSummary()` — typed interfaces for `CausalityGraphNode`, `CausalityGraphEdge`, `AttackPath`, `MitreTechnique`
- Phase 7: `getCases()`, `createCase()`, `getCase()`, `patchCase()`, `getCaseTimeline()`, `uploadArtifact()`, `getHuntTemplates()`, `executeHunt()`

**NOTE:** The frontend `api.ts` calls `/events`, `/timeline`, `/graph`, `/alerts` (without `/api/` prefix) — these are OLD routes from `backend/src/api/routes.py`, not the new DuckDB-backed API. The causality, case, and hunt endpoints correctly use `/api/` prefix.

**Frontend components (`frontend/src/components/`):**

- `AttackChain.svelte` — Cytoscape + cytoscape-dagre graph rendering, calls `getAttackGraph()`, highlights attack paths, node click handling
- `ThreatGraph.svelte` — Cytoscape graph calling `getGraph()` (old /graph endpoint)
- `graph/AttackChain.svelte` — same as above but in subdir (duplicate?)
- `graph/ThreatGraph.svelte` — Cytoscape calling `getGraph()` (old endpoint)
- `panels/CasePanel.svelte` — case management UI
- `panels/EvidencePanel.svelte` — evidence display
- `panels/HuntPanel.svelte` — threat hunting queries
- `panels/InvestigationPanel.svelte` — investigation workflow
- `timeline/EventTimeline.svelte` — D3-based timeline

**`dashboard/src/components/`:**
- `AttackChain.svelte`, `ThreatGraph.svelte`, `CasePanel.svelte`, `EvidencePanel.svelte`, `HuntPanel.svelte`, `InvestigationPanel.svelte`
- `graph/ThreatGraph.svelte`

**Graph visualization:**
- `cytoscape@^3.31.0` — installed in both `frontend/` and `dashboard/`
- `cytoscape-dagre@^2.5.0` — installed in `frontend/` only
- `d3@^7.9.0` — installed in both

### GAPS

- `frontend/src/routes/+page.svelte` is a stub (7 lines, delegates to App.svelte).
- No `App.svelte` has been read — tab structure unknown beyond component existence.
- The `frontend/api.ts` calls `/events`, `/alerts`, `/graph`, `/timeline` with no `/api/` prefix — these route to the old in-memory `backend/src/api/routes.py` system, not the DuckDB-backed API.
- `dashboard/` vs `frontend/` split is confusing — `main.py` serves `dashboard/dist` but development seems to target both.

---

## 6. Detection Engine

### EXISTS

**`detections/matcher.py`** — 742 lines — production-quality Sigma rule matching against DuckDB.

`SigmaMatcher` class:
- `load_rules_dir(rules_dir)` — recursively loads `.yml`/`.yaml` files using `SigmaRule.from_yaml()`
- `rule_to_sql_with_params(rule)` — converts Sigma detection block to `(WHERE_clause, params)` tuple
- Supports modifiers: `|contains`, `|startswith`, `|endswith`, `|contains|all`, `|re` (partial)
- Supports conditions: simple reference, `NOT`, `AND`, `OR`, `1 of selection*`, `all of them`
- `match_rule(rule, sql_where, params, case_id)` — executes against `normalized_events`, creates `DetectionRecord` objects
- `run_all(case_id)` — runs all loaded rules, returns all `DetectionRecord`s
- `save_detections(detections)` — persists `DetectionRecord`s to SQLite
- SQL injection safe: values are parameterized, field names come from `SIGMA_FIELD_MAP` (closed dict)

**`detections/field_map.py`** — maps Sigma field names to DuckDB column names. Includes `INTEGER_COLUMNS` set.

**Sigma rules (`fixtures/sigma/`):**
- `failed_authentication.yml` — detects `EventType: 'UserLogonFailed'` (medium)
- `powershell_download_cradle.yml` — PowerShell detection
- `suspicious_network_connection.yml` — network detection

**`detections/rules/windows/`** — empty (no production rules checked in).

**Second detection system** at `backend/src/detection/` (used by old in-memory routes):
- `rules.py` — custom rule evaluator
- `sigma_loader.py` — loads Sigma rules for old pipeline
- `threat_scorer.py` — threat scoring
- `attack_mapper.py` — MITRE mapping

### GAPS

- `SigmaMatcher` is **not mounted in any API route**. It exists as a library class only.
- No `/api/detect/run` endpoint calls `SigmaMatcher.run_all()`.
- Only 3 fixture Sigma rules. `detections/rules/windows/` exists but is empty.
- No scheduled or trigger-based detection — rules are never automatically run on new events.
- `backend/src/detection/` is a parallel detection system that the causality routes depend on, creating two detection paths.

---

## 7. Ingestion Pipeline

### EXISTS

**`ingestion/parsers/`:**
- `base.py` — `BaseParser` ABC with `parse(file_path)` → `Iterator[NormalizedEvent]`
- `evtx_parser.py` — Windows EVTX via `python-evtx`
- `json_parser.py` — JSON/NDJSON/JSONL
- `csv_parser.py` — CSV
- `osquery_parser.py` — osquery log format

**`ingestion/loader.py`** — 504 lines — `IngestionLoader` orchestrator:

Full pipeline: `file → parser → normalize → deduplicate → DuckDB batch INSERT (1000/batch) → Chroma embed (100/batch) → entity extraction → SQLite graph`

`IngestionResult` dataclass: `file_path`, `parsed`, `loaded`, `embedded`, `edges_created`, `errors[]`

In-memory job tracker (`_jobs` dict) for async file upload progress polling.

**`ingestion/normalizer.py`** — produces `NormalizedEvent` from raw dicts. Maps source-specific fields to canonical schema fields (hostname, username, process_name, etc.). Severity normalization.

**`ingestion/entity_extractor.py`** — extracts entities and edges from `NormalizedEvent` and writes to SQLite. Creates graph nodes for host, user, process, file, IP, domain entities.

### GAPS

- No Suricata/Zeek parser (despite `infra/suricata/` directory existing).
- No syslog parser in `ingestion/parsers/` (the old `backend/src/ingestion/syslog_parser.py` exists but is not in the main pipeline).
- `ingestion/normalizers/` directory exists but appears empty or stub.
- No streaming ingestion path — all parsers read entire files.

---

## 8. Existing Fixtures

### EXISTS

**`fixtures/ndjson/sample_events.ndjson`** — 6 events in old-style JSON (not NormalizedEvent format):
- Fields: `timestamp`, `host`, `src_ip`, `dst_ip`, `event` (not `event_type`), `query`, `port`, `severity`
- **NOT compatible with NormalizedEvent schema** directly — needs normalizer transformation
- Contains: dns_query events, connection events, a suspicious domain query

**`fixtures/sigma/`** (3 rules):
- `failed_authentication.yml` — `EventType: UserLogonFailed`, medium severity
- `powershell_download_cradle.yml` — PowerShell download detection
- `suspicious_network_connection.yml` — network detection

**`fixtures/evtx/`** — empty (directory exists, no .evtx files)

**`fixtures/syslog/`** — empty (directory exists, no syslog files)

**`data/artifacts/`** — 6 UUID-named directories with actual uploaded artifact files (runtime data from testing).

### GAPS

- No sample EVTX files for testing Windows event log parsing.
- No syslog fixture files.
- The NDJSON sample uses old field names (`host`, `query`) not matching `NormalizedEvent` (`hostname`, `domain`) — will require normalizer mapping.
- No large-scale fixtures for load/performance testing.

---

## 9. Investigation/Causality Modules

### EXISTS

**`backend/investigation/`:**

| File | Lines | Status |
|---|---|---|
| `investigation_routes.py` | 274 | Real implementation |
| `case_manager.py` | 128 | Real implementation |
| `hunt_engine.py` | 98 | Real implementation |
| `timeline_builder.py` | 97 | Real implementation |
| `artifact_store.py` | 75 | Real implementation |
| `tagging.py` | unknown | Present |

`case_manager.py` — `CaseManager` class with connection-injection pattern (takes `sqlite3.Connection` as arg, enabling testability with `:memory:`). Implements `create_investigation_case`, `get_investigation_case`, `list_investigation_cases`, `update_investigation_case`.

`hunt_engine.py` — 4 DuckDB hunt templates: `suspicious_ip_comms`, `powershell_children`, `unusual_auth`, `ioc_search`. `execute_hunt()` runs parameterized SQL. **Real working implementation.**

`timeline_builder.py` — `build_timeline(case_id, duckdb_store, sqlite_store)` queries `normalized_events WHERE case_id = ?` ordered by timestamp, scores confidence (1.0 if alert-linked, 0.8 if has attack_technique, 0.5 default), extracts entity references. **Real implementation but limited** — only shows events explicitly tagged with `case_id`.

`artifact_store.py` — saves uploaded file bytes to `data/artifacts/{case_id}/`, inserts record into SQLite `case_artifacts` table.

**`backend/causality/`:**

| File | Lines | Status |
|---|---|---|
| `engine.py` | 108 | Real but uses in-memory `_events`/`_alerts` |
| `causality_routes.py` | 271 | Real but wrong data source |
| `attack_chain_builder.py` | 66 | Real BFS implementation |
| `entity_resolver.py` | 86 | Real implementation |
| `mitre_mapper.py` | 75 | Real static technique catalog |
| `scoring.py` | 65 | Real additive scoring |

**CRITICAL ARCHITECTURAL ISSUE:** `causality_routes.py` imports from `backend.src.api.routes import _events, _alerts` — these are the old in-memory Python lists from the Phase 1-4 in-memory backend. The causality engine operates on this stale in-memory data, NOT on the DuckDB/SQLite stores that all ingestion goes through.

`attack_chain_builder.py` — real BFS using entity fingerprints. `find_causal_chain(start_event_id, all_events, max_depth=5, max_events=50)` traverses events sharing canonical entity IDs.

`entity_resolver.py` — `resolve_canonical_id(event, entity_type)` resolves entity type → field name mapping for old-style event dicts (uses `host`, `user`, `process` field names, not `hostname`, `username`, `process_name`).

`mitre_mapper.py` — static `TECHNIQUE_CATALOG` dict with 25 techniques across 10 tactics. `map_techniques(sigma_tags, event_type, alert_category)` parses `attack.tXXXX` Sigma tags.

`scoring.py` — `score_chain(chain_events, chain_alerts, techniques)` returns 0-100 additive score. Components: max alert severity (0-40), technique count (0-20), chain length (0-20), entity recurrence (0-20).

### GAPS

**The single largest gap in the entire codebase:**

The causality engine (`backend/causality/`) reads from the old in-memory `_events`/`_alerts` lists (`backend.src.api.routes._events`, `_alerts`). In a production deployment where ingestion goes through `/api/ingest` → DuckDB, those lists will be **empty**. All causality/attack-chain/investigation-summary responses will return empty results.

To function correctly, the causality engine must be rewired to read from:
- `DuckDBStore.fetch_df()` for events
- `SQLiteStore.get_detection()` / `get_detections_by_case()` for alerts

Additional gaps:
- `timeline_builder.py` only returns events with matching `case_id` — if events were not ingested with a `case_id`, they won't appear in the timeline.
- No automatic case-event linking — creating a case does not pull in related events.
- The `CaseManager` in `investigation/case_manager.py` takes a raw `sqlite3.Connection`, but `investigation_routes.py` calls `sqlite.create_investigation_case()` directly on the `SQLiteStore` wrapper (which has duplicate implementation). Inconsistency.
- No way to link an existing detection to a case without manual PATCH.

---

## Summary: Reusable vs Must-Build

### CAN REUSE AS-IS

- `correlation/clustering.py` — both clustering algorithms are production-quality
- `graph/schema.py` — entity/edge type constants
- `graph/builder.py` — BFS subgraph retrieval (uses SQLite correctly)
- `backend/models/event.py` — complete data model
- `backend/stores/duckdb_store.py` — single-writer async DuckDB pattern
- `backend/stores/sqlite_store.py` — full graph + detection + case persistence
- `detections/matcher.py` — Sigma → DuckDB SQL compilation and matching
- `ingestion/loader.py` + parsers — full ingestion pipeline
- `backend/investigation/hunt_engine.py` — 4 hunt templates
- `backend/investigation/artifact_store.py` — artifact file management
- `backend/causality/mitre_mapper.py` — MITRE technique catalog
- `backend/causality/scoring.py` — chain scoring
- `backend/causality/attack_chain_builder.py` — BFS logic (needs rewiring to DuckDB)
- All `backend/api/*.py` routes — real, working endpoints backed by DuckDB/SQLite
- `frontend/src/lib/api.ts` — typed client (partially maps to old routes)
- `frontend/src/components/graph/AttackChain.svelte` — Cytoscape + dagre rendering

### MUST BUILD / REWIRE

1. **Wire causality engine to DuckDB/SQLite** — `causality_routes.py` must read from stores, not `_events`/`_alerts` in-memory lists
2. **Expose Sigma matching via API** — add `POST /api/detect/run` that calls `SigmaMatcher.run_all()`
3. **Expose clustering via API** — add `/api/correlate` endpoint calling `cluster_events_by_entity()`
4. **Case-event auto-linking** — mechanism to associate events with a case (either at ingest time or retroactively)
5. **Timeline enrichment** — `build_timeline()` currently only returns events with `case_id` set; needs to also pull from related detections
6. **Fix frontend API routes** — `getEvents()`, `getAlerts()`, `getGraph()`, `getTimeline()` call old `/events`, `/alerts`, `/graph`, `/timeline` endpoints without `/api/` prefix — these go to the old in-memory backend
7. **`entity_resolver.py` field mapping** — uses `host`/`user`/`process` field names but `NormalizedEvent` uses `hostname`/`username`/`process_name`
8. **Production Sigma rules** — `detections/rules/windows/` is empty; only 3 fixture rules exist

---

*Codebase audit: 2026-03-17*
