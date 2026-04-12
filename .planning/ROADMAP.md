# Roadmap

**Project:** AI-SOC-Brain
**Date:** 2026-03-15
**Status:** IN PROGRESS — Phase 28 (Dashboard Integration Fixes) next

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
**Status:** COMPLETE
**Depends on:** Phase 22 complete
**Goal:** The SOC can receive, parse, and normalise telemetry from a connected IPFire firewall appliance (syslog) and its Suricata IDS (EVE JSON). All inbound firewall telemetry is stored as NormalizedEvent records, enabling correlation and graph enrichment with perimeter visibility. A polling/streaming collector job manages connectivity and heartbeat monitoring.

### Requirements
- P23-T01: IPFire syslog parser — `ingestion/parsers/ipfire_syslog_parser.py` parses RFC 3164/5424 syslog lines from IPFire; maps firewall log fields (src_ip, dst_ip, proto, action, zone, interface) to NormalizedEvent schema; handles ALLOW/DROP/REJECT action variants; preserves raw line in provenance field; unit tests with fixture syslog lines
- P23-T02: Suricata EVE JSON parser — `ingestion/parsers/suricata_eve_parser.py` parses Suricata EVE JSON records (alert, flow, dns, http event types); maps to NormalizedEvent; preserves MITRE ATT&CK tactic/technique from alert.metadata if present; severity mapped from alert.severity (1=critical,2=high,3=medium,4=low); unit tests with fixture EVE JSON records
- P23-T03: Firewall collector job — `ingestion/jobs/firewall_collector.py` polls or streams telemetry from the firewall; configurable via settings (FIREWALL_SYSLOG_HOST, FIREWALL_SYSLOG_PORT, FIREWALL_EVE_PATH); handles connectivity loss gracefully (exponential backoff, alert on consecutive failures); missed heartbeat detection (configurable threshold); all events written through existing batch ingest + Chroma embed coordinator
- P23-T04: Heartbeat normalisation — firewall heartbeat events normalised to NormalizedEvent with event_type="heartbeat"; last_seen timestamp stored in system_kv; GET /api/firewall/status returns connectivity state (connected/degraded/offline) based on heartbeat recency; threshold configurable in settings

*Phase 23 added: 2026-04-03 (Firewall Telemetry Ingestion)*
**Plans:** 5/5 plans complete

Plans:
- [x] 23-00-PLAN.md — Wave 0: test stubs (3 files), ingestion/jobs/__init__.py, fixtures/syslog/ipfire_sample.log
- [x] 23-01-PLAN.md — Wave 1: IPFireSyslogParser implementation (P23-T01)
- [x] 23-02-PLAN.md — Wave 1: SuricataEveParser implementation (P23-T02) [parallel with 23-01]
- [x] 23-03-PLAN.md — Wave 2: FirewallCollector + GET /api/firewall/status + settings + main.py wiring (P23-T03, P23-T04)
- [x] 23-04-PLAN.md — Wave 3: Final verification checkpoint

## Phase 23.5: Security Hardening (Expert Panel Findings)
**Status:** TODO
**Depends on:** Phase 23 complete
**Goal:** Close all CRITICAL and HIGH findings from the full-panel security sweep (18 findings, 3 attack chains). Quick-win findings are implemented atomically. Sprint findings are batched by domain. The system must not have a zero-configuration unauthenticated admin path, must not have unsanitized prompt injection surfaces, and must have verified firewall protection on Ollama. All security tests must be green before Phase 24 proceeds.

### Requirements
- P23.5-T01 [CRITICAL]: Default token guard — startup assertion rejects AUTH_TOKEN=="changeme"; warn and exit; test confirms 401 on default token (E3-01)
- P23.5-T02 [CRITICAL]: Legacy admin bypass fix — legacy-admin path in auth.py requires TOTP verification or is removed; no backdoor admin path without MFA (E3-02)
- P23.5-T03 [CRITICAL]: Indirect prompt injection hardening — move [EVIDENCE] chunk content to system prompt section; add base64 + Unicode normalization before regex scrubbing; adversarial eval fixture (E6-01)
- P23.5-T04 [HIGH]: Direct chat injection fix — apply _scrub_injection() to body.question in chat.py before prompt construction (E6-02)
- P23.5-T05 [HIGH]: Sigma SQL injection + wrong backend — implement parameterized Sigma SQL test (remove @xfail); evaluate pySigma-backend-duckdb availability and switch if available (E1-01, E10-01)
- P23.5-T06 [HIGH]: Ollama network isolation verification — add to scripts/status.ps1 a PowerShell check that port 11434 is not reachable from non-loopback; document in THREAT_MODEL.md (E4-01)
- P23.5-T07 [HIGH]: Meta-detection rules — add anomaly Sigma rules: auth failure burst (10+ failures in 60s), LLM token spike (>5x baseline), unexpected collection delete event (E8-02)
- P23.5-T08 [MEDIUM]: CSP headers — add Content-Security-Policy, X-Frame-Options, X-Content-Type-Options to Caddyfile (E9-01)
- P23.5-T09 [MEDIUM]: Health endpoint sanitization — sanitize exception detail strings in /health; return generic component error strings not internal paths or schema names (E3-04)
- P23.5-T10 [MEDIUM]: Log rotation — add TimedRotatingFileHandler with 30-day retention and 100MB max size to backend/core/logging.py (E8-01)
- P23.5-T11 [MEDIUM]: TOTP replay persistence — persist seen-TOTP codes to SQLite system_kv; survive app restart; add replay-after-restart test (E2-01)
- P23.5-T12 [MEDIUM]: Full prompt audit logging — log full prompt_text (not just char count) to llm_calls table; hash for integrity (E7-02)

**Plans:** 7/7 plans complete

Plans:
- [x] 23.5-01-PLAN.md — Wave 1: Test stubs + fixtures + Sigma meta-rule stubs (all requirements)
- [x] 23.5-02-PLAN.md — Wave 2: Auth hardening — AUTH_TOKEN validator + legacy TOTP gate (P23.5-T01, P23.5-T02)
- [x] 23.5-03-PLAN.md — Wave 2: Injection hardening — _scrub_injection b64/Unicode + EVIDENCE in system turn + chat scrub (P23.5-T03, P23.5-T04)
- [ ] 23.5-04-PLAN.md — Wave 3: Sigma SQL injection test + matcher audit (P23.5-T05)
- [ ] 23.5-05-PLAN.md — Wave 3: Infrastructure fixes — CSP headers, health sanitization, log rotation, Ollama port check (P23.5-T06, P23.5-T08, P23.5-T09, P23.5-T10)
- [ ] 23.5-06-PLAN.md — Wave 4: Meta-detection rules + TOTP persistence + full prompt logging (P23.5-T07, P23.5-T11, P23.5-T12)
- [ ] 23.5-07-PLAN.md — Wave 5: Final verification checkpoint

*Phase 23.5 added: 2026-04-05 (Security Hardening — Expert Panel Sweep)*

## Phase 24: Recommendation Artifact Store and Approval API
**Status:** IN PROGRESS
**Depends on:** Phase 23.5 complete
**Goal:** The SOC can create, store, and approve AI-assisted recommendation artifacts conforming to contracts/recommendation.schema.json. A human-in-the-loop approval gate is enforced programmatically — no artifact crosses the trust boundary without analyst_approved=true and schema validation. The recommendation lifecycle (draft > approved > dispatched) is fully tracked with audit trail.

### Requirements
- P24-T01: DB schema — DuckDB tables: `recommendations` (all artifact fields, status enum), `recommendation_dispatch_log` (dispatch attempts, response codes, timestamps); schema migration via existing store migration pattern
- P24-T02: Pydantic model — `RecommendationArtifact` model in `backend/models/` mirroring `contracts/recommendation.schema.json` v1.0.0; all required fields typed; `prompt_inspection` as nested Pydantic model; full JSON Schema validation on instantiation using jsonschema library against the pinned contracts/ file
- P24-T03: API routes — POST /api/recommendations (create draft); GET /api/recommendations/{id}; PATCH /api/recommendations/{id}/approve (set analyst_approved=true, approved_by, override_log if required); GET /api/recommendations (list with filters)
- P24-T04: Human-in-the-loop gate — PATCH /approve enforces: schema valid, analyst_approved only via this endpoint, approved_by non-empty, expires_at in future, override_log required when inference_confidence in [low, none] or prompt_inspection.passed=false; gate failures return 422 with structured error
- P24-T05: Tests — unit tests for RecommendationArtifact model validation; integration tests for all four API routes; gate enforcement tests; at least 10 test cases



**Plans:** 6/6 plans complete

