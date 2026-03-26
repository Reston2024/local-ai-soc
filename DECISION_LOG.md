# DECISION_LOG.md
# AI-SOC-Brain — Architecture Decision Record

**Format:** Decision | Alternatives | Why Chosen | Trade-offs | Phase

---

## ADR-001: Python 3.12 (not 3.14)

**Date:** 2026-03-15
**Status:** ACCEPTED

**Context:** System Python is 3.14.3. uv can manage multiple Python versions.

**Decision:** Use Python 3.12 via `uv python install 3.12` and `uv venv --python 3.12`.

**Alternatives considered:**
- Python 3.14 — rejected: PEP 649 (deferred annotation evaluation) breaks PyO3-based libraries at runtime. pySigma, pydantic-core, and pyevtx-rs all depend on PyO3. Security/ML ecosystem lags 3-6 months behind new Python releases.
- Python 3.13 — acceptable fallback if 3.12 unavailable.

**Trade-offs:** Slightly older standard library features vs. guaranteed ecosystem compatibility. 3.12 has LTS-equivalent support in scientific/security ecosystem.

**NIST alignment:** NIST SP 800-61 emphasizes reproducible, predictable tooling. Using a battle-tested Python version supports reproducibility.

---

## ADR-002: Native Ollama (not Docker)

**Date:** 2026-03-15
**Status:** ACCEPTED

**Context:** RTX 5080 requires direct CUDA access. Docker GPU passthrough on Windows requires WSL2 with additional complexity.

**Decision:** Install Ollama natively on Windows. Never run Ollama in Docker.

**Alternatives considered:**
- Ollama in Docker with GPU passthrough — rejected: adds WSL2 NVIDIA container toolkit complexity, <5% performance difference doesn't justify it, GPU passthrough has historically had issues with new architectures (Blackwell sm_120).

**Trade-offs:** Native install means Ollama updates are manual (not `docker pull`). Mitigated by `ollama update` command.

**Security note:** Set `OLLAMA_HOST=0.0.0.0` for Docker bridge but restrict port 11434 via Windows Firewall to localhost + Docker vNIC only.

---

## ADR-003: DuckDB over SQLite/PostgreSQL for Event Storage

**Date:** 2026-03-15
**Status:** ACCEPTED

**Context:** Need efficient storage and analytical queries over security events (millions of records, time-range queries, aggregations).

**Decision:** DuckDB 1.5.0 embedded as the primary event store.

**Alternatives considered:**
- SQLite — rejected for events: row-oriented, poor analytical query performance at scale, no columnar compression.
- PostgreSQL — rejected: server process required, connection management overhead, unnecessary for single-user desktop analytics.
- TimescaleDB — rejected: PostgreSQL extension adds server complexity.

**Rationale:** DuckDB provides columnar analytics on 24 cores, reads CSV/JSON/Parquet natively, handles out-of-core processing for datasets exceeding RAM. Zero-server embedded.

**Trade-offs:** Single-writer semantics require a write queue pattern. Addressed in ADR-005.

**NIST alignment:** NIST CSF 2.0 Identify function — structured data collection and analytics capability.

---

## ADR-004: ChromaDB for Vector Retrieval

**Date:** 2026-03-15
**Status:** ACCEPTED

**Context:** Need semantic search over evidence, analyst notes, and unstructured content for RAG pipeline.

**Decision:** Chroma PersistentClient (embedded, not HTTP server mode). Version pinned. Use native Chroma client API directly — never the LangChain Chroma wrapper.

**Alternatives considered:**
- Qdrant — deferred: requires separate server process, filtering performance at >1M vectors, overkill for desktop scale.
- Pinecone — rejected: violates local-first constraint (cloud service).
- FAISS — rejected: no hybrid BM25+semantic search, no metadata filtering, requires more custom code.
- LangChain Chroma wrapper — rejected: breaks independently of ChromaDB, hides configuration, re-embeds documents unexpectedly.

**Trade-offs:** ChromaDB has had breaking storage backend migrations. Mitigated by version pinning and JSON export/import safety net script.

**NIST AI RMF alignment:** Traceability — storing embedding model identifier alongside vectors enables model provenance tracking.

---

## ADR-005: DuckDB Single-Writer + Read-Only Pool Pattern

**Date:** 2026-03-15
**Status:** ACCEPTED

**Context:** DuckDB enforces single-writer semantics. FastAPI async handlers could deadlock if multiple handlers attempt concurrent writes.

**Decision:** One global write connection serialized through an `asyncio.Queue`. All read-path API queries use `duckdb.connect(read_only=True)` connections. All DuckDB calls wrapped in `asyncio.to_thread()` to avoid blocking the event loop.

