# Project Manifest

Generated: 2026-03-31
Branch: feature/phase-12-api-hardening
(reflects Phase 15 reality)

## File Tree

```
ai-soc-brain/
│
├── backend/                          ← FastAPI application (Python 3.12)
│   ├── __init__.py
│   ├── main.py                       ← App factory: create_app() + lifespan context
│   ├── api/
│   │   ├── __init__.py
│   │   ├── chat.py                   ← POST /api/investigations/{id}/chat — SSE AI copilot
│   │   ├── correlate.py              ← GET /api/correlate — event correlation clustering
│   │   ├── detect.py                 ← POST /api/detect/run, GET /api/detect
│   │   ├── events.py                 ← GET/POST /api/events
│   │   ├── explain.py                ← POST /api/explain — LLM explanation generation
│   │   ├── export.py                 ← GET /api/export — NDJSON export
│   │   ├── graph.py                  ← GET /api/graph/global, /api/graph/{investigation_id}, etc.
│   │   ├── health.py                 ← GET /health — unauthenticated status check
│   │   ├── ingest.py                 ← POST /api/ingest, POST /api/ingest/file, GET /api/ingest/{job_id}
│   │   ├── investigate.py            ← POST /api/investigate — unified investigation endpoint
│   │   ├── investigations.py         ← POST/GET /api/investigations
│   │   ├── metrics.py                ← GET /api/metrics — SOC metrics and KPIs (Phase 13)
│   │   ├── query.py                  ← POST /api/query — semantic/DuckDB search
│   │   ├── score.py                  ← POST /api/score — entity risk scoring
│   │   ├── telemetry.py              ← GET /api/telemetry — osquery live telemetry
│   │   ├── timeline.py               ← GET /api/investigations/{id}/timeline
│   │   └── top_threats.py            ← GET /api/top-threats — top scored entities
│   ├── causality/
│   │   ├── __init__.py
│   │   ├── attack_chain_builder.py   ← ATT&CK kill chain reconstruction
│   │   ├── causality_routes.py       ← GET /api/causality endpoints
│   │   ├── engine.py                 ← Parent/child process causality engine
│   │   ├── entity_resolver.py        ← Hostname/user/process entity resolution
│   │   ├── mitre_mapper.py           ← MITRE ATT&CK technique tagging
│   │   └── scoring.py                ← Detection-level scoring
│   ├── core/
│   │   ├── __init__.py
│   │   ├── auth.py                   ← Bearer token auth (verify_token FastAPI dependency)
│   │   ├── config.py                 ← Pydantic-settings Settings singleton
│   │   ├── deps.py                   ← Stores container dataclass
│   │   └── logging.py                ← structlog + rotating file handler + LLM audit logger
│   ├── intelligence/
│   │   ├── __init__.py
│   │   ├── anomaly_rules.py          ← Statistical anomaly detection rules
│   │   ├── explain_engine.py         ← LLM-based explanation generation
│   │   └── risk_scorer.py            ← Entity risk scoring model
│   ├── investigation/
│   │   ├── __init__.py
│   │   ├── artifact_store.py         ← Saved investigation artifact management
│   │   ├── case_manager.py           ← Case lifecycle management
│   │   ├── hunt_engine.py            ← Threat hunt query engine
│   │   ├── investigation_routes.py   ← Investigation sub-routes
│   │   ├── tagging.py                ← Entity and event tagging
│   │   └── timeline_builder.py       ← Attack timeline construction
│   ├── models/
│   │   ├── __init__.py
│   │   └── event.py                  ← NormalizedEvent Pydantic model + field definitions
│   ├── services/
│   │   ├── __init__.py
│   │   └── ollama_client.py          ← Ollama HTTP client (generate + embed + LLM audit log)
│   └── stores/
│       ├── __init__.py
│       ├── chroma_store.py           ← ChromaDB PersistentClient wrapper
│       ├── duckdb_store.py           ← DuckDB store with write queue pattern
│       └── sqlite_store.py           ← SQLite store (graph edges, detections, cases)
│
├── ingestion/                        ← Event parsing and normalization pipeline
│   ├── __init__.py
│   ├── entity_extractor.py           ← Entity/edge extraction for graph
│   ├── loader.py                     ← Batch ingest + Chroma embed coordinator
│   ├── normalizer.py                 ← Field normalization, severity mapping, injection scrubbing
│   ├── osquery_collector.py          ← osquery live telemetry collector
│   ├── registry.py                   ← Parser registry
│   └── parsers/
│       ├── __init__.py
│       ├── base.py                   ← Parser base class
│       ├── csv_parser.py             ← CSV event parser
│       ├── evtx_parser.py            ← Windows EVTX parser (pyevtx-rs)
│       ├── json_parser.py            ← JSON/NDJSON event parser
│       └── osquery_parser.py         ← osquery result log parser
│
├── detections/                       ← Sigma rule matching
│   ├── __init__.py
│   ├── backends/
│   │   └── __init__.py
│   ├── field_map.py                  ← Sigma field → DuckDB column mapping
│   ├── matcher.py                    ← Custom DuckDB SQL backend for Sigma
│   └── pipelines/
│       └── __init__.py
│
├── correlation/                      ← Event clustering
│   ├── __init__.py
│   └── clustering.py                 ← Union-Find + temporal window correlation
│
├── graph/                            ← Graph schema and traversal
│   ├── __init__.py
│   ├── builder.py                    ← Cytoscape node/edge builder
│   └── schema.py                     ← Graph schema constants
│
├── prompts/                          ← LLM prompt templates
│   ├── __init__.py
│   ├── analyst_qa.py
│   ├── evidence_explain.py
│   ├── incident_summary.py
│   ├── investigation_summary.py
│   ├── threat_hunt.py
│   └── triage.py
│
├── dashboard/                        ← Svelte 5 SPA (npm project)
│   ├── src/
│   │   ├── App.svelte                ← Root layout + view router + navigation state
│   │   ├── main.ts                   ← Entry point
│   │   ├── components/
│   │   │   ├── InvestigationPanel.svelte  ← Legacy investigation panel
│   │   │   └── graph/
│   │   │       └── ThreatGraph.svelte     ← Threat graph visualization
│   │   ├── lib/
│   │   │   └── api.ts                ← Typed API client — all fetch calls go through here
│   │   └── views/
│   │       ├── AssetsView.svelte     ← Entity inventory
│   │       ├── DetectionsView.svelte ← Sigma alert feed + "Investigate →" navigation
│   │       ├── EventsView.svelte     ← Normalized event table
│   │       ├── GraphView.svelte      ← Cytoscape.js fCoSE attack graph (Phase 15)
│   │       ├── HuntingView.svelte    ← Threat hunt queries (Beta)
│   │       ├── IngestView.svelte     ← File upload ingestion
│   │       ├── InvestigationView.svelte  ← Timeline, attack chain, AI copilot chat
│   │       ├── PlaybooksView.svelte  ← SOAR playbook stubs (Beta)
│   │       ├── QueryView.svelte      ← Semantic + DuckDB hybrid search
│   │       ├── ReportsView.svelte    ← Compliance report stubs (Beta)
│   │       └── ThreatIntelView.svelte ← IOC lookup (Beta)
│   ├── package.json                  ← cytoscape-fcose@^2.2.0, cytoscape-dagre@^2.5.0
│   └── vite.config.ts
│
├── tests/                            ← pytest test suite
│   ├── conftest.py
│   ├── unit/                         ← 589+ unit tests (no I/O)
│   │   ├── test_anomaly_rules.py
│   │   ├── test_api_endpoints.py
│   │   ├── test_api_extended.py
│   │   ├── test_auth.py
│   │   ├── test_causality_modules.py
│   │   ├── test_chroma_store.py
│   │   ├── test_config.py
│   │   ├── test_csv_parser.py
│   │   ├── test_duckdb_store.py
│   │   ├── test_entity_extractor.py
│   │   ├── test_eval_models.py
│   │   ├── test_evtx_parser.py
│   │   ├── test_explain_api.py
│   │   ├── test_explain_engine.py
│   │   ├── test_export_api.py
│   │   ├── test_graph_api.py         ← Phase 15: 28 graph API tests
│   │   ├── test_ingest_api.py
│   │   ├── test_investigation_chat.py
│   │   ├── test_investigation_timeline.py
│   │   ├── test_investigation_utils.py
│   │   ├── test_json_parser.py
│   │   ├── test_loader.py
│   │   ├── test_matcher.py
│   │   ├── test_metrics_api.py
│   │   ├── test_metrics_service.py
│   │   ├── test_normalizer.py
│   │   ├── test_ollama_audit.py
│   │   ├── test_ollama_client.py
│   │   ├── test_osquery_collector.py
│   │   ├── test_rate_limiting.py
│   │   ├── test_risk_scorer.py
│   │   ├── test_score_api.py
│   │   ├── test_sqlite_store.py
│   │   ├── test_timeline_builder.py
│   │   └── test_top_threats_api.py
│   ├── security/                     ← Security-focused tests
│   │   ├── test_auth.py              ← All non-health endpoints require 401 without token
│   │   └── test_injection.py         ← Injection pattern stripping, path traversal rejection
│   ├── integration/
│   │   ├── test_backend_health.py
│   │   ├── test_investigation_roundtrip.py
│   │   └── test_osquery_pipeline.py
│   └── sigma_smoke/
│       └── test_sigma_matcher.py
│
├── .github/
│   └── workflows/
│       └── ci.yml                    ← CI: ruff lint + pytest (≥70% coverage) + pip-audit + gitleaks
│
├── scripts/                          ← PowerShell + Python management scripts
│   ├── _check-health.ps1             ← Internal health check helper
│   ├── _e2e-verify.ps1               ← E2E verification helper
│   ├── _start-backend.ps1            ← Backend start helper
│   ├── configure-acls.ps1            ← data/ directory ACL hardening
│   ├── configure-firewall.ps1        ← Block port 11434 except localhost+Docker NIC
│   ├── eval_models.py                ← LLM evaluation script (Phase 14)
│   ├── load-scenario.py              ← Load APT scenario fixture
│   ├── seed_siem_data.py             ← Seed SIEM test data
│   ├── smoke-test-phase1.ps1
│   ├── smoke-test-phase8.ps1
│   ├── start.cmd / start.ps1         ← Start FastAPI + Caddy
│   ├── status.cmd / status.ps1       ← Show service health
│   ├── stop.cmd / stop.ps1           ← Stop all services
│   └── verify-firewall.ps1           ← Verify firewall rule config
│
├── fixtures/                         ← Test fixture data
│   └── ndjson/
│       ├── sample_events.ndjson
│       └── apt_scenario.ndjson       ← 15-event APT "Operation NightCrawler" scenario
│
├── config/
│   └── caddy/
│       └── Caddyfile
│
├── docs/
│   ├── ADR-020-hf-model.md           ← ADR: HuggingFace embedding model selection
│   ├── decision-log.md               ← Redirect → DECISION_LOG.md (root)
│   ├── manifest.md                   ← this file
│   └── reproducibility.md            ← Redirect → REPRODUCIBILITY_RECEIPT.md (root)
│
├── ARCHITECTURE.md                   ← System design, data architecture, decision rationale
├── CLAUDE.md                         ← Claude Code conventions for this repo
├── DECISION_LOG.md                   ← ADR-001 through ADR-021
├── PROJECT.md                        ← Project brief
├── README.md                         ← Quick start, features, API reference
├── REPRODUCIBILITY_RECEIPT.md        ← Pinned dependency versions + verification status
├── STATE.md                          ← Live project state + phase completion log
├── THREAT_MODEL.md                   ← Threat model for local desktop deployment
├── docker-compose.yml                ← Caddy container definition
├── pyproject.toml                    ← Python deps with exact pins (uv.lock source of truth)
└── uv.lock
```

