# AI-SOC-Brain — Live Project State

**Last updated:** 2026-04-16
**Current milestone:** v1.0 COMPLETE — v1.1 COMPLETE (Phases 31-46) — Phase 50 COMPLETE
**Overall status:** SOC BRAIN OPERATIONAL

---

## Active Work

**v1.2 — Next phases queued**

| Phase | Description | Status |
|-------|-------------|--------|
| 51 | Outbound Alerting — email/Slack/PagerDuty for critical detections | Planned |
| 52 | Firewalla Gold Integration — bridge device REST API ingestion | Blocked — hardware in transit |
| 53 | IPFire SSH Health Stats — live router/firewall stats in Overview | Planned |
| 54 | LLM Fine-tuning — Foundation-Sec-8B on Phase 44 verdict data (HuggingFace) | Planned |
| 55 | GMKtec MISP Backup — mysqldump + Valkey backup strategy over SSH | Planned |

---

## Phase Completion — v1.1 + v1.2 (Phases 31-50)

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
| Phase 16: Security Hardening | End-to-end auth, citation verification, injection scrubbing, frontend CI | ✅ DONE | 2026-03-31 |
| Phase 17: SOAR & Playbook Engine | 5 NIST IR playbooks, analyst-gated execution, SSE, PlaybooksView UI | ✅ DONE | 2026-03-31 |
| Phase 18: Reporting & Compliance | PDF reports, MITRE ATT&CK heatmap, KPI trends, NIST CSF 2.0, TheHive export | ✅ DONE | 2026-04-01 |
| Phase 19: Identity & RBAC | Operator table, bcrypt, role-based guards, session management | ✅ DONE | 2026-04-01 |
| Phase 20: Schema Standardisation | ECS/OCSF alignment, NormalizedEvent migration, DuckDB column renames | ✅ DONE | 2026-04-02 |
| Phase 21: Evidence Provenance | SHA-256 content hashing, provenance chain, chain-of-custody audit | ✅ DONE | 2026-04-02 |
| Phase 22: AI Lifecycle Hardening | Model drift detection, grounding scores, confidence tracking, LLMOps audit | ✅ DONE | 2026-04-03 |
| Phase 23: Firewall Telemetry | IPFire syslog + Suricata EVE parsers, collector, heartbeat | ✅ DONE | 2026-04-03 |
| Phase 23.5: Security Hardening | All 18 expert panel findings: token validation, MFA, injection scrubbing, CSP, DuckDB lockdown, ChromaDB ACL, Ollama digest pinning, CI gate | ✅ DONE | 2026-04-05 |
| Phase 24: Recommendation Workflow | AI artifact store; approve/dispatch pipeline; JSON schema validation; dispatch log | ✅ DONE | 2026-04-05 |
| Phase 25: Receipt Ingestion | Firewall execution receipts → case state propagation; audit trail | ✅ DONE | 2026-04-06 |
| Phase 26: Graph Schema Versioning | schema_version in SQLite; firewall_zone + network_segment entity types; migration support | ✅ DONE | 2026-04-06 |
| Phase 27: Malcolm NSM Integration | MalcolmCollector polls OpenSearch; ECS field normalization; 30s poll cycle | ✅ DONE | 2026-04-07 |
| Phase 28: Dashboard Integration Fixes | RAG SSE endpoint, event search shape, ingest status route, SettingsView routing | ✅ DONE | 2026-04-08 |
| Phase 29: Missing Phase Verifiers | VERIFICATION.md for all 30 phases | ✅ DONE | 2026-04-08 |
| Phase 30: Final Security + Sign-Off | Sigma guard, Caddy digest pin, Phase 22 UI sign-off | ✅ DONE | 2026-04-08 |
| Phase 31: Malcolm Real Telemetry | EVE JSON ingestion expanded; Malcolm collector wired to all EVE types | ✅ DONE | 2026-04-09 |
| Phase 32: Real Threat Hunting | HuntingView backend API; live hunt queries against DuckDB | ✅ DONE | 2026-04-09 |
| Phase 33: Real Threat Intelligence | IOC matching, OSINT feed enrichment (Feodo, CISA KEV, ThreatFox) | ✅ DONE | 2026-04-09 |
| Phase 34: Asset Inventory | Auto-derived asset inventory from Malcolm telemetry; AssetsView wired | ✅ DONE | 2026-04-10 |
| Phase 35: Auto AI Triage | Auto AI triage background loop; `/api/triage/run` endpoint | ✅ DONE | 2026-04-10 |
| Phase 36: Zeek Full Telemetry | Netgear GS308E SPAN port (port 1→5) active; Zeek live telemetry flowing | ✅ DONE | 2026-04-10 |
| Phase 37: Report Templates | Analyst report templates, structured case export, evidence archive | ✅ DONE | 2026-04-11 |
| Phase 38: CISA Playbook Library | Expanded CISA playbook library; multi-source playbooks | ✅ DONE | 2026-04-11 |
| Phase 39: CAR Analytics | MITRE CAR descriptions + coverage badges in DetectionsView | ✅ DONE | 2026-04-11 |
| Phase 40: Threat Map | Geolocated attacker IP map; OSINT enrichment via ipinfo.io | ✅ DONE | 2026-04-12 |
| Phase 41: Anomaly Baseline | DuckDB sliding-window statistical baselines; severity heat map | ✅ DONE | 2026-04-12 |
| Phase 42: Behavioral Profiles | River online anomaly scoring; score trend sparklines in AnomalyView | ✅ DONE | 2026-04-12 |
| Phase 43: Sigma v2 Correlations | Port scan, brute force, beaconing, multi-stage chain detection via YAML | ✅ DONE | 2026-04-12 |
| Phase 44: Analyst Feedback Loop | TP/FP verdicts; River online classifier; k-NN similar incidents; feedback KPIs | ✅ DONE | 2026-04-12 |
| Phase 45: Agentic Investigation | Autonomous investigation pipeline; `/api/investigate/auto` | ✅ DONE | 2026-04-13 |
| Phase 46: Playbook Library Expansion | 30 playbooks; multi-source; category filtering | ✅ DONE | 2026-04-13 |
| Phase 47: SPA Routing Hardening | Caddy + backend SPA catch-all; direct URL navigation fixed | ✅ DONE | 2026-04-14 |
| Phase 48: Hayabusa EVTX Hunting | Hayabusa binary integration; MITRE tag extraction; amber chip in DetectionsView; Overview health signal | ✅ DONE | 2026-04-14 |
| Phase 49: Chainsaw EVTX Analysis | Chainsaw Windows event analysis; SQLite dedup; teal chip; health row | ✅ DONE | 2026-04-15 |
| Phase 50: MISP Threat Intel | MISP Docker on GMKtec; PyMISP sync; 4,568 IOCs; MISP panel in ThreatIntelView; purple health row in Overview | ✅ DONE | 2026-04-16 |

