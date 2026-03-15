# Project State

**Project:** AI-SOC-Brain
**Last updated:** 2026-03-15
**Current phase:** Phase 1 (in progress)
**Overall status:** Executing

---

## Active Phase

**Phase 1: Foundation**
Status: IN PROGRESS
Next action: Continue remaining Phase 1 plans

## Progress

| Phase | Status | Completed |
|-------|--------|-----------|
| Phase 1: Foundation | TODO | — |
| Phase 2: Ingestion Pipeline | TODO | — |
| Phase 3: Detection + RAG | TODO | — |
| Phase 4: Graph + Correlation | TODO | — |
| Phase 5: Dashboard | TODO | — |
| Phase 6: Hardening + Integration | TODO | — |

## Key Decisions Made

| Decision | Rationale |
|----------|-----------|
| Python 3.12 (not 3.14) | PyO3/PEP649 compatibility with pySigma, chromadb, pyevtx-rs |
| Ollama native Windows | Direct CUDA access to RTX 5080; no Docker GPU passthrough |
| DuckDB embedded single-writer | Zero-server columnar analytics; write queue pattern prevents deadlocks |
| Chroma embedded PersistentClient | No external server; pin version; native client (not LangChain wrapper) |
| SQLite for graph edges | Lightweight, battle-tested, WAL mode; graph as derived view not primary store |
| Caddy (only Docker container) | Auto-TLS for localhost HTTPS; ~40MB; simple Caddyfile |
| Svelte 5 SPA | 39% faster than React 19, 2.5x smaller bundles; Cytoscape.js + D3.js direct API |
| Flat tsconfig.json for dashboard | Avoids @tsconfig/svelte extend brittleness; allowImportingTsExtensions + noEmit for Vite builds |
| Cytoscape COSE layout | Built-in, no extra plugin; adequate for subgraphs under ~200 nodes |
| SSE collected to string in Phase 1 | Real-time token streaming deferred to Phase 3 when query API is finalized |
| LangGraph (not LangChain chains) | LangChain chains deprecated; LangGraph 1.0 stable; human-in-the-loop built in |
| qwen3:14b as primary model | Best fit for 16GB VRAM at Q8; strong reasoning + cybersecurity analysis |
| mxbai-embed-large | MTEB retrieval 64.68 vs nomic 53.01; 1024 dimensions |
| Reject Wazuh | 8+ vCPU Java fleet SIEM; no unique value for single desktop |
| Defer Velociraptor | Fleet management tool; osquery covers single-host telemetry need |
| Defer Open WebUI | Optional companion chat UI; custom dashboard is primary |

## Critical Pitfalls to Watch

1. **RTX 5080 CUDA** — Validate GPU layers > 0 on Day 1 before writing any code
2. **Sigma silent failures** — Custom DuckDB backend + field mapping + smoke test suite
3. **DuckDB concurrency** — Single-writer + read-only pool established in Phase 1
4. **Python 3.14 compat** — Use 3.12; validate all deps before starting
5. **Chroma stability** — Pin version; build export/import on Day 1

## Environment

| Item | Value |
|------|-------|
| OS | Windows 11 Pro 26H2 (Build 26200.8037) |
| CPU | Intel Core Ultra 9 285K, 24 cores, 3.7 GHz |
| RAM | 96 GB |
| GPU | NVIDIA RTX 5080, 16 GB VRAM, CUDA 13.1 |
| Disk free | 3.4 TB (C:) |
| Python | 3.14.3 installed; will use 3.12 via uv for project |
| uv | 0.10.6 |
| Node | v24.14.0 |
| Docker | 29.2.1 + Compose v5.0.2 |
| Ollama | NOT YET INSTALLED |
| osquery | NOT YET INSTALLED |

## Repository State

| Artifact | Status |
|---------|--------|
| `.planning/config.json` | ✓ committed |
| `.planning/PROJECT.md` | ✓ committed |
| `.planning/research/` (5 files) | ✓ committed |
| `.planning/REQUIREMENTS.md` | ✓ committed |
| `.planning/ROADMAP.md` | ✓ committed |
| `.planning/STATE.md` | this file |
| `backend/` | ✓ committed (Phase 1 plans 01-03) |
| `dashboard/` | ✓ committed (Phase 1 plan 04) |
| `ingestion/` | ✓ committed (Phase 1 plans 01-05) |
| `detections/` | ✓ committed (Phase 1 plans 01-05) |
| `fixtures/` | ✓ committed (Phase 1 plan 05) |
| `tests/` | ✓ committed (Phase 1 plan 05) |
| Root docs (ARCHITECTURE.md, etc.) | ✓ committed |

## Session Notes

- 2026-03-15: Project initialized. Environment inspected. Config locked. Research complete (4 agents). Synthesis complete. Requirements and roadmap written. Ready for Phase 1.
- Python 3.14 is system Python but project will use 3.12 via uv venv.
- RTX 5080 confirmed 16GB VRAM, CUDA 13.1, Driver 591.74. Should be compatible with Ollama 0.13+.
- No existing Docker containers or images — clean slate.
- Ollama not yet installed — Phase 1 task 1.
- 2026-03-15: Phase 1 plan 04 complete. Svelte 5 dashboard SPA built. 10 tasks, 10 commits, 15 files, build verified. Stopped at: 01-04-PLAN.md complete.
- 2026-03-15: Phase 1 plan 05 complete. Fixtures and test suite created. 30-event NDJSON attack scenario, 3 Sigma rules, osquery snapshot, 89 unit/smoke tests all passing. Stopped at: 01-05-PLAN.md complete.
