# AI-SOC-Brain

**Local Windows AI Cybersecurity Investigation Platform**

A single-analyst, air-gapped cybersecurity workstation. All inference, detection, graph correlation, and visualization runs locally on a Windows desktop — no cloud, no telemetry, no external services.

**Status:** Phase 23.5 complete — Security Hardening: all 18 expert panel findings addressed (10 CRITICAL/HIGH closed, 5 MEDIUM closed, 2 accepted risk, 1 mitigated). 842 tests passing. Next: Phase 24 (Recommendation Artifact Store + Approval API).

---

## Features

| Capability | Status | Details |
|-----------|--------|---------|
| **Event Ingestion** | ✅ | EVTX, JSON/NDJSON, CSV, osquery log parsers |
| **Sigma Detection** | ✅ | pySigma + custom DuckDB backend; MITRE ATT&CK tagging |
| **Graph Correlation** | ✅ | Entity extraction → SQLite graph; Union-Find clustering |
| **Investigation Engine** | ✅ | Timeline, attack chain, causality, case management |
| **AI Analyst Copilot** | ✅ | RAG over events; Ollama qwen3:14b; SSE streaming |
| **Attack Graph UI** | ✅ | Cytoscape.js fCoSE, risk-scored nodes, Dijkstra attack paths |
| **Svelte 5 Dashboard** | ✅ | Detections, Events, Graph, Investigation, Query, Assets views |
| **SOAR Playbooks** | ✅ | 5 NIST IR playbooks; analyst-gated step execution; SSE stream; audit trail |
| **Reporting & Compliance** | ✅ | WeasyPrint PDF reports, MITRE ATT&CK heatmap, D3 KPI trends, NIST CSF 2.0 + TheHive ZIP export |
| **Threat Hunting** | Beta | Structured hunt queries, hypothesis tracking |
| **Bearer Token Auth** | ✅ | Startup validator rejects weak tokens; MFA-gated legacy admin path |
| **Citation Verification** | ✅ | LLM responses verified against retrieved context; `citation_verified` in payload |
| **Prompt Injection Scrubbing** | ✅ | Base64/Unicode NFC normalization + regex scrub on all free-text fields; evidence in system turn |
| **LLM Audit Logging** | ✅ | Full prompt text (64KB cap) + SHA-256 hash logged to `llm_calls` table |
| **TOTP Replay Protection** | ✅ | SQLite `system_kv` persistent across restarts; L1 in-process cache |
| **Security Headers** | ✅ | CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy via Caddy |
| **Meta-Detection Rules** | ✅ | Sigma rules monitoring auth burst, LLM token spikes, ChromaDB deletions |
| **Identity & RBAC** | ✅ | Operator table, bcrypt hashed passwords, role-based route guards |
| **Firewall Integration** | ✅ | IPFire syslog + Suricata EVE JSON ingestion; heartbeat monitoring |
| **osquery Telemetry** | Optional | Live host telemetry via `OSQUERY_ENABLED=True` |
| **CI Pipeline** | ✅ | ruff + pytest (≥70% coverage) + pip-audit + gitleaks + frontend build/svelte-check |

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12 | `uv python install 3.12` |
| uv | 0.10+ | `winget install astral-sh.uv` |
| Node.js | 18+ LTS | `winget install OpenJS.NodeJS.LTS` |
| Docker Desktop | Latest | [docs.docker.com/desktop](https://docs.docker.com/desktop/install/windows-install/) |
| PowerShell 7 | 7.0+ | `winget install Microsoft.PowerShell` |
| Ollama | 0.13+ | `winget install Ollama.Ollama` |

> PowerShell 7 (`pwsh`) is required for the management scripts. Windows ships with PS 5.1 by default.

---

## Quick Start

```powershell
# Clone and set up Python environment
git clone https://github.com/Reston2024/local-ai-soc.git AI-SOC-Brain
cd AI-SOC-Brain
uv venv --python 3.12
.venv\Scripts\activate
uv sync

# Pull required Ollama models
ollama pull qwen3:14b
ollama pull mxbai-embed-large

# Configure auth token
echo AUTH_TOKEN=changeme > .env

# Start backend (FastAPI on :8000)
uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# In a second terminal — start frontend dev server
cd dashboard
npm install
npm run dev
```

Open **http://localhost:5173/app/** in your browser.

For HTTPS via Caddy:

```powershell
scripts\start.cmd        # starts FastAPI + Caddy Docker container
```

Then open **https://localhost**.

---

## Ingesting Events

```powershell
# Ingest sample NDJSON events
curl -X POST http://localhost:8000/api/ingest/file `
  -H "Authorization: Bearer changeme" `
  -F "file=@fixtures/ndjson/sample_events.ndjson"

# Run Sigma detection
curl -X POST http://localhost:8000/api/detect/run `
  -H "Authorization: Bearer changeme"
```

---

## Development

```powershell
# Run all unit tests
uv run pytest tests/unit/ -q

# Run with coverage report
uv run pytest tests/unit/ --cov=backend --cov=ingestion --cov-report=term-missing

# Frontend dev server (hot reload)
cd dashboard && npm run dev

# Frontend production build
cd dashboard && npm run build

# Lint Python
uv run ruff check .
```

**Current test baseline:** 575 passing, 56 new playbook tests (631 collected); 56 playbook unit tests isolated-pass

---

## Architecture

```
                      Browser (http://localhost:5173 dev | https://localhost prod)
                                        │
                         ┌──────────────▼──────────────┐
                         │    Caddy (Docker) — prod      │  TLS termination
                         └──────────────┬──────────────┘
                                        │ :8000
                         ┌──────────────▼──────────────────────────┐
                         │           FastAPI Backend                 │
                         │                                          │
                         │  /health  /api/events  /api/ingest       │
                         │  /api/detect  /api/graph  /api/query     │
                         │  /api/investigate  /api/investigations   │
                         │  /api/score  /api/metrics  /api/export   │
                         │  /api/playbooks  /api/playbook-runs      │
                         └──┬──────────┬─────────────┬─────────────┘
                            │          │             │
                      HTTP REST    embed/SQL        SQL
                            │          │             │
               ┌────────────▼┐  ┌─────▼────┐  ┌────▼──────────┐
               │  Ollama      │  │  Chroma  │  │  DuckDB  │SQLite│
               │  :11434      │  │  embed   │  │  events  │graph │
               │  qwen3:14b   │  │  persist │  │  columnar│edges │
               └─────────────┘  └──────────┘  └────────────────┘
```

**Storage:**
- `data/events.duckdb` — normalized events (columnar analytics)
- `data/chroma/` — vector embeddings (BM25 + semantic search)
- `data/graph.sqlite3` — entity nodes, edges, detections, cases (WAL mode)

**Dashboard (Svelte 5):** `dashboard/src/views/`
- `DetectionsView` — Sigma alerts with ATT&CK tactic/technique
- `InvestigationView` — timeline, attack chain, AI chat copilot, "Run Playbook" entry point
- `GraphView` — Cytoscape.js fCoSE attack graph, Dijkstra path highlighting
- `PlaybooksView` — SOAR playbook library browser + step-execution UI with audit trail
- `EventsView`, `AssetsView`, `QueryView`, `IngestView`
- `HuntingView`, `ReportsView`, `ThreatIntelView` (Beta)

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Status check (unauthenticated) |
| GET/POST | `/api/events` | List / ingest single event |
| POST | `/api/ingest` | Batch ingest with source label |
| POST | `/api/ingest/file` | Ingest from uploaded file |
| GET | `/api/ingest/{job_id}` | Ingest job status |
| POST | `/api/query` | Semantic + DuckDB hybrid search |
| POST | `/api/detect/run` | Run Sigma rules against stored events |
| GET | `/api/detect` | List detection results |
| GET | `/api/graph/global` | Global entity graph (all entities + edges) |
| GET | `/api/graph/{investigation_id}` | Subgraph for investigation |
| GET | `/api/graph/entity/{entity_id}` | Entity neighbours |
| GET | `/api/graph/traverse/{entity_id}` | BFS traversal from entity |
| GET | `/api/export` | Export events as NDJSON |
| POST | `/api/investigate` | Unified investigation pipeline |
| GET/POST | `/api/investigations` | List / create investigations |
| GET | `/api/investigations/{id}/timeline` | Investigation timeline |
| POST | `/api/investigations/{id}/chat` | AI copilot chat (SSE) |
| POST | `/api/score` | Entity risk scoring |
| GET | `/api/top-threats` | Top-scored threat entities |
| POST | `/api/explain` | LLM explanation for detection/event |
| GET | `/api/metrics` | SOC metrics and KPIs |
| GET | `/api/correlate` | Event correlation clusters |
| GET | `/api/causality` | Process causality graph |
| GET | `/api/telemetry` | osquery live telemetry status |
| GET | `/api/playbooks` | List all playbooks |
| POST | `/api/playbooks` | Create a playbook |
| GET | `/api/playbooks/{id}` | Get playbook by ID |
| GET | `/api/playbooks/{id}/runs` | List run history for playbook |
| POST | `/api/playbooks/{id}/run/{inv_id}` | Start a playbook run against an investigation |
| PATCH | `/api/playbook-runs/{run_id}/step/{n}` | Analyst confirms step N (human-in-the-loop gate) |
| PATCH | `/api/playbook-runs/{run_id}/cancel` | Cancel an in-progress run |
| GET | `/api/playbook-runs/{run_id}` | Fetch run state |
| GET | `/api/playbook-runs/{run_id}/stream` | SSE stream of step-completion events |

**Auth:** All `/api/*` routes require `Authorization: Bearer <token>`. Set `AUTH_TOKEN=<value>` in `.env` (default: `changeme` — always on).

---

## Project Structure

```
backend/           FastAPI app (Python 3.12)
  api/             Route handlers (including playbooks.py)
  causality/       Process causality engine + ATT&CK mapping
  core/            Config, auth, logging, dependencies
  data/            Built-in playbook definitions (builtin_playbooks.py)
  intelligence/    Risk scorer, anomaly rules, LLM explanation
  investigation/   Case manager, timeline, hunt engine
  models/          Pydantic models (NormalizedEvent, Playbook, PlaybookRun, …)
  services/        Ollama HTTP client (with LLM audit logging)
  stores/          DuckDB, Chroma, SQLite store wrappers
ingestion/         Event parsing + normalization pipeline
  parsers/         EVTX, JSON/NDJSON, CSV, osquery parsers
detections/        Sigma rule matching (pySigma + DuckDB backend)
correlation/       Event clustering (Union-Find + temporal window)
graph/             Graph schema constants and BFS traversal
prompts/           LLM prompt templates
dashboard/         Svelte 5 SPA (npm)
  src/views/       DetectionsView, InvestigationView, GraphView, ...
  src/lib/api.ts   Typed API client
tests/             pytest suite (unit/, integration/, security/, sigma_smoke/)
config/caddy/      Caddyfile
scripts/           PowerShell management scripts
fixtures/          Test fixture data (NDJSON, EVTX samples)
```

---

## Management Scripts

| Script | Description |
|--------|-------------|
| `scripts\start.cmd` | Start FastAPI backend + Caddy Docker container |
| `scripts\stop.cmd` | Stop all services |
| `scripts\status.cmd` | Show service health |
| `scripts\configure-acls.ps1` | Harden `data/` directory permissions |
| `scripts\configure-firewall.ps1` | Block Ollama port 11434 from non-localhost |

---

## Phase History

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Foundation — FastAPI, DuckDB, SQLite, Chroma | ✅ |
| 2 | Ingestion — EVTX/JSON/CSV/osquery parsers, entity extraction | ✅ |
| 3 | Detection + RAG — Sigma/pySigma, DuckDB backend, Chroma search | ✅ |
| 4 | Graph + Correlation — SQLite graph, Union-Find clustering | ✅ |
| 5 | Dashboard — Svelte 5 SPA, Cytoscape.js | ✅ |
| 6 | Hardening — Caddy HTTPS, type safety, test coverage | ✅ |
| 7 | Investigation Engine — RAG, timeline, attack chain | ✅ |
| 8 | SOC Brain — Full investigation platform, APT fixture, osquery | ✅ |
| 9 | Intelligence — Risk scorer, anomaly rules, LLM explanations | ✅ |
| 10 | Compliance Hardening — Auth, audit logging, CI, ACLs | ✅ |
| 11 | Cleanup — backend/src/ deleted, coverage ≥70% | ✅ |
| 12 | API Hardening + Parser Coverage | ✅ |
| 13 | SOC Metrics, KPIs, HuggingFace model upgrade | ✅ |
| 14 | LLMOps Evaluation, Investigation AI Copilot | ✅ |
| 15 | Attack Graph UI — Cytoscape.js fCoSE, attack paths, MITRE overlay | ✅ |
| 16 | Security Hardening — end-to-end auth, citation verification, injection scrubbing, frontend CI | ✅ |
| 17 | SOAR & Playbook Engine — 5 NIST IR playbooks, analyst-gated execution, SSE, UI | ✅ |
| 18 | Reporting & Compliance — PDF reports, MITRE ATT&CK heatmap, KPI trends, NIST CSF 2.0 + TheHive export | ✅ |
| 19 | Identity & RBAC — operator table, bcrypt, role-based guards, session management | ✅ |
| 20 | Schema Standardisation — ECS/OCSF alignment, NormalizedEvent schema migration, DuckDB column renames | ✅ |
| 21 | Evidence Provenance — SHA-256 content hashing, provenance chain, chain-of-custody audit | ✅ |
| 22 | AI Lifecycle Hardening — model drift detection, grounding scores, confidence tracking, LLMOps audit | ✅ |
| 23 | Firewall Telemetry Ingestion — IPFire syslog + Suricata EVE JSON parsers, collector, heartbeat, `GET /api/firewall/status` | ✅ |
| 23.5 | Security Hardening (expert panel) — all 18 findings addressed: token validation, MFA, injection scrubbing, CSP, DuckDB external access disabled, ChromaDB ACL, Ollama digest pinning, CI gate | ✅ |

---

## Documentation

| File | Description |
|------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, data architecture, decision rationale |
| [DECISION_LOG.md](DECISION_LOG.md) | Architecture Decision Records (ADR-001 – ADR-021) |
| [THREAT_MODEL.md](THREAT_MODEL.md) | Threat model for local desktop deployment |
| [REPRODUCIBILITY_RECEIPT.md](REPRODUCIBILITY_RECEIPT.md) | Pinned dependency versions |
| [docs/manifest.md](docs/manifest.md) | Full file tree and API reference |

---

## License

Private — single-analyst internal tooling.
