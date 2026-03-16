# Requirements

**Project:** AI-SOC-Brain
**Source:** PROJECT.md + research synthesis (2026-03-15)
**Status:** APPROVED — YOLO mode, proceed to roadmap

---

## Scope

A local Windows desktop AI cybersecurity investigation platform for a single analyst. Human-in-the-loop only — no autonomous response. The system ingests evidence, detects threats via Sigma rules, answers analyst questions with local LLM + RAG, and provides interactive graph/timeline visualization.

## Out of Scope

| Area | Reason |
|------|--------|
| Autonomous response (kill process, block IP, quarantine file) | Human-in-the-loop only; response is a future phase |
| Linux collector, network appliance, broader infrastructure | Desktop brain scope only |
| Cloud API calls for LLM inference | Local-first, Ollama only |
| Multi-tenant / multi-user collaboration | Single-analyst desktop tool |
| Real-time continuous EDR agent | Ingest snapshots from existing tools; be the analysis brain |
| PostgreSQL, Neo4j, Kafka, Elasticsearch, Wazuh | Banned unless proven necessary; DuckDB + Chroma + SQLite cover the need |
| Plugin/extension marketplace | Premature for v1 |
| NL-to-SQL generation | Unreliable; use structured search + RAG instead |

---

## Phase 1: Foundation
**Goal:** Install and validate all infrastructure components, establishing the non-negotiable foundation. Every subsequent phase depends on this being correct.

### FR-1.1 — Python 3.12 Virtual Environment
The project must use Python 3.12 (not 3.14) via uv. PEP 649 / PyO3 compatibility requires 3.12. All dependencies must install and import without error under 3.12.

**Verification:** `python --version` shows 3.12.x. All core packages import successfully: `import fastapi, duckdb, chromadb, pydantic, httpx, pySigma`.

### FR-1.2 — Ollama Installed and GPU-Accelerated
Ollama must be installed natively on Windows (not Docker), version 0.13+ for RTX 5080 Blackwell support. After installation, inference must run on the RTX 5080 GPU (not CPU).

**Verification:** `ollama ps` shows GPU layer count > 0 during inference. `nvidia-smi` shows GPU utilization > 0% during `ollama run llama3.2:1b`.

### FR-1.3 — Target Models Pulled and Accessible
The following models must be pulled via Ollama and accessible from the FastAPI backend:
- `qwen3:14b` (primary reasoning/Q&A model)
- `mxbai-embed-large` (embedding model for RAG)

**Verification:** `ollama list` shows both models. Embedding API call returns a 1024-dimension vector.

### FR-1.4 — FastAPI Backend Skeleton
A FastAPI application must exist at `backend/` with:
- `/health` endpoint returning component status (Ollama, DuckDB, Chroma, SQLite)
- Lifespan management for all embedded stores (init on startup, close on shutdown)
- Single uvicorn worker process
- Python 3.12, uv venv, pyproject.toml
- Structured JSON logging

**Verification:** `GET /health` returns 200 with all components healthy.

### FR-1.5 — DuckDB Store with Single-Writer Pattern
DuckDB must be initialized at `data/events.duckdb` with the normalized event schema. Connection management must implement:
- One write connection (used by ingestion, serialized via asyncio.Queue)
- Read-only connections for API queries (`read_only=True`)
- All DuckDB calls wrapped in `asyncio.to_thread()` from async handlers

**Verification:** Concurrent ingestion + queries run for 60 seconds without hangs or deadlocks.

### FR-1.6 — Chroma PersistentClient Initialized
Chroma must run as `PersistentClient` at `data/chroma/`. Version must be pinned in `pyproject.toml`. A JSON export/import script must exist for the Chroma collection.

**Verification:** Data survives backend restart (stop/start uvicorn). Export/import round-trip test passes (export to JSON, clear collection, import, verify doc count matches).

### FR-1.7 — SQLite Graph Store Initialized
SQLite must be initialized at `data/graph.sqlite3` with WAL mode enabled and the entity-edge schema:
- `entities` table (id, type, attributes JSON)
- `edges` table (source_type, source_id, edge_type, target_type, target_id, properties JSON)
- Indexes on both source and target columns

