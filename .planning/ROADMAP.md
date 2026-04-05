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
| Causality engine package | `backend/causality/engine.py`, `entity_resolver.py`, `attack_chain_builder.py`, `mitre_mapper.py`, `scoring.py` | 14 test_phase6.py tests XPASS | 6/6 | Complete    | 2026-03-28 | GET /graph/{alert_id}, GET /entity/{id}, GET /attack_chain/{alert_id}, POST /query return 200 |
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
| Investigation package | `backend/investigation/` (6 modules) | 16 test_phase7.py tests XPASS | 5/5 | Complete    | 2026-03-31 | investigation_cases, case_artifacts, case_tags tables |
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

**Plans:** 5/5 plans complete

Plans:
- [ ] 12-01-PLAN.md — Create feature branch + rate limiting (slowapi, SlowAPIMiddleware, per-endpoint decorators)
- [ ] 12-02-PLAN.md — Caddy request_body size limits (100MB ingest, 10MB general API)
- [ ] 12-03-PLAN.md — EVTX parser coverage: 15% to 80%+ (7 test classes, no binary fixtures)
- [ ] 12-04-PLAN.md — Caddy image digest pin (Docker checkpoint required)
- [ ] 12-05-PLAN.md — PR workflow: push branch, open PR, merge to main, sync master

*Phase 12 added: 2026-03-26 (API Hardening & Parser Coverage)*

---

## Phase 13: Mature SOC Metrics, KPIs & HF Model Upgrade
**Status:** TODO
**Depends on:** Phase 12 complete
**Goal:** Elevate AI SOC Brain from a capable detection engine to a credible SOC command centre by (1) upgrading the local LLM to a cybersecurity-specialised model via the industry-standard LLMOps security-first selection process, (2) implementing the full Metrics & KPIs layer (MTTD, MTTR, MTTC, alert volume trends, false positive rate, assets monitored, log sources, active rules, open cases), and (3) wiring those metrics into the Svelte dashboard with live polling and the polished navy/cyan UI theme.

### Requirements
- P13-T01: HF model security review & selection — evaluate Foundation-Sec-8B (fdtn-ai) and Seneca-Cybersecurity-LLM (AlicanKiraz0) GGUF variants; document security scan results, hardware fit, and selection rationale in docs/ADR-020-hf-model.md; configure chosen model as `model_cybersec` in backend/core/config.py (Settings) alongside existing default
- P13-T02: Ollama cybersec model integration — add model-selection logic to backend/services/ollama_client.py so investigation summaries, AI Query, and triage prompts can optionally route to the cybersec model; controlled by OLLAMA_CYBERSEC_MODEL env var; no breaking changes to existing flows
- P13-T03: HF dataset seed script — write scripts/seed_siem_data.py that downloads a small slice (≤500 rows) of darkknight25/Advanced_SIEM_Dataset via the HF datasets library, normalises records to NormalizedEvent schema, and ingests them via IngestionLoader; enables realistic KPI testing without real events
- P13-T04: Backend metrics service — create backend/services/metrics_service.py with functions: compute_mttd(), compute_mttr(), compute_mttc(), compute_false_positive_rate(), compute_alert_volume(), compute_active_rules(), compute_open_cases(); each queries DuckDB/SQLite stores; all return typed Pydantic models
- P13-T05: GET /api/metrics/kpis endpoint — add router backend/api/metrics.py returning all KPIs in one JSON payload; 60-second APScheduler background task recomputes and caches results; endpoint returns cached value instantly
- P13-T06: Svelte KPI dashboard — replace DetectionsView metric card stubs with live data from /api/metrics/kpis; add MTTD, MTTR, MTTC, False Positive Rate, Active Cases, Active Rules, Pipeline cards alongside existing severity pills; polling every 60 s; last-updated timestamp; consistent cyan/navy theme
- P13-T07: Assets & Coverage live data — wire AssetsView.svelte to real entity counts from the graph store and ingestion source health from /api/health; replace hardcoded zeros with live values

**Plans:** 5/5 plans complete

Plans:
- [ ] 13-01-PLAN.md — HF model security review & ADR-020 (P13-T01)
- [ ] 13-02-PLAN.md — OLLAMA_CYBERSEC_MODEL config & OllamaClient routing (P13-T02)
- [ ] 13-03-PLAN.md — HF SIEM dataset seed script (P13-T03)
- [ ] 13-04-PLAN.md — Backend metrics service + GET /api/metrics/kpis endpoint (P13-T04, P13-T05)
- [ ] 13-05-PLAN.md — Svelte KPI dashboard + AssetsView live data (P13-T06, P13-T07)

*Phase 13 added: 2026-03-27 (Mature SOC Metrics, KPIs & HF Model Upgrade)*