## Active API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /health | None | Status check — always unauthenticated |
| GET | /openapi.json | None | OpenAPI spec |
| GET | /docs | None | Swagger UI |
| GET/POST | /api/events | Bearer | List / ingest single event |
| POST | /api/ingest | Bearer | Batch event ingest with source label |
| POST | /api/ingest/file | Bearer | Ingest from uploaded file |
| GET | /api/ingest/{job_id} | Bearer | Ingest job status |
| POST | /api/query | Bearer | Semantic + DuckDB hybrid search |
| POST | /api/detect/run | Bearer | Run Sigma rules against stored events |
| GET | /api/detect | Bearer | List detection results |
| GET | /api/graph/global | Bearer | All entities + edges (Phase 15) |
| GET | /api/graph/{investigation_id} | Bearer | Investigation subgraph (Phase 15) |
| GET | /api/graph/entity/{entity_id} | Bearer | Entity neighbours |
| GET | /api/graph/entities | Bearer | Entity list |
| GET | /api/graph/traverse/{entity_id} | Bearer | BFS traversal from entity |
| GET | /api/graph/case/{case_id} | Bearer | Entities for a case |
| GET | /api/export | Bearer | Export events as NDJSON |
| POST | /api/score | Bearer | Entity risk scoring |
| GET | /api/top-threats | Bearer | Top-scored threat entities |
| POST | /api/explain | Bearer | LLM explanation for detection/event |
| GET/POST | /api/investigations | Bearer | List / create investigations |
| GET | /api/investigations/{id}/timeline | Bearer | Investigation timeline |
| POST | /api/investigations/{id}/chat | Bearer | AI copilot chat (SSE stream) |
| GET | /api/metrics | Bearer | SOC metrics and KPIs (Phase 13) |
| GET | /api/correlate | Bearer | Event correlation clusters |
| GET | /api/causality | Bearer | Process causality graph |
| POST | /api/investigate | Bearer | Unified investigation pipeline |
| GET | /api/telemetry | Bearer | osquery live telemetry status |