Plans:
- [ ] 24-00-PLAN.md — Wave 0: pre-skipped test stubs (test_recommendation_model.py, test_recommendation_api.py)
- [ ] 24-01-PLAN.md — Wave 1: DuckDB schema migration — recommendations + dispatch_log tables (P24-T01)
- [ ] 24-02-PLAN.md — Wave 1: RecommendationArtifact Pydantic model + jsonschema validation (P24-T02) [parallel with 24-01]
- [ ] 24-03-PLAN.md — Wave 2: CRUD API routes — POST, GET/{id}, GET list + main.py wiring (P24-T03)
- [ ] 24-04-PLAN.md — Wave 2: Approval gate — PATCH /approve + _run_approval_gate (P24-T04) [parallel with 24-03]
- [ ] 24-05-PLAN.md — Wave 3: Activate all tests — 22 test cases passing (P24-T05)

*Phase 24 added: 2026-04-03 (Recommendation Artifact Store and Approval API)*

## Phase 25: Receipt Ingestion and Case-State Propagation
**Status:** in_progress (plans 25-00 through 25-03 complete; 25-04 next)
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
**Status:** planned
**Depends on:** Phase 25 complete
**Goal:** The graph store gains explicit schema versioning and two new perimeter entity types (firewall_zone, network_segment) with associated edge types (blocks, permits, traverses). All changes are strictly additive. Malcolm/OpenSearch schema compatibility maintained. Dashboard graph view renders perimeter nodes.

### Requirements
- P26-T01: Graph schema versioning — `graph_schema_version` field in graph metadata (SQLite); current version "2.0.0"; migration defaults pre-existing installs to "1.0.0"; GET /api/graph/schema-version returns current version
- P26-T02: Perimeter node types — `firewall_zone` node (zone_name, zone_color [RED/GREEN/ORANGE/BLUE], interface) and `network_segment` node (cidr, zone, description) added to graph schema constants; existing node types unchanged
- P26-T03: Perimeter edge types — `blocks`, `permits`, `traverses` edge types added; edges created by IPFire syslog parser on ingest; existing edge types unchanged
- P26-T04: Additive-only constraint — migration uses ALTER TABLE ADD COLUMN only (never DROP/MODIFY); migration test asserts no existing columns/tables removed; Malcolm/OpenSearch parser test asserts existing field preservation
- P26-T05: Dashboard graph rendering — firewall_zone nodes rendered with zone-color coding; network_segment nodes as subnet bubbles; new edge types with distinct styles; no visual regression on existing types; human visual verification checkpoint required

**Plans:** 5/5 plans complete

Plans:
- [ ] 26-00-PLAN.md — Wave 0: pre-skipped test stubs (test_graph_schema.py, test_graph_versioning.py)
- [ ] 26-01-PLAN.md — Wave 1: schema constants + versioning route (graph/schema.py, sqlite_store.py, graph.py)
- [ ] 26-02-PLAN.md — Wave 2: IPFire perimeter edge emission (entity_extractor.py)
- [ ] 26-03-PLAN.md — Wave 2: dashboard perimeter rendering (GraphView.svelte) [autonomous: false]
- [ ] 26-04-PLAN.md — Wave 3: activate all tests (12 tests passing)

*Phase 26 added: 2026-04-03 (Graph Schema Versioning and Perimeter Entities)*

## Phase 27: Malcolm NSM Integration and Live Feed Collector
**Status:** complete
**Completed:** 2026-04-08
**Depends on:** Phase 26 complete
**Goal:** Live telemetry flows from Malcolm NSM (OpenSearch) into local-ai-soc in real time. A new MalcolmCollector polls arkime_sessions3-* (Suricata alerts) and malcolm_beats_syslog_* (IPFire firewall) on a configurable interval, normalizes to NormalizedEvent, and persists to DuckDB + Chroma. Recommendation dispatch validates approved artifacts against the recommendation schema before any firewall action. ChromaDB corpus from supportTAK-server is available locally for RAG queries. End-to-end alert flow is verified from IPFire → Suricata → Malcolm → local-ai-soc → Svelte dashboard.

### Requirements
- P27-T01: Expose Malcolm OpenSearch to LAN — port 9200 accessible at 192.168.1.22 (either docker-compose port mapping or Caddy proxy); verified via curl from Windows host
- P27-T02: MalcolmCollector — new ingestion/jobs/malcolm_collector.py polls arkime_sessions3-* for event.dataset:alert events and malcolm_beats_syslog_* for syslog events; uses httpx with SSL verify=False; tracks last-seen @timestamp to avoid re-ingest; normalizes to NormalizedEvent; runs on configurable MALCOLM_POLL_INTERVAL (default 30s)
- P27-T03: Settings integration — MALCOLM_OPENSEARCH_URL, MALCOLM_OPENSEARCH_USER, MALCOLM_OPENSEARCH_PASS, MALCOLM_OPENSEARCH_VERIFY_SSL, MALCOLM_POLL_INTERVAL added to backend/core/config.py (pydantic-settings); collector registered in backend/main.py lifespan alongside existing FirewallCollector
- P27-T04: Recommendation dispatch validation — PATCH /api/recommendations/{id}/approve triggers schema validation of the artifact against contracts/recommendation.schema.json before dispatch; Svelte dashboard shows "Dispatch" button on approved recommendations; dispatch endpoint returns 422 if schema validation fails
- P27-T05: ChromaDB corpus sync — rsync or scp of /var/lib/chromadb from supportTAK-server (192.168.1.22) to local data/chroma/; sync script scripts/sync-chroma-corpus.ps1; existing local embeddings preserved; post-sync collection count verified
- P27-T06: End-to-end verification — curl trigger on IPFire generates Suricata alert; alert ingested by MalcolmCollector within 2 poll cycles; alert visible in GET /api/events and Svelte Detections view; test documented in scripts/e2e-malcolm-verify.ps1

**Plans:** 7/7 plans complete

Plans:
- [x] 27-00-PLAN.md — Wave 0: test stubs (test_malcolm_collector.py, test_malcolm_normalizer.py, test_dispatch_endpoint.py)
- [x] 27-01-PLAN.md — Wave 1: expose Malcolm OpenSearch port 9200 to LAN via docker-compose [autonomous: false]
- [x] 27-02-PLAN.md — Wave 2A: MALCOLM_* settings + MalcolmCollector polling skeleton + main.py lifespan wiring
- [x] 27-03-PLAN.md — Wave 2B: Malcolm field normalization (_normalize_alert, _normalize_syslog) + test activation
- [x] 27-04-PLAN.md — Wave 3A: POST /api/recommendations/{id}/dispatch endpoint + Svelte Dispatch button
- [x] 27-05-PLAN.md — Wave 3B: ChromaDB corpus sync script (scripts/sync-chroma-corpus.ps1)
- [x] 27-06-PLAN.md — Wave 4: end-to-end alert pipeline verification (scripts/e2e-malcolm-verify.ps1) [autonomous: false]

*Phase 27 added: 2026-04-07 (Malcolm NSM Integration and Live Feed Collector)*

## Phase 28: Dashboard Integration Fixes
**Status:** complete
**Added:** 2026-04-08
**Completed:** 2026-04-08
**Goal:** Close the 6 dashboard–backend contract mismatches found in the v1.0 milestone audit. The RAG query flow returns empty answers (wrong endpoint), event search crashes (shape mismatch), SettingsView is unreachable (not routed), ingest progress always shows 0%, pagination always returns page 1, and TS field names are wrong. All 6 are UI/api.ts fixes with no backend schema changes required.
**Gap closure:** INT-01, INT-02, INT-03, INT-04, INT-05, INT-06

### Requirements
- P28-T01: Fix RAG query SSE — change api.query.ask() to POST /api/query/ask/stream; update QueryView streaming parser to match token/done SSE format
- P28-T02: Fix event search shape — update /api/events/search to return {results:[{event,score}]} OR update api.ts + EventsView to read res.events directly
- P28-T03: Wire SettingsView — add 'settings' to App.svelte nav items; import and render SettingsView.svelte; add gear icon to nav
- P28-T04: Fix ingest job progress — map loader.py _JOBS result.loaded → events_processed, result.parsed → events_total; add started_at/completed_at timestamps
- P28-T05: Fix pagination — add offset/limit query params to GET /api/events backend (or update api.ts to use page/page_size); align api.ts EventsListResponse interface
- P28-T06: Fix NormalizedEvent TS types — update api.ts interface: process_pid → process_id, raw_data → raw_event

**Plans:** 4/4 plans complete

