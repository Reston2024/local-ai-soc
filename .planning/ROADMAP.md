# Roadmap

**Project:** AI-SOC-Brain
**Date:** 2026-03-15
**Status:** IN PROGRESS — Phase 12 (API Hardening & Parser Coverage) next

---

## Summary

6 phases. Phases 1–2 build infrastructure and data. Phase 3 delivers the two core analyst capabilities (detection + AI Q&A). Phase 4 adds graph correlation. Phase 5 delivers the visual dashboard. Phase 6 hardens for daily use.

**The system is usable after Phase 3.** Phases 4–6 make it excellent.

---

## Phase 1: Foundation
**Status:** TODO
**Goal:** Install and validate all infrastructure. Every subsequent phase depends on this being correct.
**Gating requirement:** RTX 5080 GPU-accelerated Ollama inference confirmed before writing any code beyond Phase 1.

### Deliverables

| Deliverable | Files | Verification |
|-------------|-------|-------------|
| Python 3.12 venv | `pyproject.toml`, `.python-version` | `python --version` = 3.12.x, all core deps import |
| Ollama native install + GPU validated | — (native install) | `nvidia-smi` shows GPU util during inference, `ollama ps` > 0 GPU layers |
| Models pulled | — | `ollama list` shows `qwen3:14b` + `mxbai-embed-large` |
| FastAPI skeleton | `backend/main.py`, `backend/core/`, `backend/api/health.py` | `GET /health` returns 200 with all components healthy |
| DuckDB store | `backend/stores/duckdb_store.py`, `data/events.duckdb` | Single-writer + read-only pool; 60s concurrent load test passes |
| Chroma store | `backend/stores/chroma_store.py`, `data/chroma/` | PersistentClient; data survives restart; export/import round-trip |
| SQLite graph store | `backend/stores/sqlite_store.py`, `data/graph.sqlite3` | WAL mode; entity + edge schema; INSERT/SELECT test |
| Caddy HTTPS | `docker-compose.yml`, `config/caddy/Caddyfile` | `curl -k https://localhost/health` returns 200 |
| Docker-Ollama bridge | `docker-compose.yml` | `curl host.docker.internal:11434` from container returns 200 |
| Phase 1 smoke tests | `scripts/smoke-test-phase1.ps1` | All checks pass/fail with clear output |
| Structured logging | `backend/core/logging.py` | `logs/backend.jsonl` produced; JSON fields verified |

### Tasks

```
[ ] 1. Validate Python 3.14 vs 3.12 compatibility (test pySigma, chromadb, duckdb, evtx imports)
[ ] 2. Install Python 3.12 via `uv python install 3.12` and create venv
[ ] 3. Create pyproject.toml with all Phase 1 dependencies (pinned versions)
[ ] 4. Install Ollama (native Windows, download OllamaSetup.exe from ollama.com/download)
[ ] 5. Set CUDA_VISIBLE_DEVICES=0, OLLAMA_HOST=0.0.0.0, OLLAMA_ORIGINS=* as system env vars
[ ] 6. Validate RTX 5080 GPU acceleration: ollama run llama3.2:1b + nvidia-smi check
[ ] 7. Pull target models: qwen3:14b, mxbai-embed-large
[ ] 8. Create backend/ directory structure (main.py, core/, api/, services/, stores/)
[ ] 9. Implement FastAPI lifespan with embedded store initialization
[ ] 10. Implement DuckDB store with single-writer + read-only connection pattern
[ ] 11. Implement Chroma PersistentClient store
[ ] 12. Implement SQLite WAL store with entity + edge schema
[ ] 13. Implement GET /health endpoint (checks Ollama, DuckDB, Chroma, SQLite)
[ ] 14. Create docker-compose.yml with Caddy service
[ ] 15. Create Caddyfile with reverse_proxy to localhost:8000 + HTTPS
[ ] 16. Validate Docker-to-Ollama bridge (host.docker.internal:11434)
[ ] 17. Implement JSON structured logging
[ ] 18. Create smoke-test-phase1.ps1
[ ] 19. Run all smoke tests, fix any failures
[ ] 20. Commit Phase 1
```

### Definition of Done

- [ ] `python --version` = 3.12.x
- [ ] `nvidia-smi` shows GPU utilization during `ollama run llama3.2:1b`
- [ ] `ollama ps` shows GPU layer count > 0
- [ ] `ollama list` shows `qwen3:14b` and `mxbai-embed-large`
- [ ] `GET https://localhost/health` returns `{"status": "healthy", "ollama": true, "duckdb": true, "chroma": true, "sqlite": true}`
- [ ] DuckDB concurrent load test passes (60s, no hangs)
- [ ] Chroma data survives restart
- [ ] Export/import round-trip test passes
- [ ] Docker-to-Ollama bridge: `curl host.docker.internal:11434` from container = 200
- [ ] smoke-test-phase1.ps1 all green
- [ ] No hardcoded secrets

### Pitfalls This Phase Addresses

- Python 3.14 PyO3/PEP649 incompatibility → use 3.12
- RTX 5080 Blackwell CUDA failure → Ollama 0.13+, CUDA_VISIBLE_DEVICES=0
- Docker-to-Ollama bridge → OLLAMA_HOST=0.0.0.0
- DuckDB concurrency deadlocks → single-writer pattern from the start
- Chroma version instability → pin + export/import script

