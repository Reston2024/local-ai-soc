# Project Research Summary

**Project:** AI-SOC-Brain
**Domain:** Local-first Windows desktop AI cybersecurity investigation platform
**Researched:** 2026-03-15
**Confidence:** HIGH

---

## Executive Summary

AI-SOC-Brain is a single-analyst, local-first investigation workstation that ingests host telemetry and analyst evidence, runs Sigma-based detections, provides AI-grounded Q&A with evidence citations, and renders interactive graph and timeline visualizations -- all without sending data to the cloud. The research confirms that no existing open-source tool combines Sigma matching, local LLM Q&A with citations, graph visualization, and timeline analysis in a single desktop application. Zircolite/Chainsaw are CLI-only detection tools. Timesketch and DFIR-IRIS require server infrastructure. The gap this tool fills is real and validated by recent academic work (RAGIntel 2025) and practitioner talks (RAGnarok, BSides LV 2025).

The recommended approach is an almost entirely native Windows stack: Ollama for LLM inference (RTX 5080, 16 GB VRAM), FastAPI as the single backend process with three embedded databases (DuckDB for structured events, Chroma for vector retrieval, SQLite for graph edges and detection state), and a Svelte 5 SPA dashboard. The only Docker container is Caddy for localhost HTTPS. This "embedded everything" pattern eliminates server management, simplifies deployment, and keeps latency minimal for a single-user desktop tool. Python 3.12 is required (not 3.14) due to PyO3/pySigma compatibility concerns with PEP 649 deferred annotations.

The three highest-risk areas are: (1) RTX 5080 Blackwell CUDA compatibility with Ollama, which must be validated on day one before any other work proceeds; (2) Sigma rule silent failures, where rules convert without errors but match nothing because field names in the normalized schema do not align with Sigma canonical fields -- this requires a custom pySigma DuckDB backend and a smoke test suite; and (3) DuckDB single-writer concurrency under FastAPI, which requires a deliberate read-only connection pool plus write queue pattern from Phase 1. All three pitfalls have clear mitigations documented below and baked into the architecture.

---

## Architecture Decision (Confirmed)

The architecture is confirmed as proposed, with one critical modification: **Python 3.12 via uv, not Python 3.14**.

| Layer | Technology | Runtime | Rationale |
|-------|-----------|---------|-----------|
| **LLM Inference** | Ollama 0.13+ | Native Windows | Direct CUDA access to RTX 5080. Docker GPU passthrough on Windows adds WSL2 complexity for <5% perf difference. |
| **Backend API** | FastAPI + Uvicorn | Native Python (uv, Python 3.12) | In-process access to all embedded DBs. Async SSE/WebSocket for LLM streaming. Best SecOps/ML library ecosystem. |
| **Structured Storage** | DuckDB 1.5.0 (embedded) | In-process | Columnar analytics on 24 cores. CSV/JSON/Parquet native reads. Single-writer + read-only pool pattern. |
| **Vector Storage** | Chroma (PersistentClient, pinned version) | In-process | Hybrid BM25 + semantic search. No external server. Pin to known-good version, not LangChain wrapper. |
| **Graph/State Storage** | SQLite (embedded) | In-process | WAL mode. Graph edge tables, detection state, case metadata. Battle-tested, zero-config. |
| **TLS Proxy** | Caddy 2.9+ | Docker (only container) | Auto-TLS for localhost. Reverse proxy to FastAPI:8000. Tiny footprint (~40 MB image). |
| **Dashboard** | Svelte 5 SPA | Static files served by FastAPI/Caddy | 39% faster than React 19, 2.5x smaller bundles. Cytoscape.js for graphs, D3.js for timeline. |
| **Detection** | pySigma + custom DuckDB backend | In-process | Sigma YAML to DuckDB SQL. Field mapping pipeline. Smoke test suite. |

**Process model (total: 3 processes + 1 container):**

```
[Browser] --> [Caddy:443 (Docker)] --> [FastAPI:8000 (native Python)]
                                            |
                                            +--> Ollama:11434 (native Windows)
                                            +--> DuckDB (embedded, in-process)
                                            +--> Chroma (embedded, in-process)
                                            +--> SQLite (embedded, in-process)
```