Plans:
- [x] 28-01-PLAN.md — Add /ingest/status/{id} compat route + filename in _JOBS (P28-T04)
- [x] 28-02-PLAN.md — Fix SSE URL and event search shape in api.ts + EventsView (P28-T01, P28-T02)
- [x] 28-03-PLAN.md — Fix pagination translation and NormalizedEvent field names in api.ts (P28-T05, P28-T06)
- [x] 28-04-PLAN.md — Wire SettingsView into App.svelte nav and routing (P28-T03)

*Phase 28 added: 2026-04-08 (Dashboard Integration Fixes — milestone gap closure)*

## Phase 29: Missing Phase Verifiers
**Status:** planned
**Added:** 2026-04-08
**Goal:** Run the GSD verifier against the 8 phases that were completed without a VERIFICATION.md. Creates authoritative VERIFICATION.md for each. If any gaps are found they are documented but do not block milestone completion (all phases are confirmed functionally working via integration check).
**Gap closure:** Missing VERIFICATION.md for phases 01, 06, 10, 12, 18, 19, 23, 27

### Requirements
- P29-T01: Verify Phase 27 (Malcolm NSM Integration) — pipeline confirmed working, verifier documents evidence
- P29-T02: Verify Phase 19 (Identity & RBAC) — operators API confirmed working; SettingsView gap addressed in Phase 28
- P29-T03: Verify Phase 23 (Firewall Telemetry Ingestion) — IPFire syslog collector confirmed working
- P29-T04: Verify Phase 18 (Reporting & Compliance) — reports/export confirmed working via integration check
- P29-T05: Verify Phase 12 (API Hardening & Parser Coverage) — rate limiting, Caddy limits confirmed
- P29-T06: Verify Phase 10 (Compliance Hardening) — compliance report generation confirmed
- P29-T07: Verify Phase 06 (Hardening & Integration) — pre-GSD phase, document confirmed working state
- P29-T08: Verify Phase 01 (Foundation) — pre-GSD phase, document confirmed working state

**Plans:** 8/8 plans complete

Plans:
- [ ] 29-01-PLAN.md — Verify Phase 27: Malcolm NSM Integration (P29-T01)
- [ ] 29-02-PLAN.md — Verify Phase 19: Identity & RBAC (P29-T02)
- [ ] 29-03-PLAN.md — Verify Phase 23: Firewall Telemetry Ingestion (P29-T03)
- [ ] 29-04-PLAN.md — Verify Phase 18: Reporting & Compliance (P29-T04)
- [ ] 29-05-PLAN.md — Verify Phase 12: API Hardening & Parser Coverage (P29-T05)
- [ ] 29-06-PLAN.md — Verify Phase 10: Compliance Hardening (P29-T06)
- [ ] 29-07-PLAN.md — Verify Phase 06: Hardening & Integration — pre-GSD (P29-T07)
- [ ] 29-08-PLAN.md — Verify Phase 01: Foundation — pre-GSD (P29-T08)

*Phase 29 added: 2026-04-08 (Missing Phase Verifiers — milestone gap closure)*

## Phase 30: Final Security and Human Sign-off
**Status:** planned
**Added:** 2026-04-08
**Goal:** Close the remaining human-action items before milestone completion: pin the Caddy Docker image to an immutable sha256 digest (requires Docker Desktop running), verify 3 Phase 22 UI items with the live frontend, and add a guard to prevent silent 0-detection failures when Sigma rule directories are absent.
**Gap closure:** P11-T02, P22 human verification, Sigma rules guard

### Requirements
- P30-T01: Pin Caddy digest — start Docker Desktop, docker inspect caddy:2.9-alpine, update docker-compose.yml to caddy:2.9-alpine@sha256:<digest> [human action required]
- P30-T02: Phase 22 human UI verification — confirm advisory banner has no dismiss button, Settings System tab loads model-status card, confidence badge colour thresholds render correctly [human action required]
- P30-T03: Sigma rules guard — add explicit warning log + non-zero exit when 0 rules loaded in POST /api/detect/run; create rules/sigma/ directory with README

**Plans:** 3/3 plans complete

Plans:
- [ ] 30-01-PLAN.md — Sigma rules guard: HTTPException(422) when 0 rules loaded, rules/sigma/README.md, unit tests
- [ ] 30-02-PLAN.md — Caddy digest pin: verify sha256 in docker-compose.yml, optional re-pin via Docker Desktop
- [ ] 30-03-PLAN.md — Phase 22 human UI sign-off: advisory banner, confidence badge, citations, Settings System tab

*Phase 30 added: 2026-04-08 (Final Security and Human Sign-off — milestone gap closure)*

## Phase 31: Malcolm Real Telemetry + Evidence Archive
**Status:** COMPLETE — 2026-04-09
**Added:** 2026-04-09
**Revised:** 2026-04-09 — Zeek normalizers deferred to Phase 36 (no Zeek data without SPAN port). Focus on 235K EVE events currently ignored + Ubuntu data pipeline + forensic evidence archive.
**Goal:** (1) Expand Malcolm collector to poll ALL 5 Suricata EVE types (TLS, DNS, fileinfo, anomaly are in OpenSearch but not collected — 235K events ignored). (2) Add raw evidence archive to Ubuntu external drive with SHA256 chain of custody. (3) Add Ubuntu normalization pipeline (ECS NDJSON endpoint, desktop polls every 60s). (4) EventsView filter chips. No Zeek — requires SPAN port hardware (Phase 36).

### Requirements
- P31-T01: Expand NormalizedEvent model with ~20 EVE-specific fields: DNS (dns_query, dns_query_type, dns_rcode, dns_answers, dns_ttl), TLS (tls_version, tls_ja3, tls_ja3s, tls_sni, tls_cipher, tls_cert_subject, tls_validation_status), File (file_md5, file_sha256_eve, file_mime_type, file_size_bytes), HTTP (http_method, http_uri, http_status_code, http_user_agent). Run DuckDB migration via _ECS_MIGRATION_COLUMNS pattern.
- P31-T02: Add _normalize_tls() to MalcolmCollector — map EVE TLS fields to NormalizedEvent. event_type="tls". Cursor key: malcolm.tls.last_timestamp.
- P31-T03: Add _normalize_dns() to MalcolmCollector — map EVE DNS fields. event_type="dns_query". Cursor key: malcolm.dns.last_timestamp.
- P31-T04: Add _normalize_fileinfo() to MalcolmCollector — map EVE file info. event_type="file_transfer". Cursor key: malcolm.fileinfo.last_timestamp.
- P31-T05: Add _normalize_anomaly() to MalcolmCollector — map EVE anomaly events. event_type="anomaly". severity: high. Cursor key: malcolm.anomaly.last_timestamp.
- P31-T06: Expand _poll_and_ingest() to poll all 5 EVE type filters in arkime_sessions3-*. Each type has its own cursor and normalizer.
- P31-T07: Implement EvidenceArchiver class on Ubuntu — tails raw syslog and EVE JSON, writes daily gzip files to $EVIDENCE_ARCHIVE_PATH/raw/{syslog,eve}/. Rotates at midnight UTC, writes SHA256 to $EVIDENCE_ARCHIVE_PATH/checksums/. EVIDENCE_ARCHIVE_PATH env var, default /mnt/evidence.
- P31-T08: Implement Ubuntu normalization HTTP server — lightweight FastAPI: GET /normalized/{date} streams day's NDJSON.gz, GET /normalized/latest returns today's partial file, GET /normalized/index lists available dates. No AI, pure field mapping.
- P31-T09: Add Ubuntu poll source to desktop Malcolm collector — poll GET http://192.168.1.22:{PORT}/normalized/latest every 60s alongside OpenSearch. Cursor: malcolm.ubuntu_normalized.last_offset.
- P31-T10: Add EventsView filter chips — horizontal chip row: All | Alert | TLS | DNS | File | Anomaly | Syslog. Single-select, maps to ?event_type= param on GET /api/events. Backend adds optional WHERE clause.
- P31-T11: Add OCSF class UID entries for new event_type values (tls, dns_query, file_transfer, anomaly) to OCSF_CLASS_UID_MAP in event.py.

**Plans:** 3/3 plans complete

Plans:
- [x] 31-01-PLAN.md — EVE schema expansion: 20 new fields, 4 normalizers, 5-type poll loop
- [x] 31-02-PLAN.md — Ubuntu EvidenceArchiver + normalization FastAPI server + systemd units
- [x] 31-03-PLAN.md — Ubuntu poll setting, EventsView filter chips

- P31-T12: Add beta/coming-soon Zeek log type chips to EventsView — grayed-out, non-clickable chips for Connection | HTTP | SSL | SMB | Auth | SSH | SMTP | DHCP with "Phase 36 — SPAN port in transit" tooltip. No API calls. Real SOC UX pattern: shows analysts what telemetry arrives when SPAN is configured.

