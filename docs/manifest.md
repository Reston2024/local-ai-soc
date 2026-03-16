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

---

## Phase 5: Suricata EVE + Threat Scoring + ATT&CK Tagging — 2026-03-16

Branch: `feature/ai-soc-phase3-detection`

### New Files

| File | Type | Purpose |
|------|------|---------|
| `backend/src/parsers/suricata_parser.py` | Python | Suricata EVE JSON parser. `parse_eve_line()` handles alert/flow/dns/http/tls event types. Maps `dest_ip` → `dst_ip` (Snort convention trap). Inverts severity scale (1=critical, 4=low). |
| `backend/src/detection/threat_scorer.py` | Python | Additive threat score model 0–100. `score_alert()` combines suricata severity (40/30/20/10) + sigma hit (+20) + recurrence (+10) + graph connectivity (+10). Capped at 100. |
| `backend/src/detection/attack_mapper.py` | Python | Static ATT&CK tactic/technique mapper. `map_attack_tags()` returns list of dicts (`[{"tactic":..., "technique":..., "technique_id":...}]`) or `[]` for unmapped events. |
| `fixtures/suricata_eve_sample.ndjson` | Fixture | 5 EVE JSON lines (one per event type: alert, dns, flow, http, tls). Used in integration tests and reproducibility validation. |
| `backend/src/tests/test_phase5.py` | Test | 18 tests covering P5-T1 through P5-T18: parser field mapping, severity inversion, model fields, scorer components, mapper paths, route integration. |
| `infra/suricata/suricata.yaml` | Config | Scaffold Suricata config (commented). Documents Windows Docker blocker (requires `--net=host` + Linux kernel caps unavailable under WSL2). |
| `infra/suricata/rules/local.rules` | Rules | Empty placeholder for local Suricata rules. Ready for production Linux deployment. |

### Modified Files

| File | Change |
|------|--------|
| `backend/src/api/models.py` | Added `IngestSource.suricata` enum value; added `Alert.threat_score` (`int = 0`) and `Alert.attack_tags` (`list[dict] = []`). |
| `backend/src/api/routes.py` | Added Phase 5 scoring block in `_store_event()` with deferred imports; added `rule_suricata_alert` detection rule; added `GET /threats` endpoint; `POST /events` reads `source` from payload. |
| `infra/vector/vector.yaml` | Added `suricata_eve` file source + `normalise_suricata` VRL transform + `backend_suricata` HTTP sink as commented scaffold. |
| `infra/docker-compose.yml` | Added `jasonish/suricata` service as commented scaffold with Windows blocker note. |
| `frontend/src/lib/api.ts` | Extended `AlertItem` interface with `threat_score: number` and `attack_tags: AttackTag[]`; added `getThreats()` function for `GET /threats`. |
| `frontend/src/components/panels/EvidencePanel.svelte` | Added threat score badge (color-coded by severity) and ATT&CK tag pills displaying tactic + technique_id. |

### Phase 5 Endpoint Added

| Method | Path | Description |
|--------|------|-------------|
| GET | /threats | Returns alerts filtered/sorted by threat_score > 0, descending |

### Phase 5 Scaffold Items

| Item | Location | Activation |
|------|----------|------------|
| Suricata EVE Vector source | `infra/vector/vector.yaml` (commented) | Uncomment + configure EVE log path |
| Suricata container | `infra/docker-compose.yml` (commented) | Linux Docker host with `net_admin`/`net_raw` caps required |
