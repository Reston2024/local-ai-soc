# AI-SOC-Brain

**Local Windows AI Cybersecurity Investigation Platform**

A single-analyst, local-first cybersecurity workstation. All inference, detection, graph correlation, and visualization runs locally — no cloud, no telemetry, no external services.

**Status:** v1.0 complete (Phases 1–30). v1.1 complete (Phases 31–46). v1.2 active — Phase 53 (Privacy Monitoring) complete. See [`governance/release_state.yaml`](governance/release_state.yaml) for canonical state.

---

## Architecture (Two-Box)

```
  supportTAK-server (Ubuntu, GMKtec N150)          Desktop (Windows 11, RTX 5080)
  192.168.1.22                                       SOC Brain
  ┌─────────────────────────────────┐               ┌────────────────────────────────────────────┐
  │  Malcolm NSM (17 containers)    │               │  Caddy (Docker) — TLS termination           │
  │  ├─ OpenSearch  7.4 GB RAM      │    syslog /   │  FastAPI backend — port 8000                │
  │  ├─ Logstash                    │  EVE JSON /   │  ├─ DuckDB (events.duckdb)                  │
  │  ├─ Filebeat                    │  beats ──────▶│  ├─ ChromaDB (vector embeddings)            │
  │  ├─ Arkime (sessions)           │               │  ├─ SQLite (graph.sqlite3)                  │
  │  └─ 13 idle containers *        │               │  └─ Ollama qwen3:14b — GPU 50-80+ tok/s    │
  └─────────────────────────────────┘               │                                            │
                                                     │  Svelte 5 Dashboard — https://localhost     │
  * No SPAN port → pcap-capture, Zeek,              └────────────────────────────────────────────┘
    Strelka, NetBox, Keycloak idle.
    Zeek produces 0 logs.
```

**Ubuntu box is a dumb pipe only.** It collects and indexes raw telemetry. No AI, no inference, no analysis. All intelligence runs on the desktop GPU.

**Malcolm telemetry — honest status (as of 2026-04-09):**
- IPFire syslog → malcolm_beats_syslog_* → 22M+ docs ✓
- Suricata EVE alerts → arkime_sessions3-* → 71K docs ✓ (collecting)
- Suricata EVE TLS / DNS / fileinfo / anomaly → NOT collecting yet (Phase 31 fixes this)
- Zeek logs → 0 docs — no SPAN port, no packet source
- 17 Malcolm containers run but most are idle without PCAP feed (~630MB RAM consumed)

---

## Features