**Hardware note:** 2TB external drive purchased 2026-04-09 (Ubuntu evidence archive, not yet mounted). Netgear GS308E managed switch purchased 2026-04-09 (SPAN port for Phase 36, not yet arrived). See Phase 36 for Zeek activation.

*Phase 31 revised: 2026-04-09 (Real telemetry only — no theater, no Zeek without hardware)*

## Phase 32: Real Threat Hunting + OSINT Enrichment + Threat Map
**Status:** COMPLETE — 2026-04-09
**Added:** 2026-04-09
**Revised:** 2026-04-09 — Added passive OSINT enrichment pipeline and IP threat trace map.
**Goal:** Replace the completely disabled HuntingView with a working threat hunting engine. NL→SQL hunt queries against real telemetry. Passive OSINT enrichment (WHOIS, AbuseIPDB, VirusTotal, Shodan read-only) for every threat IP — no active scanning. IP threat trace map: geo-IP world map showing source IPs from detections, click-through to associated events.

**OSINT scope (passive/legal only):** Read-only lookups against public APIs and databases. No active port scanning or external host probing. All APIs free-tier or no-key: MaxMind GeoLite2 (geo-IP), AbuseIPDB (reputation, free), WHOIS (socket), Shodan free tier (read-only host info), VirusTotal free tier (hash + IP reports).

### Requirements
- P32-T01: Implement backend/api/hunting.py — POST /api/hunts/query (NL→SQL via Ollama), GET /api/hunts/{hunt_id}/results, GET /api/hunts/presets
- P32-T02: Implement hunt query engine in backend/services/ — NL prompt → validated DuckDB SQL → execute → rank results by severity/recency
- P32-T03: Store hunt results in SQLite (hunt_id, query, sql, results_json, created_at, analyst_id)
- P32-T04: Wire HuntingView.svelte — remove all disabled attributes, connect input to POST /api/hunts/query, display results table with event drill-down, add OSINT enrichment panel per result row
- P32-T05: Make preset hunt cards functional — each preset sends its MITRE-mapped query to the hunt engine and shows results
- P32-T06: Add hunt history panel — analyst can replay previous hunts, see results over time
- P32-T07: Register hunting router in main.py with auth
- P32-T08: Implement passive OSINT enrichment service — backend/services/osint.py: given an IP/domain/hash, queries (async, rate-limited): AbuseIPDB confidence score + report count, WHOIS registrar + creation date, MaxMind GeoLite2 country/ASN/city, VirusTotal free-tier malicious count, Shodan free host info. Results cached in SQLite (osint_cache table, 24h TTL). All lookups passive/read-only.
- P32-T09: Implement GET /api/osint/{ip} endpoint — returns cached or fresh OSINT enrichment for an IP. Used by hunt results panel and detection detail view.
- P32-T10: Add IP threat trace map — new MapView (or panel within HuntingView): world map using Leaflet.js + OpenStreetMap tiles (free, no API key). Plots src_ip values from recent detections as markers, coloured by severity (red=critical, orange=high, yellow=medium). Click marker → side panel shows IP enrichment (OSINT data) + associated events. MaxMind GeoLite2 (local mmdb file, free, no external API call at render time) for lat/long resolution.
- P32-T11: Add map nav item — MapView accessible from sidebar as "Threat Map". Real-time: refreshes markers every 60s from GET /api/detections with src_ip filter.

**Plans:** 4/4 plans complete

Plans:
- [x] 32-01-PLAN.md — Hunt engine backend: NL→SQL, SQL validation, SQLite hunts schema, FastAPI endpoints
- [x] 32-02-PLAN.md — OSINT enrichment service: WHOIS/AbuseIPDB/MaxMind/VT/Shodan + GET /api/osint/{ip}
- [x] 32-03-PLAN.md — HuntingView wire-up: results table, OSINT panel, preset cards, hunt history
- [x] 32-04-PLAN.md — MapView threat map: Leaflet + OSM tiles, severity markers, OSINT panel, nav item

### Post-Phase Operational Fixes (2026-04-09)

The following fixes were applied after phase verification to address live-data issues
discovered when running against real Malcolm telemetry:

- **Evidence timelines:** `get_investigation_timeline()` now resolves `investigation_id` as a
  detection primary key first (via `matched_event_ids`), eliminating empty timelines.
- **Attack graph fixture data:** Cleared all fixture entities (ndjson/windows_event/osquery
  source types). Added `POST /api/graph/backfill` endpoint to rebuild entity graph from DuckDB.
  Backfilled 17,896 real Malcolm Suricata events → 20 unique entities (1 sensor host + 19
  external IPs) and 17,896 edges. Standalone script: `scripts/backfill_graph.py`.
- **Executive reports empty:** Wired real DuckDB queries into `generate_executive_report()`
  (total_events, severity_breakdown, top_hostnames, top_event_types, top_src_ips).
- **ChromaDB remote init crash:** `HttpClient()` now wrapped in try/except with graceful
  fallback to local `PersistentClient` when remote Chroma is unreachable.
- **Sidebar UX:** Redesigned to Claude-style — uniform muted text, no per-item accent colours,
  active item uses subtle background highlight, auto-scroll active nav item into view.
- **Network device health:** `GET /health/network` endpoint added (TCP reachability, unauthenticated).
  Three config vars: `MONITOR_ROUTER_HOST`, `MONITOR_FIREWALL_HOST`, `MONITOR_GMKTEC_HOST`.
  Sidebar shows coloured dots (green/red) for Router, Firewall, GMKtec, polled every 30s.

*Phase 32 revised: 2026-04-09 (OSINT enrichment + IP threat trace map added — passive/legal only)*

## Phase 33: Threat Intelligence Platform (Commercial Grade)
**Status:** planned
**Added:** 2026-04-09
**Revised:** 2026-04-09 — Full TIP rebuild. Target: feature parity with Elastic Security TI, IBM QRadar TI, and Microsoft Sentinel TI blade. All sources free/open.
**Goal:** Build a production-grade Threat Intelligence Platform. Multi-source IOC ingestion from 10+ free feeds. Automated enrichment on every detection without analyst action. Entity risk scoring (0-100) with confidence decay. IOC lifecycle management (TLP, confidence, revocation). STIX/TAXII 2.1 ingestion. Retroactive hunting — when new IOC arrives, automatically search all historical events. PassiveDNS pivoting. Certificate intelligence. IOC relationship graph. ThreatIntelView becomes a real TIP console.

### Feed Inventory (all free, no paid subscriptions)
| Feed | Source | IOC Types | Key | Sync |
|------|--------|-----------|-----|------|
| Abuse.ch URLhaus | CSV | Malicious URLs | None | Hourly |
| Abuse.ch MalwareBazaar | REST | File hashes + malware family | None | Hourly |
| Abuse.ch ThreatFox | REST | IPs, domains, hashes + actor tags | None | Hourly |
| Feodo Tracker | CSV | C2 IPs (banking trojans, ransomware) | None | Hourly |
| CISA KEV | JSON | Known exploited CVEs | None | Daily |
| AlienVault OTX | REST | Full IOC pulses + actor attribution | Free key | 6-hourly |
| MISP community | TAXII 2.1 | STIX bundles, all types | Free | 6-hourly |
| Blocklist.de | CSV | Attack IPs by category | None | Hourly |
| PhishTank | CSV | Phishing URLs | None | Daily |
| Emerging Threats | Rules | Suricata detection rules | None | Daily |
| Greynoise community | REST | IP context (scanner/malicious) | Free key | On-demand |

### Enrichment Per Entity (automated, cached 24h in SQLite)
- **IP:** AbuseIPDB score + categories, MaxMind geo+ASN, BGPView prefix/org, PassiveDNS (CIRCL.lu — no key), Greynoise community context, Shodan free host info, ThreatFox/URLhaus/Feodo match
- **Domain:** WHOIS (registrar, age, registrant org), PassiveDNS historical IPs (CIRCL.lu), crt.sh certificate history, URLhaus match, PhishTank match, VirusTotal free-tier (4 req/min)
- **Hash (MD5/SHA256):** MalwareBazaar (malware family, actor tag, AV detections), ThreatFox match, VirusTotal free-tier detection count
- **URL:** URLhaus (tags, reporter), PhishTank (verified phish), VirusTotal free-tier

### Risk Scoring Model (0–100, per entity)
- IOC match from C2/ransomware feed (Feodo, ThreatFox): +50
- IOC match from general abuse feed (URLhaus, Blocklist.de): +25
- AbuseIPDB confidence >80: +30 | 50–80: +15
- Greynoise "malicious" tag: +35 | "scanner" tag: +10
- Active in OTX pulse: +20 (+ actor confidence weight)
- VirusTotal malicious engines >5: +25
- Decay: −5 points per week without new signal
- Floor: 0 (never goes negative from decay alone)
- Score surfaced on: EventsView, DetectionsView, HuntingView, InvestigationView