**Auth:** All `/api/*` routes require `Authorization: Bearer <token>`. Token validated against `AUTH_TOKEN` env var. Implemented in `backend/core/auth.py`.

## Dashboard Views

| View | File | Phase | Description |
|------|------|-------|-------------|
| Detections | DetectionsView.svelte | 5 | Sigma alert feed, ATT&CK tactic/technique |
| Events | EventsView.svelte | 5 | Normalized event table |
| Investigation | InvestigationView.svelte | 8 | Timeline, attack chain, AI copilot, "Open in Graph" |
| Query | QueryView.svelte | 5 | Semantic + DuckDB hybrid search |
| Ingest | IngestView.svelte | 5 | File upload ingestion |
| Assets | AssetsView.svelte | 9 | Entity inventory + risk scores |
| Graph | GraphView.svelte | 15 | Cytoscape.js fCoSE attack graph, Dijkstra paths |
| Threat Intel | ThreatIntelView.svelte | 13 | IOC lookup (Beta) |
| Hunting | HuntingView.svelte | 13 | Structured threat hunt queries (Beta) |
| Playbooks | PlaybooksView.svelte | 17* | SOAR playbook stubs (Beta) |
| Reports | ReportsView.svelte | 18* | Compliance report stubs (Beta) |

\* Stubs present; full implementation in planned phases.

