---
status: awaiting_human_verify
trigger: "system-end-to-end-verification — confirm AI-SOC-Brain is genuinely functional, not stubs/theater"
created: 2026-04-11T00:00:00Z
updated: 2026-04-11T20:00:00Z
---

## Current Focus

hypothesis: All three bugs confirmed and fixed — awaiting server restart + user verification
test: 1063 unit tests pass, imports clean, server needs restart to load new code
expecting: After restart: explain endpoint works, telemetry shows live event counts, assets populate from Malcolm ingest
next_action: User restarts server, confirms explain and telemetry work

## Symptoms

expected: Every feature works end-to-end — API returns real DB data, ingestion works, AI calls Ollama, frontend displays real data
actual: Unknown — no specific failure reported, user wants proof of real functionality vs theater
errors: None reported
reproduction: N/A — verification investigation
started: Post Phase 37 completion — pre-milestone confidence check

## Eliminated

- hypothesis: "Frontend is using hardcoded/mock data"
  evidence: All views import from api.ts; grep found zero MOCK_DATA/hardcoded array patterns; views call real api.* functions
  timestamp: 2026-04-11T18:30:00Z

- hypothesis: "Ollama AI pipeline is a stub/mock"
  evidence: OllamaClient is a real httpx client; /api/query/ask returns genuine LLM analysis with cited event IDs; /api/triage/latest contains real multi-paragraph LLM output with detection reasoning; /health shows ollama: ok
  timestamp: 2026-04-11T18:45:00Z

- hypothesis: "DuckDB has no real data (all stubs)"
  evidence: 18,019 real Suricata EVE events from Malcolm/OpenSearch, Apr 8 ingestion. Full raw_event JSON with network packets, flow IDs, JA3 hashes, MITRE ATT&CK mappings
  timestamp: 2026-04-11T18:30:00Z

- hypothesis: "Malcolm collector is broken/fake"
  evidence: Collector is RUNNING (logs show HTTP 200 from OpenSearch every 30s), cursor advances, heartbeat updates. Data gap Apr 9-11 is because SPAN port arrived Apr 10 and Zeek confirmation pending — OpenSearch has no new Suricata alert data in that window
  timestamp: 2026-04-11T19:00:00Z

## Evidence

- timestamp: 2026-04-11T17:40:00Z
  checked: GET /health
  found: status=healthy, ollama=ok, duckdb=ok, chroma=ok (soc_evidence collection), sqlite=ok (20 entities, 18 edges, 6 detections)
  implication: All four storage backends are alive and connected

- timestamp: 2026-04-11T17:42:00Z
  checked: GET /api/events
  found: 18,019 real Suricata EVE events from Apr 8, 2026. Full structured JSON with IPs, ports, JA3 hashes, MITRE techniques, rule names
  implication: DuckDB has genuine ingest data from real network traffic (Malcolm/OpenSearch)

- timestamp: 2026-04-11T17:44:00Z
  checked: GET /api/detect
  found: 6 real detections: "Multiple Failed Authentication Attempts" (T1110), "PowerShell Download Cradle", "Suspicious Outbound Network Connection", etc.
  implication: Sigma rule matching ran and produced real detections

- timestamp: 2026-04-11T17:45:00Z
  checked: GET /api/triage/latest
  found: Multi-paragraph real LLM analysis naming specific detections, reasoning about C2 activity, PowerShell attack chains
  implication: Triage AI pipeline is real — Ollama (llama3:latest) called and responded

- timestamp: 2026-04-11T17:46:00Z
  checked: GET /api/intel/feeds
  found: feodo (6 IOCs, synced today), cisa_kev (1,559 CVEs, synced today), threatfox (138 IOCs, synced today)
  implication: Threat intel feed sync is real and running hourly

- timestamp: 2026-04-11T17:48:00Z
  checked: GET /api/analytics/mitre-coverage, GET /api/top-threats, GET /api/attack/coverage
  found: 14 MITRE tactics with per-technique coverage, top threats from real detections, tactic coverage across 80+ techniques
  implication: Analytics layer queries real detection data

- timestamp: 2026-04-11T17:50:00Z
  checked: GET /api/metrics/kpis
  found: MTTD=5796 min (real, based on detection timing), alert_volume_24h=0 (broken — see bug below)
  implication: KPI computation is real but 24h window query broken in telemetry

