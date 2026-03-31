# AI-SOC-Brain — Live Project State

**Last updated:** 2026-03-31
**Current phase:** Phase 15 — COMPLETE
**Overall status:** SOC BRAIN OPERATIONAL

---

## Active Work

No active phases. Phase 15 complete as of 2026-03-29.

Next: Phase 16 (Threat Hunting), Phase 17 (SOAR), Phase 18 (Reporting) — planned but not started.

---

## Phase Completion

| Phase | Description | Status | Date |
|-------|-------------|--------|------|
| Planning + Research | .planning/ artifacts committed | ✅ DONE | 2026-03-15 |
| Phase 1: Foundation | FastAPI app, DuckDB, SQLite, Chroma | ✅ DONE | 2026-03-15 |
| Phase 2: Ingestion | EVTX/JSON/CSV/osquery parsers, entity extraction | ✅ DONE | 2026-03-15 |
| Phase 3: Detection + RAG | Sigma/pySigma, DuckDB backend, Chroma RAG | ✅ DONE | 2026-03-15 |
| Phase 4: Graph + Correlation | SQLite graph, Union-Find clustering | ✅ DONE | 2026-03-16 |
| Phase 5: Dashboard | Svelte 5 SPA initial build | ✅ DONE | 2026-03-16 |
| Phase 6: Hardening | Caddy HTTPS, type safety, test coverage | ✅ DONE | 2026-03-16 |
| Phase 7: Investigation Engine | RAG, timeline, attack chain | ✅ DONE | 2026-03-16 |
| Phase 8: SOC Brain | Full investigation platform, APT fixture, osquery | ✅ DONE | 2026-03-17 |
| Phase 9: Intelligence | Risk scorer, anomaly rules, LLM explanations | ✅ DONE | 2026-03-22 |
| Phase 10: Compliance Hardening | Bearer auth, audit logging, CI, ACLs | ✅ DONE | 2026-03-24 |
| Phase 11: Cleanup + Coverage | backend/src/ deleted, coverage ≥70% | ✅ DONE | 2026-03-26 |
| Phase 12: API Hardening | Parser coverage, API security hardening | ✅ DONE | 2026-03-27 |
| Phase 13: SOC Metrics + KPIs | Metrics API, dashboard KPI widgets, HF model upgrade | ✅ DONE | 2026-03-28 |
| Phase 14: LLMOps + AI Copilot | Evaluation harness, investigation chat copilot | ✅ DONE | 2026-03-28 |
| Phase 15: Attack Graph UI | Cytoscape.js fCoSE, risk scoring, attack paths, MITRE overlay | ✅ DONE | 2026-03-29 |

---

## Verified Capabilities (2026-03-29)

| Capability | Status | Evidence |
|------------|--------|---------|
| Event ingestion (EVTX, JSON, CSV, osquery) | ✅ | All parsers passing unit tests |
| Sigma detection with ATT&CK tagging | ✅ | pySigma + DuckDB backend; 3+ rules active |
| Entity graph: nodes + edges from events | ✅ | SQLite graph store; entity_extractor |
| Union-Find event correlation | ✅ | temporal window clustering; correlation tests pass |
| Investigation timeline + attack chain | ✅ | timeline_builder, attack_chain_builder |
| Bearer token auth on all /api/* routes | ✅ | verify_token dependency; security tests pass |
| AI analyst copilot (RAG + Ollama) | ✅ | SSE streaming chat on /api/investigations/{id}/chat |
| Entity risk scoring | ✅ | risk_scorer.py; /api/score; /api/top-threats |
| Causality engine (process parent/child) | ✅ | causality_routes, entity_resolver |
| SOC metrics + KPIs dashboard | ✅ | /api/metrics; MetricsView |
| Attack Graph UI (Cytoscape.js fCoSE) | ✅ | GraphView.svelte 458 lines; 12/12 truths verified |
| Two-click Dijkstra attack path highlighting | ✅ | Browser UAT confirmed (phase 15) |
| Graph ↔ Investigation bidirectional navigation | ✅ | App.svelte state lifting; confirmed in UAT |
| Unit tests passing | ✅ | 589 passed, 16 xpassed, 1 skipped (606 collected) |
| CI pipeline | ✅ | .github/workflows/ci.yml: lint + test + audit + scan |
| osquery live telemetry (optional) | ✅ | OSQUERY_ENABLED=True activates collector |

---

## Environment

| Item | Value | Status |
|------|-------|--------|
| OS | Windows 11 Pro 26H2 | ✅ |
| CPU | Intel Core Ultra 9 285K 24c | ✅ |
| RAM | 96 GB | ✅ |
| GPU | RTX 5080 16GB VRAM CUDA 13.1 | ✅ |
| Python | 3.12 via uv | ✅ |
| uv | 0.10.6+ | ✅ |
| Node | v24.14.0 | ✅ |
| Docker + Compose | 29.2.1 + 5.0.2 | ✅ |
| Ollama | Installed + running | ✅ |
| osquery | Optional (OSQUERY_ENABLED=False default) | ✅ |

---

## Blockers

None.

---

## Key Entry Points

```powershell
# Start backend
uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# Start frontend dev server (second terminal)
cd dashboard && npm run dev
# Open http://localhost:5173/app/

# Ingest sample events
curl -X POST http://localhost:8000/api/ingest/file \
  -H "Authorization: Bearer changeme" \
  -F "file=@fixtures/ndjson/sample_events.ndjson"

# Run Sigma detection
curl -X POST http://localhost:8000/api/detect/run \
  -H "Authorization: Bearer changeme"

# Run tests
uv run pytest tests/unit/ -q --tb=short
```

---

## Session Log

- 2026-03-15: Project initialized, research complete, planning done
- 2026-03-15: Root-level docs written, directory tree created
- 2026-03-15: Phase 1 execution started
- 2026-03-15 to 2026-03-16: Phases 1-7 completed (foundation through investigation engine)
- 2026-03-17: Phase 8 — Full SOC investigation platform, APT scenario "Operation NightCrawler"
- 2026-03-22: Phase 9 — Intelligence layer: risk scorer, anomaly rules, LLM explanations
- 2026-03-24: Phase 10 — Compliance hardening: auth, CI, audit logging, ACL/firewall scripts
- 2026-03-26: Phase 11 — Cleanup: backend/src/ deleted, coverage enforced ≥70%
- 2026-03-27: Phase 12 — API hardening and parser coverage improvements
- 2026-03-28: Phase 13 — SOC metrics/KPIs, HuggingFace embedding model upgrade
- 2026-03-28: Phase 14 — LLMOps evaluation harness, investigation AI copilot chat
- 2026-03-29: Phase 15 — Attack Graph UI: Cytoscape.js fCoSE, risk scoring, Dijkstra attack paths,
               MITRE ATT&CK tactic overlay, bidirectional Graph↔Investigation navigation
- 2026-03-30: Phase 15 UAT complete (5/5 tests pass); entity panel CSS bug fixed; all bugs committed
- 2026-03-31: Repo docs updated to reflect full Phase 1-15 progress