---

## Phase 2: Ingestion Pipeline
**Status:** TODO
**Depends on:** Phase 1 complete
**Goal:** Ingest evidence from EVTX, JSON, NDJSON, and CSV into normalized storage with entity edge extraction.

### Deliverables

| Deliverable | Files | Verification |
|-------------|-------|-------------|
| Normalized event schema | `backend/models/event.py` | 10 fixture events validate without error | 6/9 | In Progress|  | New parser added without changing existing code |
| EVTX parser (pyevtx-rs) | `ingestion/parsers/evtx.py` | 100MB+ Security.evtx parses without memory spike |
| JSON/NDJSON/CSV parsers | `ingestion/parsers/json_ndjson.py`, `ingestion/parsers/csv_parser.py` | 3 fixture files ingest correctly | 2/3 | Complete    | 2026-03-16 | Deduplication on re-ingest tested |
| Chroma embedding loader | `ingestion/loader.py` | Semantic search returns relevant events |
| Entity edge extractor | `ingestion/loader.py` | Process-to-user + process-to-network edges confirmed |
| Ingest API endpoint | `backend/api/ingest.py` | File upload + async progress reporting works |
| Fixtures | `fixtures/*.evtx.sample`, `fixtures/*.ndjson`, `fixtures/*.csv`, `fixtures/*.json` | All 4 formats ingest without error |
| Field mapping documentation | `detections/pipelines/windows_field_map.py` | Sigma canonical fields mapped to schema columns |

### Tasks

```
[ ] 1. Test pyevtx-rs installation on Python 3.12 + Windows: `pip install evtx`, import test
[ ] 2. Design + document normalized event schema (Pydantic NormalizedEvent)
[ ] 3. Create field name mapping table: Sigma canonical → normalized schema
[ ] 4. Implement BaseParser interface
[ ] 5. Implement EVTX parser (pyevtx-rs, batched, corruption handling)
[ ] 6. Implement JSON/NDJSON parser
[ ] 7. Implement CSV parser
[ ] 8. Implement parser registry (extension → parser class)
[ ] 9. Implement DuckDB event schema (CREATE TABLE normalized_events ...)
[ ] 10. Implement DuckDB loader (batched INSERT, deduplication)
[ ] 11. Implement Chroma embedding loader (batched, model version metadata)
[ ] 12. Implement entity edge extractor (process-user, process-host, process-file, process-network)
[ ] 13. Implement ingestion orchestrator (parse → normalize → load → embed → extract_edges)
[ ] 14. Implement POST /ingest endpoint with file upload + async job
[ ] 15. Implement GET /ingest/{job_id} progress endpoint
[ ] 16. Create fixture files (all 4 formats)
[ ] 17. Run all ingestion tests with fixtures
[ ] 18. Verify DuckDB event count, Chroma doc count, SQLite edge count after ingestion
[ ] 19. Commit Phase 2
```

### Definition of Done

- [ ] `NormalizedEvent` Pydantic schema defined and validated with 10 fixtures
- [ ] EVTX fixture parses without memory spike > 2GB
- [ ] All 3 parser types ingest correctly
- [ ] Deduplication: re-ingesting same file produces same event count
- [ ] Chroma: semantic search for "PowerShell execution" returns relevant results
- [ ] SQLite: process-to-user and process-to-network edges present after ingestion
- [ ] POST /ingest + progress endpoint working
- [ ] Field mapping documented (Sigma canonical → schema columns)

---

## Phase 3: Detection + RAG (Scoped) ✅
**Status:** COMPLETE — 2026-03-16
**Depends on:** Phase 2 complete (need ingested events in DuckDB + Chroma)
**Goal:** OpenSearch live indexing + Sigma YAML detection rules surfaced in /alerts. Keep all 32 existing tests passing.

**Plans:** 3/3 plans complete

Plans:
- [x] 03-01-PLAN.md — Wave 0: Write test_phase3.py stubs before any implementation
- [x] 03-02-PLAN.md — Activate OpenSearch: remove sink guard, add GET /search, wire docker-compose + vector.yaml
- [x] 03-03-PLAN.md — Sigma detection: sigma_loader.py + suspicious_dns.yml + routes.py integration

> ⚠️ **Research flag: HIGH** — Custom pySigma DuckDB backend is custom engineering. No reference implementation exists. Budget extra time (3–5 days beyond estimate).

### Deliverables