**Why Python 3.12 and not 3.14:** Python 3.14 introduced PEP 649 (deferred evaluation of annotations) which breaks PyO3-based libraries at runtime. pySigma, pydantic-core, and pyevtx-rs all depend on PyO3. The security/ML library ecosystem lags 3-6 months behind new Python releases. Python 3.12 is the safe choice; 3.13 is acceptable. Use `uv python install 3.12` and `uv venv --python 3.12`.

---

## Component Decisions

| Component | Decision | Phase | Rationale |
|-----------|----------|-------|-----------|
| **ollama/ollama** | USE NOW | Phase 1 | Core LLM runtime. Native Windows, RTX 5080 CUDA. Install v0.13+ for Blackwell support. |
| **langchain-ai/langgraph** | USE NOW | Phase 3 | RAG orchestration with human-in-the-loop patterns. Use LangGraph graphs directly, NOT legacy LangChain chains. v1.0 is stable. |
| **chroma-core/chroma** | USE NOW | Phase 1 | Embedded PersistentClient. Pin version. Hybrid search (BM25 + semantic). Do NOT use LangChain Chroma wrapper -- use native client. |
| **SigmaHQ/sigma** | USE NOW | Phase 3 | Detection rule corpus. 4000+ community rules. Lingua franca of detection engineering. |
| **SigmaHQ/pySigma** | USE NOW | Phase 3 | Rule parsing and compilation. Write custom DuckDB backend using SQL backend base class. Build field mapping pipeline. |
| **SigmaHQ/sigma-cli** | USE NOW | Phase 3 | Rule management CLI. Validate, list, convert rules. Use `--fail-unsupported` during dev. |
| **osquery/osquery** | USE NOW | Phase 6 | Endpoint telemetry via SQL. v5.22.1. Windows support mature. Lightweight. Install when ingestion pipeline is ready. |
| **open-webui/open-webui** | DEFER | Phase 6+ | Optional companion chat UI alongside custom dashboard. 90K+ stars, RAG built-in. Run in Docker with `host.docker.internal:11434`. Low effort to add later. Does NOT replace the custom investigation UI. |
| **Velocidex/velociraptor** | DEFER | If needed | Agent/server model for fleet management. Overkill for single desktop. osquery covers endpoint telemetry. Reconsider only if project expands to multi-host. |
| **wazuh/wazuh** | REJECT | -- | 8+ vCPU, 8+ GB RAM minimum. Java-based indexer uses 70% CPU. Fleet SIEM architecture. DuckDB + Sigma + osquery cover all its functionality for single-desktop scope with a fraction of the resource cost. No unique value. |

---

## LLM Model Recommendations (RTX 5080, 16 GB VRAM)

| Model | Size | Quantization | Purpose | Confidence |
|-------|------|-------------|---------|------------|
| **qwen3:14b** | ~14 GB | Q8 | Primary reasoning: analyst Q&A, triage, correlation, threat analysis | HIGH |
| **deepseek-r1:14b** | ~14 GB | Q4_K_M | Alternative: explicit chain-of-thought reasoning traces for complex analysis | MEDIUM |
| **mxbai-embed-large** | ~1.2 GB | -- | Embedding: MTEB retrieval 64.68 vs nomic-embed-text 53.01. 1024 dimensions. | HIGH |

**Loading rules:**
- Only one reasoning model loaded at a time (~14 GB fills VRAM).
- Embedding model (~1.2 GB) loads/unloads automatically via Ollama API.
- Never load two 14B models simultaneously.
- Set `CUDA_VISIBLE_DEVICES=0` to force discrete GPU (Intel CPU has no iGPU conflict, but set it defensively).

---

## Critical Pitfall Resolutions

These mitigations are baked into the architecture. Each must be verified at the specified phase.

