# Wave 1 Manifest

Generated: 2026-03-15
Branch: feature/ai-soc-wave1-foundation

## File Tree

```
ai-soc-brain/
├── backend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── main.py          ← FastAPI app factory
│   │   │   ├── models.py        ← Pydantic response models
│   │   │   └── routes.py        ← All 7 route handlers
│   │   ├── parsers/
│   │   │   ├── __init__.py
│   │   │   └── normalizer.py    ← Raw → NormalizedEvent
│   │   ├── graph/
│   │   │   ├── __init__.py
│   │   │   └── builder.py       ← Events → Cytoscape nodes/edges
│   │   ├── detection/
│   │   │   ├── __init__.py
│   │   │   └── rules.py         ← Suspicious DNS + IP alerts
│   │   ├── fixtures/
│   │   │   ├── __init__.py
│   │   │   └── loader.py        ← NDJSON fixture loader
│   │   └── tests/
│   │       ├── __init__.py
│   │       └── smoke_test.py    ← 7 pytest smoke tests
│   ├── requirements.txt / requirements-wave1.txt
│   └── Dockerfile / Dockerfile.wave1
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── graph/
│   │   │   │   └── ThreatGraph.svelte    ← Cytoscape.js graph
│   │   │   ├── timeline/
│   │   │   │   └── EventTimeline.svelte  ← D3 timeline
│   │   │   └── panels/
│   │   │       └── EvidencePanel.svelte  ← Selected node details
│   │   ├── lib/
│   │   │   └── api.ts           ← Typed fetch client
│   │   ├── routes/
│   │   │   └── +page.svelte     ← Main route (Wave 1 spec)
│   │   ├── App.svelte           ← Root layout
│   │   ├── app.css              ← Dark SOC theme
│   │   └── main.ts              ← Entry point
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── svelte.config.js
│   ├── tsconfig.json
│   └── Dockerfile
│
├── infra/
│   ├── docker-compose.yml       ← 5 services: backend+frontend+opensearch+vector+caddy
│   ├── Caddyfile                ← localhost HTTPS proxy
│   ├── vector/
│   │   └── vector.yaml          ← NDJSON → backend /events
│   └── scripts/
│       ├── start.ps1
│       ├── stop.ps1
│       └── status.ps1
│
├── fixtures/
│   ├── ndjson/
│   │   └── sample_events.ndjson ← 6 realistic firewall events
│   ├── evtx/                    ← placeholder (Wave 2)
│   └── syslog/                  ← placeholder (Wave 2)
│
└── docs/
    ├── decision-log.md          ← Wave 1 tech decisions
    ├── manifest.md              ← this file
    └── reproducibility.md       ← build + verify commands
```

## Counts

| Area | Files |
|------|-------|
| Backend (src/) | 13 |
| Frontend | 12 |
| Infra | 6 |
| Fixtures | 3 (+ 2 placeholders) |
| Docs | 3 |
| **Total** | **37** |

## Notable Generated Files

- `backend/src/api/main.py` — FastAPI app with CORS, Wave 1 only
- `backend/src/api/routes.py` — All 7 endpoints with in-memory store
- `frontend/src/components/graph/ThreatGraph.svelte` — Live Cytoscape graph
- `frontend/src/components/timeline/EventTimeline.svelte` — D3 timeline
- `infra/docker-compose.yml` — Full 5-service stack
- `fixtures/ndjson/sample_events.ndjson` — 6 realistic firewall events