| Deliverable | Files | Verification |
|-------------|-------|-------------|
| pySigma DuckDB backend | `detections/backends/duckdb.py`, `detections/pipelines/windows_field_map.py` | 10 smoke test rules match test events |
| Sigma rule loading + compilation | `detections/compiler.py` | 20+ Sigma rules from SigmaHQ corpus load without error |
| Detection matcher | `detections/matcher.py` | Mimikatz fixture → T1003 detection fires exactly once |
| ATT&CK enrichment | `backend/services/attack.py` | Detection shows technique name + tactic |
| Detection SQLite records | `backend/stores/sqlite_store.py` | Detection records + detection-to-event edges |
| GET/POST /detect endpoint | `backend/api/detect.py` | Sortable/filterable list + drilldown to raw event |
| Sigma smoke test suite | `tests/sigma_smoke/` | All 10 tests pass |
| Contextual anomaly detector | `detections/anomaly.py` | Same count triggers differently per entity/context |
| LangGraph RAG pipeline | `backend/services/retrieval.py` | Query returns response with at least 1 verified citation |
| Citation verification layer | `backend/services/retrieval.py` | Fabricated event ID flagged as unverified |
| Prompt templates (5) | `prompts/` | All 5 templates produce structured output |
| POST /query endpoint (SSE) | `backend/api/query.py` | Streaming response + citations array |

### Tasks

```
[ ] 1. Research pySigma SQL backend base class API + Cookiecutter template
[ ] 2. Design field mapping pipeline (all Windows Sigma canonical fields to NormalizedEvent columns)
[ ] 3. Implement custom pySigma DuckDB backend (SQL base class extension)
[ ] 4. Test backend with 5 simple Sigma rules end-to-end
[ ] 5. Create Sigma smoke test suite (10 rules + crafted test events)
[ ] 6. Implement Sigma rule loader (scan YAML, compile, cache, report status)
[ ] 7. Implement detection matcher (run compiled SQL against DuckDB events)
[ ] 8. Implement detection SQLite records + detection-to-event edges
[ ] 9. Implement ATT&CK enrichment service
[ ] 10. Implement GET /detect and POST /detect/run endpoints
[ ] 11. Implement contextual anomaly detector (per-entity baselines, z-score)
[ ] 12. Run sigma smoke test suite — fix any failures
[ ] 13. Implement LangGraph RAG pipeline (embed → search → context → prompt → stream)
[ ] 14. Implement Ollama streaming client (httpx async)
[ ] 15. Implement citation extraction + verification layer
[ ] 16. Write 5 prompt templates
[ ] 17. Implement POST /query SSE endpoint
[ ] 18. Test RAG pipeline with cybersecurity fixture queries
[ ] 19. Validate no hallucinated IOCs in test suite
[ ] 20. Commit Phase 3
```

### Definition of Done

- [ ] 10 Sigma smoke test rules all match their test events
- [ ] 20+ SigmaHQ windows-sysmon rules load without error
- [ ] Mimikatz fixture → T1003 detection fires exactly once with ATT&CK enrichment
- [ ] Contextual anomaly: same event count triggers differently for different entity baselines
- [ ] POST /query streaming response includes at least 1 verified citation
- [ ] Citation verification: fabricated event ID flagged as unverified
- [ ] All 5 prompt templates produce structured output
- [ ] No fabricated IOCs in any automated test query

---

## Phase 4: Graph + Correlation ✅
**Status:** COMPLETE — 2026-03-16
**Depends on:** Phase 3 (need detection records + entity edges from ingestion)
**Goal:** Build queryable investigation graph and correlate events into investigation threads.

**Plans:** 3/3 plans complete

Plans:
- [x] 04-01-PLAN.md — Wave 0: test_phase4.py stubs (8 xfail classes)
- [x] 04-02-PLAN.md — Wave 1: Replace graph models + rewrite builder.py + ThreatGraph.svelte src/dst update
- [ ] 04-03-PLAN.md — Wave 2: _correlate() with 4 patterns + full GET /graph/correlate route

### Deliverables

| Deliverable | Files | Verification |
|-------------|-------|-------------|
| Graph query service | `backend/services/graph_builder.py`, `graph/query.py` | 2-hop expansion from process returns user + host + files + network |
| GET /graph endpoint | `backend/api/graph.py` | Entity expansion + path query working |
| Event clustering | `correlation/clustering.py` | Process tree fixture → 1 cluster, relatedness_score > 0.8 |
| Alert aggregation | `correlation/aggregation.py` | 5 detections from same process tree → 1 investigation thread | 5/5 | Complete   | 2026-03-16 | Event drilldown returns full correlation context |

### Tasks

```
[ ] 1. Implement graph query service (expand, path, subgraph) over SQLite edges
[ ] 2. Implement entity attribute fetching from DuckDB
[ ] 3. Implement GET /graph/entity/{id} and GET /graph/path endpoints
[ ] 4. Implement event clustering (shared entity, temporal, causal chain)
[ ] 5. Implement alert aggregation into investigation threads
[ ] 6. Implement GET /graph/correlate endpoint
[ ] 7. Test with process tree fixture (parent + children + network)
[ ] 8. Validate max traversal depth limit (3 hops)
[ ] 9. Validate max response size limit (200 nodes)
[ ] 10. Commit Phase 4
```

### Definition of Done

- [ ] 2-hop expansion from a process entity returns user, host, files, network connections
- [ ] Path query finds path between two related entities
- [ ] Process tree fixture clusters into 1 cluster with relatedness_score > 0.8
- [ ] 5 detections from same process tree aggregate into 1 investigation thread
- [ ] Max node limit enforced (query returning > 200 nodes truncates with metadata)

---