---

## Phase 14: LLMOps Evaluation & Investigation AI Copilot
**Status:** TODO
**Depends on:** Phase 13 complete
**Goal:** Complete the LLMOps evaluation loop for Foundation-Sec-8B (benchmark quality against qwen3:14b, add model-performance monitoring) and close the most critical SOC analyst experience gap by delivering a unified investigation timeline, streaming AI Copilot chat, and entity enrichment panel — transforming InvestigationView from a placeholder into a production analyst workbench.

### Requirements
- P14-T01: Foundation-Sec-8B evaluation harness — scripts/eval_models.py that loads ≤100 rows from the seeded SIEM dataset, runs both qwen3:14b and foundation-sec:8b on triage + summarisation prompts, scores responses (latency, token count, keyword recall against ground-truth labels), writes results to data/eval_results.jsonl and prints a markdown report; automated; no GPU-heavy fine-tuning
- P14-T02: LLMOps monitoring layer — extend OllamaClient to record every generate() call (model, prompt_tokens, completion_tokens, latency_ms, endpoint) to a new duckdb table `llm_calls`; expose aggregates via GET /api/metrics/kpis extension (avg_latency_ms per model, total calls, error rate)
- P14-T03: Investigation unified timeline — GET /api/investigations/{id}/timeline returns events, detections, graph edges, and playbook runs sorted by timestamp for a given investigation; Svelte InvestigationView renders a vertical timeline with severity colour-coding, entity badges, and MITRE tactic tags
- P14-T04: AI Copilot streaming chat — POST /api/investigations/{id}/chat accepts a user question + investigation context; streams foundation-sec:8b response via SSE; Svelte copilot panel renders streamed tokens in real time with stop button; chat history persisted in SQLite per investigation

### Plans
**Plans:** 6/6 plans complete

Plans:
- [ ] 14-01-PLAN.md — Wave 0: Test stubs for eval harness, timeline, and chat contracts
- [ ] 14-02-PLAN.md — Eval harness: scripts/eval_models.py benchmarks qwen3:14b vs foundation-sec:8b
- [ ] 14-03-PLAN.md — LLMOps telemetry: DuckDB llm_calls table, OllamaClient hook, KPI metrics extension
- [ ] 14-04-PLAN.md — Timeline API: GET /api/investigations/{id}/timeline with DuckDB+SQLite merge
- [ ] 14-05-PLAN.md — InvestigationView: two-panel workbench with timeline + AI Copilot SSE chat

*Phase 14 added: 2026-03-27 (LLMOps Evaluation & Investigation AI Copilot)*

## Phase 15: Attack Graph UI
**Status:** TODO
**Depends on:** Phase 14 complete
**Goal:** Transform the stub Attack Graph view into a production interactive network graph using Cytoscape.js — rendering entities (users, devices, IPs, processes) as nodes and their relationships (lateral movement, process chains, network connections) as edges, with risk-scored colouring, MITRE ATT&CK tactic overlays, and drill-down to InvestigationView. Follows MITRE ATT&CK Navigator and SANS graph analysis best practices.

### Requirements
- P15-T01: Graph data API extension — GET /api/graph/{investigation_id} returns nodes (entity type, name, risk_score, attributes) and edges (relationship type, timestamp, MITRE tactic/technique) for an investigation; GET /api/graph/global returns the full cross-investigation entity graph (paginated); both endpoints read from the existing SQLite graph store
- P15-T02: Cytoscape.js graph component — Svelte 5 GraphView.svelte renders a force-directed or hierarchical layout using cytoscape npm package; nodes sized by risk_score, coloured by entity type (user=blue, device=green, IP=orange, process=red); edges labelled with relationship type; tooltips show entity attributes on hover
- P15-T03: Attack path highlighting — given a selected detection or investigation, the graph highlights the shortest attack path (BFS from source entity to target entity) using a distinct visual style (thick red edges, pulsing nodes); toggle between full graph and attack-path-only view
- P15-T04: Graph ↔ Investigation integration — clicking a node in GraphView navigates to InvestigationView for that entity's associated investigation; "Open in Graph" button in InvestigationView launches GraphView centred on the investigation's primary entity

### Plans
**Plans:** 4/4 plans complete

- [ ] 15-01-PLAN.md — Wave 0: xfail test stubs + npm install cytoscape-fcose/dagre
- [ ] 15-02-PLAN.md — Backend: GET /api/graph/global and GET /api/graph/{investigation_id} endpoints
- [ ] 15-03-PLAN.md — Frontend: fCoSE layout, risk-scored nodes, attack path highlighting (P15-T02, P15-T03)
- [ ] 15-04-PLAN.md — Navigation wiring: Graph ++ InvestigationView bidirectional navigation (P15-T04)

