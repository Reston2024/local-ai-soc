# Project Manifest

Generated: 2026-03-26
Branch: feature/recent-improvements
(reflects Phase 9-10 reality)

## File Tree

```
ai-soc-brain/
│
├── backend/                          ← FastAPI application (canonical package layout)
│   ├── __init__.py
│   ├── main.py                       ← App factory: create_app() + lifespan context
│   ├── api/
│   │   ├── __init__.py
│   │   ├── correlate.py              ← GET /api/correlate — event correlation clustering
│   │   ├── detect.py                 ← GET /api/detect — Sigma rule matching
│   │   ├── events.py                 ← GET/POST /api/events
│   │   ├── explain.py                ← POST /api/explain — LLM explanation generation (Phase 9)
│   │   ├── export.py                 ← GET /api/export — NDJSON export
│   │   ├── graph.py                  ← GET /api/graph — Cytoscape graph
│   │   ├── health.py                 ← GET /health — unauthenticated status check
│   │   ├── ingest.py                 ← POST /api/ingest, GET /api/ingest/{job_id}
│   │   ├── investigate.py            ← POST /api/investigate — unified investigation endpoint (Phase 8)
│   │   ├── investigations.py         ← POST/GET /api/investigations/saved (Phase 9)
│   │   ├── query.py                  ← POST /api/query — semantic/DuckDB search
│   │   ├── score.py                  ← POST /api/score — entity risk scoring (Phase 9)
│   │   ├── telemetry.py              ← GET /api/telemetry — osquery live telemetry
│   │   └── top_threats.py            ← GET /api/top-threats — top scored entities (Phase 9)
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
│   │   ├── auth.py                   ← Bearer token auth (Phase 10 — verify_token FastAPI dep)
│   │   ├── config.py                 ← Pydantic-settings Settings singleton
│   │   ├── deps.py                   ← Stores container dataclass
│   │   └── logging.py                ← structlog + rotating file handler + LLM audit logger
│   ├── intelligence/
│   │   ├── __init__.py
│   │   ├── anomaly_rules.py          ← Statistical anomaly detection rules
│   │   ├── explain_engine.py         ← LLM-based explanation generation (Phase 9)
│   │   └── risk_scorer.py            ← Entity risk scoring model (Phase 9)
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
│   ├── stores/
│   │   ├── __init__.py
│   │   ├── chroma_store.py           ← ChromaDB PersistentClient wrapper
│   │   ├── duckdb_store.py           ← DuckDB store with write queue pattern
│   │   └── sqlite_store.py           ← SQLite store (graph edges, detections, cases)
│   └── src/                          ← DELETED in Phase 11 (see "Deprecated Paths" below)
│
├── ingestion/                        ← Event parsing and normalization pipeline
│   ├── __init__.py
│   ├── entity_extractor.py           ← Entity/edge extraction for graph
│   ├── loader.py                     ← Batch ingest + Chroma embed coordinator
│   ├── normalizer.py                 ← Field normalization, severity mapping, injection scrubbing (Phase 10)
│   ├── osquery_collector.py          ← osquery live telemetry collector (Phase 9)
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
│   │   ├── App.svelte                ← Root layout + router
│   │   ├── main.ts                   ← Entry point
│   │   ├── components/
│   │   │   └── InvestigationPanel.svelte  ← Cytoscape graph + attack timeline UI (Phase 8-9)
│   │   │   └── graph/
│   │   │       └── ThreatGraph.svelte     ← Threat graph visualization
│   │   ├── lib/
│   │   │   └── api.ts                ← Typed API client — all fetch calls go through here
│   │   └── views/
│   │       ├── DetectionsView.svelte
│   │       ├── EventsView.svelte
│   │       ├── GraphView.svelte
│   │       ├── IngestView.svelte
│   │       └── QueryView.svelte
│   └── vite.config.ts
│
├── tests/                            ← pytest test suite
│   ├── conftest.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_anomaly_rules.py
│   │   ├── test_auth.py              ← Auth token tests: valid/missing/wrong (Phase 10)
│   │   ├── test_entity_extractor.py
│   │   ├── test_explain_api.py
│   │   ├── test_explain_engine.py
│   │   ├── test_json_parser.py
│   │   ├── test_normalizer.py        ← Injection scrubbing tests (Phase 10)
│   │   ├── test_ollama_audit.py      ← LLM audit logging tests (Phase 10)
│   │   ├── test_osquery_collector.py
│   │   ├── test_risk_scorer.py
│   │   ├── test_score_api.py
│   │   ├── test_sqlite_store.py
│   │   └── test_top_threats_api.py
│   ├── security/                     ← Security-focused tests (Phase 10)
│   │   ├── __init__.py
│   │   ├── test_auth.py              ← All non-health endpoints require 401 without token
│   │   └── test_injection.py         ← Injection pattern stripping, path traversal rejection
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_backend_health.py
│   │   ├── test_investigation_roundtrip.py
│   │   └── test_osquery_pipeline.py
│   └── sigma_smoke/
│       ├── __init__.py
│       └── test_sigma_matcher.py
│
├── .github/
│   └── workflows/
│       └── ci.yml                    ← CI pipeline: lint + test + dep-audit + secret-scan (Phase 10)
│
├── scripts/                          ← PowerShell management scripts
│   ├── configure-acls.ps1            ← data/ directory ACL hardening (Phase 10)
│   ├── configure-firewall.ps1        ← Block port 11434 except localhost+Docker NIC (Phase 10)
│   ├── load-scenario.py              ← Load APT scenario fixture
│   ├── smoke-test-phase1.ps1
│   ├── smoke-test-phase8.ps1
│   ├── start.cmd / start.ps1
│   ├── status.cmd / status.ps1
│   ├── stop.cmd / stop.ps1
│   └── verify-firewall.ps1           ← Verify firewall rule config (Phase 10)
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
│   ├── decision-log.md               ← Redirect → DECISION_LOG.md (root)
│   ├── manifest.md                   ← this file
│   └── reproducibility.md            ← Redirect → REPRODUCIBILITY_RECEIPT.md (root)
│
├── DECISION_LOG.md                   ← Architecture Decision Records ADR-001 through ADR-019
├── REPRODUCIBILITY_RECEIPT.md        ← Pinned dependency versions + verification status
├── THREAT_MODEL.md
├── pyproject.toml                    ← Python deps with exact pins (uv.lock source of truth)
└── uv.lock
```