## Phase 5: Dashboard ✅
**Status:** COMPLETE — 2026-03-16
**Depends on:** Phase 4 (all API endpoints stable and returning real data)
**Goal:** Suricata EVE JSON ingestion, ATT&CK-aware threat scoring, and score/tag display in the existing dashboard.

**Plans:** 5/5 plans complete

Plans:
- [ ] 05-00-PLAN.md -- Wave 0: test_phase5.py stubs (18 xfail) + parser/scorer/mapper stubs + EVE fixture
- [ ] 05-01-PLAN.md -- Wave 1: Suricata EVE parser + IngestSource.suricata + Alert model extension
- [ ] 05-02-PLAN.md -- Wave 1: Threat scorer (score_alert) + ATT&CK mapper (map_attack_tags)
- [ ] 05-03-PLAN.md -- Wave 2: Route wiring + Vector/docker-compose scaffolds + frontend badges
- [ ] 05-04-PLAN.md -- Wave 3: Docs (decision-log, manifest, reproducibility)

### Deliverables

| Deliverable | Files | Verification |
|-------------|-------|-------------|
| Svelte 5 SPA scaffold | `dashboard/package.json`, `dashboard/src/` | `npm run build` succeeds, FastAPI serves at `/` |
| API client layer | `dashboard/src/api/` | Type-safe, auto-generated from OpenAPI spec |
| AI Q&A panel | `dashboard/src/components/QueryPanel.svelte` | Streaming response + citation links working |
| Detection panel | `dashboard/src/components/DetectionPanel.svelte` | Sort/filter + evidence drilldown working |
| Timeline view (D3.js) | `dashboard/src/components/Timeline.svelte` | 10K events render without lag; zoom works |
| Graph view (Cytoscape.js) | `dashboard/src/components/GraphView.svelte` | Progressive disclosure, dagre layout, entity filter |
| Evidence drilldown panel | `dashboard/src/components/EvidencePanel.svelte` | Raw JSON + structured fields render in < 500ms |
| Case management | `dashboard/src/components/CaseSelector.svelte` | Switching cases filters all views |

### Tasks

```
[ ] 1. Scaffold Svelte 5 project with Vite, adapter-static
[ ] 2. Install Cytoscape.js and D3.js
[ ] 3. Generate TypeScript API client from FastAPI OpenAPI spec
[ ] 4. Implement app shell (navigation: Q&A, Detections, Timeline, Graph, Cases)
[ ] 5. Implement AI Q&A panel with SSE streaming
[ ] 6. Implement detection panel with sort/filter
[ ] 7. Implement evidence drilldown panel (raw JSON + structured)
[ ] 8. Implement D3.js timeline (zoom, filter, color-code, 10K event test)
[ ] 9. Implement Cytoscape.js graph view (1-hop default, progressive disclosure)
[ ] 10. Implement graph entity type filtering
[ ] 11. Implement visual aggregation for large node sets (> 100)
[ ] 12. Implement dagre layout for process trees, force-directed for discovery
[ ] 13. Implement case management UI
[ ] 14. Build and serve via FastAPI static files + Caddy
[ ] 15. End-to-end test: ingest fixture → detection fires → timeline shows event → graph expands → Q&A answers with citation
[ ] 16. Test graph view with 200+ node dataset (usability test)
[ ] 17. Fix any graph hairball issues from 200+ node test
[ ] 18. Commit Phase 5
```

### Definition of Done

- [ ] `npm run build` produces dist/; FastAPI serves it at `/`
- [ ] Q&A panel streams tokens + citation links open evidence drilldown
- [ ] Detection panel: filter by critical shows only critical; click opens raw event
- [ ] Timeline: 10K events render without lag; 1-minute zoom shows individual events
- [ ] Graph: progressive disclosure works; max 100 nodes visible; entity filter works
- [ ] 200-node test: analyst finds key entities within 30 seconds
- [ ] Evidence drilldown renders raw JSON in < 500ms
- [ ] Case switching filters all views correctly

---

## Phase 6: Hardening + Integration ✅
**Status:** COMPLETE — 2026-03-16
**Depends on:** Phase 5 (system fully functional, ready for operational polish)
**Goal:** Threat Causality & Investigation Engine — reconstruct attack chains from correlated events, expose via investigation graph APIs, and surface in the SOC dashboard.

> **Note:** Scope redefined from original roadmap (osquery/IOC/hardening) by PRD in CONTEXT.md. Original hardening work is deferred.

**Plans:** 6/6 plans complete

Plans:
- [ ] 06-00-PLAN.md — Wave 0: TDD stubs (14 xfail) + causality package stubs + ThreatGraph src/dst bug fix
- [ ] 06-01-PLAN.md — Wave 1: entity_resolver + attack_chain_builder (parallel)
- [ ] 06-02-PLAN.md — Wave 1: mitre_mapper + scoring (parallel with 06-01)
- [ ] 06-03-PLAN.md — Wave 2: causality engine orchestrator + investigation_summary prompt
- [ ] 06-04-PLAN.md — Wave 3: API endpoints (GET /graph/{id}, GET /entity/{id}, GET /attack_chain/{id}, POST /query, POST /investigate/{id}/summary)
- [ ] 06-05-PLAN.md — Wave 4: Dashboard (AttackChain.svelte + InvestigationPanel.svelte + api.ts extensions)