*Phase 15 added: 2026-03-28 (Attack Graph UI)*
## Phase 16: Security Hardening
**Status:** IN PROGRESS
**Depends on:** Phase 15 complete
**Goal:** Close the 5 highest-priority security and operational gaps identified in the external security critique (B/83 grade). Deliver: (1) auth coherent end-to-end with frontend Bearer token propagation and secure-by-default posture, (2) upload route unified and Caddy limits aligned, (3) security claims converted to demonstrable code controls (injection scrubbing, citation verification, LLM I/O audit logging), (4) frontend validation added to CI pipeline, (5) pyproject.toml dev/runtime deps separated.

### Requirements
- P16-SEC-01: Auth E2E — AUTH_TOKEN defaults to "changeme"; empty string rejected as 401; api.ts attaches Bearer header on all fetch calls
- P16-SEC-02: Upload unification — api.ts ingestFile() posts to /api/ingest/file; Caddy 100MB limit confirmed on /api/ingest/file
- P16-SEC-03a: Injection scrubbing — normalizer.py scrubs known injection patterns from command_line, domain, url, file_path, raw_event; tested
- P16-SEC-03b: Citation verification — verify_citations() added to /query/ask and /investigations/{id}/chat; citation_verified field in responses
- P16-SEC-03c: LLM audit logging — ollama_client.py _audit_log writes to logs/llm_audit.jsonl; file handler confirmed via test
- P16-CI-04: Frontend CI — .github/workflows/ci.yml has parallel frontend job (npm ci + build + check)
- P16-DEP-05: Pyproject dev deps — pytest, pytest-asyncio, ruff in [dependency-groups] dev; CI uses uv sync --group dev

### Plans
**Plans:** 5/5 plans complete

- [ ] 16-01-PLAN.md — Auth backend: AUTH_TOKEN default + empty-string rejection (P16-SEC-01)
- [ ] 16-02-PLAN.md — Dep hygiene: pyproject.toml dev group + CI update (P16-DEP-05)
- [ ] 16-03-PLAN.md — Auth frontend: Bearer token in api.ts + upload route fix (P16-SEC-01, P16-SEC-02)
- [ ] 16-04-PLAN.md — Frontend CI: add parallel frontend job (P16-CI-04)
- [ ] 16-05-PLAN.md — Security controls: citation verification + injection/audit tests (P16-SEC-03a/b/c)

*Phase 16 added: 2026-03-31 (Security Hardening — expedited via PRD Express Path)*


## Phase 16: Threat Hunting Workspace
**Status:** TODO
**Depends on:** Phase 15 complete
**Goal:** Deliver a proactive threat hunting workspace that closes the gap between reactive alert triage and proactive adversary discovery — following SANS FOR508 threat hunting methodology and MITRE ATT&CK data source coverage model. Analysts can build structured hunt hypotheses, execute DuckDB queries with AI assistance, save/replay hunts, and visualise anomaly baselines.

### Requirements
- P16-T01: Hunt hypothesis engine — SQLite hunts table stores hunt name, hypothesis, MITRE tactic/technique, query, status (active/archived), created_at, last_run_at, result_count; GET /api/hunts lists all hunts; POST /api/hunts creates; PUT /api/hunts/{id} updates; DELETE /api/hunts/{id} archives
- P16-T02: AI-assisted query builder — POST /api/hunts/suggest accepts a natural-language hypothesis and returns a structured DuckDB SQL query + explanation using foundation-sec:8b; analyst reviews/edits before saving; query is validated against the normalized_events schema before execution
- P16-T03: Hunt execution engine — POST /api/hunts/{id}/run executes the saved DuckDB query against normalized_events; returns matching events with entity enrichment; execution time, row count, and result sample stored in hunt record; results streamed via SSE for long-running queries
- P16-T04: Anomaly baseline view — GET /api/analytics/baselines returns per-entity statistical baselines (event frequency, process counts, connection counts) computed from a 7-day rolling window in DuckDB; Svelte HuntingView renders a time-series chart (SVG sparklines or lightweight chart library) showing baseline vs. observed activity with anomaly markers

### Plans
**Plans:** 0/0 plans complete

*Phase 16 added: 2026-03-28 (Threat Hunting Workspace)*

## Phase 17: SOAR & Playbook Engine
**Status:** TODO
**Depends on:** Phase 16 complete
**Goal:** Deliver a human-in-the-loop SOAR capability following the CACAO Playbook standard and NIST SP 800-61r3 incident response lifecycle — allowing analysts to define response playbooks as ordered action sequences, manually execute them against investigations, track execution state, and record evidence. No autonomous response — every action requires analyst approval per the REQUIREMENTS.md human-in-the-loop constraint.