## Active API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /health | None | Status check — always unauthenticated |
| GET | /openapi.json | None | OpenAPI spec — unauthenticated |
| GET | /docs | None | Swagger UI — unauthenticated |
| GET | /api/events | Bearer | All stored events (paginated) |
| POST | /api/events | Bearer | Ingest single event |
| POST | /api/ingest | Bearer | Batch event ingest with source label |
| GET | /api/ingest/{job_id} | Bearer | Ingest job status |
| POST | /api/query | Bearer | Semantic + DuckDB hybrid search |
| GET | /api/detect | Bearer | Run Sigma rules against stored events |
| GET | /api/graph | Bearer | Cytoscape-compatible nodes + edges |
| GET | /api/export | Bearer | Export events as NDJSON |
| POST | /api/score | Bearer | Entity risk scoring (Phase 9) |
| GET | /api/top-threats | Bearer | Top-scored threat entities (Phase 9) |
| POST | /api/explain | Bearer | LLM explanation for detection/event (Phase 9) |
| POST | /api/investigations/saved | Bearer | Save investigation snapshot (Phase 9) |
| GET | /api/investigations/saved | Bearer | List saved investigations (Phase 9) |
| GET | /api/causality | Bearer | Causality graph (deferred router — loads if module present) |
| GET | /api/correlate | Bearer | Event correlation clusters (deferred router) |
| POST | /api/investigate | Bearer | Unified investigation: detection→events→graph→timeline (Phase 8) |
| GET | /api/telemetry | Bearer | osquery live telemetry feed (deferred router) |

**Auth:** All `/api/*` routes require `Authorization: Bearer <token>`. Token validated against `AUTH_TOKEN` env var. Implemented in `backend/core/auth.py` (Phase 10).

## Deferred Routers (Loaded Conditionally)

The following routers are loaded via `try/except ImportError` in `main.py` for graceful degradation:

| Router | Mount point | Module |
|--------|-------------|--------|
| Causality | `/api/causality` | `backend.causality.causality_routes` |
| Correlate | `/api/correlate` | `backend.api.correlate` |
| Investigate | `/api/investigate` | `backend.api.investigate` |
| Telemetry | `/api/telemetry` | `backend.api.telemetry` |
| Score | `/api/score` | `backend.api.score` |
| Top Threats | `/api/top-threats` | `backend.api.top_threats` |
| Explain | `/api/explain` | `backend.api.explain` |
| Investigations | `/api/investigations` | `backend.api.investigations` |

## Phase 10: Compliance Hardening Additions

| File | Description |
|------|-------------|
| `backend/core/auth.py` | Bearer token authentication — `verify_token` FastAPI dependency |
| `ingestion/normalizer.py` | Added prompt injection pattern scrubbing (`_INJECTION_PATTERNS`) |
| `.github/workflows/ci.yml` | CI pipeline: ruff lint + pytest + pip-audit + gitleaks |
| `scripts/configure-firewall.ps1` | Block Ollama port 11434 from non-localhost |
| `scripts/verify-firewall.ps1` | Verify firewall rule state |
| `scripts/configure-acls.ps1` | Restrict data/ directory permissions |
| `tests/unit/test_auth.py` | Auth unit tests (valid/missing/wrong token → 401) |
| `tests/unit/test_normalizer.py` | Injection pattern scrubbing unit tests |
| `tests/security/test_auth.py` | Security: all protected endpoints return 401 without token |
| `tests/security/test_injection.py` | Security: injection patterns stripped, path traversal rejected |
| `DECISION_LOG.md` | Added ADR-019: backend/src/ deprecation decision |

## Deprecated Paths

- `backend/src/` — DELETED in Phase 11 (2026-03-26). Legacy path from early development (Phases 1-5); marked deprecated per ADR-019. Contents were superseded by the canonical `backend/` flat package layout. The directory was not imported anywhere in the active codebase and has been removed.

---

*Manifest last regenerated: 2026-03-26 (Phase 11 cleanup — backend/src/ deleted, CI threshold raised to 70%)*
