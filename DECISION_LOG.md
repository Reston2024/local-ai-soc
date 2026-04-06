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


---

## ADR-020: Cybersecurity-Specialised LLM (Foundation-Sec-8B)

**Date:** 2026-03-27
**Status:** ACCEPTED

**Summary:** Selected `Foundation-Sec-8B` (Cisco Foundation AI, Apache 2.0) as the cybersecurity-domain LLM alongside `qwen3:14b`. Configured via `OLLAMA_CYBERSEC_MODEL=foundation-sec:8b`. Fits within remaining VRAM headroom (~4.8 GB at Q4_K_M) when qwen3:14b is loaded.

**Rejected:** `Seneca-Cybersecurity-LLM` — unclear licence, undocumented training data, individual publisher, no first-party GGUF.

**Full ADR:** `docs/ADR-020-hf-model.md`

---

## ADR-021: Cytoscape.js + fCoSE for Attack Graph Visualization

**Date:** 2026-03-29
**Status:** ACCEPTED

**Context:**
Phase 15 required a production-quality interactive attack graph for the Svelte 5 dashboard. Requirements: force-directed layout, risk-scored node sizing, two-click Dijkstra attack path highlighting, MITRE ATT&CK tactic overlay, and bidirectional navigation to/from InvestigationView.

**Alternatives Considered:**

| Option | VRAM | Assessment |
|--------|------|------------|
| Cytoscape.js + fCoSE | npm bundle | First-class Svelte integration; mature ecosystem; fCoSE is force-directed with compound graph support |
| D3.js force simulation | npm bundle | Already a dep (timeline); would require building graph primitives from scratch |
| Sigma.js | npm bundle | WebGL-first; overkill for single-analyst desktop; smaller ecosystem |
| vis-network | npm bundle | Less maintained; no Svelte 5 bindings; larger bundle |

**Decision:** Cytoscape.js with `cytoscape-fcose@^2.2.0` (force-directed fCoSE layout) and `cytoscape-dagre@^2.5.0` (hierarchical fallback).

**Implementation notes:**
- `cytoscape.use(fcose)` / `cytoscape.use(dagre)` registered at module scope (not in `onMount`) — safe because Svelte modules execute once
- Node sizing via `data()` functions: `Math.max(20, Math.min(50, 20 + risk_score * 0.3))`
- Entity IDs contain colons (e.g., `user:jsmith`) — use `cy.getElementById(id)` not `cy.$('#id')` to avoid CSS selector parsing errors
- Cytoscape tap callbacks run outside Svelte's reactive context — state updates bridged via `container.dispatchEvent(new CustomEvent('cynodetap', ...))` handled by `oncynodetap` on the container div
- Flex layout: `.cy-container` requires `min-width: 0` to shrink when entity panel appears as a flex sibling

**Consequences:**
- `dashboard/package.json`: cytoscape-fcose and cytoscape-dagre added as dependencies
- `GraphView.svelte`: 457-line production component
- Attack graph feature verified: 12/12 automated truths + 5/5 browser UAT tests pass

---

## ADR-022: Svelte 5 Runes-Only State Management

**Date:** 2026-03-29
**Status:** ACCEPTED

**Context:**
The dashboard started with Svelte 5 runes (`$state`, `$derived`, `$effect`) but could have used legacy writable stores. As cross-view state lifting became necessary (Graph ↔ Investigation navigation), the pattern needed to be standardised.

**Decision:** Use Svelte 5 runes exclusively throughout the dashboard. No `writable()` stores, no `svelte:store` subscriptions.

**Implementation:**
- Cross-view state lifted to `App.svelte` as `$state` variables
- `graphFocusEntityId` and `currentView` live in App.svelte
- Props passed down; callbacks (`onOpenInGraph`, `onNavigateInvestigation`) propagate events up
- `$effect` in GraphView watches `focusEntityId` prop changes to trigger `loadSubgraph()`

**Consequences:**
- Consistent reactive pattern across all 11 views
- Documented in `CLAUDE.md` conventions: "Svelte 5 runes: $state(), $derived(), $effect() — NOT stores"
- No `svelte:store` or `writable()` usage anywhere in the codebase

---

## ADR-023: Firewall Telemetry — File-Tail Over UDP Listener

**Date:** 2026-04-03
**Status:** ACCEPTED

**Context:**
Phase 23 required ingesting IPFire syslog and Suricata EVE JSON from a connected firewall appliance. Windows asyncio does not support `create_datagram_endpoint` with `reuse_port`, making a native UDP listener unreliable on the desktop target.