**Verification:** Entity and edge records INSERT and SELECT without error. WAL mode confirmed via `PRAGMA journal_mode`.

### FR-1.8 — Caddy HTTPS Reverse Proxy
Caddy must run in Docker, terminating HTTPS on port 443 and proxying to FastAPI on port 8000. Localhost HTTPS must be accessible at `https://localhost`.

**Verification:** `curl -k https://localhost/health` returns 200. TLS certificate present (self-signed for localhost is acceptable).

### FR-1.9 — Docker-to-Ollama Bridge Validated
Ollama must be reachable from inside the Caddy container via `http://host.docker.internal:11434`. `OLLAMA_HOST=0.0.0.0` and `OLLAMA_ORIGINS=*` must be set as Windows system environment variables.

**Verification:** `docker exec caddy curl http://host.docker.internal:11434` returns Ollama API response.

### FR-1.10 — Phase 1 Smoke Tests
A PowerShell smoke test script (`scripts/smoke-test-phase1.ps1`) must verify all Phase 1 requirements with pass/fail output.

---

## Phase 2: Ingestion Pipeline
**Goal:** Ingest evidence from multiple formats into normalized storage, building the foundation for detection, RAG, and visualization.

### FR-2.1 — Normalized Event Schema
A Pydantic model (`NormalizedEvent`) must define the central data contract for all ingested evidence. Required fields: `event_id` (UUID), `timestamp`, `ingested_at`, `source_type`, `source_file`. Optional entity fields: `hostname`, `username`, `process_name`, `process_id`, `parent_process_name`, `parent_process_id`, `file_path`, `file_hash_sha256`, `command_line`, `src_ip`, `src_port`, `dst_ip`, `dst_port`, `domain`, `url`. Classification fields: `event_type`, `severity`, `confidence`, `detection_source`, `attack_technique`, `attack_tactic`. Provenance: `raw_event`, `tags`, `case_id`. A `to_embedding_text()` method must produce text for vector embedding.

**Verification:** 10 fixture events (EVTX-derived, osquery-derived, manual) all validate against the schema without error.

### FR-2.2 — Parser Registry
An extensible parser registry must map file extensions to parser classes implementing `BaseParser.parse(file_path) -> Iterator[NormalizedEvent]`. Adding a new format requires only a new parser file with no changes to existing code.

**Verification:** 3 parsers registered (EVTX, JSON/NDJSON, CSV). New parser can be added by dropping a file without modifying the registry.

### FR-2.3 — EVTX Parser
An EVTX parser using `pyevtx-rs` (Rust bindings, `pip install evtx`) must stream-parse Windows Event Log files in batches of 1000 records. Must handle corrupt records gracefully (log and skip, not crash). Must map Windows EVTX field names to the normalized schema (e.g., `SubjectUserName` → `username`, `Image` → `process_name`).

**Verification:** Parse a real Security.evtx file ≥100MB without memory spike above 2GB or timeout. Corruption handling tested with truncated file.

### FR-2.4 — JSON / NDJSON / CSV Parser
Parsers for JSON objects, NDJSON (one JSON object per line), and CSV files. Must normalize field names to the normalized schema where possible, preserving unmapped fields in a `raw_event` JSON blob.

**Verification:** 3 fixture files (one per format) ingest correctly with expected field counts.

### FR-2.5 — DuckDB Loader
The DuckDB loader must INSERT normalized events in batches (1000 rows per transaction) using the write queue. Must assign UUIDs to events without IDs. Must deduplicate events by source_file + timestamp + process_id on re-ingestion.

**Verification:** Re-ingesting the same file twice produces the same event count, not double.

### FR-2.6 — Chroma Embedding Loader
The Chroma loader must:
- Embed event text using `mxbai-embed-large` via Ollama embedding API
- Store `event_id`, `source_type`, `timestamp`, `case_id` as metadata
- Store embedding model name as collection metadata (for future migration safety)
- Batch embedding requests (100 events per batch)

**Verification:** Semantic search for "PowerShell execution" returns relevant events from ingested Windows logs.