### Requirements
- P17-T01: Playbook data model — SQLite playbooks table (playbook_id, name, description, trigger_conditions JSON, steps JSON array, version, created_at); playbook_runs table (run_id, playbook_id, investigation_id, status, started_at, completed_at, steps_completed JSON, analyst_notes); GET /api/playbooks lists; POST /api/playbooks creates; GET /api/playbooks/{id}/runs lists run history
- P17-T02: Built-in playbook library — ship 5 starter playbooks aligned to NIST IR phases: (1) Phishing Initial Triage, (2) Lateral Movement Investigation, (3) Privilege Escalation Response, (4) Data Exfiltration Containment, (5) Malware Isolation — each as a JSON step sequence with analyst-approval gates and evidence-collection prompts
- P17-T03: Playbook execution engine — POST /api/playbooks/{id}/run/{investigation_id} starts a run; PATCH /api/playbook-runs/{run_id}/step/{step_n} advances to next step (analyst must explicitly confirm each step); each step result and analyst note stored in steps_completed; SSE endpoint streams step-completion events to the Svelte frontend
- P17-T04: PlaybooksView Svelte component — lists available playbooks with trigger-condition summaries; "Run Playbook" button on InvestigationView launches PlaybooksView in context; running playbook shows step-by-step checklist with confirm/skip/note controls; completed runs show audit trail with timestamps

### Plans
**Plans:** 3/3 plans complete

Plans:
- [ ] 17-01-PLAN.md — Playbook data model, SQLite schema, built-in library (P17-T01, P17-T02)
- [ ] 17-02-PLAN.md — Execution engine: start/advance/cancel run + SSE stream (P17-T03)
- [ ] 17-03-PLAN.md — PlaybooksView UI + InvestigationView Run Playbook button (P17-T04)



*Phase 17 added: 2026-03-28 (SOAR & Playbook Engine)*

## Phase 18: Reporting & Compliance
**Status:** TODO
**Depends on:** Phase 17 complete
**Goal:** Deliver executive and operational reporting capabilities aligned to NIST CSF 2.0, CIS Controls v8, and SOC 2 Type II evidence requirements — enabling analysts to generate PDF investigation reports, trend dashboards with MTTD/MTTR/MTTC time-series, MITRE ATT&CK coverage heatmaps, and exportable compliance artefacts. Closes the "reporting & auditing" gap identified in the SOC maturity assessment.

### Requirements
- P18-T01: Report generation API — POST /api/reports/investigation/{id} generates a structured investigation report (timeline, entities, detections, AI Copilot chat, playbook run audit trail); POST /api/reports/executive generates a period summary (date range, alert volume, MTTD/MTTR trends, top tactics, false positive rate); reports stored as JSON in SQLite and rendered to PDF via WeasyPrint or reportlab (local, no cloud)
- P18-T02: MITRE ATT&CK coverage heatmap — GET /api/analytics/mitre-coverage returns a matrix of tactic/technique coverage (detected, hunted, playbook-covered vs. not covered) derived from detections + hunt results + playbooks; Svelte ReportingView renders an ATT&CK navigator-style grid with colour-coded coverage cells
- P18-T03: Trend charts and KPI history — GET /api/analytics/trends?metric=mttd&days=30 returns time-series data from a new daily_kpi_snapshots DuckDB table populated by an APScheduler daily job; ReportingView renders MTTD/MTTR/MTTC/alert-volume trend lines using SVG charts
- P18-T04: Compliance evidence export — GET /api/reports/compliance?framework=nist-csf generates a structured evidence package mapping each NIST CSF 2.0 subcategory to artefacts in the system (detections, investigations, playbook runs, KPI snapshots); exported as a ZIP containing JSON evidence files and a human-readable HTML summary

### Plans
**Plans:** 4/5 plans executed

Plans:
- [ ] 18-01-PLAN.md — Report generation API: SQLite reports table, WeasyPrint PDF, REST endpoints
- [ ] 18-02-PLAN.md — MITRE ATT&CK coverage analytics API
- [ ] 18-03-PLAN.md — KPI trend history: DuckDB daily_kpi_snapshots, APScheduler job, trends endpoint
- [ ] 18-04-PLAN.md — Compliance evidence export: nist-csf and thehive ZIP packages
- [ ] 18-05-PLAN.md — ReportingView: four-tab frontend with D3 trend charts and ATT&CK heatmap

*Phase 18 added: 2026-03-28 (Reporting & Compliance)*

## Phase 19: Identity & RBAC
**Status:** COMPLETE — 2026-04-01
**Depends on:** Phase 18 complete
**Goal:** Upgrade from single shared bearer token to named-operator identity with role-based access control and per-operator audit attribution — the NIST CSF 2.0 Govern baseline for a defensible AI-SOC platform. Each analyst gets a named account with a hashed API key, role assignment, and optional TOTP MFA. All API actions are attributed to a specific operator in audit logs. An admin operator manages accounts via API and Svelte settings UI.