## Test Baseline (2026-03-31)

```
uv run pytest tests/unit/ -q
589 passed, 1 skipped, 16 xpassed (606 collected)
```

Coverage target: ≥70% (enforced in CI).

## Phase Additions (12–15)

### Phase 12: API Hardening + Parser Coverage

| File | Description |
|------|-------------|
| `tests/unit/test_api_extended.py` | Extended API endpoint coverage |
| `tests/unit/test_rate_limiting.py` | Rate limiting tests |
| `tests/unit/test_evtx_parser.py` | EVTX parser unit tests |
| `tests/unit/test_csv_parser.py` | CSV parser unit tests |

### Phase 13: SOC Metrics, KPIs, HuggingFace Model

| File | Description |
|------|-------------|
| `backend/api/metrics.py` | GET /api/metrics — MTTD, MTTR, FP rate, active rules/cases |
| `tests/unit/test_metrics_api.py` | Metrics API tests |
| `tests/unit/test_metrics_service.py` | Metrics service tests |
| `docs/ADR-020-hf-model.md` | ADR: embedding model upgrade decision |

### Phase 14: LLMOps Evaluation + AI Copilot

| File | Description |
|------|-------------|
| `backend/api/chat.py` | POST /api/investigations/{id}/chat — SSE AI copilot |
| `backend/api/timeline.py` | GET /api/investigations/{id}/timeline |
| `scripts/eval_models.py` | LLM evaluation harness |
| `tests/unit/test_investigation_chat.py` | Chat copilot tests |
| `tests/unit/test_investigation_timeline.py` | Timeline tests |
| `tests/unit/test_eval_models.py` | Eval harness tests |

### Phase 15: Attack Graph UI

| File | Description |
|------|-------------|
| `backend/api/graph.py` | Added GET /api/graph/global + GET /api/graph/{investigation_id} |
| `dashboard/src/views/GraphView.svelte` | 457-line Cytoscape.js component (fCoSE, attack paths, MITRE) |
| `dashboard/src/App.svelte` | graphFocusEntityId state + bidirectional nav callbacks |
| `dashboard/src/views/InvestigationView.svelte` | "Open in Graph" button wired to entity_id |
| `dashboard/src/lib/api.ts` | api.graph.global() + api.graph.caseGraph() methods |
| `tests/unit/test_graph_api.py` | 28 graph API tests (global, investigation, route ordering) |

---

*Manifest last regenerated: 2026-03-31 (Phase 15 complete — Attack Graph UI)*