### FR-2.7 — Entity Edge Extractor
During ingestion, the loader must extract entity relationships from normalized events and write to SQLite edges:
- `process → user` (executed_by): process_name + PID to username
- `process → host` (ran_on): process_name to hostname
- `process → file` (accessed): process_name to file_path (if file event)
- `process → network` (connected_to): process_name to dst_ip:dst_port (if network event)
- `domain → ip` (resolved_to): domain to dst_ip (if DNS event)

**Verification:** After ingesting a Sysmon-style fixture, the edges table contains process-to-user and process-to-network edges.

### FR-2.8 — Ingest API Endpoint
`POST /ingest` must accept file uploads (multipart/form-data), detect format from extension, run the appropriate parser, and execute the ingestion pipeline asynchronously with progress reporting. Response must include an ingestion job ID. `GET /ingest/{job_id}` must return progress status.

**Verification:** Upload a 10MB JSON log file. Progress endpoint shows completion. DuckDB event count increases. Chroma doc count increases.

### FR-2.9 — Ingestion Fixtures
A `fixtures/` directory must contain sample data for development and testing:
- `fixtures/windows_security.evtx.sample` — excerpt from a real Security.evtx
- `fixtures/sysmon_sample.ndjson` — 100 Sysmon events in NDJSON format
- `fixtures/network_sample.csv` — 50 network connection events
- `fixtures/test_events.json` — 20 hand-crafted events covering all entity types

**Verification:** All fixtures ingest without errors.

---

## Phase 3: Detection + RAG
**Goal:** Detect threats using Sigma rules and answer analyst questions using RAG. These are the two core capabilities that differentiate this tool.

### FR-3.1 — pySigma DuckDB Backend
A custom pySigma backend that compiles Sigma YAML rules to DuckDB-compatible SQL WHERE clauses must be implemented. The backend must:
- Extend the pySigma SQL backend base class
- Include a field mapping processing pipeline (all Sigma canonical Windows fields to normalized schema columns)
- Use `--fail-unsupported` behavior so unsupported rules surface errors, not silence
- Support condition expressions: AND, OR, NOT, wildcards (`*`, `?`)
- NOT support aggregate/count-based detection (explicitly unsupported, documented)

**Verification:** 10 Sigma smoke test rules (covering process creation, network connection, file creation, registry modification) produce valid DuckDB SQL that matches crafted test events.

### FR-3.2 — Sigma Rule Loading
The system must load Sigma rules from `detections/rules/` (YAML files). A rule management service must:
- Scan for YAML files on startup
- Compile each to DuckDB SQL via the custom backend
- Cache compiled rules (invalidate on file modification)
- Report loading status per rule (success / unsupported / error)

**Verification:** 20+ Sigma rules from the SigmaHQ windows-sysmon corpus load without error.

### FR-3.3 — Detection Matcher
The detection matcher must:
- Run compiled Sigma SQL queries against DuckDB events (triggered on ingestion and on-demand)
- Write detection records to SQLite: `rule_id`, `rule_name`, `severity`, `matched_event_ids`, `attack_technique`, `attack_tactic`, `timestamp`, `case_id`
- Write detection-to-event edges to SQLite
- NOT fire duplicate detections for the same event/rule combination

**Verification:** Ingest a fixture containing a Mimikatz-pattern event. The corresponding Sigma rule fires once and exactly once. Detection record contains correct ATT&CK technique (T1003).

### FR-3.4 — ATT&CK Enrichment
The system must enrich detection records with MITRE ATT&CK technique and tactic information sourced from the Sigma rule `tags` field. Must resolve technique IDs (e.g., `T1059.001`) to technique name and tactic phase.

**Verification:** A detection from a Sigma rule tagged with `attack.execution, attack.t1059.001` shows technique "PowerShell" under tactic "Execution" in the API response.

### FR-3.5 — Detection API Endpoint
`GET /detect` must return a list of detection records, sortable and filterable by severity, technique, tactic, time range, and case_id. `GET /detect/{detection_id}` must return the detection record with full matched event details (from DuckDB). `POST /detect/run` must trigger a detection scan on demand.