### Deliverables

| Deliverable | Files | Verification |
|-------------|-------|-------------|
| Causality engine package | `backend/causality/engine.py`, `entity_resolver.py`, `attack_chain_builder.py`, `mitre_mapper.py`, `scoring.py` | 14 test_phase6.py tests XPASS |
| Investigation API endpoints | `backend/src/api/routes.py` | GET /graph/{alert_id}, GET /entity/{id}, GET /attack_chain/{alert_id}, POST /query return 200 |
| AI investigation summary | `prompts/investigation_summary.py` | POST /investigate/{alert_id}/summary returns summary string |
| Attack chain dashboard | `frontend/src/components/graph/AttackChain.svelte`, `panels/InvestigationPanel.svelte` | npm run build exits 0 |
| ThreatGraph bug fix | `frontend/src/components/graph/ThreatGraph.svelte` | Edges render (e.src/e.dst mapping fixed) |

### Definition of Done

- [ ] `uv run pytest backend/src/tests/test_phase6.py -v` — all 14 tests XPASS
- [ ] `uv run pytest backend/src/tests/ -v` — full suite green (no regressions)
- [ ] `cd frontend && npm run build` exits 0
- [ ] GET /graph/{alert_id} returns 200 with nodes + edges + techniques + score
- [ ] GET /entity/{entity_id} returns 200 with entity attributes + related events
- [ ] GET /attack_chain/{alert_id} returns 200 with chain ordered by timestamp
- [ ] POST /query returns 200 with paginated graph results
- [ ] POST /investigate/{alert_id}/summary returns 200 with AI summary string
- [ ] AttackChain.svelte renders attack graph with dagre layout and orange attack-path highlighting
- [ ] InvestigationPanel.svelte shows score badge, MITRE techniques, AI summary button

---

## Phase 7: Threat Hunting & Case Management ✅
**Status:** COMPLETE — 2026-03-17
**Depends on:** Phase 6 (causality engine, graph model, DuckDB + SQLite stores)
**Goal:** Full investigation workflow layer — structured cases, threat hunting queries, timeline reconstruction, and forensic artifact storage.

**Plans:** 9/9 plans complete

Plans:
- [ ] 07-00-PLAN.md — Wave 0: xfail stubs (16) + backend/investigation/ package stubs + SQLiteStore DDL extension
- [ ] 07-01-PLAN.md — Wave 1: case_manager.py + tagging.py + SQLiteStore CRUD methods
- [ ] 07-02-PLAN.md — Wave 1: hunt_engine.py (4 DuckDB SQL templates + execute_hunt) — parallel with 07-01
- [ ] 07-03-PLAN.md — Wave 2: timeline_builder.py + artifact_store.py
- [ ] 07-04-PLAN.md — Wave 3: investigation_routes.py (8 endpoints) + main.py router mount
- [x] 07-05-PLAN.md — Wave 4: CasePanel.svelte + HuntPanel.svelte + api.ts Phase 7 extensions (completed 2026-03-17)
- [ ] 07-06-PLAN.md — Gap closure Wave 1: App.svelte tab nav + import all 4 new panels
- [ ] 07-07-PLAN.md — Gap closure Wave 1: HuntRequest.template_id rename + integration round-trip test
- [ ] 07-08-PLAN.md — Gap closure Wave 1: scripts/.cmd wrappers + REPRODUCIBILITY_RECEIPT.md + README.md PS7 docs

### Deliverables

| Deliverable | Files | Verification |
|-------------|-------|-------------|
| Investigation package | `backend/investigation/` (6 modules) | 16 test_phase7.py tests XPASS |
| SQLite schema extension | `backend/stores/sqlite_store.py` | investigation_cases, case_artifacts, case_tags tables |
| Case management API | `POST /api/cases`, `GET /api/cases`, `GET /api/cases/{id}`, `PATCH /api/cases/{id}` | P7-T04/T05/T06/T07 XPASS |
| Threat hunting API | `POST /api/hunt`, `GET /api/hunt/templates` | P7-T10/T11 XPASS |
| Timeline API | `GET /api/cases/{id}/timeline` | P7-T13 XPASS |
| Artifact API | `POST /api/cases/{id}/artifacts` | P7-T15 XPASS |
| Dashboard panels | `frontend/src/components/panels/CasePanel.svelte`, `HuntPanel.svelte` | npm run build exits 0 |

### Definition of Done

- [ ] `uv run pytest backend/src/tests/test_phase7.py -v` — all 16 tests XPASS (P7-T01 through P7-T16)
- [ ] `uv run pytest backend/src/tests/ -v` — full suite green (no regressions from Phases 3–6)
- [ ] `cd frontend && npm run build` exits 0
- [ ] POST /api/cases returns 200 with case_id
- [ ] GET /api/cases returns paginated list
- [ ] GET /api/hunt/templates returns 4 templates (suspicious_ip_comms, powershell_children, unusual_auth, ioc_search)
- [ ] GET /api/cases/{id}/timeline returns ordered timeline entries with confidence_score
- [ ] POST /api/cases/{id}/artifacts returns artifact_id and writes file to data/artifacts/
- [ ] CasePanel.svelte renders case list, create form, timeline view (Svelte 5 runes)
- [ ] HuntPanel.svelte renders template selector, params, results table, pivot-to-case button