- timestamp: 2026-04-11T17:52:00Z
  checked: Ollama model check
  found: Installed models = ['llama3:latest', 'mxbai-embed-large:latest']. Config default OLLAMA_MODEL="qwen3:14b" (overridden by .env to llama3:latest). model-status endpoint shows active=llama3:latest
  implication: Model wiring correct everywhere except two code paths below

- timestamp: 2026-04-11T17:55:00Z
  checked: GET /api/explain with real detection_id
  found: ERROR "model 'qwen3:14b' not found" — explain_engine.py had hardcoded default model="qwen3:14b"
  implication: BUG #1 — /api/explain always fails silently. FIXED.

- timestamp: 2026-04-11T17:57:00Z
  checked: GET /api/telemetry/summary
  found: Returns all zeros. Logs show "DuckDB telemetry query failed: Scalar Function with name datetime does not exist!" — SQLite datetime() syntax used in DuckDB query
  implication: BUG #2 — telemetry summary always returns 0s. FIXED.

- timestamp: 2026-04-11T18:05:00Z
  checked: GET /api/assets, SQLite assets table
  found: 0 assets. Malcolm loader initialized in main.py WITHOUT asset_store parameter
  implication: BUG #3 — assets never populate even though 18k events ingested. FIXED.

- timestamp: 2026-04-11T18:10:00Z
  checked: causality_routes.py
  found: Uses os.getenv("OLLAMA_MODEL", "qwen3:14b") — bypasses pydantic Settings. OLLAMA_MODEL not in OS environment, so always defaults to qwen3:14b
  implication: BUG #4 — causality/investigate/summary endpoint always fails LLM call. FIXED.

- timestamp: 2026-04-11T18:20:00Z
  checked: All frontend views
  found: Zero hardcoded data patterns. All views import from api.ts and call api.* functions (api.events.list, api.assets.list, api.detections.list, api.intel.feeds, etc.)
  implication: Frontend is genuinely wired to real backend

- timestamp: 2026-04-11T18:25:00Z
  checked: Malcolm collector run loop and OpenSearch HTTP logs
  found: Collector polls every 30s, gets HTTP 200 from OpenSearch syslog index. No new Suricata alert data after Apr 8. Cursor at 2026-04-11T19:29:44Z. Data gap is expected — SPAN port active but Zeek data flowing into different indexes pending Phase 36 confirmation
  implication: Collector pipeline is real and working; data gap explained by hardware context (Phase 36)

- timestamp: 2026-04-11T18:35:00Z
  checked: /api/query/ask with real question
  found: Returns genuine LLM analysis citing specific event IDs, reasoning about alert event types
  implication: Semantic search + Chroma RAG + Ollama generation all wired end-to-end

- timestamp: 2026-04-11T20:00:00Z
  checked: 1063 unit tests after all 4 fixes
  found: All pass (1063 pass, 2 skip, 9 xfail, 7 xpass)
  implication: Fixes are correct and didn't break existing tests

## Resolution

root_cause: System is genuinely functional, not theater. Four real bugs found and fixed:
  1. explain_engine.py: generate_explanation() had hardcoded default model="qwen3:14b" — changed to None (falls through to ollama_client.model = llama3:latest)
  2. telemetry.py: DuckDB queries used SQLite datetime('now', '-1 day') syntax — changed to DuckDB NOW() - INTERVAL 1 DAY
  3. main.py: Malcolm IngestionLoader created without asset_store= parameter — assets never populated from 18k ingested events
  4. causality_routes.py: os.getenv("OLLAMA_MODEL", "qwen3:14b") bypasses pydantic Settings — changed to settings.OLLAMA_MODEL

fix: |
  - backend/intelligence/explain_engine.py: model default changed from "qwen3:14b" to None
  - backend/api/telemetry.py: DuckDB datetime() → NOW() - INTERVAL 1 DAY
  - backend/main.py: _MCLoader creation now passes asset_store=asset_store
  - backend/causality/causality_routes.py: os.getenv replaced with settings.OLLAMA_MODEL

verification: 1063 unit tests pass. Server restart needed to apply fixes at runtime.

files_changed:
  - backend/intelligence/explain_engine.py
  - backend/api/telemetry.py
  - backend/main.py
  - backend/causality/causality_routes.py