**Verification:** After ingesting Mimikatz fixture, GET /detect returns the detection with ATT&CK mapping. Drilldown returns raw event JSON.

### FR-3.6 — Sigma Smoke Test Suite
A smoke test suite (`tests/sigma_smoke/`) must verify that 10 known Sigma rules match their corresponding crafted test events. This is the primary regression guard for the detection engine.

**Verification:** All 10 smoke tests pass. Any field mapping change that breaks detection causes at least one test failure.

### FR-3.7 — LangGraph RAG Pipeline
A LangGraph graph (not LangChain chains) must implement the analyst Q&A retrieval pipeline:
1. Query embedding (embed analyst question with `mxbai-embed-large`)
2. Chroma similarity search (top-10 most relevant evidence chunks, with metadata filters)
3. DuckDB structured context (related events by entity, time range query)
4. Context assembly (combine vector results + structured results)
5. Prompt construction (from prompt template, inject context)
6. Ollama streaming inference (stream tokens via `httpx` async client)
7. Citation extraction (identify event IDs referenced in the response)

**Verification:** Query "What did the suspicious PowerShell process do?" against a fixture containing Sysmon events returns a response that cites at least one real event ID.

### FR-3.8 — Citation Verification Layer
After the LLM generates a response, a verification step must:
- Extract all event IDs cited in the response
- Confirm each exists in DuckDB
- Flag any citation that cannot be verified as "unverified"
- This verification result must be included in the API response payload

**Verification:** Manually inject a fabricated event ID into a test response. Verification layer flags it as unverified.

### FR-3.9 — Prompt Templates
Prompt templates must exist for 5 analyst workflows, each as a separate Python module in `prompts/`:
- `analyst_qa.py` — general analyst Q&A with evidence grounding
- `triage.py` — prioritize a set of detections, explain most critical
- `threat_hunt.py` — hypothesis-driven hunting query
- `incident_summary.py` — produce a structured incident narrative
- `evidence_explain.py` — explain what a specific raw event means in plain language

Each template must include: system prompt with "ONLY based on provided context" constraint, context injection variables, and output format specification.

**Verification:** Each template invokes successfully against a test fixture and produces structured output matching the specified format.

### FR-3.10 — Query API Endpoint
`POST /query` must accept `{question: str, case_id: str | null, filters: dict}` and return a streaming response via Server-Sent Events (SSE). The final event in the stream must include `citations: [{event_id, verified: bool}]`.

**Verification:** POST /query with a question about a fixture event returns streaming tokens followed by a citations array with at least one verified citation.

### FR-3.11 — Contextual Anomaly Detection
The detection engine must support a contextual anomaly detector that:
- Establishes per-entity baselines (partitioned by user, hostname, event_type, time-of-day bucket)
- Flags events that deviate ≥2.5 standard deviations from their entity baseline
- Includes the baseline context in every anomaly detection record ("flagged because count=X, baseline_mean=Y, stddev=Z for this user/host during this time window")
- Does NOT use global/static thresholds

**Verification:** The same event count triggers differently for two different user/host pairs with different historical baselines. Anomaly detection record contains the baseline explanation.

---

## Phase 4: Graph + Correlation
**Goal:** Build a queryable investigation graph and correlate related events into investigation threads.

### FR-4.1 — Graph Query Service
A graph query service must traverse SQLite entity edges to answer:
- `expand(entity_id, depth=N)` — return all entities within N hops
- `path(source_id, target_id)` — find paths between two entities
- `subgraph(entity_ids)` — return the induced subgraph for a set of entities

Each node in the response must include entity attributes from DuckDB (timestamps, metadata). Maximum traversal depth: 3 hops. Maximum response: 200 nodes.

**Verification:** Starting from a process entity, a 2-hop expansion returns the process's user, host, accessed files, and network connections.

### FR-4.2 — Graph API Endpoint
`GET /graph/entity/{entity_id}?depth=2` must return the subgraph centered on an entity. `GET /graph/path?from={id}&to={id}` must return paths between entities. Response format: `{nodes: [{id, type, attributes}], edges: [{source, target, type, properties}]}`.

