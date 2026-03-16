# Roadmap

**Project:** AI-SOC-Brain
**Date:** 2026-03-15
**Status:** ACTIVE — Phase 1 next

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
| Normalized event schema | `backend/models/event.py` | 10 fixture events validate without error |
| Parser registry | `ingestion/parsers/base.py`, `ingestion/registry.py` | New parser added without changing existing code |
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

## Phase 3: Detection + RAG (Scoped)
**Status:** PLANNING COMPLETE
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

## Phase 4: Graph + Correlation
**Status:** PLANNING COMPLETE
**Depends on:** Phase 3 (need detection records + entity edges from ingestion)
**Goal:** Build queryable investigation graph and correlate events into investigation threads.

**Plans:** 3 plans

Plans:
- [ ] 04-01-PLAN.md — Wave 0: test_phase4.py stubs (8 xfail classes)
- [ ] 04-02-PLAN.md — Wave 1: Replace graph models + rewrite builder.py + ThreatGraph.svelte src/dst update
- [ ] 04-03-PLAN.md — Wave 2: _correlate() with 4 patterns + full GET /graph/correlate route

### Deliverables

| Deliverable | Files | Verification |
|-------------|-------|-------------|
| Graph query service | `backend/services/graph_builder.py`, `graph/query.py` | 2-hop expansion from process returns user + host + files + network |
| GET /graph endpoint | `backend/api/graph.py` | Entity expansion + path query working |
| Event clustering | `correlation/clustering.py` | Process tree fixture → 1 cluster, relatedness_score > 0.8 |
| Alert aggregation | `correlation/aggregation.py` | 5 detections from same process tree → 1 investigation thread |
| GET /graph/correlate endpoint | `backend/api/graph.py` | Event drilldown returns full correlation context |

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

## Phase 5: Dashboard
**Status:** TODO
**Depends on:** Phase 4 (all API endpoints stable and returning real data)
**Goal:** Visual investigation surface. Graph + timeline + AI Q&A + detections in one browser tab.

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

## Phase 6: Hardening + Integration
**Status:** TODO
**Depends on:** Phase 5 (system fully functional, ready for operational polish)
**Goal:** Daily-use tool: osquery, IOC matching, operational scripts, smoke tests, reproducibility.

### Deliverables

| Deliverable | Files | Verification |
|-------------|-------|-------------|
| osquery integration | `ingestion/parsers/osquery.py`, `scripts/osquery-collect.ps1` | osquery JSON results ingest correctly |
| IOC matching | `ingestion/parsers/ioc_lists.py`, `backend/services/ioc.py` | IOC hit fires detection with source |
| Startup/shutdown scripts | `scripts/start.ps1`, `scripts/stop.ps1`, `scripts/status.ps1` | Cold start to operational in < 3 min |
| Full smoke test suite | `scripts/smoke-test-full.ps1` | All integration points pass |
| Structured logging | `logs/`, `backend/core/logging.py` | JSON logs with all required fields |
| Reproducibility receipt | `REPRODUCIBILITY_RECEIPT.md` | New env reproduced in 30 min from receipt |
| Security hardening | Windows Firewall rules, ACLs, `.env` | Port 11434 blocked from non-local interfaces |
| Export / reports | `backend/api/export.py` | JSON + CSV + Markdown exports non-empty |

### Tasks

```
[ ] 1. Install osquery via Chocolatey: choco install osquery
[ ] 2. Implement osquery result parser (JSON output from osqueryi)
[ ] 3. Implement osquery scheduled query collector script (PowerShell)
[ ] 4. Test osquery ingestion into DuckDB + Chroma
[ ] 5. Implement IOC list CSV ingestor
[ ] 6. Implement IOC matcher (hash, IP, domain, URL against events)
[ ] 7. Implement IOC match → detection record creation
[ ] 8. Write start.ps1 (Ollama check, Docker start, uvicorn start, health wait)
[ ] 9. Write stop.ps1 (graceful uvicorn stop, Docker stop)
[ ] 10. Write status.ps1 (component health summary)
[ ] 11. Write smoke-test-full.ps1 (all integration points)
[ ] 12. Set Windows Firewall rule: block port 11434 from non-local interfaces
[ ] 13. Set Windows ACLs on data/ directory (current user only)
[ ] 14. Verify .env is gitignored
[ ] 15. Implement prompt injection sanitization on event text before embedding
[ ] 16. Implement GET /export/case/{id} endpoint (JSON, CSV, Markdown)
[ ] 17. Write REPRODUCIBILITY_RECEIPT.md
[ ] 18. Run full smoke test suite — all green
[ ] 19. Final commit Phase 6
```

### Definition of Done

- [ ] `osqueryi "SELECT * FROM processes LIMIT 10" --json` ingests correctly
- [ ] IOC list ingest + match → detection fires with source attribution
- [ ] `start.ps1` brings system operational from cold in < 3 minutes
- [ ] `smoke-test-full.ps1` all green in < 5 minutes
- [ ] `logs/backend.jsonl` contains structured JSON logs
- [ ] `REPRODUCIBILITY_RECEIPT.md` complete with all versions
- [ ] Port 11434 blocked from non-local interfaces (verified via nmap from different machine)
- [ ] Export produces non-empty JSON, CSV, and Markdown files

---

## Phased Capability Timeline

| Capability | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 | Phase 6 |
|-----------|---------|---------|---------|---------|---------|---------|
| Infrastructure (Ollama, FastAPI, Caddy) | ✓ | | | | | |
| EVTX/JSON/CSV ingestion | | ✓ | | | | |
| Normalized event storage | | ✓ | | | | |
| Sigma rule detection | | | ✓ | | | |
| ATT&CK enrichment | | | ✓ | | | |
| AI Q&A with citations | | | ✓ | | | |
| Contextual anomaly detection | | | ✓ | | | |
| Graph correlation | | | | ✓ | | |
| Event clustering / investigation threads | | | | ✓ | | |
| Timeline view | | | | | ✓ | |
| Graph visualization | | | | | ✓ | |
| Detection panel + drilldown | | | | | ✓ | |
| osquery integration | | | | | | ✓ |
| IOC matching | | | | | | ✓ |
| Export / reports | | | | | | ✓ |
| Operational scripts + smoke tests | | | | | | ✓ |

**System becomes analyst-usable at Phase 3 completion.**
**System becomes excellent at Phase 5 completion.**
**System becomes production-quality at Phase 6 completion.**

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
| osquery/osquery | **USE NOW** | Phase 6 | Endpoint telemetry |
| open-webui/open-webui | **DEFER** | Phase 6+ | Optional companion chat UI. Not a replacement for custom dashboard. |
| Velocidex/velociraptor | **DEFER** | If multi-host | Fleet tool, overkill for single desktop |
| wazuh/wazuh | **REJECT** | — | 8+ vCPU Java fleet SIEM. No unique value vs DuckDB + Sigma + osquery. |

---

*Roadmap generated: 2026-03-15*
*Run `/gsd:plan-phase 1` to begin execution.*