### Requirements
- P19-T01: Operator data model — SQLite `operators` table (operator_id UUID, name, hashed_api_key, role ENUM admin|analyst, totp_secret nullable, created_at, last_seen, active BOOL); bcrypt-hash all API keys at rest; bootstrap first `admin` operator from ADMIN_API_KEY env var on first run if table empty
- P19-T02: Multi-operator auth — refactor verify_token to look up incoming Bearer token against operators table (bcrypt verify); extract and inject operator_id + role into request.state; stamp operator_id on all llm_audit.jsonl entries and existing SQLite audit events
- P19-T03: RBAC middleware — FastAPI dependency `require_role("admin")` guards user-management and config routes; `require_role("analyst")` guards investigation/detection/playbook routes; return 403 with structured error for role violations; unit tests for each role boundary
- P19-T04: Optional TOTP MFA — pyotp TOTP second-factor per operator; verify_token checks X-TOTP-Code header when operator has totp_secret set; POST /api/operators/{id}/totp/enable generates secret + QR (qrcode lib); graceful pass-through for operators without TOTP configured
- P19-T05: Operator management API + SettingsView tab — GET /api/operators (admin), POST /api/operators (admin, creates operator + returns one-time API key), DELETE /api/operators/{id} (admin, soft-delete sets active=False), POST /api/operators/{id}/rotate-key (admin); Svelte SettingsView "Operators" tab showing operator list with role badges and key-rotation button

**Plans:** 4/5 plans executed

Plans:
- [ ] 19-00-PLAN.md — Wave 0 test stubs + dependency install (P19-T01–T05 RED phase)
- [ ] 19-01-PLAN.md — Operator data model, bcrypt utils, OperatorContext, verify_token refactor (P19-T01, P19-T02)
- [ ] 19-02-PLAN.md — RBAC require_role() dependency factory (P19-T03)
- [ ] 19-03-PLAN.md — TOTP MFA utilities + verify_token enforcement (P19-T04)
- [ ] 19-04-PLAN.md — Operators management API + SettingsView Operators tab (P19-T05)
*Phase 19 added: 2026-04-01 (Identity & RBAC)*

## Phase 20: Schema Standardisation (ECS/OCSF)
**Status:** TODO
**Depends on:** Phase 19 complete
**Goal:** Replace the project-local event schema with an ECS (Elastic Common Schema) and OCSF (Open Cybersecurity Schema Framework) aligned normalised event model — the prerequisite for detection fidelity, AI grounding accuracy, and future interoperability with external tools. Every ingested event is mapped to a canonical normalised model; field names, types, and semantics are consistent regardless of source parser. Sigma field mappings, enrichment, and the AI Copilot all operate on the canonical model.

### Requirements
- P20-T01: Canonical NormalizedEvent model — extend/replace the existing Pydantic NormalizedEvent with ECS-aligned core fields (event.kind, event.category, event.type, event.action, host.name, host.ip, user.name, process.name, process.pid, network.protocol, source/destination.ip/port, file.path, url.full); OCSF class_uid mapping for event classification; backward-compatible: all existing parsers still produce valid NormalizedEvent instances
- P20-T02: Parser field mapping layer — update EVTX, JSON/NDJSON, CSV, and osquery parsers to emit ECS-aligned field names via a centralised FieldMapper utility; FieldMapper is a pure function (input: raw dict + source_type → output: NormalizedEvent); no parser touches DuckDB directly; unit tests for each parser's field mapping
- P20-T03: DuckDB schema migration — add ECS columns to the events table (event_kind, event_category, event_type, host_name, host_ip, user_name, process_name, network_protocol, src_ip, src_port, dst_ip, dst_port, file_path); migration is additive (ALTER TABLE ADD COLUMN IF NOT EXISTS); existing rows gain NULL values in new columns; schema version tracked in a db_meta table
- P20-T04: Sigma field map update — update detections/field_map.py to map Sigma field names to the new ECS-aligned DuckDB column names; all existing Sigma smoke tests still pass; add smoke tests for the new ECS field mappings; detection correctness validated end-to-end with sample events
- P20-T05: Enrichment and AI Copilot alignment — update entity_extractor.py to extract entities from ECS fields; update AI Copilot prompt templates (prompts/) to reference canonical field names; update graph schema constants to use ECS host/user/process/network node types; integration test: ingest sample EVTX, confirm entity graph uses ECS fields

**Plans:** 6/6 plans complete