| # | Pitfall | Mitigation | Phase | Verification |
|---|---------|-----------|-------|-------------|
| 1 | **Python 3.14 breaks PyO3/pySigma** | Use Python 3.12 via `uv venv --python 3.12`. PEP 649 deferred annotations break pySigma, pydantic-core, pyevtx-rs at runtime. | Pre-Phase 1 | All deps install and import without error on 3.12. |
| 2 | **RTX 5080 CUDA / Ollama GPU fallback** | Ollama 0.13+. NVIDIA Studio Drivers (clean install). CUDA 12.8+. `CUDA_VISIBLE_DEVICES=0`. Validate GPU layers with `ollama ps` on day 1 before writing any code. | Phase 1 | `nvidia-smi` shows GPU util during `ollama run llama3.2:1b`. `ollama ps` shows GPU layers > 0. |
| 3 | **Docker-to-native-Ollama bridge** | `OLLAMA_HOST=0.0.0.0` + `OLLAMA_ORIGINS=*` as Windows system env vars. Restart Ollama after setting. Use `host.docker.internal:11434` in Docker Compose. Windows Firewall rule: port 11434 only from localhost + Docker vNIC. | Phase 1 | `curl http://host.docker.internal:11434` from inside Caddy container returns 200. |
| 4 | **Sigma rules convert but match nothing** | Custom pySigma DuckDB backend. Explicit field mapping pipeline (every Sigma canonical field to normalized DuckDB column). `--fail-unsupported` during dev. Smoke test suite: 5-10 known rules + crafted log entries that must match. | Phase 3 | All smoke test rules match their test events. Zero false negatives on known-bad data. |
| 5 | **DuckDB concurrency deadlocks** | Single write connection + `asyncio.Queue` write queue. Read-only connection pool (`read_only=True`) for API queries. Single uvicorn worker. `asyncio.to_thread()` for DuckDB calls from async handlers. | Phase 1 | Load test: concurrent ingestion + queries for 60s without hangs. |
| 6 | **Chroma version instability** | Pin `chromadb==X.Y.Z` (latest known-good for Python 3.12). Store embedding model identifier in collection metadata. JSON export/import script from day 1. Use native Chroma client, NOT LangChain wrapper. | Phase 1 | Version pinned. Export/import round-trip test passes. Restart preserves data. |
| 7 | **Graph visualization hairball** | Progressive disclosure: 1-hop default, expand on click. Max ~100 visible nodes. Visual aggregation (collapse child processes). Entity type filtering. Dagre layout for process trees, force-directed for relationship discovery. | Phase 5 | Usability test with 200+ node dataset. Analyst finds key entities within 30s. |
| 8 | **EVTX parsing performance** | Use `pyevtx-rs` (Rust bindings, 650x faster than pure Python `python-evtx`). Stream-parse in batches of 1000. Async background ingestion with progress reporting. | Phase 2 | Parse real Security.evtx (100MB+) without memory spike or timeout. |
| 9 | **LLM hallucination on security evidence** | System prompts with hard "ONLY based on provided context" constraints. Citation verification layer (programmatic check that cited event IDs exist). Confidence indicators from Chroma similarity scores. Human-in-the-loop only, never auto-execute. | Phase 3 | Citation verification passes for 100% of test queries. No fabricated IOCs in test suite. |
| 10 | **Naive threshold-based anomaly detection** | Contextual anomaly detection from the start: partition by time/user/host/activity. Explainable evidence chains ("Z standard deviations above baseline for this user during this window"). Analyst feedback loop (true/false positive markings). | Phase 3 | Same event count triggers differently for different entities/contexts. |

---

## Key Findings

### From STACK.md

The stack is mature and well-validated. Every core technology has HIGH confidence except Svelte 5 (MEDIUM -- smaller ecosystem than React but sufficient for this use case). Key version constraints:

- **Ollama 0.13+** required for RTX 5080 Blackwell CUDA support
- **DuckDB 1.5.0** -- LTS release, columnar analytics, parallel execution on 24 cores
- **Chroma** -- pin to specific version, use PersistentClient (not HTTP server mode)
- **pySigma 1.1.1** -- no native DuckDB backend exists; must write one using SQL backend base class
- **pyevtx-rs** (not python-evtx) -- Rust-based EVTX parser, 650x faster
- **LangGraph 1.0** -- use directly, not through LangChain chains (deprecated)
- **Svelte 5 + Cytoscape.js + D3.js** -- 39% faster than React, Cytoscape handles up to ~10K elements, D3 for timeline

### From FEATURES.md