---

## Phase Completion — v1.0 (All 30 Phases)

---

## v1.0 Milestone Audit Summary

**Audited:** 2026-04-08  
**Result:** COMPLETE — tech_debt status (no blocking issues)

| Metric | Value |
|--------|-------|
| Phases completed | 30/30 |
| Formal requirements (FR/NFR/SR) | 59/59 satisfied |
| E2E integration flows | 8/8 complete |
| Tests passing | 938+ |
| Blocking gaps | 0 |

**Tech debt (non-blocking):**
- Dead code: `getGraph()`, `getGraphCorrelate()` in api.ts + ThreatGraph.svelte (unreachable)
- P28-T05: detect endpoint pagination mismatch (page/page_size vs limit/offset), default path works
- Phase 11 VERIFICATION.md stale (gap was resolved in Phase 30)
- 21 phases with partial Nyquist validation (test-first adopted from Phase 23.5)
- Phase 22/30: confidence badge + citation tag UI — human_needed (requires active AI session)

Full audit: `.planning/v1.0-v1.0-MILESTONE-AUDIT.md`

---

## Verified Capabilities (2026-04-08)

| Capability | Status | Evidence |
|------------|--------|---------|
| Event ingestion (EVTX, JSON, CSV, osquery) | ✅ | All parsers passing unit tests |
| Sigma detection with ATT&CK tagging | ✅ | pySigma + DuckDB backend; rules active |
| Entity graph: nodes + edges from events | ✅ | SQLite graph store; entity_extractor |
| Union-Find event correlation | ✅ | temporal window clustering; tests pass |
| Investigation timeline + attack chain | ✅ | timeline_builder, attack_chain_builder |
| Bearer token auth on all /api/* routes | ✅ | verify_token dependency; 32+ char enforcement |
| AI analyst copilot (RAG + Ollama) — reactive | ✅ | SSE streaming; QueryView + InvestigationView |
| Investigation chat copilot | ✅ | SSE streaming per investigation |
| Entity risk scoring | ✅ | risk_scorer.py; /api/score; /api/top-threats |
| Attack Graph UI (Cytoscape.js fCoSE) | ✅ | GraphView.svelte; Dijkstra paths |
| SOAR playbook engine (5 NIST IR playbooks) | ✅ | analyst-gated; no auto-advance |
| PDF reports + MITRE heatmap | ✅ | WeasyPrint; TheHive ZIP export |
| Identity & RBAC (operator table) | ✅ | bcrypt; SettingsView wired in Phase 28 |
| Citation verification | ✅ | verify_citations(); citation_verified in payloads |
| Prompt injection scrubbing | ✅ | normalizer.py; system/user turn separation |
| LLM audit logging | ✅ | logs/llm_audit.jsonl; all Ollama calls logged |
| DuckDB external access disabled | ✅ | enable_external_access=false on all connections |
| Caddy supply-chain pinned | ✅ | sha256 digest in docker-compose.yml (Phase 30) |
| Ollama model digest verification | ✅ | verify_model_digest() on startup |
| Recommendation workflow | ✅ | approve/dispatch/receipt chain; JSON schema |
| Evidence provenance chain | ✅ | SHA-256 receipt chain; chain-of-custody |
| Malcolm NSM integration | ✅ (partial) | Collecting syslog + alerts. EVE expansion in Phase 31. |
| Sigma guard (Sigma rules test on startup) | ✅ | Phase 30 |
| RAG SSE streaming (QueryView) | ✅ | INT-01 fixed in Phase 28 |
| Event search endpoint (EventsView) | ✅ | INT-02 fixed in Phase 28 |
| Ingest status route (IngestView) | ✅ | INT-03 fixed in Phase 28 |
| SettingsView → /api/operators wired | ✅ | INT-04 fixed in Phase 28 |
| CI pipeline | ✅ | lint + test + audit + scan + frontend build |
| **HuntingView (backend API)** | ❌ | Phase 32 |
| **ThreatIntelView (IOC matching)** | ❌ | Phase 33 |
| **Asset Inventory (auto-discovery)** | ❌ | Phase 34 |
| **Auto AI triage loop** | ❌ | Phase 35 |
| **Zeek full telemetry** | ❌ | Phase 36 — blocked on hardware |

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
| Ollama | 0.18.2 + running | ✅ |
| supportTAK-server | Ubuntu (GMKtec N150) — 192.168.1.22 | ✅ |
| Malcolm NSM | 17 containers (Ubuntu) | Running — full telemetry (Zeek + Suricata + syslog) |
| osquery | Optional (OSQUERY_ENABLED=False default) | ✅ |
| Netgear GS308E | 8-port managed switch — SPAN port 1→5 active | ✅ |
| MISP | Docker on GMKtec — 192.168.1.22:8443 | Running — 4,568 IOCs synced |
| Backup drive | F: (1.82TB) — robocopy incremental backup daily 02:00 | ✅ |
| Firewalla Gold | Bridge device — REST API integration planned (Phase 52) | In transit |

---

## Blockers

| Blocker | Phase | Status |
|---------|-------|--------|
| ~~No managed switch with SPAN port~~ | ~~Phase 36 (Zeek)~~ | ✅ RESOLVED — Netgear GS308E arrived 2026-04-10, SPAN port 1→5 active |
| Firewalla Gold not yet arrived | Phase 52 | Ordered — hardware in transit |

---

## Key Entry Points

```powershell
# Start backend
uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# Start frontend dev server (second terminal)
cd dashboard && npm run dev
# Open http://localhost:5173/app/

# Ingest sample events
curl -X POST http://localhost:8000/api/ingest/file `
  -H "Authorization: Bearer <your-token>" `
  -F "file=@fixtures/ndjson/sample_events.ndjson"

# Run Sigma detection
curl -X POST http://localhost:8000/api/detect/run `
  -H "Authorization: Bearer <your-token>"

# Run tests
uv run pytest tests/unit/ -q --tb=short
```

---

## Session Log

- 2026-03-15: Project initialized, research complete, planning done
- 2026-03-15 to 2026-03-16: Phases 1-7 completed (foundation through investigation engine)
- 2026-03-17: Phase 8 — Full SOC investigation platform, APT scenario "Operation NightCrawler"
- 2026-03-22: Phase 9 — Intelligence layer: risk scorer, anomaly rules, LLM explanations
- 2026-03-24: Phase 10 — Compliance hardening: auth, CI, audit logging, ACL/firewall scripts
- 2026-03-26: Phase 11 — Cleanup: backend/src/ deleted, coverage enforced ≥70%
- 2026-03-27: Phase 12 — API hardening and parser coverage improvements
- 2026-03-28: Phase 13 — SOC metrics/KPIs, HuggingFace embedding model upgrade
- 2026-03-28: Phase 14 — LLMOps evaluation harness, investigation AI copilot chat
- 2026-03-29: Phase 15 — Attack Graph UI: Cytoscape.js fCoSE, risk scoring, Dijkstra attack paths, MITRE ATT&CK tactic overlay, bidirectional Graph↔Investigation navigation
- 2026-03-30: Phase 15 UAT complete; entity panel CSS bug fixed
- 2026-03-31: Phase 16 — Security hardening: auth, citation verification, injection scrubbing, LLM audit logging, frontend CI
- 2026-03-31: Phase 17 — SOAR & Playbook Engine: 5 NIST IR playbooks, analyst-gated execution, SSE, PlaybooksView UI
- 2026-04-01: Phase 18 — Reporting & Compliance: PDF, MITRE heatmap, KPI trends, NIST CSF 2.0, TheHive export
- 2026-04-01: Phase 19 — Identity & RBAC: operator table, bcrypt, role-based guards
- 2026-04-02: Phase 20 — Schema Standardisation: ECS/OCSF alignment, NormalizedEvent migration
- 2026-04-02: Phase 21 — Evidence Provenance: SHA-256 chain, chain-of-custody audit
- 2026-04-03: Phase 22 — AI Lifecycle Hardening: model drift detection, LLMOps audit
- 2026-04-03: Phase 23 — Firewall Telemetry: IPFire syslog + Suricata EVE parsers, collector
- 2026-04-05: Phase 23.5 — Security Hardening: 18 expert panel findings fully addressed; 842 tests pass
- 2026-04-05: Phase 24 — Recommendation Artifact Store: approve/dispatch pipeline, JSON schema validation
- 2026-04-06: Phase 25 — Receipt Ingestion: firewall execution receipts → case state propagation
- 2026-04-06: Phase 26 — Graph Schema Versioning: schema_version, firewall_zone, network_segment entities
- 2026-04-07: Phase 27 — Malcolm NSM Integration: MalcolmCollector, OpenSearch polling, ECS normalization
- 2026-04-08: Phase 28 — Dashboard Integration Fixes: all 4 INT gaps closed; human verified
- 2026-04-08: Phase 29 — Missing Phase Verifiers: VERIFICATION.md for all phases
- 2026-04-08: Phase 30 — Final Security + Sign-Off: Sigma guard, Caddy digest pin; 938+ tests pass
- 2026-04-08: v1.0 milestone audit complete — 59/59 requirements, 8/8 E2E flows, 0 blocking gaps
- 2026-04-09: Docs updated to reflect v1.0 complete + v1.1 state
- 2026-04-09 to 2026-04-12: Phases 31-44 completed — Malcolm telemetry, hunting, IOC feeds, asset inventory, auto-triage, anomaly engine, Sigma v2 correlations, analyst feedback loop
- 2026-04-10: Netgear GS308E SPAN switch arrived; Phase 36 (Zeek) unblocked and completed
- 2026-04-13: Phase 45 — Agentic investigation pipeline; Phase 46 — 30-playbook library expansion
- 2026-04-14: Phase 47 — SPA routing hardened (Caddy + backend catch-all); Phase 48 — Hayabusa EVTX threat hunting integration
- 2026-04-15: Phase 49 — Chainsaw Windows event log analysis integrated
- 2026-04-16: Phase 50 — MISP threat intelligence: Docker on GMKtec, 4 iptables/DNS fixes, 4,568 IOCs synced, ThreatIntelView panel, purple health row in Overview
- 2026-04-16: Backup drive F: (1.82TB) arrived; incremental robocopy script with daily scheduled task
- 2026-04-16: Network topology: hostname deduplication, Docker bridge IP filtering, DESKTOP-R5MSQJQ correctly shown at 192.168.1.102