**Verification:** API response renders correctly in the dashboard graph view (Phase 5 integration test).

### FR-4.3 — Event Clustering
A clustering service must group related events by:
1. **Shared entity cluster**: events sharing the same process PID, user, or network connection
2. **Temporal cluster**: events within 5 minutes of each other on the same host
3. **Causal chain**: process tree (parent-child PID relationships)

Each cluster must have a `relatedness_score` (0.0-1.0) and a summary of shared entities.

**Verification:** A fixture with a process tree (parent spawning 3 children, each making network connections) produces a single cluster containing all 7 events with relatedness_score > 0.8.

### FR-4.4 — Alert Aggregation
Related detections (same attack chain, same process tree, same user within 15 minutes) must be aggregated into investigation threads. Each thread must include: constituent detection IDs, time range, affected entities, ATT&CK techniques present.

**Verification:** 5 Sigma rule hits from the same process tree aggregate into 1 investigation thread.

### FR-4.5 — Graph Correlation Endpoint
`GET /graph/correlate?event_id={id}` must return all events, detections, and entities correlated with a given event, including the investigation thread it belongs to.

**Verification:** Querying a process creation event returns its parent process, child processes, network connections, and any associated detections.

---

## Phase 5: Dashboard
**Goal:** Deliver the visual investigation surface. This is first-class, not optional.

### FR-5.1 — Svelte 5 SPA Scaffold
A Svelte 5 SPA must be scaffolded in `dashboard/` using Vite 6 with `@sveltejs/adapter-static`. The built output must be served as static files by FastAPI. Served at the root path (`/`) via Caddy reverse proxy.

**Verification:** `npm run build` produces a `dist/` directory. FastAPI serves `dashboard/dist/index.html` at `GET /`.

### FR-5.2 — API Client Layer
A typed API client in TypeScript must be auto-generated from the FastAPI OpenAPI spec (using `openapi-typescript` or equivalent). All API calls must go through this client — no ad-hoc `fetch` calls.

**Verification:** API client regenerates in < 5 seconds from `openapi.json`. TypeScript compilation passes.

### FR-5.3 — AI Q&A Panel
A chat interface panel must:
- Accept analyst questions in a text input
- Connect to `POST /query` via SSE for streaming responses
- Render response tokens as they stream
- Display citations as clickable links (clicking opens the evidence drilldown panel)
- Display unverified citations with a visual warning
- Support selection of prompt template (analyst Q&A, triage, threat hunt, etc.)

**Verification:** Ask "What processes ran as SYSTEM?" against a fixture. Response streams correctly. Citation link opens the corresponding raw event.

### FR-5.4 — Detection Panel
A detection panel must:
- Display all detections for the current case, sorted by severity (critical first)
- Show: rule name, severity badge, ATT&CK technique, timestamp, affected entities
- Support filter by severity, technique, tactic, time range
- On click: open evidence drilldown showing matched raw event
- Show investigation threads (aggregated clusters) as collapsible groups

**Verification:** Load 20 detections of mixed severity. Filtering by "critical" shows only critical detections. Clicking a detection opens correct raw event.

### FR-5.5 — Timeline View
A D3.js timeline view must:
- Display events chronologically on a zoomable timeline
- Color-code events by severity (grey=info, blue=low, yellow=medium, orange=high, red=critical)
- Support filtering by event type, severity, and entity (host/user/process)
- Handle 10,000+ events without browser lag (use aggregation at high zoom levels)
- On click: open evidence drilldown for the event

**Verification:** Load 10,000 events. Timeline renders without lag. Zoom to 1-minute window shows individual events.

### FR-5.6 — Graph View (Cytoscape.js)
A Cytoscape.js graph view must:
- Start with a single focal entity (current selected detection or event)
- Default to 1-hop neighbors visible
- Support click-to-expand (2-hop, 3-hop on subsequent clicks)
- Maximum 100 visible nodes; aggregate beyond that (e.g., "svchost (47 children)")
- Use dagre layout for process trees, force-directed for relationship discovery
- Support entity type filtering (toggle visibility of hosts, users, processes, files, network, detections)
- Highlight paths (clicking two nodes shows the shortest path between them)
- Node types must be visually distinct by color/shape: host (blue square), user (green circle), process (yellow hexagon), file (grey document), network (orange diamond), detection (red octagon)