**Table stakes (P1 -- must have for launch):**
- EVTX/JSON/CSV/NDJSON ingestion with normalized schema (ECS-style field names)
- Full-text search across ingested events (<2s for 1M events)
- Sigma rule matching with ATT&CK technique tagging
- Detection/alert list with severity and evidence drilldown
- Timeline view (zoom, filter, color-code by severity/source)
- Local AI Q&A with evidence citations (the killer differentiator)
- Basic case/session separation

**Differentiators (P2 -- add after core validation):**
- Graph-based investigation surface (node-link, entity types, click-to-expand)
- Event clustering and relatedness scoring
- IOC list ingestion and matching
- Contextual anomaly detection (not naive thresholds)
- AI triage summaries (3-paragraph "what probably happened")
- Prompt templates for analyst workflows
- Analyst notes integrated into RAG corpus

**Defer to v2+:**
- Full attack trace visualization (capstone: requires graph + timeline + detections all working)
- Export/report generation (JSON, CSV, Markdown)
- osquery live integration (scheduled queries)
- Sigma rule authoring assistance via AI

**Anti-features (deliberately NOT built):**
- Autonomous response actions (kill process, block IP) -- human-in-the-loop only
- Real-time continuous monitoring / EDR agent -- be the analysis brain, not the collection agent
- Multi-tenant / multi-user collaboration -- single-analyst desktop tool
- NL-to-SQL generation -- unreliable, use structured search + RAG instead
- Plugin/extension marketplace -- premature for v1

### From ARCHITECTURE.md

Single-process FastAPI backend with three embedded databases, communicating with native Ollama over localhost HTTP. All data flows through an ingestion pipeline (parse, normalize, load) into DuckDB (structured queries), Chroma (semantic retrieval), and SQLite (graph edges). Detection runs compiled Sigma rules as DuckDB SQL queries against ingested events. RAG assembles context from both Chroma (vector similarity) and DuckDB (structured context) before prompting Ollama. The graph is a derived view from stored data, not a primary store.

**Key architectural patterns:**
1. **Embedded database composition** -- DuckDB + Chroma + SQLite in one process, each doing what it does best
2. **Service layer orchestration** -- thin API routes delegate to service classes; services are testable without HTTP
3. **Parser registry** -- each evidence format has a parser implementing a common interface; new formats require zero changes to existing code
4. **Compiled detection rules** -- Sigma YAML compiled once to DuckDB SQL, cached, executed many times
5. **Graph as derived view** -- SQLite edge tables built during ingestion, not a separate graph database

### From PITFALLS.md

Nine pitfalls identified (3 critical, 3 high, 3 medium). All have documented mitigations. The three with highest recovery cost if caught late:

1. **Sigma silent failures** (HIGH recovery cost) -- requires building field mapping pipeline and re-testing all rules. Weeks of rework if discovered late. Prevention: smoke test suite from day one.
2. **Graph hairball** (HIGH recovery cost) -- near-complete rewrite of graph component if progressive disclosure is not designed from the start.
3. **Naive threshold anomaly detection** (HIGH recovery cost) -- complete detection logic rewrite. Cannot be patched incrementally.

The three with lowest recovery cost (fix in hours/minutes):
- RTX 5080 CUDA failure (driver reinstall + env var)
- Docker-Ollama bridge (set OLLAMA_HOST=0.0.0.0)
- Python 3.14 compat (switch to 3.12 via uv)

---

## Implications for Roadmap

### Phase 1: Foundation

**Rationale:** Everything depends on Ollama GPU acceleration, FastAPI with embedded stores, and Caddy HTTPS being operational. Validating the RTX 5080 CUDA setup is a day-one blocker. The DuckDB single-writer pattern and Chroma version pinning must be established before any data flows through the system.

**Delivers:**
- Ollama installed, GPU-accelerated, models pulled (qwen3:14b, mxbai-embed-large)
- FastAPI skeleton with /health endpoint, lifespan management for embedded stores
- DuckDB schema + single-writer/read-only connection pattern
- Chroma PersistentClient + JSON export/import safety net
- SQLite graph edge schema
- Caddy Docker container with HTTPS reverse proxy to FastAPI
- Smoke tests: GPU validation, Docker-to-Ollama bridge, store persistence