### IOC Lifecycle
- **TLP levels:** WHITE / GREEN / AMBER / RED — controls display and sharing
- **Confidence:** 0–100 (feed-assigned or calculated). Decays daily.
- **Status:** active | expired | revoked | false_positive
- **Expiry:** IOCs > max_age with confidence < threshold → auto-expired
- **Revocation:** analyst can mark false positive → suppressed from future matching

### Requirements
- P33-T01: Create SQLite ioc_store schema — ioc_id, ioc_type (ip/domain/hash/url/cve), value, source_feed, confidence (0-100), tlp, status (active/expired/revoked/false_positive), actor_tag, malware_family, tags JSON, first_seen, last_seen, hit_count, decay_rate
- P33-T02: Create SQLite ioc_enrichment_cache schema — entity_type, entity_value, enrichment_json, fetched_at, expires_at. 24h TTL, async background refresh.
- P33-T03: Create SQLite ioc_relationships schema — from_value, to_value, relationship_type (resolves_to / associated_with / delivers / hosted_by / owned_by), source, created_at
- P33-T04: Implement feed sync engine — backend/services/intel/feed_sync.py: async workers per feed, rate-limited, upsert to ioc_store, conflict resolution (highest confidence wins), deduplication by value+type. Scheduled via asyncio background task every N minutes per feed.
- P33-T05: Implement Abuse.ch feeds (URLhaus CSV, MalwareBazaar REST, ThreatFox REST) — no API key, parse into IOC schema, extract actor_tag + malware_family from ThreatFox tags
- P33-T06: Implement Feodo Tracker + Blocklist.de + CISA KEV + PhishTank + Emerging Threats rule sync
- P33-T07: Implement AlienVault OTX feed sync — OTX_API_KEY env var (graceful skip if unset), poll subscribed pulses, extract IOCs + actor attribution + MITRE ATT&CK tags from pulse metadata
- P33-T08: Implement MISP/TAXII 2.1 feed ingestion — MISP_TAXII_URL + MISP_TAXII_KEY env vars, use taxii2-client library, parse STIX 2.1 indicator objects, map STIX pattern → ioc_store schema
- P33-T09: Implement IOC matching on ingest — after each NormalizedEvent normalizes, check src_ip/dst_ip/dns_query/file_md5/file_sha256_eve/http_uri against ioc_store (fast path: SQLite indexed lookup). Tag matching events: ioc_matched=True, ioc_confidence, ioc_actor_tag in NormalizedEvent. Add these fields to DuckDB schema via migration.
- P33-T10: Implement risk scoring engine — backend/services/intel/risk_score.py: given entity type+value, compute 0-100 score from enrichment data + IOC matches + decay. Store in SQLite entity_risk_scores table (entity_type, entity_value, score, components_json, computed_at). Background task recomputes daily.
- P33-T11: Implement enrichment service — backend/services/intel/enrichment.py: async enrichment for IP/domain/hash/URL. Rate-limited per API (AbuseIPDB 1k/day, VirusTotal 4/min, Shodan 1/sec). Results stored in ioc_enrichment_cache. Triggered automatically on IOC match and on-demand via API.
- P33-T12: Implement PassiveDNS pivot — GET /api/intel/passivedns/{domain} and /{ip}: queries CIRCL.lu passive DNS API (no API key required), returns historical resolutions, caches 6h. Used in enrichment panel and investigation view.
- P33-T13: Implement certificate intelligence — GET /api/intel/certs/{domain}: queries crt.sh REST API (no key), returns TLS cert history with SANs, issuer, validity dates. Reveals actor infrastructure reuse across domains.
- P33-T14: Implement retroactive hunting — SQLite retrohunt_queue table (ioc_id, status, events_found, created_at, completed_at). When new IOC added: queue DuckDB full-scan against normalized_events for matching fields. Background asyncio task processes queue every 5 min. If matches found: create DetectionRecord with detection_source="retrohunt_ioc_match", surface in DetectionsView.
- P33-T15: Implement backend/api/intel.py — GET /api/intel/iocs (search + filter by type/status/actor), POST /api/intel/iocs (manual IOC add), DELETE /api/intel/iocs/{id} (revoke), GET /api/intel/feeds (status + last sync + IOC count per feed), POST /api/intel/feeds/{name}/sync (manual trigger), GET /api/intel/enrichment/{type}/{value} (on-demand enrichment), GET /api/intel/risk/{type}/{value} (risk score), GET /api/intel/relationships/{value} (IOC relationship graph)
- P33-T16: Wire ThreatIntelView.svelte — real TIP console: feed status dashboard (last sync, IOC count, health), IOC search with faceted filters (type/actor/malware/TLP/status), IOC detail panel (all enrichment data, risk score, relationship graph using Cytoscape.js), manual IOC add form with TLP selector, retrohunt queue status
- P33-T17: Add IOC enrichment panel to EventsView, DetectionsView, InvestigationView — when an event has ioc_matched=True, show inline enrichment card: risk score (colour-coded), actor tag, malware family, AbuseIPDB score, geo/ASN, PassiveDNS count, VirusTotal detection count

**Plans:** 3/3 plans complete

Plans:
- [ ] 33-01-PLAN.md — Data layer: ioc_store DDL + IocStore class + 3 feed workers + DuckDB migration + confidence decay
- [ ] 33-02-PLAN.md — IOC matching pipeline: at-ingest hook in loader.py + retroactive scan + ioc_hits recording
- [ ] 33-03-PLAN.md — API endpoints (GET /api/intel/ioc-hits, GET /api/intel/feeds) + ThreatIntelView rewrite

*Phase 33 scoped: 2026-04-09 — 3 feeds only (Feodo, CISA KEV, ThreatFox CSV). TAXII/MISP/OTX/enrichment panels deferred to Phase 34.*

*Phase 33 revised: 2026-04-09 — Commercial-grade TIP. Feature parity with Elastic Security TI and Microsoft Sentinel TI blade. All sources free.*

## Phase 34: MITRE ATT&CK + Actor Intelligence + Asset Inventory + UEBA
**Status:** complete
**Added:** 2026-04-09
**Revised:** 2026-04-09 — Combined ATT&CK/actor intelligence with asset inventory and basic UEBA. This is the attribution and asset layer that turns detection into understanding.
**Goal:** (1) Full MITRE ATT&CK integration: auto-tag every detection with technique/tactic, ATT&CK coverage heatmap, actor group profile matching. (2) Campaign tracking: cluster related detections by TTP pattern + timeframe + infrastructure. (3) Diamond Model view for any campaign. (4) Real asset inventory from telemetry. (5) Basic UEBA: behavioral baselines per user/host, anomaly detection.

### MITRE ATT&CK Integration
- Local ATT&CK Enterprise JSON (offline file, free from attack.mitre.org, updated quarterly)
- SQLite tables: attack_techniques (id, name, tactic, description, detection, data_sources), attack_groups (id, name, aliases, country, TTPs JSON), attack_software (id, name, type, aliases, associated_groups), attack_campaigns (id, name, groups, TTPs, targets)
- Auto-tag on ingest: Sigma rules already contain `tags: [attack.tXXXX]` — extract and store with DetectionRecord
- Actor matching: given a set of detected technique IDs, find ATT&CK groups that use ≥60% of them → "Likely actor: [Group] (73% TTP match)"
- ATT&CK coverage heatmap: SVG matrix (tactics × techniques), green=have rule, yellow=partial, red=no coverage. Shows defensive gaps.

### Campaign Tracking
- Cluster related DetectionRecords: same actor tag OR same src_ip OR ≥3 shared ATT&CK techniques, within 7-day window
- Auto-name from actor (if matched) or tactic + date
- Campaign stored in SQLite: campaign_id, name, actor_tag, technique_ids JSON, src_ips JSON, affected_assets JSON, first_seen, last_seen, status (active/closed)
- CampaignView: timeline of detections in campaign, ATT&CK techniques heat, affected assets, actor profile card

### Diamond Model
- For any campaign: 4-quadrant viz (Adversary / Capability / Infrastructure / Victim)
- Adversary: actor name + confidence + aliases + country
- Capability: TTPs, tools (from ATT&CK software), malware families (from ThreatFox/MalwareBazaar)
- Infrastructure: C2 IPs + domains + TLS cert fingerprints (from Phase 33)
- Victim: affected assets + targeted users + targeted services