**Alternatives considered:**
- Shared single connection — rejected: deadlocks under concurrent load.
- Connection per request — rejected: DuckDB doesn't support this safely.
- Multiple uvicorn workers — rejected: each worker gets its own in-process DuckDB = inconsistent state.

**Trade-offs:** Write operations are serialized (no concurrent writes). For single-user desktop, this is not a bottleneck. Maximum throughput is ~50K events/second on this hardware.

---

## ADR-006: SQLite for Graph Edges and Detection State

**Date:** 2026-03-15
**Status:** ACCEPTED

**Context:** Need lightweight storage for entity-relationship edges and detection records. Graph is a derived view, not a primary store.

**Decision:** SQLite with WAL mode. Entity nodes, relationship edges, detection records, and case metadata all in `graph.sqlite3`.

**Alternatives considered:**
- Neo4j — rejected: JVM-based graph database, 4+ GB RAM minimum, requires server process, overkill when graph traversal is shallow (1-3 hops at desktop scale). Complex recursive queries not needed.
- DuckDB for graph — rejected: DuckDB's graph extension is immature. Separate SQLite file isolates graph operations.
- NetworkX (in-memory) — deferred: useful for complex graph algorithms (community detection, PageRank) as a Phase 4+ addition when needed.

**Trade-offs:** Complex graph algorithms (shortest path across 10K+ nodes) would need NetworkX overlay. Mitigated by early-phase scope: 3-hop max traversal depth is sufficient for investigation use cases.

**NIST CSF alignment:** Detect/Respond — threat propagation tracing through entity relationships.

---

## ADR-007: Caddy over nginx for HTTPS Proxy

**Date:** 2026-03-15
**Status:** ACCEPTED

**Context:** Need localhost HTTPS. PROJECT.md constraint: "localhost HTTPS is already provided via Docker and must be preserved."

**Decision:** Caddy 2.9 in Docker. Caddyfile with `reverse_proxy localhost:8000`. Auto-TLS via internal CA for localhost.

**Alternatives considered:**
- nginx — rejected: more complex config for local TLS, nginx-local-ca setup less straightforward than Caddy's built-in.
- Traefik — rejected: heavier, more configuration for a simple reverse proxy.
- mkcert + FastAPI direct — rejected: certificate management outside Docker is less reproducible.

**Trade-offs:** Caddy is a Docker container (adds ~40MB, Docker dependency). Accepted because TLS cert management in a container is more reproducible.

---

## ADR-008: Svelte 5 over React for Dashboard

**Date:** 2026-03-15
**Status:** ACCEPTED (MEDIUM confidence)

**Context:** Need a local browser-based investigation dashboard.

**Decision:** Svelte 5 SPA with Vite 6 and `@sveltejs/adapter-static`.

**Alternatives considered:**
- React 19 — acceptable alternative: larger ecosystem (10x more components), but 39% slower and 2.5x larger bundles vs Svelte 5. For a single-developer cybersecurity dashboard with Cytoscape.js + D3.js (both framework-agnostic), Svelte's DX advantage wins.
- Vue 3 — acceptable: good performance but smaller than React ecosystem, no clear advantage over Svelte for this use case.
- Vanilla JS — rejected: too much boilerplate for complex interactive dashboard.

**Fallback:** If a critical Svelte 5 component is unavailable, vanilla JS web components or React can fill specific gaps without migrating the whole app.

---

## ADR-009: LangGraph over LangChain Chains for RAG

**Date:** 2026-03-15
**Status:** ACCEPTED

**Context:** Need RAG orchestration for analyst Q&A.

**Decision:** Use LangGraph 1.0 graphs directly. Explicitly forbidden: legacy LangChain chains, LCEL pipelines.

**Rationale:** LangChain's chain abstraction is deprecated in favor of LangGraph. LangGraph handles branching, loops, human-in-the-loop, and stateful workflows that linear chains cannot. For a security tool, LangGraph's explicit graph nodes give full visibility into what context the LLM sees — critical for citation traceability.

**Alternatives considered:**
- LlamaIndex — rejected: LangGraph is more flexible for custom agent workflows with conditional retrieval steps.
- Direct httpx + manual assembly — acceptable for simple RAG, insufficient for multi-step retrieval (query rewriting, document grading, context windowing).

---

## ADR-010: pyevtx-rs over python-evtx for EVTX Parsing

**Date:** 2026-03-15
**Status:** ACCEPTED

**Context:** Need to parse Windows Event Log (.evtx) files, potentially multi-GB.

**Decision:** `pyevtx-rs` (Rust bindings via `pip install evtx`). ~650x faster than pure-Python `python-evtx`.

**Alternatives considered:**
- `python-evtx` — fallback only: pure Python, extremely slow on large files, stream parsing fragile on corrupt records.
- `libevtx` native bindings — more complex install, less Python-friendly.