---

## Phased Capability Timeline

| Capability | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 | Phase 6 | Phase 7 |
|-----------|---------|---------|---------|---------|---------|---------|---------|
| Infrastructure (Ollama, FastAPI, Caddy) | ✓ | | | | | | |
| EVTX/JSON/CSV ingestion | | ✓ | | | | | |
| Normalized event storage | | ✓ | | | | | |
| Sigma rule detection | | | ✓ | | | | |
| ATT&CK enrichment | | | ✓ | | | | |
| AI Q&A with citations | | | ✓ | | | | |
| Contextual anomaly detection | | | ✓ | | | | |
| Graph correlation | | | | ✓ | | | |
| Event clustering / investigation threads | | | | ✓ | | | |
| Timeline view | | | | | ✓ | | |
| Graph visualization | | | | | ✓ | | |
| Detection panel + drilldown | | | | | ✓ | | |
| Causality engine + attack chain reconstruction | | | | | | ✓ | |
| AI investigation summaries | | | | | | ✓ | |
| Interactive attack graph (dagre + highlighting) | | | | | | ✓ | |
| MITRE ATT&CK expanded mapping (25+ techniques) | | | | | | ✓ | |
| Structured case management (SQLite-backed) | | | | | | | ✓ |
| Threat hunting queries (4 DuckDB templates) | | | | | | | ✓ |
| Timeline reconstruction with confidence scoring | | | | | | | ✓ |
| Forensic artifact storage | | | | | | | ✓ |
| Case + Hunt dashboard panels | | | | | | | ✓ |

**System becomes analyst-usable at Phase 3 completion.**
**System becomes excellent at Phase 5 completion.**
**System becomes production-quality at Phase 6 completion.**
**System becomes investigation-ready at Phase 7 completion.**

---

## Component Decisions (Final)

| Component | Decision | Phase | Rationale |
|-----------|----------|-------|-----------|
| ollama/ollama | **USE NOW** | Phase 1 | Core LLM runtime, native Windows, RTX 5080 |
| chroma-core/chroma | **USE NOW** | Phase 1 | Embedded PersistentClient, hybrid search |
| langchain-ai/langgraph | **USE NOW** | Phase 3 | RAG orchestration, human-in-the-loop. Use directly, not LangChain chains. |
| SigmaHQ/sigma | **USE NOW** | Phase 3 | Detection rule corpus |
| SigmaHQ/pySigma | **USE NOW** | Phase 3 | Rule compilation, custom DuckDB backend |
| SigmaHQ/sigma-cli | **USE NOW** | Phase 3 | Rule management CLI |
| cytoscape-dagre | **USE NOW** | Phase 6 | Hierarchical DAG layout for attack chain visualization |
| mitreattack-python | **REJECT** | — | Requires 12MB STIX bundle download; static dict approach sufficient |
| osquery/osquery | **USE NOW** | Phase 8 | Deferred from Phase 6 — live Windows telemetry via log-tail collector |
| open-webui/open-webui | **DEFER** | Phase 6+ | Optional companion chat UI. Not a replacement for custom dashboard. |
| Velocidex/velociraptor | **DEFER** | If multi-host | Fleet tool, overkill for single desktop |
| wazuh/wazuh | **REJECT** | — | 8+ vCPU Java fleet SIEM. No unique value vs DuckDB + Sigma + osquery. |

---

## Phase 8: Production Hardening & Live Telemetry ✅

**Goal:** Fix integration test regressions, add live osquery telemetry collection, expose a telemetry status API, and produce a reproducible smoke test + documentation for the operational system.
**Status:** COMPLETE — 2026-03-17
**Requirements:** P8-T01, P8-T02, P8-T03, P8-T04, P8-T05, P8-T06, P8-T07, P8-T08, P8-T09, P8-T10, P8-T11, P8-T12
**Depends on:** Phase 7
**Plans:** 4/4 plans executed

Plans:
- [x] 08-00-PLAN.md — Wave 0 (TDD baseline): Fix 4 failing integration tests + create xfail stubs (P8-T01–T04, P8-T08)
- [x] 08-01-PLAN.md — Wave 1: OsqueryCollector full implementation + OSQUERY_ENABLED config + main.py lifespan wiring
- [x] 08-02-PLAN.md — Wave 2: GET /api/telemetry/osquery/status endpoint + config/osquery/osquery.conf
- [x] 08-03-PLAN.md — Wave 3 (final): smoke-test-phase8.ps1 + REPRODUCIBILITY_RECEIPT.md + ARCHITECTURE.md updates

### Definition of Done