Plans:
- [ ] 20-00-PLAN.md — Wave 0: RED test stubs for P20-T01, T02, T03 (19 failing tests)
- [ ] 20-01-PLAN.md — Canonical NormalizedEvent: 6 ECS fields + OCSF_CLASS_UID_MAP (P20-T01)
- [ ] 20-02-PLAN.md — FieldMapper utility + loader.py _INSERT_SQL extension (P20-T02)
- [ ] 20-03-PLAN.md — DuckDB additive migration: db_meta + 6 ECS columns (P20-T03)
- [ ] 20-04-PLAN.md — Sigma SIGMA_FIELD_MAP ECS additions + smoke tests (P20-T04)
- [ ] 20-05-PLAN.md — entity_extractor, graph/schema.py, prompt ECS alignment (P20-T05)
*Phase 20 added: 2026-04-01 (Schema Standardisation ECS/OCSF)*

## Phase 21: Evidence Provenance
**Status:** in_progress
**Depends on:** Phase 20 complete
**Plans:** 6/6 plans complete
**Goal:** Establish a defensible chain-of-custody for every artefact in the system — ingested events, detections, AI Copilot responses, and playbook runs. Each artefact carries a cryptographic hash, a source fingerprint, and a transformation lineage record (parser version, rule version, model version, prompt template version). Analysts and compliance reviewers can trace any finding back to the raw source with full provenance metadata. This is the prerequisite for DFIR validity and NIST AI RMF trustworthiness requirements.

### Requirements
- P21-T01: Ingest provenance — every batch ingested via loader.py receives a provenance record: SHA-256 hash of raw bytes, source file path, parser name + version, ingest timestamp, operator_id; stored in a new SQLite `ingest_provenance` table; GET /api/provenance/ingest/{event_id} returns full chain-of-custody for any event
- P21-T02: Detection provenance — every detection match written to SQLite carries the Sigma rule file SHA-256, rule title, pySigma backend version, and field_map version at match time; GET /api/provenance/detection/{id} returns rule + backend version that produced the finding
- P21-T03: AI response provenance — every LLM response in llm_audit.jsonl gains: model_id, prompt_template_name, prompt_template_sha256, response_sha256, operator_id, grounding_event_ids (list of event IDs the response was grounded on); GET /api/provenance/llm/{audit_id} returns full AI lineage record
- P21-T04: Playbook run provenance — every playbook run record gains: playbook_file_sha256, playbook_version, trigger_event_ids, operator_id_who_approved; GET /api/provenance/playbook/{run_id} returns playbook version + approver chain
- P21-T05: Provenance API + ProvenanceView tab — all four GET endpoints exposed under /api/provenance/; Svelte ProvenanceView tab in the existing UI (4th nav item) with per-artefact provenance panels; hash values displayed with copy-to-clipboard; timeline of transformation steps from raw ingest → detection → AI response → playbook action

*Phase 21 added: 2026-04-01 (Evidence Provenance)*

## Phase 22: AI Lifecycle Hardening
**Status:** TODO
**Depends on:** Phase 21 complete
**Goal:** Harden the AI Copilot from a useful but ungoverned assistant into a trustworthy, evaluable, NIST AI RMF-aligned system component. Every LLM response is grounded against retrieved evidence, confidence-scored, and clearly marked as advisory. An offline evaluation harness enables regression testing of prompt templates. Response drift and model substitution are detectable. This closes the gap between "responsible prompt engineering" and "trustworthy AI system management" identified in the SOC maturity assessment.

### Requirements
- P22-T01: Response grounding enforcement — every AI Copilot response must cite the specific event IDs, detection IDs, or investigation IDs it was grounded on; the grounding_event_ids field from Phase 21 provenance is propagated to the API response; GET /api/copilot/response/{audit_id} returns response + cited sources; UI displays citations inline with response text; responses with zero grounding are flagged as "ungrounded" with a visual warning
- P22-T02: Confidence scoring — a lightweight heuristic confidence score (0.0–1.0) is computed for each LLM response based on: grounding coverage (how many cited events match query terms), response length vs. context size, and presence of hedging language patterns; score stored in llm_audit_provenance; displayed as a confidence badge in the UI (green ≥0.8, amber 0.5–0.8, red <0.5)
- P22-T03: Evaluation harness — an offline pytest-based eval harness at tests/eval/ that loads fixture prompt+context pairs, runs them through a mock LLM (no real Ollama call), and asserts response properties (contains expected entities, cites correct sources, does not hallucinate missing event IDs); at least 5 eval fixtures covering analyst_qa, triage, and threat_hunt prompt templates; harness runnable with uv run pytest tests/eval/ -v
- P22-T04: Model drift detection — on each LLM call, compare the active model_id (from Ollama /api/tags) against the last-known model_id stored in SQLite settings; if changed, emit a structured WARNING log entry and store a model_change_event in SQLite; GET /api/settings/model-status returns current model, last-known model, and drift status; SettingsView displays model drift alert if detected
- P22-T05: Advisory separation — all AI Copilot responses in the UI carry a persistent "AI Advisory — not verified fact" banner; confidence badge is non-dismissable; response text uses a visually distinct style (italic, muted colour) to distinguish AI content from human-confirmed investigation notes; prompt templates updated to instruct the model to prefix uncertain claims with "Possible:" or "Unverified:"

