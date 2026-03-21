# STATE.md
# AI-SOC-Brain — Live Project State

**Last updated:** 2026-03-17
**Current phase:** Phase 8 — COMPLETE
**Overall status:** SOC BRAIN OPERATIONAL

---

## Active Work

**Phase 8 v2: SOC Investigation Platform — COMPLETE**

All capabilities operational as of 2026-03-17:
- Ingest APT scenario events via `POST /api/ingest/events` ✓
- Run Sigma detection via `POST /api/detect/run` ✓
- Full investigation graph via `POST /api/investigate` ✓
- Cytoscape dashboard at `/app/` ✓
- 66 unit tests passing, 4 integration tests xpassed ✓

## Phase Completion

| Phase | Status | Notes |
|-------|--------|-------|
| Planning + Research | ✅ DONE | .planning/ artifacts committed |
| Phase 1: Foundation | ✅ DONE | FastAPI app, DuckDB, SQLite, Chroma |
| Phase 2: Ingestion | ✅ DONE | EVTX/JSON/CSV/osquery parsers, entity extraction |
| Phase 3: Detection + RAG | ✅ DONE | Sigma/pySigma, DuckDB backend |
| Phase 4: Graph + Correlation | ✅ DONE | SQLite graph, Union-Find clustering |
| Phase 5: Dashboard | ✅ DONE | Svelte 5 SPA, Cytoscape.js |
| Phase 6: Hardening | ✅ DONE | Caddy HTTPS, type safety, test coverage |
| Phase 7: Investigation Engine | ✅ DONE | RAG, timeline, attack chain |
| Phase 8 v1: Infra + Telemetry | ✅ DONE | OsqueryCollector, smoke test, 4 test fixes |
| Phase 8 v2: SOC Brain | ✅ DONE | Full investigation platform, APT fixture |

## Verified Capabilities (2026-03-17)

| Capability | Status | Evidence |
|------------|--------|---------|
| Ingest 15-event APT scenario | ✅ | 15 parsed, 21 edges created |
| Sigma detection fires on APT events | ✅ | 3 detections (PowerShell, C2, Auth) |
| Graph: 53 nodes, 42 edges from one investigation | ✅ | winword->ps->svchosts->cmd chain visible |
| Attack chain reconstruction (7-hop) | ✅ | T1059/T1105/T1071/T1547/T1003/T1047 |
| MITRE ATT&CK techniques: 11 identified | ✅ | All major APT phases covered |
| Dashboard Cytoscape render | ✅ | npm run build passes, /app/ served |
| OsqueryCollector live telemetry | ✅ | OSQUERY_ENABLED=True activates |
| Unit tests | ✅ | 66 passed, 4 xpassed |

## Environment

| Item | Value | Status |
|------|-------|--------|
| OS | Windows 11 Pro 26H2 | ✅ |
| CPU | Intel Core Ultra 9 285K 24c | ✅ |
| RAM | 96 GB | ✅ |
| GPU | RTX 5080 16GB VRAM CUDA 13.1 | ✅ |
| Disk free | 3.4 TB | ✅ |
| Python 3.12 | via uv | ✅ |
| uv | 0.10.6+ | ✅ |
| Node | v24.14.0 | ✅ |
| Docker + Compose | 29.2.1 + 5.0.2 | ✅ |
| Ollama | Installed + running | ✅ |
| osquery | Optional (OSQUERY_ENABLED=False default) | ✅ |

## Blockers

None. All P8-T01 through P8-T12 requirements addressed.

## Key Entry Points

```powershell
# Start backend
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Load APT scenario
uv run python scripts/load-scenario.py

# Run smoke test (Phase 8)
pwsh -File scripts\smoke-test-phase8.ps1

# Run tests
uv run pytest tests/unit/ -q --tb=short
```

## Session Log

- 2026-03-15: Project initialized, research complete, planning done
- 2026-03-15: Root-level docs written, directory tree created
- 2026-03-15: Phase 1 execution started
- 2026-03-15 to 2026-03-16: Phases 1-7 completed (foundation through investigation engine)
- 2026-03-17: Phase 8 v1 — OsqueryCollector, telemetry API, smoke test, 4 integration test fixes
- 2026-03-17: Phase 8 v2 — Full SOC investigation platform built and verified end-to-end
  - APT scenario "Operation NightCrawler" (15 events, 3 hosts, C2 185.220.101.45)
  - Attack chain: winword.exe -> powershell.exe -> svchosts.exe -> lateral movement via WMI
  - POST /api/investigate returns 53-node graph, 42 edges, 11 MITRE techniques
  - Dashboard upgraded: InvestigationPanel (Cytoscape) + DetectionsView (Run Detection + Investigate)