### Asset Inventory
- SQLite asset_store: asset_id, ip, hostname, mac, os_guess, first_seen, last_seen, open_ports JSON, tags, alert_count, risk_score (from Phase 33 scoring)
- Auto-upsert from normalized events: every src_ip/dst_ip seen becomes an asset record
- Enriched with Phase 36 Zeek data when available: DHCP hostname, conn open ports, software banner
- Asset risk: inherit risk score from Phase 33 entity scoring, plus detection frequency weight
- Actor targeting: show which ATT&CK groups target this asset's OS/service profile

### UEBA (User and Entity Behavior Analytics)
- 7-day rolling baseline per user and per host (distinct from real-time detection)
- Behavioral features: login hours, unique dst_ips per day, process set, avg bytes/hour, unique domains queried
- Anomaly triggers: new country in src_ip, first-seen process, hour-of-day outside baseline (>3σ), volume spike (>5x daily average)
- Score anomaly 0-100, create DetectionRecord with detection_source="ueba_anomaly"
- Baseline stored in SQLite entity_baselines table, recomputed nightly

### Requirements
- P34-T01: Download and parse MITRE ATT&CK Enterprise JSON → SQLite (attack_techniques, attack_groups, attack_software, attack_campaigns tables)
- P34-T02: Auto-tag DetectionRecords with ATT&CK technique IDs from Sigma rule tags on detection fire
- P34-T03: Implement actor profile matching — given detected technique set, score each ATT&CK group by TTP overlap %, surface top-3 candidate actors with confidence %
- P34-T04: Build ATT&CK coverage heatmap — GET /api/attack/coverage returns technique matrix with coverage status. Frontend: SVG grid colored by coverage.
- P34-T05: Implement campaign clustering — background worker groups related DetectionRecords into campaigns using shared infrastructure + TTP + time window
- P34-T06: Implement Diamond Model view — CampaignView.svelte or InvestigationView panel: 4-quadrant layout populated from campaign + ATT&CK + TI data
- P34-T07: Implement asset_store upsert pipeline — on every normalized event, upsert src_ip/dst_ip as assets. Update last_seen, hostname, open_ports.
- P34-T08: Implement backend/api/assets.py — GET /api/assets (list, filter by risk/tag/alert_count), GET /api/assets/{id} (detail: events, detections, campaigns, OSINT enrichment, actor targeting), POST /api/assets/{id}/tag
- P34-T09: Wire AssetsView.svelte — live asset table: risk score badge, last-seen, hostname, alert count, actor targeting warning. Click-through to asset detail with event timeline, associated detections, Diamond Model if in campaign.
- P34-T10: Implement UEBA baseline engine — nightly asyncio task computes behavioral baselines per user/host. Real-time anomaly check on each new event. Creates DetectionRecord on trigger.
- P34-T11: Add CampaignView nav item and actor profile cards — actor card shows: name, aliases, country, targets, tools, TTPs, confidence score, link to MITRE page.

**Plans:** 4/4 plans executed

Plans:
- [x] 34-01-PLAN.md — ATT&CK data layer: AttackStore, STIX bootstrap, Sigma tag extraction, detection-time tagging (Wave 1)
- [x] 34-02-PLAN.md — Asset data layer: AssetStore, IP classification, loader.py upsert pipeline (Wave 1)
- [x] 34-03-PLAN.md — Backend APIs + main.py wiring: assets.py, attack.py routers, store init, STIX bootstrap task (Wave 2)
- [x] 34-04-PLAN.md — Frontend: AssetsView rewrite, AttackCoverageView, api.ts methods, App.svelte nav (Wave 3)

*Phase 34 revised: 2026-04-09 — ATT&CK integration + actor intelligence + campaign tracking + Diamond Model + asset inventory + UEBA. This is the attribution layer.*
*Phase 34 scoped: 2026-04-10 — T05/T06/T10/T11 (campaign/Diamond/UEBA/actor-cards) deferred to Phase 35. Phase 34 ships: T01-T04 + T07-T09.*

## Phase 35: SOC Completeness
**Status:** planned
**Added:** 2026-04-09
**Revised:** 2026-04-09 — Added automated AI triage loop (P35-T08 through T10). The AI was reactive-only; it required analyst initiation. A professional SOC AI automatically triages new detections without human prompting.
**Goal:** Eliminate all remaining theatre, broken flows, and professional gaps. Critically: wire the AI to automatically triage new detections — the AI currently sits idle until asked. Fix explain.py, wire timeline playbooks, add EventsView filters, remove BETA badges, and build the automated triage background worker.

### Requirements
- P35-T01: Fix explain.py — replace silent return {} with structured error response; ensure investigation context always returns evidence or an explicit "no context" message with reason
- P35-T02: Wire playbook runs into investigation timeline — timeline.py returns real PlaybookRun rows from SQLite when case_id matches
- P35-T03: Add event_type filter to EventsView — filter chips for DNS/HTTP/TLS/Connection/Alert/Anomaly/Auth/File/SMB pull from real NormalizedEvent.event_type values
- P35-T04: Remove all "BETA — Coming Soon" badges from nav items — once phases 32/33/34 are complete, features are real
- P35-T05: Add Malcolm telemetry summary to dashboard home/overview — show counts by EVE type (N DNS, N TLS, N alerts, N anomalies) in last 24h
- P35-T06: Ensure Sigma rules can match on new EVE fields — update field_map.py to cover dns_query, http_user_agent, tls_ja3 so detection rules can fire on full telemetry
- P35-T07: End-to-end smoke test — ingest Malcolm telemetry sample, verify EVE event types appear in EventsView with chips, confirm hunt returns results, confirm IOC matching fires, confirm asset inventory populates
- P35-T08: Add triage_result storage — SQLite table: (triage_id, detection_ids JSON, model, prompt_hash, result_text, severity_summary, created_at, provenance_sha256). Mark DetectionRecords as triaged (add triaged_at column to detections table).
- P35-T09: Implement POST /api/triage/run — pulls unanalyzed DetectionRecords from SQLite (triaged_at IS NULL), builds prompt via prompts/triage.build_prompt(), calls OllamaClient.generate(), stores result with full provenance, marks detections as triaged. Returns triage_id + severity_summary. Requires auth (verify_token).
- P35-T10: Wire automated triage background worker — asyncio task in main.py lifespan that polls for unanalyzed detections every 60s and calls POST /api/triage/run internally. Dashboard surfaces latest triage result in a Triage panel (non-blocking — analyst can still query manually). This closes the gap: the AI now analyzes detections automatically without analyst initiation.

**Plans:** 3/4 plans executed

Plans:
- [ ] 35-01-PLAN.md — Broken flow fixes + quick wins: explain.py early return, playbook timeline, ZEEK chips, BETA badge removal, field_map Zeek entries (Wave 1)
- [ ] 35-02-PLAN.md — Triage data layer: triage_results SQLite DDL, triaged_at column, save/get store methods (Wave 1)
- [ ] 35-03-PLAN.md — Triage API + background worker: POST /api/triage/run, GET /api/triage/latest, _auto_triage_loop 60s poll, main.py wiring (Wave 2)
- [ ] 35-04-PLAN.md — Frontend: OverviewView landing page, triage panel in DetectionsView, GET /api/telemetry/summary, api.ts extensions (Wave 2)

*Phase 35 revised: 2026-04-09 (Auto-triage added — AI analyzes detections without analyst prompting)*

## Phase 36: Zeek Full Telemetry
**Status:** planned — hardware arrived, SPAN port active
**Added:** 2026-04-09
**Hardware status:** Netgear GS308E managed switch arrived and configured 2026-04-10. LAN port 1 mirrored to port 5 (GMKtec/Ubuntu). SPAN port active — Malcolm's Zeek containers will produce full telemetry once confirmed in OpenSearch.
**Goal:** Once a managed switch is installed with SPAN mirroring to Malcolm's capture interface, expand Malcolm collector to all 40+ Zeek log types. Implement normalizers for: conn, dns, http, ssl, x509, files, notice, weird, dhcp, ssh, smtp, rdp, smb_mapping, smb_files, software, kerberos, ntlm, ftp, sip, socks, tunnel, pe, known_hosts, known_services, intel, signatures, and ICS protocols if present. Full NormalizedEvent expansion. DuckDB migration. EventsView chip expansion.