*Phase 22 added: 2026-04-02 (AI Lifecycle Hardening)*
**Plans:** 10/10 plans complete

Plans:
- [ ] 22-00-PLAN.md — Wave 0 test stubs: tests/eval/ package, conftest.py, 5 NDJSON fixtures, all test files pre-skipped
- [ ] 22-01-PLAN.md — Response grounding: thread audit_id/grounding_event_ids/is_grounded to /ask and /ask/stream (P22-T01)
- [ ] 22-02-PLAN.md — Confidence scoring: confidence_score DDL + heuristic + badge in InvestigationView (P22-T02)
- [ ] 22-03-PLAN.md — Eval harness: fill in analyst_qa, triage, threat_hunt eval tests with real assertions (P22-T03)
- [ ] 22-04-PLAN.md — Model drift: system_kv + model_change_events + GET /api/settings/model-status + SettingsView card (P22-T04)
- [ ] 22-05-PLAN.md — Advisory separation: prompt prefix + non-dismissable banner + confidence badge in InvestigationView (P22-T05)
- [ ] 22-06-PLAN.md — Checkpoint: full suite green + human visual verification

## Phase 23: Firewall Telemetry Ingestion
**Status:** TODO
**Depends on:** Phase 22 complete
**Goal:** The SOC can receive, parse, and normalise telemetry from a connected IPFire firewall appliance (syslog) and its Suricata IDS (EVE JSON). All inbound firewall telemetry is stored as NormalizedEvent records, enabling correlation and graph enrichment with perimeter visibility. A polling/streaming collector job manages connectivity and heartbeat monitoring.

### Requirements
- P23-T01: IPFire syslog parser — `ingestion/parsers/ipfire_syslog_parser.py` parses RFC 3164/5424 syslog lines from IPFire; maps firewall log fields (src_ip, dst_ip, proto, action, zone, interface) to NormalizedEvent schema; handles ALLOW/DROP/REJECT action variants; preserves raw line in provenance field; unit tests with fixture syslog lines
- P23-T02: Suricata EVE JSON parser — `ingestion/parsers/suricata_eve_parser.py` parses Suricata EVE JSON records (alert, flow, dns, http event types); maps to NormalizedEvent; preserves MITRE ATT&CK tactic/technique from alert.metadata if present; severity mapped from alert.severity (1=critical,2=high,3=medium,4=low); unit tests with fixture EVE JSON records
- P23-T03: Firewall collector job — `ingestion/jobs/firewall_collector.py` polls or streams telemetry from the firewall; configurable via settings (FIREWALL_SYSLOG_HOST, FIREWALL_SYSLOG_PORT, FIREWALL_EVE_PATH); handles connectivity loss gracefully (exponential backoff, alert on consecutive failures); missed heartbeat detection (configurable threshold); all events written through existing batch ingest + Chroma embed coordinator
- P23-T04: Heartbeat normalisation — firewall heartbeat events normalised to NormalizedEvent with event_type="heartbeat"; last_seen timestamp stored in system_kv; GET /api/firewall/status returns connectivity state (connected/degraded/offline) based on heartbeat recency; threshold configurable in settings

*Phase 23 added: 2026-04-03 (Firewall Telemetry Ingestion)*
**Plans:** 1/5 plans executed

Plans:
- [ ] 23-00-PLAN.md — Wave 0: test stubs (3 files), ingestion/jobs/__init__.py, fixtures/syslog/ipfire_sample.log
- [ ] 23-01-PLAN.md — Wave 1: IPFireSyslogParser implementation (P23-T01)
- [ ] 23-02-PLAN.md — Wave 1: SuricataEveParser implementation (P23-T02) [parallel with 23-01]
- [ ] 23-03-PLAN.md — Wave 2: FirewallCollector + GET /api/firewall/status + settings + main.py wiring (P23-T03, P23-T04)
- [ ] 23-04-PLAN.md — Wave 3: Final verification checkpoint

## Phase 24: Recommendation Artifact Store and Approval API
**Status:** TODO
**Depends on:** Phase 23 complete
**Goal:** The SOC can create, store, and approve AI-assisted recommendation artifacts conforming to contracts/recommendation.schema.json. A human-in-the-loop approval gate is enforced programmatically — no artifact crosses the trust boundary without analyst_approved=true and schema validation. The recommendation lifecycle (draft > approved > dispatched) is fully tracked with audit trail.