**Decision:** Implement file-tail collection (`FirewallCollector`) reading log files written by an intermediate syslog agent rather than binding a UDP socket directly.

**Implementation:**
- `ingestion/jobs/firewall_collector.py` — asyncio task; `asyncio.to_thread()` for all file I/O
- `ingestion/parsers/ipfire_syslog_parser.py` — RFC 3164 IPFire format: FORWARDFW/INPUTFW/DROP_*/REJECT_* prefixes, iptables fields
- `ingestion/parsers/suricata_eve_parser.py` — EVE JSON: alert/flow/dns/http; severity inversion (1=critical); MITRE ATT&CK from `alert.metadata`
- Heartbeat stored in `system_kv`; `GET /api/firewall/status` derives connected/degraded/offline from heartbeat age
- `FIREWALL_SYSLOG_HOST`/`PORT` settings stubbed for future UDP; current path uses file-tail

**Consequences:**
- All telemetry flows through `IngestionLoader.ingest_events()` — free dedup, embedding, graph extraction, provenance
- 817 tests passing on Phase 23 completion

---

## ADR-024: Two-Bounded-Systems Trust Architecture (SOC ↔ Firewall)

**Date:** 2026-04-03
**Status:** ACCEPTED

**Context:**
The firewall appliance (enforcement plane) and the SOC Brain (analysis plane) must interoperate without allowing raw LLM output to reach the enforcement plane. NIST AI RMF GOVERN 1.1 requires human-in-the-loop for consequential AI actions.

**Decision:** Establish explicit trust boundary: SOC produces recommendation artifacts (schema-validated JSON); firewall executes them only after analyst approval. No raw LLM text crosses the boundary.

**Implementation:**
- `docs/ADR-030-ai-recommendation-governance.md` — governance rules for recommendation artifacts
- `docs/ADR-031-transport-contract-reference.md` — SOC consumer obligations
- `docs/ADR-032-executor-failure-reference.md` — receipt `failure_taxonomy` → case-state transitions
- `contracts/recommendation.schema.json` — versioned JSON Schema v1.0.0 with `prompt_inspection`, `override_log`, `expires_at`
- `validation_failed` and `rolled_back` receipts require mandatory analyst review; `expired_rejected` triggers re-approval

**Consequences:**
- SOC never dispatches to unreachable endpoint silently — transport failures surface as case state
- Firewall repo holds canonical transport/executor ADRs and receipt schema

---

## ADR-025: Security Hardening — AUTH_TOKEN Startup Validation

**Date:** 2026-04-05
**Status:** ACCEPTED

**Context:**
Expert panel (E3-01) identified `AUTH_TOKEN: str = "changeme"` as a CRITICAL finding. Any operator who forgets to set the token ships with an exploitable default.

**Decision:** Add `model_validator(mode="after")` to `Settings` that raises `ValueError` at construction if `AUTH_TOKEN == "changeme"` or `len(AUTH_TOKEN) < 32`. The literal string `"dev-only-bypass"` is an explicit allow-list for local development.

**Implementation:**
- `backend/core/config.py` — validator in `Settings` class
- `LEGACY_TOTP_SECRET: str = ""` default disables legacy admin path entirely; opt-in via `.env`
- `tests/security/test_auth_hardening.py::test_default_token_rejected`

**Consequences:**
- Zero-config deployments fail fast at startup with a clear error message
- Legacy admin path requires both `LEGACY_TOTP_SECRET` (non-empty) and `X-TOTP-Code` header

**Deprecation plan:** The legacy admin path (E3-02) has a hard deprecation target of Phase 26 (2026-Q2).
All new deployments must use operator table authentication. The legacy path will be removed entirely in Phase 26.

---

## ADR-026: Security Hardening — Prompt Injection Scrubbing Architecture

**Date:** 2026-04-05
**Status:** ACCEPTED

**Context:**
Expert panel (E6-01, E6-02) identified two injection vectors: (1) RAG evidence bypassing scrubbing via base64/Unicode homoglyphs; (2) `body.question` interpolated directly into prompts without scrubbing.

**Decision:**
1. `_normalize_for_scrub()` applies Unicode NFC normalization and base64 decode heuristic (≥16 chars, >70% text ratio in decoded output) before regex pattern matching.
2. `build_prompt()` returns `tuple[str, str]` — evidence in system turn, question in user turn.
3. `body.question` scrubbed with `_scrub_injection()` before prompt construction in `chat.py`.