**Trade-offs:** Rust binary dependency (must build on Windows). Mitigated by: pre-built wheels available on PyPI for Windows. If build fails on Python 3.12, fall back to python-evtx with streaming.

---

## ADR-011: Reject Wazuh

**Date:** 2026-03-15
**Status:** ACCEPTED

**Context:** Wazuh listed as "optional/only if justified" in PROJECT.md.

**Decision:** Reject. Do not install or integrate Wazuh.

**Rationale:** Wazuh central components (manager + indexer + dashboard) require 8+ vCPU and 8+ GB RAM minimum. Java-based indexer alone uses 70% CPU under load. Wazuh is designed for fleet SIEM. This project already has: DuckDB (structured storage), Sigma/pySigma (detection rules), osquery (telemetry). Wazuh adds no unique capability that justifies its resource cost on a single-analyst desktop.

**NIST alignment:** NIST CSF 2.0 principle of right-sizing security controls. Wazuh would be a disproportionate control.

---

## ADR-012: Custom pySigma DuckDB Backend

**Date:** 2026-03-15
**Status:** ACCEPTED (HIGH risk, custom engineering)

**Context:** pySigma has backends for Splunk, Elastic, Sentinel — but no mature DuckDB backend exists.

**Decision:** Write a custom pySigma backend that extends the SQL backend base class and compiles Sigma rules to DuckDB-compatible SQL WHERE clauses. Include a field mapping processing pipeline mapping Sigma canonical Windows fields to the normalized DuckDB schema.

**Alternatives considered:**
- Use Sigma-to-Python dict matching — simpler but loses SQL optimization benefits; DuckDB SQL is more efficient.
- Use an existing Splunk/Elastic backend and translate — wrong SQL dialect, too many quirks.
- sigma-cli with generic SQL backend — closest built-in option; may work for simple rules but untested on DuckDB's SQL dialect.

**Trade-offs:** Custom engineering, no reference implementation. Budget 3-5 extra days. Must validate with smoke test suite before claiming detection capability.

---

## ADR-013: Graph as Derived View (not Neo4j)

**Date:** 2026-03-15
**Status:** ACCEPTED

**Context:** PROJECT.md requires graph/node-link view. Team evaluated Neo4j vs. lightweight alternatives.

**Decision:** Graph is built from events and detections stored in DuckDB/SQLite, not a separate graph database. SQLite edge tables with adjacency list structure. Cytoscape.js for visualization.

**Rationale:** At desktop scale (hundreds to low thousands of entities per investigation), SQLite edge tables + NetworkX (if needed) + Cytoscape.js covers all required graph operations: expansion, path finding, subgraph queries, visual layout. Neo4j adds JVM server complexity with no benefit at this scale.

**MITRE ATT&CK alignment:** Attack graph visualization maps directly to the ATT&CK navigator concept — techniques as nodes, kill chain as edges.

---

## ADR-014: Human-in-the-Loop Only (No Autonomous Response)

**Date:** 2026-03-15
**Status:** ACCEPTED (Non-negotiable)

**Context:** PROJECT.md constraint: "must not autonomously block, quarantine, kill processes, alter firewall rules, or perform destructive response unless explicitly approved in a later phase."

**Decision:** The system presents findings, explanations, and recommendations to the analyst. The analyst decides and executes all response actions manually.

**Rationale:**
- NIST AI RMF 1.0: Human oversight and control is required for AI systems in high-stakes decisions.
- NIST CSF 2.0 Respond: Response decisions require human judgment for context and impact assessment.
- One false-positive automated kill-process on a production system would permanently destroy analyst trust in the tool.

**Future phase:** Autonomous response with explicit analyst pre-approval may be considered in v2+ after the investigation workflow is proven reliable.


---

## ADR-015: Causality Engine Rewired to DuckDB (Phase 8 v2)

**Date:** 2026-03-17
**Status:** ACCEPTED — retroactive fix

**Context:** `backend/causality/causality_routes.py` was importing `_events` and `_alerts` from `backend.src.api.routes` — in-memory lists populated only by the old Phase 1-4 in-memory ingestion path. In production (DuckDB ingestion), these lists are always empty. The entire causality engine was a dead branch.

**Decision:** Rewrite all causality route handlers to query `request.app.state.stores` (DuckDB for events, SQLite for detections) directly. Zero in-memory state. Entity resolver field mapping fixed to use `hostname`/`username`/`process_name` (NormalizedEvent canonical names) rather than stale `host`/`user`/`process` names.

**Trade-offs:** Causality routes now require running DuckDB to be useful. Acceptable — they were never useful before. The deferred import pattern was preserved for the causality router mount.