### Requirements
- P24-T01: DB schema — DuckDB tables: `recommendations` (all artifact fields, status enum), `recommendation_dispatch_log` (dispatch attempts, response codes, timestamps); schema migration via existing store migration pattern
- P24-T02: Pydantic model — `RecommendationArtifact` model in `backend/models/` mirroring `contracts/recommendation.schema.json` v1.0.0; all required fields typed; `prompt_inspection` as nested Pydantic model; full JSON Schema validation on instantiation using jsonschema library against the pinned contracts/ file
- P24-T03: API routes — POST /api/recommendations (create draft); GET /api/recommendations/{id}; PATCH /api/recommendations/{id}/approve (set analyst_approved=true, approved_by, override_log if required); GET /api/recommendations (list with filters)
- P24-T04: Human-in-the-loop gate — PATCH /approve enforces: schema valid, analyst_approved only via this endpoint, approved_by non-empty, expires_at in future, override_log required when inference_confidence in [low, none] or prompt_inspection.passed=false; gate failures return 422 with structured error
- P24-T05: Tests — unit tests for RecommendationArtifact model validation; integration tests for all four API routes; gate enforcement tests; at least 10 test cases

*Phase 24 added: 2026-04-03 (Recommendation Artifact Store and Approval API)*

## Phase 25: Receipt Ingestion and Case-State Propagation
**Status:** TODO
**Depends on:** Phase 24 complete
**Goal:** The SOC ingests execution receipts from the firewall executor and propagates case-state updates automatically. Every receipt is stored with full audit linkage to its recommendation_id and case_id. The five failure_taxonomy paths each produce a deterministic case-state transition per ADR-032. Analyst notification is triggered for conditions requiring human review.

### Requirements
- P25-T01: Receipt ingestion route — POST /api/receipts accepts an execution receipt JSON; validates against a pinned local copy of contracts/execution-receipt.schema.json (stub acceptable if firewall canonical not yet available); stores receipt in `execution_receipts` DuckDB table linked to recommendation_id and case_id; returns 202 Accepted
- P25-T02: Case-state propagation — on receipt ingest, apply case-state transition per ADR-032: applied/noop_already_present to containment_confirmed, validation_failed/expired_rejected to containment_failed, rolled_back to containment_rolled_back; update case record atomically
- P25-T03: Analyst notification trigger — for validation_failed and rolled_back, emit a structured notification event; GET /api/notifications returns pending notifications with required_action enum (re_approve_required / manual_review_required)
- P25-T04: Receipt schema stub — `contracts/execution-receipt.schema.json` stub (SOC local copy) with required fields; note canonical version lives in firewall repo; version pinned to "1.0.0-stub"
- P25-T05: Tests — unit tests for all 5 failure_taxonomy transitions; integration tests for POST /api/receipts with each value; notification trigger tests; idempotency test (same receipt_id twice returns 409)

*Phase 25 added: 2026-04-03 (Receipt Ingestion and Case-State Propagation)*

## Phase 26: Graph Schema Versioning and Perimeter Entities
**Status:** TODO
**Depends on:** Phase 25 complete
**Goal:** The graph store gains explicit schema versioning and two new perimeter entity types (firewall_zone, network_segment) with associated edge types (blocks, permits, traverses). All changes are strictly additive. Malcolm/OpenSearch schema compatibility maintained. Dashboard graph view renders perimeter nodes.

### Requirements
- P26-T01: Graph schema versioning — `graph_schema_version` field in graph metadata (SQLite); current version "2.0.0"; migration defaults pre-existing installs to "1.0.0"; GET /api/graph/schema-version returns current version
- P26-T02: Perimeter node types — `firewall_zone` node (zone_name, zone_color [RED/GREEN/ORANGE/BLUE], interface) and `network_segment` node (cidr, zone, description) added to graph schema constants; existing node types unchanged
- P26-T03: Perimeter edge types — `blocks`, `permits`, `traverses` edge types added; edges created by IPFire syslog parser on ingest; existing edge types unchanged
- P26-T04: Additive-only constraint — migration uses ALTER TABLE ADD COLUMN only (never DROP/MODIFY); migration test asserts no existing columns/tables removed; Malcolm/OpenSearch parser test asserts existing field preservation
- P26-T05: Dashboard graph rendering — firewall_zone nodes rendered with zone-color coding; network_segment nodes as subnet bubbles; new edge types with distinct styles; no visual regression on existing types; human visual verification checkpoint required

*Phase 26 added: 2026-04-03 (Graph Schema Versioning and Perimeter Entities)*