- [x] `uv run pytest -q --tb=short` — 0 failures (4 integration test regressions fixed)
- [x] `uv run pytest tests/unit/test_osquery_collector.py -v` — P8-T01/T02/T03/T04 all XPASS
- [x] `uv run pytest tests/integration/test_osquery_pipeline.py -v` — P8-T08 XPASS
- [x] `GET /api/telemetry/osquery/status` returns 200 + JSON with enabled/running/lines_processed fields
- [x] `config/osquery/osquery.conf` exists with 4 scheduled queries
- [x] `scripts/smoke-test-phase8.ps1` exists and validates HTTPS health + Ollama GPU layers
- [x] REPRODUCIBILITY_RECEIPT.md — no TBD version placeholders for core Python packages
- [x] ARCHITECTURE.md — OsqueryCollector section present

---

---

## Phase 9: Intelligence & Analyst Augmentation ✅
**Status:** COMPLETE — 2026-03-26
**Depends on:** Phase 8 (full investigation platform operational)
**Goal:** Transform the system from a data-driven investigation tool into an intelligent SOC assistant that prioritizes threats, explains what is happening, and reduces analyst cognitive load.

**Plans:** 7/7 plans complete

Plans:
- [x] 09-00-PLAN.md — Wave 0: TDD stubs (all 9 xfail test classes across 7 test files)
- [ ] 09-01-PLAN.md — Wave 1: backend/intelligence/ package — risk_scorer.py + anomaly_rules.py
- [ ] 09-02-PLAN.md — Wave 1: SQLite schema extension — risk_score column + saved_investigations table (parallel with 09-01)
- [ ] 09-03-PLAN.md — Wave 2: POST /api/score + GET /api/top-threats routers + main.py wiring
- [ ] 09-04-PLAN.md — Wave 2: explain_engine.py + POST /api/explain router (parallel with 09-03)
- [ ] 09-05-PLAN.md — Wave 3: Dashboard upgrade — InvestigationPanel.svelte risk badges + panels + api.ts extensions
- [x] 09-06-PLAN.md — Wave 4: Saved investigations API + full Phase 9 suite verification
 (completed 2026-03-26)

### Requirements
- P9-T01: Risk scoring engine assigns numeric scores to events, entities, and attack paths
- P9-T02: Anomaly/prioritization layer flags unusual process chains and parent-child relationships
- P9-T03: AI analyst (Ollama) explains attack chains grounded in stored evidence
- P9-T04: Investigation explanation engine generates "what happened", "why it matters", "next steps"
- P9-T05: Dashboard shows risk scores, highlighted attack path, top suspicious entities
- P9-T06: /api/score endpoint returns risk-scored entities
- P9-T07: /api/explain endpoint returns Ollama-generated grounded explanation
- P9-T08: /api/top-threats endpoint returns ranked threat list
- P9-T09: Case management — save investigation snapshot, store graph + metadata, retrieve
- P9-T10: Verification — system identifies most suspicious node, AI explanation matches graph evidence

---

*Roadmap generated: 2026-03-15*
*Phase 6 scope updated: 2026-03-16 (Threat Causality Engine — see 06-CONTEXT.md)*
*Phase 7 added: 2026-03-17 (Threat Hunting & Case Management — see 07-CONTEXT.md)*
*Phase 8 added: 2026-03-17 (Production Hardening & Live Telemetry — see 08-CONTEXT.md)*
*Phase 9 added: 2026-03-17 (Intelligence & Analyst Augmentation)*

## Phase 10: Compliance Hardening
**Status:** TODO
**Depends on:** Phase 9 complete
**Goal:** Close the material compliance gaps identified in the audit-grade compliance report (2026-03-25). Deliver: CI/CD pipeline, prompt injection sanitization, missing operational scripts, Caddy hardening, dependency pinning completion, API authentication, LLM audit logging, and security test coverage. Move posture from "prototype" to "partially compliant / audit-ready for limited scope."

**Plans:** 6/9 plans executed

Plans:
- [ ] 10-01-PLAN.md — Wave 0: TDD stubs for all Phase 10 test files
- [ ] 10-02-PLAN.md — Wave 1: Prompt injection sanitization (normalizer.py + security tests)
- [ ] 10-03-PLAN.md — Wave 1: API authentication layer (auth.py + main.py wiring)
- [ ] 10-04-PLAN.md — Wave 1: LLM audit logging (ollama_client.py + logging.py)
- [ ] 10-05-PLAN.md — Wave 2: Dependency pinning + REPRODUCIBILITY_RECEIPT.md VERIFIED
- [ ] 10-06-PLAN.md — Wave 2: CI/CD pipeline (.github/workflows/ci.yml)
- [ ] 10-07-PLAN.md — Wave 3: Firewall scripts (configure-firewall.ps1 + verify-firewall.ps1)
- [ ] 10-08-PLAN.md — Wave 3: Docker/Caddy hardening + ACL script
- [ ] 10-09-PLAN.md — Wave 4: Documentation cleanup (manifest, ADR-019, reproducibility)