**Implementation:**
- `ingestion/normalizer.py` — `_normalize_for_scrub()` helper
- `prompts/analyst_qa.py` — `build_prompt()` returns `(system_str, user_str)`
- `backend/api/chat.py` — `safe_question = _scrub_injection(body.question)`
- `tests/eval/fixtures/injection_b64_bypass.json` — adversarial eval fixture

**Consequences:**
- RAG evidence cannot contaminate the user turn; separates LLM trust domains at prompt level
- 831 tests passing on Phase 23.5 completion; all 12 expert panel findings closed

---

## ADR-027: Security Hardening — DuckDB External Access Disabled

**Date:** 2026-04-05
**Status:** ACCEPTED

**Context:**
Expert panel (E5-02) identified that DuckDB's default configuration allows `COPY TO 'file'`, `COPY TO 'http://...'`, and `LOAD 'httpfs'` — all of which could be exploited via a Sigma SQL injection (E1-01) to exfiltrate data. This is especially relevant given the compounded attack chain: Sigma rule injection → DuckDB COPY TO exfiltration.

**Decision:** Apply `SET enable_external_access = false` to every DuckDB connection immediately after opening. This disables all remote reads, remote writes, and extension loading from network sources.

**Implementation:**
- `backend/stores/duckdb_store.py` — setting applied in `__init__` (write connection) and `get_read_conn()` (all read connections)
- `tests/unit/test_duckdb_store.py::TestDuckDBStoreSecurity` — confirms `COPY TO` raises permission error

**Consequences:**
- `COPY TO` file and HTTP exfiltration paths are blocked at the DuckDB engine level
- No functional impact: the application never uses COPY TO or httpfs for legitimate operations
- Attack chain 3 (Sigma → DB exfil) broken in combination with E1-01 parameterization

---

## ADR-028: Security Hardening — ChromaDB Collection Delete Authorization

**Date:** 2026-04-05
**Status:** ACCEPTED

**Context:**
Expert panel (E5-01) identified that ChromaDB collection operations had no access control. A compromised code path could delete the entire RAG knowledge base, destroying the SOC Brain's grounding capability (also detectable via the `collection_delete.yml` meta-detection rule from E8-02).

**Decision:** Gate `ChromaStore.delete_collection()` behind an explicit `_admin_override=True` keyword argument. Callers without the override receive `PermissionError`. Production API endpoints must apply `require_role("admin")` before passing the override.

**Implementation:**
- `backend/stores/chroma_store.py` — `delete_collection(name, *, _admin_override=False)` + async wrapper
- `tests/unit/test_chroma_store.py` — verifies PermissionError without override; client called with override

**Consequences:**
- No existing API endpoint exposes collection delete — defense-in-depth for internal callers
- Pattern establishes precedent for all future destructive store operations

---

## ADR-029: Security Hardening — Ollama Model Digest Verification

**Date:** 2026-04-05
**Status:** ACCEPTED

**Context:**
Expert panel (E6-03) identified that the application uses bare model name strings (e.g., `"qwen3:14b"`) with no integrity check. A compromised local Ollama installation could serve a different model under the same name, silently degrading analysis quality or injecting adversarial behavior.

**Decision:** Add optional digest verification via `OllamaClient.verify_model_digest()`, called during startup lifespan. Settings `OLLAMA_MODEL_DIGEST`, `OLLAMA_EMBEDDING_DIGEST`, and `OLLAMA_ENFORCE_DIGEST` control the behavior. Graceful degradation (warn, don't fail) when Ollama is unavailable or digest is unconfigured.

**Implementation:**
- `backend/core/config.py` — three new optional settings
- `backend/services/ollama_client.py` — `verify_model_digest()` calls `/api/show`, logs actual digest
- `backend/main.py` — verification called in startup lifespan after client construction
- `config/.env.example` — documented with curl command to retrieve digest
- `tests/unit/test_ollama_client.py` — 5 tests covering match, mismatch+enforce, mismatch+no-enforce, unavailable, unconfigured

**Consequences:**
- Default (`OLLAMA_ENFORCE_DIGEST=False`): logs digest for audit, never blocks startup
- Production hardening: set `OLLAMA_ENFORCE_DIGEST=True` with pinned digest to detect model substitution
- 842 tests passing; all 18 expert panel findings now fully addressed