**Verification:** Load a process tree with 50+ entities. Graph renders in < 2 seconds. Progressive disclosure works. Filtering by "process" hides all non-process nodes.

### FR-5.7 — Evidence Drilldown Panel
A side panel that appears when clicking any event/detection must display:
- Raw event JSON (formatted and syntax-highlighted)
- Normalized fields in a structured table
- ATT&CK technique badge (if present)
- Related detection rules that fired on this event
- Associated graph entities (clickable links to graph view)
- Timestamp, source file, ingestion time

**Verification:** Click any event. Raw JSON displays within 500ms. All fields rendered correctly.

### FR-5.8 — Case/Session Management
Basic case management must allow:
- Create a new case (name, description)
- Switch between cases (all views filter to current case's data)
- Archive a case (hide from active list, preserve data)
- Case ID persisted in all API calls and DuckDB records

**Verification:** Create two cases, ingest different data into each. Switching cases changes all view data correctly.

---

## Phase 5 Revised: Suricata + Threat Scoring
**Goal:** Deliver Suricata-backed network detection and ATT&CK-aware threat scoring on top of the existing pipeline. These requirements reflect the actual scope implemented in Phase 5 plans (00–04), which pivoted from the original dashboard-only FR-5.x scope.

### FR-5S-1 — Suricata EVE JSON Parser
`backend/src/parsers/suricata_parser.py` must implement `parse_eve_line(line: str) -> dict` that:
- Accepts one newline-delimited EVE JSON string
- Returns a normalized-compatible dict (same keys as `normalize()` in `normalizer.py`)
- Handles 5 event types: alert, flow, dns, http, tls
- Maps `dest_ip` → `dst_ip` (EVE uses `dest_ip`; normalized schema uses `dst_ip`)
- Inverts Suricata severity: 1→critical, 2→high, 3→medium, 4→low (Snort convention)
- Falls back gracefully for unknown types (event_type = `suricata_{type}`, no exception)
- Returns a safe fallback dict for invalid JSON input (no exception)

**Verification:** `uv run pytest backend/src/tests/test_phase5.py::TestSuricataParser -v` — 7 tests PASS.

### FR-5S-2 — IngestSource.suricata + Alert Model Extension
`backend/src/api/models.py` must be extended with:
- `suricata = "suricata"` added to `IngestSource` enum
- `threat_score: int = 0` added to `Alert` model (default 0, backward compatible)
- `attack_tags: list[dict] = Field(default_factory=list)` added to `Alert` model (default [], backward compatible)

**Verification:** `uv run pytest backend/src/tests/test_phase5.py::TestModels -v` — 2 tests PASS. All 41 pre-existing tests still pass.

### FR-5S-3 — Threat Scoring Model
`backend/src/detection/threat_scorer.py` must implement `score_alert(alert, events: list[dict], graph_data: dict | None = None) -> int` using an additive 0–100 model:
- `suricata_severity_points`: critical=40, high=30, medium=20, low=10, else=0
- `sigma_hit`: +20 if `alert.rule` matches UUID regex (sigma-sourced rule)
- `recurrence`: +10 if same host/IP appears ≥3 times in `events` list
- `graph_connectivity`: +10 if `graph_data` is not None and host/IP has ≥3 alert edges
- Score capped at 100
- `graph_data=None` (default) skips the +10 graph component — avoids O(n²) ingest cost

**Verification:** `uv run pytest backend/src/tests/test_phase5.py::TestThreatScorer -v` — 3 tests PASS.

### FR-5S-4 — ATT&CK Mapper
`backend/src/detection/attack_mapper.py` must implement `map_attack_tags(alert, event) -> list[dict]` using a static lookup table with 5 entries:
- `"dns request"` category → `{"tactic": "Command and Control", "technique": "T1071.004"}`
- `"potentially bad traffic"` category → `{"tactic": "Exfiltration", "technique": "T1048"}`
- `"network trojan"` category → `{"tactic": "Command and Control", "technique": "T1095"}`
- `"malware command and control activity detected"` category → `{"tactic": "Command and Control", "technique": "T1095"}`
- `"dns_query"` event_type → `{"tactic": "Command and Control", "technique": "T1071.004"}`
- Returns `[]` for unmapped events — no guessing
- First match wins (category → event_type → rule → source+severity order)

**Verification:** `uv run pytest backend/src/tests/test_phase5.py::TestAttackMapper -v` — 2 tests PASS.

### FR-5S-5 — Route Wiring
`backend/src/api/routes.py` `_store_event()` must call `score_alert()` and `map_attack_tags()` for each new alert after all detection rules run. `POST /ingest` must accept `source=suricata` (via `IngestSource.suricata`). A `GET /threats` endpoint must return alerts filtered to `threat_score > 0`, sorted descending by score. Imports of `threat_scorer` and `attack_mapper` must be deferred (inside function body, not module-level) with `try/except ImportError` guards for graceful degradation.

**Verification:** `uv run pytest backend/src/tests/test_phase5.py::TestSuricataRoute -v` — 3 tests PASS (P5-T16, P5-T17, P5-T18).

### FR-5S-6 — Frontend Badge and Tag Pills
`frontend/src/lib/api.ts` `AlertItem` interface must be extended with `threat_score: number` and `attack_tags: Array<{ tactic: string; technique: string }>`. `frontend/src/components/panels/EvidencePanel.svelte` must render:
- A numeric score badge when `threat_score > 0`, colored green (<30), yellow (30–60), red (>60)
- ATT&CK tag pills as `{tactic} · {technique}` when `attack_tags` is non-empty
- A `getThreats()` function in `api.ts` calling `GET /threats`

**Verification:** `cd frontend && npm run build` exits 0 (TypeScript compiles without errors).

### FR-5S-7 — Infrastructure Scaffolds
- `infra/vector/vector.yaml` must contain a commented-out `suricata_eve` source scaffold block, a `normalise_suricata` transform scaffold, and a `backend_suricata` sink scaffold, each with a Windows NFQUEUE blocker explanation
- `infra/docker-compose.yml` must contain a fully commented-out `jasonish/suricata` service block with `cap_add: [net_admin, net_raw, sys_nice]`, `network_mode: host`, volume mounts, and a Windows Docker Desktop blocker comment
- `infra/suricata/suricata.yaml` and `infra/suricata/rules/local.rules` placeholder files must exist

**Verification:** `grep -c "suricata_eve" infra/vector/vector.yaml` ≥ 1. `grep -c "jasonish/suricata" infra/docker-compose.yml` ≥ 1. `grep -c "BLOCKER" infra/docker-compose.yml` ≥ 1.

### FR-5S-8 — Documentation Updates
Three docs files must be updated with Phase 5 content (append only, no prior content removed):
- `docs/decision-log.md` — 8 Phase 5 decisions including `dest_ip→dst_ip` trap, severity inversion, additive scoring model, deferred import pattern, static ATT&CK table, and Windows Docker blocker
- `docs/manifest.md` — Phase 5 file inventory: 7 new files + 6 modified files tabulated
- `docs/reproducibility.md` — Runnable validation commands for fixture, parser, scorer, ATT&CK tagging, full suite (59 tests)

**Verification:** `grep -c "dest_ip" docs/decision-log.md` ≥ 1. `grep -c "suricata_parser" docs/manifest.md` ≥ 1. `grep -c "suricata_eve_sample" docs/reproducibility.md` ≥ 1.

---

## Phase 6: Hardening + Integration
**Goal:** Transform the working prototype into a daily-use tool with operational excellence.

### FR-6.1 — osquery Integration
osquery must be installed on Windows (Chocolatey: `choco install osquery`). The system must:
- Poll osquery via `osqueryi` CLI for scheduled queries (process list, network connections, listening ports, logged-in users)
- Parse osquery JSON output through the ingestion pipeline
- Display osquery results in the timeline and graph views like other events

**Verification:** `osqueryi "SELECT * FROM processes LIMIT 10" --json` parses correctly and ingests into DuckDB.

### FR-6.2 — IOC Matching
The system must:
- Ingest IOC lists in CSV format (columns: indicator_type, value, source, severity, description)
- Match ingested events against IOCs (hash, IP, domain, URL fields)
- Create detection records for IOC matches with source attribution

**Verification:** Ingest a 100-entry IOC list. Ingest events containing one known IOC. Detection fires with correct IOC source attribution.

### FR-6.3 — Startup/Shutdown Scripts
PowerShell scripts must exist:
- `scripts/start.ps1` — starts Ollama, starts Docker (Caddy), starts FastAPI via uvicorn, waits for health check
- `scripts/stop.ps1` — gracefully stops FastAPI, stops Docker containers (not Ollama — leave model loaded)
- `scripts/status.ps1` — checks health of all components and reports

**Verification:** `start.ps1` brings system from cold to fully operational in < 3 minutes. `stop.ps1` shuts down cleanly. `status.ps1` shows all green.

### FR-6.4 — Comprehensive Smoke Test Suite
A smoke test suite (`scripts/smoke-test-full.ps1`) must verify all integration points:
- Ollama GPU: inference on GPU confirmed
- Docker-Ollama bridge: container-to-host connectivity confirmed
- Ingestion: fixture file ingests without errors
- Detection: smoke test Sigma rules match test events
- RAG: query returns cited response
- Graph: entity expansion returns nodes
- Dashboard: SPA serves correctly
- HTTPS: `curl https://localhost/health` returns 200

**Verification:** All tests pass on a clean start. Total execution time < 5 minutes.

### FR-6.5 — Structured Logging
All backend components must log to JSON format at `logs/` with fields: `timestamp`, `level`, `component`, `message`, `context` (dict). Ingestion jobs must log: events parsed, events loaded, embeddings created, edges extracted, duration.

**Verification:** After ingesting a fixture, `logs/backend.jsonl` contains structured log entries with all required fields.

### FR-6.6 — Reproducibility Receipt
`REPRODUCIBILITY_RECEIPT.md` must document: OS version, Python version, uv version, all pinned dependency versions (from lockfile), Ollama version, model checksums, Docker Compose version, and exact commands to reproduce the environment from scratch.

**Verification:** A new developer can follow the receipt on the same hardware and reach a fully operational system within 30 minutes.

### FR-6.7 — Security Hardening
- Windows Firewall rule: Ollama port 11434 accessible only from localhost (127.0.0.1) and Docker's virtual network interface. Block from all other interfaces.
- DuckDB and Chroma data directories must have restricted Windows ACLs (current user only).
- All secrets and configuration in `.env` (never hardcoded). `.env` in `.gitignore`.
- Ollama prompt injection mitigation: sanitize ingested event text by escaping potential prompt injection patterns before embedding.

**Verification:** `nmap localhost` from a different machine shows port 11434 as filtered. `.env` file is gitignored.

### FR-6.8 — Export / Report Generation
`GET /export/case/{case_id}?format=json|csv|markdown` must export:
- All detection records for the case
- Event timeline data
- AI Q&A conversation history with citations
- A printable Markdown incident summary

**Verification:** Export produces non-empty files in all 3 formats. Markdown summary is human-readable.

---

## Non-Negotiable Constraints (All Phases)

| Constraint | Enforcement |
|------------|-------------|
| Ollama runs native Windows (not Docker) | No Docker GPU passthrough; Ollama in Docker is rejected |
| Python 3.12 (not 3.14) | PyO3/pySigma compatibility |
| Single uvicorn worker | DuckDB single-writer integrity |
| No LangChain chains (use LangGraph directly) | LangChain chains are deprecated upstream |
| No LangChain Chroma wrapper (use native Chroma client) | Wrapper breaks independently of Chroma |
| No hardcoded credentials or secrets | All config via .env |
| Every LLM claim must have a citation | No uncited assertions in AI responses |
| Human-in-the-loop only | No automated response actions |
| All major capabilities must have a test, receipt, or artifact | No unverifiable claims |

---

*Requirements approved: 2026-03-15*
*Mode: YOLO — proceeding directly to roadmap*