### Requirements
- P10-T01: CI/CD pipeline — GitHub Actions workflow with lint, test, dependency-audit, secret-scan jobs; test results are machine-verifiable artifacts
- P10-T02: Prompt injection sanitization — ingestion/normalizer.py scrubs LLM injection patterns before embedding; tested by new security tests
- P10-T03: Firewall config script — scripts/configure-firewall.ps1 blocks Ollama port 11434 from non-local interfaces; scripts/verify-firewall.ps1 checks rule state
- P10-T04: Caddy admin hardening — docker-compose.yml CADDY_ADMIN fixed to 127.0.0.1:2019; Caddy image pinned to immutable digest
- P10-T05: Dependency pinning — all pyproject.toml >= specifiers converted to == using uv.lock as source; backend/requirements.txt removed; REPRODUCIBILITY_RECEIPT.md TBD entries completed
- P10-T06: API authentication — shared secret token (env-configured) on all non-health endpoints; Depends() guard; tests for 401 behavior
- P10-T07: LLM audit logging — ollama_client.py logs prompt hash + response hash to dedicated logs/llm_audit.jsonl handler
- P10-T08: Data directory ACL script — scripts/configure-acls.ps1 enforces icacls restriction on data/
- P10-T09: Security test suite — tests/security/ with injection scrubbing tests, Sigma SQL injection test, auth tests, file upload path traversal test
- P10-T10: Documentation cleanup — docs/manifest.md updated to Phase 9 reality; REPRODUCIBILITY_RECEIPT.md status → VERIFIED; backend/src/ retirement ADR-019

---

*Phase 10 added: 2026-03-26 (Compliance Hardening — from audit report 2026-03-25)*

---

## Phase 11: Cleanup & Coverage
**Status:** COMPLETE
**Depends on:** Phase 10 complete
**Goal:** Complete the deferred cleanup items from Phase 10: delete the legacy `backend/src/` directory, pin the Caddy image digest, raise test coverage from the Phase 10 baseline (25%) toward 70%, and update CI coverage threshold to match.

### Requirements
- P11-T01: Delete `backend/src/` — remove the entire directory; verify no import errors; update docs/manifest.md deprecated paths section
- P11-T02: Pin Caddy image digest — run `docker inspect caddy:2.9-alpine` to get the immutable digest; update `docker-compose.yml` image reference to `caddy:2.9-alpine@sha256:<digest>`
- P11-T03: Raise test coverage to ≥70% — add unit tests for ingestion pipeline, detection/matching, and store wrappers until `pytest --cov-fail-under=70` passes; update CI threshold from 25 to 70
- P11-T04: Documentation update — update docs/manifest.md to remove `backend/src/` from deprecated paths (it no longer exists); update ROADMAP.md status for Phase 11

**Plans:** 4/4 plans complete

Plans:
- [x] 11-01-PLAN.md — Wave 0 test stubs (pyproject.toml marker, 5 new test files)
- [x] 11-02-PLAN.md — backend/src/ deletion + Caddy digest pin
- [x] 11-03-PLAN.md — Coverage tests: matcher, stores, parsers, loader, timeline_builder
- [x] 11-04-PLAN.md — CI threshold 70 + documentation cleanup

---

*Phase 11 added: 2026-03-26 (Cleanup & Coverage — deferred items from Phase 10)*

---

## Phase 12: API Hardening & Parser Coverage
**Status:** TODO
**Depends on:** Phase 11 complete
**Goal:** Move the repo from B to A- on the external security critique scorecard. Three attack surfaces: (1) API surface — add rate limiting and request size guards so the local endpoint can't be trivially abused; (2) EVTX parser — currently 15% test coverage, the most critical ingestion path for Windows SOC work; (3) PR workflow — Phase 12 is executed on a feature branch and merged via pull request, establishing the first visible PR in the repo's history and closing the "0 PRs" credibility gap.

### Requirements
- P12-T01: API rate limiting — add per-endpoint rate limiting to FastAPI using `slowapi` (or equivalent); configure sensible defaults for ingest, detect, query, and investigate endpoints; add tests
- P12-T02: Request size limits — enforce max body size on ingest and query endpoints to prevent memory exhaustion from oversized evidence payloads; configure in Caddy (client_max_body_size) and FastAPI (ContentLengthLimit middleware)
- P12-T03: EVTX parser coverage — raise `ingestion/parsers/evtx_parser.py` from 15% to ≥60% test coverage; tests must cover valid EVTX parsing, malformed input handling, and field normalization output
- P12-T04: Caddy image digest pin — complete P11-T02 deferred item: run `docker inspect caddy:2.9-alpine`, update `docker-compose.yml` image to `caddy:2.9-alpine@sha256:<digest>`; requires Docker Desktop running
- P12-T05: PR workflow — all Phase 12 work done on `feature/phase-12-hardening` branch, merged to `main` via pull request; PR body includes test evidence and smoke-test output

**Plans:** 2/5 plans executed

Plans:
- [ ] 12-01-PLAN.md — Create feature branch + rate limiting (slowapi, SlowAPIMiddleware, per-endpoint decorators)
- [ ] 12-02-PLAN.md — Caddy request_body size limits (100MB ingest, 10MB general API)
- [ ] 12-03-PLAN.md — EVTX parser coverage: 15% to 80%+ (7 test classes, no binary fixtures)
- [ ] 12-04-PLAN.md — Caddy image digest pin (Docker checkpoint required)
- [ ] 12-05-PLAN.md — PR workflow: push branch, open PR, merge to main, sync master

*Phase 12 added: 2026-03-26 (API Hardening & Parser Coverage)*
