---
created: 2026-03-15T18:08:48.668Z
title: Build Wave 1 AI SOC Foundation Branch
area: planning
files:
  - C:\Users\Admin\Downloads\gsd_execution_prompt_ai_soc_wave1_foundation.md
---

## Problem

A structured Wave 1 execution prompt exists at `C:\Users\Admin\Downloads\gsd_execution_prompt_ai_soc_wave1_foundation.md` that specifies building a reviewable AI SOC Brain foundation on a dedicated branch `feature/ai-soc-wave1-foundation`.

The prompt requires a specific directory layout that diverges from the current repo structure:

```
ai-soc-brain/
├─ backend/src/api|parsers|graph|detection|fixtures|tests/
├─ frontend/src/components/graph|timeline|panels/ + src/routes/
├─ infra/docker-compose.yml + Caddyfile + vector/vector.yaml + scripts/
├─ fixtures/ndjson|evtx|syslog/
└─ docs/decision-log.md + manifest.md + reproducibility.md
```

Current repo has a working FastAPI backend + Svelte 5 dashboard but uses a different layout (e.g. `dashboard/` not `frontend/`, `config/caddy/` not `infra/`). The prompt demands:

- **Backend**: 7 required endpoints (`/health`, `/events`, `/timeline`, `/graph`, `/alerts`, `POST /events`, `POST /fixtures/load`) with specific response shapes including graph `nodes`/`edges` format
- **Frontend**: `ThreatGraph.svelte`, `EventTimeline.svelte`, `EvidencePanel.svelte`, `+page.svelte` with live API wiring (not mock data)
- **Infra**: Docker Compose with `backend + frontend + opensearch + vector + caddy` services; Vector config reading NDJSON fixtures and forwarding to backend
- **Fixtures**: `fixtures/ndjson/sample_events.ndjson` with DNS query, outbound connection, and suspicious DNS events
- **Docs**: `decision-log.md`, `manifest.md`, `reproducibility.md` seeded with Wave 1 decisions
- **Smoke tests**: `backend/src/tests/smoke_test.py` covering all 6 endpoints
- **Release gates**: structure gate, API gate, UI gate, tooling gate, test gate

Work must stay isolated to `feature/ai-soc-wave1-foundation` — do not merge to main.

## Solution

1. Create branch `feature/ai-soc-wave1-foundation` from current `master`
2. Scaffold the exact directory tree, merging safely with existing files
3. Implement/adapt backend routes to match required response shapes (especially `/timeline`, `/graph` nodes+edges format, `/alerts`, `POST /fixtures/load`)
4. Build frontend at `frontend/` with the 4 required Svelte components wired to live API
5. Create `infra/docker-compose.yml` with all 5 services including OpenSearch and Vector
6. Create `infra/vector/vector.yaml` to read fixtures and POST to backend
7. Write `fixtures/ndjson/sample_events.ndjson` with required event types
8. Seed all 3 docs files
9. Run smoke tests and all 5 release gates
10. Output the required end summary (9 sections as specified in prompt)

Execute via `/gsd:execute-phase` or direct execution against the prompt file.