### Requirements
- P36-T01: Verify SPAN port is delivering packets to Malcolm (Zeek logs appearing in OpenSearch, doc count > 0)
- P36-T02: Add conn normalizer — every TCP/UDP/ICMP connection, conn_state (S0/S1/SF/REJ/RSTO), duration, bytes
- P36-T03: Add weird normalizer — protocol anomalies, severity: high by default
- P36-T04: Add http, ssl, x509, files, notice normalizers
- P36-T05: Add kerberos, ntlm, ssh normalizers (auth events — golden ticket, pass-the-hash)
- P36-T06: Add smb_mapping, smb_files, rdp, dce_rpc normalizers (lateral movement indicators)
- P36-T07: Add dhcp, dns (Zeek), software, known_hosts, known_services normalizers
- P36-T08: Add remaining protocol normalizers (sip, ftp, smtp, socks, tunnel, pe)
- P36-T09: Expand NormalizedEvent with conn_state, duration, bytes fields not covered in Phase 31
- P36-T10: Update EventsView chips to include Connection / SMB / Auth / SSH / Lateral Movement
- P36-T11: Update Sigma field_map.py to cover all new Zeek fields
- P36-T12: End-to-end smoke test — verify all 15+ Zeek log types appear in DuckDB

**Plans:** 2/3 plans executed

Plans:
- [ ] 36-01-PLAN.md — NormalizedEvent expansion (17 new columns) + conn/weird normalizers + Wave 0 test stubs
- [ ] 36-02-PLAN.md — Remaining 21 Zeek normalizers (http/ssl/x509/files/notice/kerberos/ntlm/ssh/smb/rdp/dce_rpc/dhcp/dns/software/known/sip/ftp/smtp/socks/tunnel/pe)
- [ ] 36-03-PLAN.md — EventsView chip fixes, Sigma field_map Phase 36 additions, smoke test docs

## Phase 37: Analyst Report Templates
**Status:** planned
**Added:** 2026-04-11
**Plans:** 3/3 plans complete
**Goal:** Add six pre-populated analyst report templates (Session Log, Security Incident Report, Playbook Execution Log, Post-Incident Review, Threat Intelligence Bulletin, Severity & Confidence Reference) to the Reports section of the dashboard. Each template pre-fills from live SOC Brain data (DuckDB event counts, SQLite detection/investigation/playbook records, TIP IOCs, git hash, triage results) and downloads as PDF. Templates live in a new "Templates" tab within the existing ReportsView.

### Requirements
- P37-T01: Session Log template — pre-filled with today's ingest stats (DuckDB event count, timespan, source types), git commit hash, current triage result summary, and blank analyst fields (session type, errors, notes)
- P37-T02: Security Incident Report template — pre-filled from an investigation case (case title, affected assets, detection timeline, IOCs from TIP, triage audit trail, ATT&CK techniques); triggered from investigation case selector
- P37-T03: Playbook Execution Log template — pre-filled from a playbook_runs record (playbook name/version, trigger alert, steps with outputs, gate results, LLM audit trail)
- P37-T04: Post-Incident Review template — pre-filled from a closed investigation case (incident summary, timeline phases, detection engineering outcome, corrective actions); triggered from case selector
- P37-T05: Threat Intelligence Bulletin template — pre-filled with selected IOC cluster from TIP (IOC table, actor match from AttackStore, ATT&CK TTPs, internal relevance from assets); analyst selects IOC set or actor
- P37-T06: Severity & Confidence Reference — static reference card, always current (no data pre-fill); reflects current known open gaps from PROJECT.md; downloadable as PDF
- P37-T07: Templates tab in ReportsView — list of 6 template cards, each with description and "Generate" button; date/case selectors where needed; PDF download after generation
- P37-T08: backend/api/report_templates.py — 6 POST endpoints generating HTML → PDF via WeasyPrint, same pattern as existing reports.py; store generated templates in SQLite reports table with type="template_*"


Plans:
- [ ] 37-01-PLAN.md -- Wave 0 test stubs + Report.type widening + Session Log / Incident Report / Playbook Log endpoints
- [ ] 37-02-PLAN.md -- PIR + TI Bulletin + Severity Reference endpoints (all 6 HTML builders complete)
- [ ] 37-03-PLAN.md -- Frontend Templates tab (2x3 card grid, Generate-to-Download, shortcut buttons)

*Phase 36 added: 2026-04-09. Hardware arrived 2026-04-10 (Netgear GS308E). SPAN port configured: port 1 → port 5 (GMKtec/Ubuntu). Activate once Zeek logs confirmed flowing in Malcolm OpenSearch (P36-T01).*

## Phase 38: CISA Playbook Content
**Status:** IN PROGRESS
**Added:** 2026-04-11
**Goal:** Replace all 5 NIST starter playbooks with CISA-derived response flows for 4 incident classes (Phishing/BEC, Ransomware, Credential/Account Compromise, Malware/Intrusion). Enrich PlaybookStep with ATT&CK technique IDs, severity-based escalation gates, SLA timers, and containment actions. Update PlaybooksView to surface all new fields.

**Plans:** 3/3 plans complete

Plans:
- [ ] 38-01-PLAN.md — Wave 0: test stubs for model, seed, and CISA content (P38-T01..T05)
- [ ] 38-02-PLAN.md — Backend: PlaybookStep model extension, CISA BUILTIN_PLAYBOOKS, seed strategy, SQLite migrations
- [ ] 38-03-PLAN.md — Frontend: source badges, technique chips, escalation banner, containment dropdown, suggest CTA, deep-link (P38-T02,T03,T04,T06)

### Requirements
- P38-T01: Ingest and parse CISA Federal IR Playbook response phases (phishing, malware, ransomware, credential abuse, unauthorized access)
- P38-T02: Map each CISA playbook step to ATT&CK technique IDs where applicable
- P38-T03: Add escalation logic to playbook steps (severity thresholds to escalate vs contain)
- P38-T04: Add containment action fields to PlaybookStep model
- P38-T05: Seed new CISA-derived playbooks into SQLite on startup (replace NIST starters)
- P38-T06: Update PlaybooksView to show ATT&CK technique badges per step and containment action labels

## Phase 39: MITRE CAR Analytics Integration
**Status:** IN PLANNING
**Added:** 2026-04-11
**Goal:** Integrate MITRE Cyber Analytics Repository (CAR) analytics as enrichment data for the detection triage workflow. When a Sigma rule fires, surface the matching CAR analytic (detection rationale, log-source requirements, triage guidance) alongside the detection so analysts have validated reasoning rather than just an alert.

**Plans:** 4/4 plans complete

Plans:
- [ ] 39-01-PLAN.md — Wave 0 TDD stubs: car_analytics.json bundle + 8 RED test stubs for CARStore
- [ ] 39-02-PLAN.md — Wave 1: CARStore implementation + startup seed + detections migration + matcher.py CAR lookup
- [ ] 39-03-PLAN.md — Wave 2: detect.py car_analytics JSON parsing + investigate.py CAR analytics section
- [ ] 39-04-PLAN.md — Wave 3: Frontend CARAnalytic interface + DetectionsView expandable row + InvestigationView CAR panel + human verify

### Requirements
- P39-T01: Ingest CAR analytics catalog into a new SQLite table (per user decision — not DuckDB)
- P39-T02: Map Sigma rule ATT&CK technique IDs to CAR analytic IDs at detection time
- P39-T03: Enrich GET /api/detect response with matched CAR analytic (rationale, log sources, analyst guidance)
- P39-T04: Update DetectionsView to show CAR analytic panel when analytic is available
- P39-T05: Add CAR analytic link to investigation evidence panel

## Phase 40: Atomic Red Team Validation
**Status:** TODO
**Added:** 2026-04-11
**Goal:** Integrate Atomic Red Team test catalog so analysts can run ATT&CK-mapped atomic tests against the local network and immediately see whether the SOC Brain detects them. Closes the loop between threat simulation and detection validation — confirms Sigma rules fire, triage logic runs, and the investigation pipeline produces real output for real behaviors.

### Requirements
- P40-T01: Ingest Atomic Red Team test catalog (atomics YAML) into SQLite (storage override: consistent with all prior catalogs)
- P40-T02: Add GET /api/atomics endpoint returning ATT&CK-mapped test catalog
- P40-T03: Add AtomicsView tab to dashboard — browse tests by technique, see detection coverage status
- P40-T04: Add "Run Atomic" button that generates the PowerShell invocation command for the selected test
- P40-T05: Add POST /api/atomics/validate — after running a test, check whether matching events/detections appeared within a 5-minute window; return pass/fail with evidence
- P40-T06: Detection coverage badge per ATT&CK technique — green (atomic confirmed detection), yellow (rule exists, not validated), red (no coverage)

### Plans
- [ ] 40-01-PLAN.md — Wave 0: TDD stubs (test_atomics_store.py + test_atomics_api.py) + atomics.json bundle generation
- [ ] 40-02-PLAN.md — Wave 1: AtomicsStore class + startup seed + main.py wiring + GET /api/atomics endpoint
- [ ] 40-03-PLAN.md — Wave 2: POST /api/atomics/validate endpoint + validation_results persistence
- [ ] 40-04-PLAN.md — Wave 3: Frontend — AtomicsView (grouped/collapsible, copy buttons, badges) + App.svelte wiring

