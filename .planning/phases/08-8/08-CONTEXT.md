# Phase 8: Production Hardening & Live Telemetry — Context

**Gathered:** 2026-03-17
**Status:** Ready for planning
**Source:** PRD Express Path (user-provided Phase 8 definition)

<domain>
## Phase Boundary

Phase 8 delivers the production-hardening and live telemetry layer on top of the completed AI-SOC-Brain
investigation platform (Phases 1–7). Phases 1–7 built: FastAPI backend, Ollama integration, EVTX/JSON/CSV
ingestion, Sigma detection, ATT&CK enrichment, graph correlation, causality engine, case management,
threat hunting, and the full investigation dashboard. Phase 8 makes the system operationally ready for
daily analyst use on a real Windows desktop, with live data collection, hardened configuration, and a
reproducible one-command setup experience.

**This phase does NOT rebuild what Phases 1–7 delivered.** It extends and hardens it.

</domain>

<decisions>
## Implementation Decisions

### Platform Constraint
- Windows desktop only — no server, no cloud, no Kubernetes
- Native Ollama on Windows is the primary and only LLM runtime (not Docker Ollama)
- RTX 5080 GPU acceleration must be preserved and validated on each start

### Architecture Lock (all inherited from Phases 1–7, must not be changed)
- Backend: FastAPI (Python 3.12 via uv)
- Structured storage: DuckDB (events) + SQLite (graph, cases, artifacts)
- Vector retrieval: Chroma PersistentClient
- Graph: Lightweight in-app graph model (no Neo4j)
- LLM: Native Ollama on Windows (host.docker.internal bridge)
- Dashboard: Svelte 5 SPA served via FastAPI static files + Caddy HTTPS

### HTTPS
- Localhost HTTPS via Docker + Caddy must be preserved and must continue working
- `curl -k https://localhost/health` must return 200 after Phase 8

### Human-in-the-loop only
- No autonomous blocking, quarantine, or destructive response actions
- All analyst-facing conclusions must remain grounded in stored evidence
- No silent removals or placeholder-only completions

### Live Telemetry
- osquery is the preferred Windows telemetry collection mechanism (deferred from Phase 6)
- osquery-compatible event model already exists in the normalized schema
- Live osquery collection must write into the existing DuckDB normalized_events table
- Fixture-driven ingestion remains valid alongside live ingestion

### Infrastructure Constraints (REJECT unless forced by verified need)
- Wazuh: REJECTED — 8+ vCPU Java fleet SIEM, no unique value
- Elastic: REJECTED — heavyweight, no unique value over DuckDB + Chroma
- Kafka: REJECTED — message broker overkill for single-desktop
- Neo4j: REJECTED — heavyweight graph DB, in-app model is sufficient
- Kubernetes: REJECTED — container orchestration overkill for desktop

### Component Classification (to be confirmed by planner after codebase inspection)
- osquery: USE NOW in Phase 8 (deferred from Phase 6 scope redefinition)
- open-webui: DEFER post-v1 (optional companion, not a dashboard replacement)
- Velociraptor: DEFER (fleet tool, overkill for single desktop)

### Verification Requirements
Phase 8 is not complete unless ALL of these are verified:
- Ollama reachable and GPU-accelerated (nvidia-smi shows utilization)
- Backend starts from `scripts\start.cmd` without errors
- Live osquery data ingests into DuckDB (if osquery integration is in scope)
- All existing test suite still passes (no regressions from Phases 1–7)
- Dashboard accessible at https://localhost/app/ after start
- At least one end-to-end threat trace works from fixture or live data

### Claude's Discretion
- Exact scope decomposition into plans (what's done in parallel vs. sequential)
- Whether live osquery integration is achievable in Phase 8 or should be a sub-phase
- Test strategy for live telemetry (mock osquery vs. real daemon)
- Any additional hardening tasks identified by inspecting the current codebase
- Documentation updates required to reflect Phase 8 additions

</decisions>

<specifics>
## Specific Ideas

### Minimum Phase 8 Deliverables (from user definition)
1. **Live telemetry collection** — osquery integration writing to DuckDB
2. **Production hardening** — config validation, startup health checks, graceful error handling
3. **Reproducible one-command setup** — `scripts\start.cmd` reliably bootstraps everything
4. **End-to-end smoke test** — full pipeline from ingestion to dashboard display
5. **Documentation** — ARCHITECTURE.md, STATE.md, DECISION_LOG.md current and accurate

### Normalized Event Schema (already complete in Phase 2, must support):
- timestamp, host, user, process, file, network connection, URL/domain/IP
- detection, evidence artifact, incident/case, ATT&CK technique
- source/provenance, severity/confidence

### Dashboard (already complete in Phases 5–7, must remain functional):
- 5-tab nav: Alerts | Cases | Hunt | Investigation | Attack Chain
- Graph view, Evidence panel, Timeline view, Case management, Hunt panel

</specifics>

<deferred>
## Deferred Ideas

- Velociraptor fleet management — deferred (overkill for single desktop)
- open-webui companion UI — deferred post-v1
- Multi-host osquery fleet — deferred (single desktop scope)
- Kubernetes deployment — rejected for this milestone

</deferred>

---

*Phase: 08-8*
*Context gathered: 2026-03-17 via PRD Express Path*