| Capability | Status | Details |
|-----------|--------|---------|
| **Event Ingestion** | Ready | EVTX, JSON/NDJSON, CSV, osquery parsers |
| **Sigma Detection** | Ready | pySigma + custom DuckDB backend; MITRE ATT&CK tagging |
| **Graph Correlation** | Ready | Entity extraction → SQLite graph; Union-Find clustering |
| **Investigation Engine** | Ready | Timeline, attack chain, causality, case management |
| **AI Copilot (RAG Q&A)** | Ready — reactive only | RAG over events; SSE streaming; analyst-initiated only. Auto-triage coming in Phase 35. |
| **Investigation Chat Copilot** | Ready | SSE streaming chat per investigation |
| **Attack Graph UI** | Ready | Cytoscape.js fCoSE, risk-scored nodes, Dijkstra attack paths |
| **Svelte 5 Dashboard** | Ready | 11 views; Detections, Events, Graph, Investigation, Query, Ingest, Assets, Reports, Settings, Operators |
| **SOAR Playbooks** | Ready | 30 built-in IR playbooks (CISA, CERT-SG, AWS, Microsoft DART, GuardSight, community); category + source filtering; analyst-gated step execution; SSE stream; audit trail |
| **Reporting & Compliance** | Ready | WeasyPrint PDF, MITRE ATT&CK heatmap, D3 KPI trends, NIST CSF 2.0, TheHive ZIP export |
| **Bearer Token Auth + TOTP** | Ready | Startup validator rejects weak tokens; MFA-gated legacy admin path |
| **Identity & RBAC** | Ready | Operator table, bcrypt, role-based route guards |
| **Citation Verification** | Ready | LLM responses verified against retrieved context; `citation_verified` in payload |
| **Prompt Injection Scrubbing** | Ready | Base64/Unicode NFC normalization + regex scrub; evidence in system turn |
| **LLM Audit Logging** | Ready | Full prompt text (64KB cap) + SHA-256 hash logged to `llm_calls` table |
| **TOTP Replay Protection** | Ready | SQLite `system_kv` persistent across restarts; L1 in-process cache |
| **Security Headers** | Ready | CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy via Caddy |
| **Meta-Detection Rules** | Ready | Sigma rules monitoring auth burst, LLM token spikes, ChromaDB deletions |
| **Malcolm NSM Integration** | Partial | Collecting syslog + alerts. EVE expansion in Phase 31. Zeek blocked on managed switch hardware. |
| **Recommendation Workflow** | Ready | AI artifact store; approve/dispatch pipeline; JSON schema validation; dispatch log |
| **Evidence Provenance Chain** | Ready | SHA-256 receipt chain; chain-of-custody audit |
| **Graph Schema Versioning** | Ready | `schema_version` in SQLite; firewall_zone + network_segment entity types |
| **Perimeter Entities** | Ready | Firewall zone nodes with colour-coded risk; network segment subnet bubbles |
| **osquery Telemetry** | Optional | Live host telemetry via `OSQUERY_ENABLED=True` |
| **CI Pipeline** | Ready | ruff + pytest (≥70% coverage) + pip-audit + gitleaks + frontend build/svelte-check |
| **Threat Hunting** | Ready | HuntingView with rule-based hunt queries, live event search |
| **Threat Intelligence** | Ready | IOC matching, OSINT enrichment, geolocated Threat Map |
| **Asset Discovery** | Ready | Auto-derived entity inventory from telemetry |
| **Auto AI Triage** | Ready | Background triage loop; POST /api/triage/run |
| **Malcolm Real Telemetry** | Ready | EVE JSON ingestion; Zeek SPAN port active (Phase 36) |
| **Sigma v2 Correlation** | Ready | Port scan, brute force, beaconing, multi-stage chain detection; CORR filter chips |
| **Streaming Behavioral Profiles** | Ready | River-based entity anomaly scoring; score trend sparklines |
| **Analyst Feedback Loop** | Ready | TP/FP verdict buttons; River classifier; Similar Cases via Chroma k-NN; feedback KPIs |

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12 (NOT 3.14) | `uv python install 3.12` |
| uv | 0.10+ | `winget install astral-sh.uv` |
| Node.js | 18+ LTS | `winget install OpenJS.NodeJS.LTS` |
| Docker Desktop | Latest | [docs.docker.com/desktop](https://docs.docker.com/desktop/install/windows-install/) |
| PowerShell 7 | 7.0+ | `winget install Microsoft.PowerShell` |
| Ollama | 0.13+ | `winget install Ollama.Ollama` |

> PowerShell 7 (`pwsh`) is required for the management scripts. Windows ships with PS 5.1 by default.
>
> Python 3.14 is the system default. Do NOT use it — PEP 649 deferred annotations break pySigma, pydantic-core, and pyevtx-rs at runtime. Use 3.12 via uv.

---

## Quick Start

```powershell
# Clone and set up Python environment
git clone https://github.com/Reston2024/local-ai-soc.git AI-SOC-Brain
cd AI-SOC-Brain
uv python install 3.12
uv venv --python 3.12
.venv\Scripts\activate
uv sync

# Pull required Ollama models
ollama pull qwen3:14b
ollama pull mxbai-embed-large

# Configure auth token (must be 32+ chars, or use "dev-only-bypass" locally)
copy config\.env.example .env
# Edit .env: AUTH_TOKEN=<generate with: python -c "import secrets; print(secrets.token_urlsafe(32))">

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
  -H "Authorization: Bearer <your-token>" `
  -F "file=@fixtures/ndjson/sample_events.ndjson"

# Run Sigma detection
curl -X POST http://localhost:8000/api/detect/run `
  -H "Authorization: Bearer <your-token>"
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

**Current test baseline:** 938+ passing tests

---

## Two-Box Infrastructure

### Desktop — SOC Brain (Windows 11, RTX 5080)

Primary compute node. All AI inference, detection, correlation, and analysis run here.

| Service | Runtime | Port |
|---------|---------|------|
| FastAPI / Uvicorn | Native Python 3.12 | :8000 |
| Caddy | Docker (~40MB) | :443 |
| Ollama qwen3:14b | Native Windows | :11434 |
| DuckDB | In-process embedded | — |
| ChromaDB | In-process embedded | — |
| SQLite | In-process embedded | — |

### supportTAK-server — Dumb Pipe (Ubuntu, GMKtec N150, 192.168.1.22)

Network telemetry collection and indexing only. No AI. No inference.

| Service | Purpose | Status |
|---------|---------|--------|
| Malcolm (17 containers) | NSM orchestration | Running |
| OpenSearch | Log indexing (7.4 GB RAM) | Running |
| Logstash | Log processing pipeline | Running |
| Filebeat | Log shipping | Running |
| Arkime | Network session indexing | Running (no PCAP feed) |
| Zeek | Network protocol logs | Running but 0 output — no SPAN port |
| pcap-capture | Packet capture | Idle — no SPAN port |
| Strelka, NetBox, Keycloak, etc. | Various | Idle — no PCAP feed |

---

## Storage

- `data/events.duckdb` — normalized events (columnar analytics)
- `data/chroma/` — vector embeddings (BM25 + semantic search)
- `data/graph.sqlite3` — entity nodes, edges, detections, cases (WAL mode)

---

## Dashboard Views

| View | File | Status |
|------|------|--------|
| Detections | `DetectionsView.svelte` | Ready |
| Investigation | `InvestigationView.svelte` | Ready |
| Attack Graph | `GraphView.svelte` | Ready — Cytoscape.js fCoSE, Dijkstra paths |
| Playbooks | `PlaybooksView.svelte` | Ready — library browser + step execution |
| Events | `EventsView.svelte` | Ready |
| Query (RAG) | `QueryView.svelte` | Ready — SSE streaming |
| Ingest | `IngestView.svelte` | Ready |
| Reports | `ReportsView.svelte` | Ready — PDF, MITRE heatmap, TheHive export |
| Settings / Operators | `SettingsView.svelte` | Ready |
| Assets | `AssetsView.svelte` | Partial — "Discover Assets" disabled (Phase 34) |
| Threat Intel | `ThreatIntelView.svelte` | Stub — fake data, "BETA" badge (Phase 33) |
| Hunting | `HuntingView.svelte` | Stub — all buttons disabled (Phase 32) |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Status check (unauthenticated) |
| GET/POST | `/api/events` | List / ingest single event |
| POST | `/api/events/search` | Search events by field |
| POST | `/api/ingest` | Batch ingest with source label |
| POST | `/api/ingest/file` | Ingest from uploaded file |
| GET | `/api/ingest/status/{job_id}` | Ingest job status |
| POST | `/api/query/ask/stream` | Semantic RAG query — SSE stream |
| POST | `/api/detect/run` | Run Sigma rules against stored events |
| GET | `/api/detect` | List detection results |
| GET | `/api/graph/global` | Global entity graph |
| GET | `/api/graph/{investigation_id}` | Investigation subgraph |
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
| POST | `/api/playbooks/{id}/run/{inv_id}` | Start a playbook run |
| PATCH | `/api/playbook-runs/{run_id}/step/{n}` | Analyst confirms step N |
| PATCH | `/api/playbook-runs/{run_id}/cancel` | Cancel a run |
| GET | `/api/playbook-runs/{run_id}` | Fetch run state |
| GET | `/api/playbook-runs/{run_id}/stream` | SSE stream of step events |
| GET/POST/PATCH | `/api/operators` | Operator CRUD (RBAC) |
| GET/POST | `/api/recommendations` | AI recommendation artifact store |
| POST | `/api/receipts` | Firewall execution receipts |
| GET | `/api/firewall/status` | FirewallCollector heartbeat |

| POST | `/api/feedback` | Submit TP/FP analyst verdict |
| GET | `/api/feedback/similar` | Chroma k-NN similar confirmed incidents |
| GET | `/api/anomaly/score` | Entity behavioral anomaly score |
| GET | `/api/anomaly/trend` | Entity score trend over time |

**Phase 45+:** `/api/investigate/auto` (agentic investigation pipeline)

**Auth:** All `/api/*` routes require `Authorization: Bearer <token>`. `AUTH_TOKEN` must be 32+ chars or `dev-only-bypass` in `.env`.

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
| 18 | Reporting & Compliance — PDF reports, MITRE ATT&CK heatmap, KPI trends, NIST CSF 2.0, TheHive export | ✅ |
| 19 | Identity & RBAC — operator table, bcrypt, role-based guards | ✅ |
| 20 | Schema Standardisation — ECS/OCSF alignment, NormalizedEvent migration | ✅ |
| 21 | Evidence Provenance — SHA-256 content hashing, chain-of-custody audit | ✅ |
| 22 | AI Lifecycle Hardening — model drift detection, grounding scores, LLMOps audit | ✅ |
| 23 | Firewall Telemetry — IPFire syslog + Suricata EVE parsers, collector, heartbeat | ✅ |
| 23.5 | Security Hardening — 18 expert panel findings: token validation, MFA, injection scrubbing, CSP, DuckDB lockdown, ChromaDB ACL, Ollama digest pinning, CI gate | ✅ |
| 24 | Recommendation Artifact Store — AI → approve → dispatch pipeline, JSON schema validation | ✅ |
| 25 | Receipt Ingestion — Firewall execution receipts → case state propagation | ✅ |
| 26 | Graph Schema Versioning — schema_version, firewall_zone, network_segment entities | ✅ |
| 27 | Malcolm NSM Integration — MalcolmCollector → OpenSearch → DuckDB | ✅ |
| 28 | Dashboard Integration Fixes — RAG SSE, event search shape, ingest status, SettingsView routing | ✅ |
| 29 | Missing Phase Verifiers — VERIFICATION.md for all phases | ✅ |
| 30 | Final Security + Sign-Off — Sigma guard, Caddy digest pin, Phase 22 UI | ✅ |
| 31 | Malcolm Real Telemetry + Evidence Archive — EVE JSON ingestion, Malcolm collector | ✅ |
| 32 | Real Threat Hunting — HuntingView backend API, live hunt queries | ✅ |
| 33 | Real Threat Intelligence — IOC matching, OSINT feeds, live enrichment | ✅ |
| 34 | Asset Inventory — auto-derived entity inventory from telemetry | ✅ |
| 35 | SOC Completeness + Auto AI Triage loop — background worker, triage API | ✅ |
| 36 | Zeek Full Telemetry — Netgear GS308E SPAN port, Zeek flow analysis | ✅ |
| 37 | Analyst Report Templates — structured report authoring, case export | ✅ |
| 38 | CISA Playbook Content — expanded playbook library | ✅ |
| 39 | CAR Analytics Integration — MITRE CAR detection enrichment in DetectionsView | ✅ |
| 40 | Threat Map — geolocated OSINT attacker map, IP enrichment | ✅ |
| 41 | Anomaly Baseline Engine — DuckDB sliding-window baselines, severity heat map | ✅ |
| 42 | Streaming Behavioral Profiles — River online anomaly scoring, score trend sparklines | ✅ |
| 43 | Sigma v2 Correlation Rules — port scan, brute force, beaconing, multi-stage chain detection | ✅ |
| 44 | Analyst Feedback Loop — TP/FP verdicts, River classifier, Chroma k-NN similar cases, feedback KPIs | ✅ |
| **45** | **Agentic Investigation** | **Next** |

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

## Documentation

| File | Description |
|------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, two-box architecture, data flow, decisions |
| [DECISION_LOG.md](DECISION_LOG.md) | Architecture Decision Records (ADR-001 through ADR-033) |
| [STATE.md](STATE.md) | Live project state — current phase, decisions, next steps |
| [THREAT_MODEL.md](THREAT_MODEL.md) | Threat model for local desktop deployment |
| [REPRODUCIBILITY_RECEIPT.md](REPRODUCIBILITY_RECEIPT.md) | Pinned dependency versions + infrastructure |
| [docs/manifest.md](docs/manifest.md) | Full file tree and API reference |

---

## License

Private — single-analyst internal tooling.