**Features addressed:** None directly (infrastructure foundation)
**Pitfalls addressed:** #1 Python 3.12, #2 RTX 5080 CUDA, #3 Docker-Ollama bridge, #5 DuckDB concurrency, #6 Chroma instability

**Research flag:** LOW risk. Well-documented patterns for all components. Ollama + FastAPI integration has multiple reference implementations.

---

### Phase 2: Ingestion Pipeline

**Rationale:** You cannot query, detect, or visualize what you have not ingested. The ingestion pipeline is the gateway for all evidence. The normalized schema must be designed with Sigma field mapping in mind (pitfall #4 prevention). Entity edge extraction during ingestion feeds the graph layer in Phase 4.

**Delivers:**
- Normalized event schema (Pydantic, ECS-style field names)
- EVTX parser (pyevtx-rs, streaming, batched)
- JSON/NDJSON/CSV parsers
- DuckDB loader (normalized event INSERT)
- Chroma loader (event text embedding with model version metadata)
- SQLite loader (entity edge extraction: process-to-file, user-to-host, etc.)
- /ingest API endpoint (file upload, async background processing with progress)
- Parser registry pattern (add new formats without touching existing code)

**Features addressed:** EVTX/JSON/CSV ingestion, normalized schema, entity extraction
**Pitfalls addressed:** #8 EVTX parsing performance (pyevtx-rs), #4 Sigma field alignment (schema design)

**Research flag:** MEDIUM risk. The EVTX parser choice (pyevtx-rs vs python-evtx) needs validation on Python 3.12. The normalized schema design requires careful field naming to align with Sigma canonical fields -- get this wrong and Phase 3 detection breaks silently.

---

### Phase 3: Detection + RAG

**Rationale:** Detection and RAG are independent consumers of stored data that can be built in parallel. Detection reads from DuckDB; RAG reads from Chroma + DuckDB. Building them together in one phase means the analyst gets both "what is wrong" (detections) and "why is it wrong" (AI Q&A) at the same time.

**Delivers:**
- Custom pySigma DuckDB backend (SQL backend base class + Cookiecutter template)
- Field mapping processing pipeline (Sigma canonical fields to normalized schema)
- Sigma rule loading and compilation (YAML to DuckDB SQL, cached)
- Detection matcher (run compiled rules against DuckDB events)
- Detection records in SQLite (rule, severity, ATT&CK technique, evidence links)
- /detect API endpoint (detection list, drilldown)
- Sigma smoke test suite (5-10 known rules + crafted test events)
- LangGraph RAG pipeline (query rewriting, Chroma retrieval, DuckDB context, Ollama streaming)
- Prompt templates (analyst Q&A, triage, threat hunt, incident summary, evidence explanation)
- Citation verification layer (programmatic check that cited event IDs exist)
- /query API endpoint (streaming Q&A with citations)
- ATT&CK technique enrichment on detections

**Features addressed:** Sigma rule matching, ATT&CK tagging, detection list with drilldown, AI Q&A with citations, prompt templates, full-text search
**Pitfalls addressed:** #4 Sigma silent failures, #9 LLM hallucination, #10 naive thresholds

**Research flag:** HIGH risk. This is the most complex phase. The custom pySigma DuckDB backend is custom engineering, not configuration. No mature/official DuckDB backend exists. The RAG pipeline quality depends on embedding model choice, chunk strategy, and prompt engineering -- all requiring iteration. Budget extra time.

---

### Phase 4: Graph + Correlation

**Rationale:** Depends on both ingestion (entity edges) and detection (linking detections to entities). Graph queries combine data from SQLite (edges) and DuckDB (entity attributes). Correlation and clustering require detection results to exist.

**Delivers:**
- Graph query service (traverse edges, fetch attributes, build subgraphs)
- Entity graph building from stored edges (process trees, network connections, user-host relationships)
- Event clustering and relatedness scoring (shared entities, temporal proximity)
- Alert aggregation for related events (investigation threads)
- /graph API endpoint (entity expansion, path queries, depth-limited traversal)
- ATT&CK enrichment integration (technique-to-detection-to-event links)

**Features addressed:** Graph investigation surface (backend), event clustering, relatedness scoring, alert aggregation
**Pitfalls addressed:** Partial #7 (graph data model must support progressive disclosure)

**Research flag:** MEDIUM risk. Graph-as-derived-view using SQLite edge tables is a well-understood pattern. Clustering algorithms (shared entities, temporal proximity) are straightforward. The risk is in graph query performance at scale -- monitor with realistic data volumes.

---

### Phase 5: Dashboard

**Rationale:** Requires all API endpoints to exist and be stable. Building UI before APIs means constant rework. By this phase, fixture data and real detections exist for meaningful visual testing.

**Delivers:**
- Svelte 5 SPA scaffold (Vite, adapter-static)
- API client layer (typed, auto-generated from FastAPI OpenAPI spec)
- AI Q&A panel (chat interface with streaming responses and evidence citation links)
- Detection panel (sortable/filterable triage queue with severity hierarchy)
- Timeline view (D3.js, zoom, filter, color-code by severity/source, handles 10K+ events)
- Graph visualization (Cytoscape.js, progressive disclosure, 1-hop default, dagre layout for process trees, max ~100 visible nodes, entity type filtering, visual aggregation)
- Evidence drilldown (click detection to see raw event JSON/fields)
- Basic case/session management UI

**Features addressed:** Timeline view, graph investigation surface, detection panel, evidence drilldown, AI Q&A panel, case management
**Pitfalls addressed:** #7 graph hairball (progressive disclosure, node limits, dagre layout)

**Research flag:** MEDIUM risk. Svelte 5 + Cytoscape.js integration is straightforward (direct JS API, no wrapper needed). D3.js timeline is well-documented. The risk is UX design for the graph view -- prototype with realistic data volumes (200+ nodes), not toy examples. Consider consulting Cambridge Intelligence's cybersecurity visualization patterns.

---

### Phase 6: Hardening + Integration

**Rationale:** Core investigation workflow must work first. osquery integration, operational tooling, and polish are final-phase concerns. This phase transforms a working prototype into a daily-use tool.

**Delivers:**
- osquery installation and integration (scheduled queries, result ingestion)
- IOC list ingestion and matching (hashes, IPs, domains, URLs)
- Case management enhancements (archive, reopen, export)
- Startup/shutdown PowerShell scripts (launch all components, graceful shutdown)
- Comprehensive smoke test suite (all components, all integration points)
- Structured logging (JSON, queryable)
- Reproducibility receipt (versions, configs, data checksums)
- Windows Firewall rules (Ollama port 11434 restricted to localhost + Docker vNIC)
- Export/report generation (JSON, CSV, Markdown)

**Features addressed:** osquery integration, IOC matching, case management, export/reports, operational tooling
**Pitfalls addressed:** Security hardening (Ollama network exposure, data access controls)

**Research flag:** LOW risk. osquery Windows installation is well-documented (Chocolatey package). PowerShell scripting is standard. Smoke tests are mechanical verification of already-working components.

---

### Phase Ordering Rationale

1. **Foundation before everything** -- cannot build on broken GPU acceleration or deadlocking database connections. Every minute spent validating infrastructure in Phase 1 saves hours of debugging in later phases.

2. **Ingestion before detection/RAG** -- you cannot detect what you have not ingested, you cannot retrieve what you have not embedded. The normalized schema design in Phase 2 directly determines whether Sigma rules match in Phase 3.

3. **Detection + RAG together** -- they are independent consumers of stored data with no dependency on each other. Building them in one phase means the analyst gets both capabilities simultaneously, which is when the tool becomes useful rather than just another log viewer.

4. **Graph after detection** -- graph edges are derived from ingested events and enriched by detections. Building the graph layer before detections exist means building it twice.

5. **Dashboard after APIs** -- building UI against unstable APIs is a recipe for constant rework. By Phase 5, all endpoints are stable and real data exists for visual testing.

6. **Hardening last** -- operational polish (startup scripts, smoke tests, firewall rules) should wrap a working system, not a prototype. osquery integration extends the data pipeline but is not required for core investigation workflows.

### Research Flags Summary

| Phase | Research Needed | Rationale |
|-------|----------------|-----------|
| Phase 1: Foundation | LOW | Well-documented patterns. Multiple reference implementations for Ollama + FastAPI. |
| Phase 2: Ingestion | MEDIUM | pyevtx-rs Python 3.12 compatibility needs validation. Schema design for Sigma alignment requires careful field mapping research. |
| Phase 3: Detection + RAG | HIGH | Custom pySigma DuckDB backend is custom engineering. No mature reference implementation. RAG quality requires iteration on embeddings, chunking, and prompts. |
| Phase 4: Graph + Correlation | MEDIUM | SQLite edge tables are standard. Clustering algorithms are well-documented. Performance at scale needs monitoring. |
| Phase 5: Dashboard | MEDIUM | Svelte + Cytoscape.js is straightforward technically. UX design for graph progressive disclosure needs prototyping with real data. |
| Phase 6: Hardening | LOW | osquery, PowerShell, smoke tests -- all standard patterns. |

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| **Stack** | HIGH | All core technologies verified against official documentation. Version constraints identified. RTX 5080 CUDA requirements confirmed via Ollama GitHub issues. |
| **Features** | HIGH | Feature landscape validated against 6+ competitor tools (Zircolite, Chainsaw, Timesketch, DFIR-IRIS, OpenCTI, Cambridge Intelligence). MVP definition is clear. Anti-features well-justified. |
| **Architecture** | HIGH | Embedded database composition pattern is well-established for desktop applications. Service layer + parser registry patterns are standard FastAPI practice. Only novel element is the pySigma DuckDB backend. |
| **Pitfalls** | HIGH | Every critical pitfall sourced from multiple primary references (GitHub issues, official docs, practitioner blogs). Recovery strategies documented. Phase-to-pitfall mapping is explicit. |

**Overall confidence:** HIGH

The one area of genuine uncertainty is the custom pySigma DuckDB backend (Phase 3). No mature implementation exists. The approach (use SQL backend base class, write field mapping pipeline) is sound in theory but unvalidated in practice. Budget 3-5 extra days for this component.

### Gaps to Address

| Gap | Impact | Resolution Strategy |
|-----|--------|---------------------|
| **No mature pySigma DuckDB backend** | Phase 3 detection engine depends on it | Write custom backend using SQL backend base class + Cookiecutter template. Smoke test with 5-10 known Sigma rules against crafted test events. Budget extra time. |
| **Chroma Python 3.12 exact version pin** | Phase 1 dependency lock | Test `chromadb` install on Python 3.12 and identify exact known-good version before starting. STACK.md references v1.5.5 but this needs validation on 3.12 specifically. |
| **pyevtx-rs on Python 3.12 on Windows** | Phase 2 EVTX parsing | Validate `pip install evtx` (pyevtx-rs) builds on Python 3.12 + Windows. If it fails, fall back to python-evtx (pure Python, slower but guaranteed compatible). |
| **Ollama 0.13+ actual version availability** | Phase 1 day-one GPU validation | STACK.md says 0.17+, PITFALLS.md says 0.13+. Use latest available. The key requirement is Blackwell sm_120 compute capability support, not a specific version number. |
| **Embedding model quality for security domain** | Phase 3 RAG retrieval precision | mxbai-embed-large scores well on MTEB but has not been benchmarked on cybersecurity-specific retrieval. Build a small evaluation set (10-20 security queries with known-good answers) early in Phase 3 to validate retrieval quality. |

---

## Open Questions / Risks

1. **pySigma DuckDB backend viability.** No one has published a working pySigma backend for DuckDB. The SQL backend base class exists, but field mapping complexity is unknown until implementation begins. Mitigation: start with 5 simple rules, validate end-to-end before scaling to the full Sigma corpus.

2. **Embedding model retrieval quality on security data.** mxbai-embed-large has strong MTEB scores but security event text (process names, command lines, registry paths) is very different from the benchmark corpus. If retrieval quality is poor, consider fine-tuning or switching to a domain-specific embedding model. Mitigation: build a 10-20 query evaluation set early in Phase 3.

3. **DuckDB write queue under sustained ingestion.** The single-writer pattern works, but sustained ingestion of large EVTX files (millions of records) while an analyst queries the system could create write queue backpressure. Mitigation: batch DuckDB INSERTs (1000 rows per transaction), use `COPY` for bulk loads, implement backpressure signaling to the ingestion pipeline.

4. **Ollama model swap latency.** Switching between qwen3:14b and deepseek-r1:14b requires unloading one model and loading another (~30-60 seconds). If analysts need to switch frequently, this creates friction. Mitigation: default to qwen3:14b for all queries; only swap to deepseek-r1 for explicitly requested "deep reasoning" mode.

5. **Svelte 5 ecosystem maturity for enterprise-style components.** Svelte's component ecosystem is ~10x smaller than React's. If the dashboard needs complex data tables, drag-and-drop, or advanced form controls, finding quality Svelte components may be harder. Mitigation: Cytoscape.js and D3.js are framework-agnostic (direct JS API). Only the basic UI shell uses Svelte components. If a specific component is missing, vanilla JS or a web component can fill the gap.

---

## Sources

### Primary (HIGH confidence)
- [Ollama GPU Support Docs](https://docs.ollama.com/gpu) -- RTX 5080 / Blackwell CUDA requirements
- [Ollama GitHub Issues #14446, #11849, #13163](https://github.com/ollama/ollama/issues/) -- GPU compatibility, Docker bridge, iGPU conflicts
- [DuckDB Concurrency Documentation](https://duckdb.org/docs/stable/connect/concurrency) -- single-writer semantics
- [pySigma Processing Pipelines](https://sigmahq-pysigma.readthedocs.io/en/latest/Processing_Pipelines.html) -- field mapping architecture
- [pySigma Backends](https://sigmahq-pysigma.readthedocs.io/en/latest/Backends.html) -- backend base classes
- [ChromaDB Migration Documentation](https://docs.trychroma.com/docs/overview/migration) -- version instability history
- [Python 3.14 What's New](https://docs.python.org/3/whatsnew/3.14.html) -- PEP 649 breaking changes
- [PyO3 Issue #5000](https://github.com/PyO3/pyo3/issues/5000) -- Python 3.14 incompatibility
- [FastAPI Release Notes](https://fastapi.tiangolo.com/release-notes/) -- v0.135.x, SSE support
- [Cytoscape.js Documentation](https://js.cytoscape.org/) -- graph visualization capabilities

### Secondary (MEDIUM confidence)
- [RAGIntel - RAG for cyber attack investigation (PeerJ 2025)](https://peerj.com/articles/cs-3371/) -- academic validation of RAG for grounded CTI
- [RAGnarok - BSides Las Vegas 2025](https://pretalx.com/security-bsides-las-vegas-2025/talk/LDTD3E/) -- local LLM + RAG for threat hunting
- [Cambridge Intelligence - Cybersecurity Visualization](https://cambridge-intelligence.com/use-cases/cybersecurity/) -- graph visualization patterns
- [Cambridge Intelligence - Fixing Data Hairballs](https://cambridge-intelligence.com/how-to-fix-hairballs/) -- progressive disclosure techniques
- [Svelte vs React 2026 Benchmarks](https://devtrios.com/blog/svelte-vs-react-which-framework-should-you-choose/) -- performance comparison
- [ScienceDirect - Hallucinations in AI-driven Cybersecurity](https://www.sciencedirect.com/science/article/abs/pii/S0045790625002502) -- hallucination risks
- [ChromaDB Migration Pitfalls](https://wwakabobik.github.io/2025/11/migrating_chroma_db/) -- version instability evidence
- [DuckDB Discussion #13719 - FastAPI Concurrency](https://github.com/duckdb/duckdb/discussions/13719) -- concurrency patterns

### Tertiary (needs validation during implementation)
- [Best LLMs for 16GB VRAM](https://medium.com/@rosgluk/best-llms-for-ollama-on-16gb-vram-gpu-c1bf6c3a10be) -- qwen3:14b recommendation (needs benchmarking on security tasks)
- [Best Embedding Models 2026](https://elephas.app/blog/best-embedding-models) -- mxbai-embed-large MTEB scores (needs security-domain validation)
- [Blackwell CUDA Fix Guide](https://apatero.com/blog/blackwell-gpu-cuda-errors-fix-troubleshooting-guide-2025) -- driver troubleshooting (situation may have improved with newer drivers)

---
*Research completed: 2026-03-15*
*Ready for roadmap: yes*
