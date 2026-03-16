# Project Manifest

Generated: 2026-03-15
Branch: feature/ai-soc-phase2-ingestion
(includes Wave 1 foundation)

## File Tree

```
ai-soc-brain/
├── backend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── main.py          ← FastAPI app factory
│   │   │   ├── models.py        ← Pydantic models + IngestSource enum (Phase 2)
│   │   │   └── routes.py        ← 9 route handlers incl. /ingest, /ingest/syslog, /events/stream
│   │   ├── parsers/
│   │   │   ├── __init__.py
│   │   │   └── normalizer.py    ← Raw → NormalizedEvent + enrichment pipeline call
│   │   ├── graph/
│   │   │   ├── __init__.py
│   │   │   └── builder.py       ← Events → Cytoscape nodes/edges
│   │   ├── detection/
│   │   │   ├── __init__.py
│   │   │   └── rules.py         ← 4 detection rules (dns, ip, port, syslog severity)
│   │   ├── ingestion/            ← Phase 2 NEW
│   │   │   ├── __init__.py
│   │   │   ├── enricher.py      ← 5-stage enrichment pipeline
│   │   │   ├── syslog_parser.py ← RFC3164 / RFC5424 / CEF parser
│   │   │   └── opensearch_sink.py ← SCAFFOLD: index when OPENSEARCH_URL set
│   │   ├── fixtures/
│   │   │   ├── __init__.py
│   │   │   └── loader.py        ← NDJSON fixture loader
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── smoke_test.py    ← 7 Wave 1 smoke tests
│   │       └── test_phase2.py   ← 25 Phase 2 tests (parser, enricher, rules, routes)
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── graph/
│   │   │   │   └── ThreatGraph.svelte    ← Cytoscape.js graph (polls /graph every 10s)
│   │   │   ├── timeline/
│   │   │   │   └── EventTimeline.svelte  ← D3 timeline (polls /timeline every 10s)
│   │   │   └── panels/
│   │   │       └── EvidencePanel.svelte  ← Selected node details
│   │   ├── lib/
│   │   │   └── api.ts           ← Typed fetch client (Phase 2: +postIngest, +ingestSyslog, +openEventStream)
│   │   ├── routes/
│   │   │   └── +page.svelte     ← Main route stub
│   │   ├── App.svelte           ← Root layout (Phase 2: alert polling, live indicators, source badges)
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
│   ├── docker-compose.yml       ← 5 services + syslog ports 514/udp, 6514/tcp on vector
│   ├── Caddyfile                ← localhost HTTPS proxy
│   ├── vector/
│   │   └── vector.yaml          ← Phase 2: syslog_udp + syslog_tcp sources, /ingest + /ingest/syslog sinks
│   └── scripts/
│       ├── start.ps1
│       ├── stop.ps1
│       └── status.ps1
│
├── fixtures/
│   ├── ndjson/
│   │   └── sample_events.ndjson ← 6 realistic firewall events
│   ├── evtx/                    ← placeholder (Phase 3)
│   └── syslog/                  ← placeholder (Phase 3)
│
└── docs/
    ├── decision-log.md          ← Wave 1 + Phase 2 decisions
    ├── manifest.md              ← this file
    └── reproducibility.md       ← build + verify commands
```

## Counts

| Area | Files |
|------|-------|
| Backend (src/) | 17 (+4 Phase 2 ingestion module) |
| Frontend | 12 (api.ts + App.svelte updated) |
| Infra | 6 (vector.yaml + compose updated) |
| Fixtures | 3 (+ 2 placeholders) |
| Tests | 2 (smoke_test.py + test_phase2.py) |
| Docs | 3 |
| **Total** | **43** |

## Active Endpoints (Phase 2)

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Status + active ingestion sources |
| GET | /events | All stored events |
| POST | /events | Ingest single event (Wave 1, preserved) |
| GET | /timeline | Events sorted ascending by timestamp |
| GET | /graph | Cytoscape-compatible nodes + edges |
| GET | /alerts | Triggered detection alerts |
| POST | /fixtures/load | Load NDJSON fixture file |
| POST | /ingest | **Phase 2** — batch event ingest with source label |
| POST | /ingest/syslog | **Phase 2** — raw RFC3164/RFC5424/CEF syslog line |
| GET | /events/stream | **Phase 2** — SSE live event stream |

## Scaffold Items (labeled, not fully live)

| Item | Location | Activation |
|------|----------|------------|
| OpenSearch indexing | `backend/src/ingestion/opensearch_sink.py` | Set `OPENSEARCH_URL` env var |
| OpenSearch Vector sink | `infra/vector/vector.yaml` (commented) | Uncomment + set `OPENSEARCH_URL` |
| Firewall log source | `infra/vector/vector.yaml` (commented) | Uncomment + set log path |
| Firewall parse transform | `infra/vector/vector.yaml` (commented) | Add vendor-specific parsing |