## Phase 41: Threat Map Overhaul
**Status:** TODO
**Added:** 2026-04-12
**Goal:** Transform the threat map from a basic detection-IP plotter into a live geospatial intelligence surface. Plot all network_connection events (not just Sigma-fired detections), differentiate inbound vs outbound flows with directional arc lines, and enrich every IP with VPN/proxy/Tor/hosting classification using free local and API sources. Analysts see the full traffic picture with context — not just alerts.

### Requirements
- P41-T01: Source all raw network_connection events from DuckDB (src_ip + dst_ip), not just detection IPs
- P41-T02: Differentiate inbound vs outbound flows visually — arc lines connecting src→dst with direction arrows, colored by threat signal
- P41-T03: VPN/proxy/Tor/hosting detection per IP — Tor exit list, ipsum blocklist, ipapi.is ASN type, ip-api.com proxy field
- P41-T04: ASN type badge per marker (hosting/datacenter/ISP/residential/education)
- P41-T05: Time window filter (1h / 6h / 24h / 7d) on map
- P41-T06: Connection volume heatmap — marker size and arc weight by connection count
- P41-T07: Side panel enrichment — geo, ASN, VPN/proxy flags, AbuseIPDB score, Shodan ports, ipsum tier

**Plans:** 4/4 plans complete

Plans:
- [ ] 41-01-PLAN.md — Wave 0: TDD stubs (test_map_api.py x5, test_osint_classification.py x6)
- [ ] 41-02-PLAN.md — Wave 1: Backend data layer — DuckDB flow query + GET /api/map/data + api.ts interfaces
- [ ] 41-03-PLAN.md — Wave 2: OSINT classification — ip-api proxy fields, ipapi.is, ipsum, Tor exit list, osint_cache migration
- [ ] 41-04-PLAN.md — Wave 3: Frontend — MapView.svelte rewrite (MarkerCluster, arc lines, LAN node, classification panel)

## Phase 42: Streaming Behavioral Profiles
**Status:** PLANNED
**Added:** 2026-04-12
**Goal:** Give every event an anomaly score at ingest time using online ML that learns continuously without batch retraining. Every (hostname, process_name) entity gets a behavioral baseline that updates with each new event via River HalfSpaceTrees. High-deviation events surface in the detections pipeline regardless of whether any Sigma rule fires — closing the gap between known-bad detection and novel-behavior detection.

**Plans:** 3/4 plans executed

Plans:
- [ ] 42-01-PLAN.md — Wave 0 RED test stubs (AnomalyScorer + anomaly API)
- [ ] 42-02-PLAN.md — River integration, per-entity model persistence, anomaly_score in DuckDB
- [ ] 42-03-PLAN.md — Anomaly API endpoints + synthetic detection creation
- [ ] 42-04-PLAN.md — AnomalyView dashboard tab (events table, sparklines, trend chart)

### Requirements
- P42-T01: Integrate River HalfSpaceTrees into the ingest pipeline — score every event against its entity's model at ingest time
- P42-T02: Persist per-entity models to disk (River model serialization) so baselines survive restarts
- P42-T03: Store anomaly_score (float) on every event in DuckDB events table
- P42-T04: Auto-surface high-anomaly events (score > threshold) as synthetic detections without requiring a Sigma rule match
- P42-T05: AnomalyView dashboard tab — list high-scoring events, entity profile sparklines, score trend over time
- P42-T06: Peer group baselining — baseline per (subnet, process_name) not just per individual host to reduce false positive rate

## Phase 43: Sigma v2 Correlation Rules
**Status:** TODO
**Added:** 2026-04-12
**Goal:** Add multi-event correlation to the detection pipeline using Sigma v2.1 correlation rule types transpiled to windowed DuckDB SQL. Detect port scans (N distinct dst_ports from one src_ip in window), brute force (N failed auths in window), and multi-stage chains (rules A+B+C all fire for same entity within T seconds) without a separate correlation engine. Also implement beaconing detection via DuckDB coefficient of variation query.

### Requirements
- P43-T01: Implement beaconing detection — CV (stddev/mean of inter-connection intervals) < 0.3 over 20+ connections per (src_ip, dst_ip, dst_port) tuple
- P43-T02: Implement port scan detection — N distinct dst_ports from one src_ip within time window
- P43-T03: Implement brute force detection — N failed auth events for same target within window
- P43-T04: Implement multi-stage chain correlation — rules A+B+C all fire for same entity within T seconds
- P43-T05: Surface correlation hits as detections with correlated_event_ids evidence list
- P43-T06: CorrelationView or correlation panel in DetectionsView showing matched event sequences

## Phase 44: Analyst Feedback Loop
**Status:** TODO
**Added:** 2026-04-12
**Goal:** Make analyst approve/reject decisions feed back into detection quality. When an analyst marks a detection True Positive or False Positive, embed the event sequence in Chroma with a label, update an SGDClassifier via partial_fit(), and surface similar confirmed incidents in future investigations. Closes the learning loop — the system gets measurably better with each analyst decision.

### Requirements
- P44-T01: Add TP/FP verdict buttons to DetectionsView per detection row
- P44-T02: POST /api/feedback endpoint — stores verdict in SQLite feedback table, embeds event sequence in Chroma labeled collection
- P44-T03: SGDClassifier.partial_fit() called on each verdict — persisted to disk between sessions
- P44-T04: Similar incident surfacing in InvestigationView — Chroma k-NN search against confirmed cases, show top 3 matches with similarity score and verdict
- P44-T05: Feedback stats in MetricsView — TP rate, FP rate, model accuracy trend over time

## Phase 45: Agentic Investigation
**Status:** TODO
**Added:** 2026-04-12
**Goal:** Replace the pre-built investigation summary with a genuine agentic loop — the LLM calls tools, reasons about intermediate results, decides what to query next, and produces a chain-of-reasoning verdict. Analysts see the investigation steps, not just the conclusion. Uses smolagents with 6 tools wrapping existing DuckDB/Chroma/IOC endpoints. qwen3:14b via Ollama handles tool-calling reliably at this scope.

### Requirements
- P45-T01: Define 6 investigation tools: query_events, get_entity_profile, enrich_ip, search_sigma_matches, get_graph_neighbors, search_similar_incidents
- P45-T02: Implement smolagents ToolCallingAgent with sandboxed execution, local Ollama backend
- P45-T03: POST /api/investigate/agentic — runs the agent loop, streams reasoning steps back to client
- P45-T04: InvestigationView agentic mode — shows tool calls, intermediate results, and final verdict as a readable chain of reasoning
- P45-T05: Hard resource limits — max 10 tool calls per investigation, 90s timeout, read-only tools only

## Phase 46: RITA + JA4 TLS Fingerprinting
**Status:** TODO
**Added:** 2026-04-12
**Goal:** Integrate RITA (Real Intelligence Threat Analytics) consuming Phase 36 Zeek SPAN port logs for production-grade beaconing, DNS tunneling, and exfiltration detection. Add JA4+ TLS fingerprinting via Zeek plugin to identify Cobalt Strike, Metasploit, and known malware by TLS fingerprint without signatures. Both consume the existing Zeek pipeline.

### Requirements
- P46-T01: Install and configure RITA against Zeek log directory from Phase 36 SPAN port
- P46-T02: Scheduled RITA analysis job — runs hourly, imports beacon/tunnel/exfil findings into SQLite
- P46-T03: Install ja4-zeek Zeek package — outputs JA4 hashes into conn.log
- P46-T04: JA4 hash cross-reference against public malware hash database (GreyNoise/Censys free datasets)
- P46-T05: Surface RITA findings and JA4 hits in ThreatHuntingView and DetectionsView

## Phase 47: GNN Lateral Movement Detection
**Status:** TODO
**Added:** 2026-04-12
**Goal:** Detect lateral movement via graph neural network analysis of authentication event sequences. Model auth events as a bipartite user→host graph, compute node2vec embeddings nightly, and flag nodes whose embeddings shift significantly between time windows. Phase in Euler GNN if node2vec proves insufficient. Requires substantial labeled data from Phase 44 feedback loop before this is effective.

### Requirements
- P47-T01: Build bipartite auth graph from DuckDB auth_failure and process_create events (user→host edges)
- P47-T02: Compute node2vec embeddings nightly via PyTorch Geometric — persist embeddings to SQLite
- P47-T03: Flag nodes with cosine distance > threshold between consecutive nightly embeddings
- P47-T04: Surface lateral movement candidates in a dedicated LateralMovementView
- P47-T05: Upgrade to Euler GNN if node2vec false positive rate > 15% after 30 days of labeled feedback