**Root cause:** Architecture drift between Phase 1 (in-memory prototype) and Phase 3+ (DuckDB production). No integration test caught the dead branch until Phase 8 verification.

---

## ADR-016: Unified Investigation Endpoint (Phase 8 v2)

**Date:** 2026-03-17
**Status:** ACCEPTED

**Context:** Investigation required coordinating: detection lookup (SQLite) → event fetch (DuckDB) → entity clustering (correlation/clustering.py) → Cytoscape graph building → timeline → MITRE technique extraction → summary. No single endpoint orchestrated this flow.

**Decision:** Create `POST /api/investigate` in `backend/api/investigate.py`. This endpoint:
1. Loads detection from SQLite by `detection_id`
2. Fetches matched events from DuckDB
3. Expands via Union-Find entity clustering to related events
4. Builds Cytoscape-format graph directly from event fields (no SQLite graph lookup required)
5. Returns `{detection, events, graph, timeline, attack_chain, techniques, entity_clusters, summary}`

**Alternatives considered:**
- Multi-step client-side orchestration (fetch detection, then events, then graph separately) — rejected: too many round trips, forces client to understand internal schema
- Use existing SQLite graph entities table — retained as fallback but not primary path; fresh investigations build graph from events directly

**Key design:** Graph always returns HTTP 200 with Cytoscape `elements.nodes`/`elements.edges` structure. Never 404/500 on empty results.

---

## ADR-017: FastAPI Route Ordering — Static Before Parametric

**Date:** 2026-03-17
**Status:** ACCEPTED — documented pitfall

**Context:** `POST /api/detect/run` returned HTTP 405 Method Not Allowed because `GET /api/detect/{detection_id}` was registered first. Starlette matches paths before checking methods — `/run` matched `/{detection_id}` (allowing GET only) before reaching `POST /run`.

**Decision:** Always register static sub-path routes (`/run`, `/status`, `/case`) BEFORE parametric catch-all routes (`/{id}`) in the same router. Order in the Python file = registration order = routing priority.

**Rule added to conventions:** In any FastAPI router, all named static sub-routes must appear before `/{param}` catch-all routes.

---

## ADR-018: APT Scenario Fixture for Integration Verification

**Date:** 2026-03-17
**Status:** ACCEPTED

**Context:** Phase 8 v2 required proving the end-to-end investigation pipeline works. A real Windows environment with live attack tools was not available. Synthetic fixture needed to be realistic enough to validate the full pipeline.

**Decision:** Create `fixtures/ndjson/apt_scenario.ndjson` — 15 NormalizedEvent-format events representing "Operation NightCrawler":
- Initial access: winword.exe macro drops powershell.exe
- Execution: PowerShell encoded command, IEX download cradle
- C2: svchosts.exe beaconing to 185.220.101.45:4444
- Persistence: HKCU Run key
- Discovery: whoami/net user/ipconfig
- Credential access: LSASS access
- Lateral movement: WMI spawn on WORKSTATION-02
- Impact: DC authentication failure from WORKSTATION-01

**Verified:** Ingest 15 events, run detection, run investigation — produces 53-node graph, 42 edges, 11 MITRE techniques, reconstructed process ancestry chain.

**Sigma rules created:** c2_beacon.yml (T1071.001), registry_persistence.yml (T1547.001), lsass_access.yml (T1003.001), wmi_lateral.yml (T1047).

---

## ADR-019: backend/src/ Directory — Deprecation and Scheduled Deletion

**Date:** 2026-03-26
**Status:** Accepted
**Deciders:** AI-SOC-Brain Phase 10 compliance hardening

### Context

The `backend/src/` directory exists as a legacy artifact from Phase 1-2 development when
the project structure was still being established. The canonical Python package layout is
`backend/` (flat, no `src/` nesting). The `backend/src/` path is not imported anywhere in
the active codebase (verified 2026-03-25 audit).

The Phase 10 compliance audit flagged this as a documentation contradiction — some early
docs reference `backend/src/` paths that no longer correspond to active code.

### Decision

**Retire, do not delete in Phase 10.** Mark the directory as deprecated with header
comments and document this ADR. Deletion is deferred to Phase 11 to avoid any unforeseen
import path regressions during the compliance hardening window.

### Consequences

- `backend/src/__init__.py` receives a deprecation header comment
- `docs/manifest.md` documents `backend/src/` under "Deprecated Paths"
- Phase 11 executor must delete `backend/src/` entirely and verify no import breakage
- No code imports `backend/src.*` — deletion risk is low

### Alternatives Considered

- **Delete in Phase 10:** Rejected — increases blast radius of compliance-only phase
- **Keep indefinitely:** Rejected — causes ongoing audit confusion

