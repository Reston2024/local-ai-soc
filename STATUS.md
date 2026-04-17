# STATUS.md — Single Source of Truth

**Last Updated:** 2026-04-16
**Supersedes:** STATE.md (archived — do not update)

---

## Milestone Summary

| Milestone | Phases | Completed | Date | Gate |
|-----------|--------|-----------|------|------|
| **v1.0** | 1–30 | ✅ COMPLETE | 2026-04-08 | 59/59 requirements · 8/8 E2E flows · 938+ tests |
| **v1.1** | 31–46 | ✅ COMPLETE | 2026-04-13 | Malcolm, hunting, IOC feeds, asset inventory, agentic investigation |
| **v1.2 (in progress)** | 47–53+ | 🔄 Phases 47–52 complete | 2026-04-16 | Hayabusa, Chainsaw, MISP, SpiderFoot, TheHive live |

---

## Key Metrics (as of 2026-04-16)

| Metric | Value |
|--------|-------|
| Tests passing | 938+ (unit + security + sigma_smoke) |
| Coverage gate | ≥70% overall · ≥80% security-critical modules |
| Phases complete | 52 of 53+ planned |
| CI checks | ruff · pytest · pip-audit · gitleaks · svelte-check |
| Commit | `3c11c16` (2026-04-16) |

---

## Phase Completion Log

### v1.0 — Foundation (Phases 1–30)

| Phase | Name | Status | Date |
|-------|------|--------|------|
| 1 | Foundation — FastAPI, DuckDB, SQLite, Chroma | ✅ | 2026-03-15 |
| 2 | Ingestion — EVTX/JSON/CSV/osquery parsers | ✅ | 2026-03-15 |
| 3 | Detection + RAG — Sigma/pySigma, Chroma RAG | ✅ | 2026-03-15 |
| 4 | Graph + Correlation — SQLite graph, Union-Find | ✅ | 2026-03-16 |
| 5 | Dashboard — Svelte 5 SPA | ✅ | 2026-03-16 |
| 6 | Hardening — Caddy HTTPS, type safety, coverage | ✅ | 2026-03-16 |
| 7 | Investigation Engine — RAG, timeline, attack chain | ✅ | 2026-03-16 |
| 8 | SOC Brain — full investigation platform, APT fixture | ✅ | 2026-03-17 |
| 9 | Intelligence — risk scorer, anomaly rules, LLM explanations | ✅ | 2026-03-22 |
| 10 | Compliance Hardening — Bearer auth, audit logging, CI, ACLs | ✅ | 2026-03-24 |
| 11 | Cleanup + Coverage — backend/src/ deleted, coverage ≥70% | ✅ | 2026-03-26 |
| 12 | API Hardening — parser coverage, API security | ✅ | 2026-03-27 |
| 13 | SOC Metrics + KPIs — metrics API, dashboard KPI widgets | ✅ | 2026-03-28 |
| 14 | LLMOps + AI Copilot — evaluation harness, investigation chat | ✅ | 2026-03-28 |
| 15 | Attack Graph UI — Cytoscape.js fCoSE, risk scoring, MITRE overlay | ✅ | 2026-03-29 |
| 16 | Security Hardening — auth, citation verification, injection scrubbing | ✅ | 2026-03-31 |
| 17 | SOAR & Playbook Engine — 5 NIST IR playbooks, SSE, PlaybooksView | ✅ | 2026-03-31 |
| 18 | Reporting & Compliance — PDF, MITRE heatmap, NIST CSF 2.0 | ✅ | 2026-04-01 |
| 19 | Identity & RBAC — operator table, bcrypt, role-based guards | ✅ | 2026-04-01 |
| 20 | Schema Standardisation — ECS/OCSF alignment, NormalizedEvent | ✅ | 2026-04-02 |
| 21 | Evidence Provenance — SHA-256 hashing, chain-of-custody audit | ✅ | 2026-04-02 |
| 22 | AI Lifecycle Hardening — model drift, grounding scores, LLMOps | ✅ | 2026-04-03 |
| 23 | Firewall Telemetry — IPFire syslog + Suricata EVE parsers | ✅ | 2026-04-03 |
| 23.5 | Security Hardening — 18 expert panel findings closed | ✅ | 2026-04-05 |
| 24 | Recommendation Artifact Store — approve/dispatch pipeline | ✅ | 2026-04-05 |
| 25 | Receipt Ingestion — firewall receipts → case state propagation | ✅ | 2026-04-06 |
| 26 | Graph Schema Versioning — firewall_zone, network_segment entities | ✅ | 2026-04-06 |
| 27 | Malcolm NSM Integration — MalcolmCollector, OpenSearch polling | ✅ | 2026-04-07 |
| 28 | Dashboard Integration Fixes — RAG SSE, event search, routing | ✅ | 2026-04-08 |
| 29 | Missing Phase Verifiers — VERIFICATION.md for all phases | ✅ | 2026-04-08 |
| 30 | Final Security + Sign-Off — Sigma guard, Caddy digest pin | ✅ | 2026-04-08 |

**v1.0 Milestone Audit:** 59/59 requirements · 8/8 E2E flows · 0 blocking gaps · REPRODUCIBILITY_RECEIPT.md VERIFIED

### v1.1 — Live Telemetry & Intelligence (Phases 31–46)

| Phase | Name | Status | Date |
|-------|------|--------|------|
| 31 | Malcolm Real Telemetry — EVE JSON expanded, all types | ✅ | 2026-04-09 |
| 32 | Real Threat Hunting — HuntingView API, live DuckDB queries | ✅ | 2026-04-09 |
| 33 | Real Threat Intelligence — IOC feed ingestion, enrichment | ✅ | 2026-04-09 |
| 34 | Asset Inventory — asset discovery, inventory API + view | ✅ | 2026-04-10 |
| 35 | SOC Completeness — auto-triage, coverage gaps, SOC score | ✅ | 2026-04-10 |
| 36 | Zeek Full Telemetry — SPAN port active (Netgear GS308E), Zeek live | ✅ | 2026-04-10 |
| 37 | Analyst Report Templates — structured incident report PDF | ✅ | 2026-04-11 |
| 38 | CISA Playbook Content — 15 CISA advisory playbooks | ✅ | 2026-04-11 |
| 39 | MITRE CAR Analytics — CAR analytic rule integration | ✅ | 2026-04-12 |
| 40 | Atomic Red Team Validation — ART test execution + coverage | ✅ | 2026-04-12 |
| 41 | Threat Map Overhaul — geographic IP map, live pins | ✅ | 2026-04-12 |
| 42 | Streaming Behavioral Profiles — per-entity baseline, anomaly score | ✅ | 2026-04-12 |
| 43 | Sigma v2 Correlation Rules — chain detection, YAML-driven | ✅ | 2026-04-13 |
| 44 | Analyst Feedback Loop — River ML, feedback API, verdict KPIs | ✅ | 2026-04-13 |
| 45 | Agentic Investigation — smolagents + Ollama, 7-tool pipeline | ✅ | 2026-04-13 |
| 46 | 30-Playbook Library Expansion — CISA/NIST expanded set | ✅ | 2026-04-13 |

### v1.2 — Extended Integrations (Phases 47–53+)

| Phase | Name | Status | Date |
|-------|------|--------|------|
| 47 | SPA Routing Hardened — Caddy + backend catch-all | ✅ | 2026-04-14 |
| 48 | Hayabusa EVTX Threat Hunting — binary integration, scan API | ✅ | 2026-04-14 |
| 49 | Chainsaw Windows Event Log Analysis — rule-based EVTX hunting | ✅ | 2026-04-15 |
| 50 | MISP Threat Intelligence — Docker on GMKtec, 4,568 IOCs synced | ✅ | 2026-04-16 |
| 51 | SpiderFoot OSINT Investigation — Docker, API, InvestigationView | ✅ | 2026-04-16 |
| 52 | TheHive Case Management — Cortex, MISP connector, auto-cases | ✅ | 2026-04-16 |
| 53 | Network Privacy Monitoring | 🔲 Not yet planned | — |

---

## Active Integrations

| Integration | Status | Host | Notes |
|-------------|--------|------|-------|
| Malcolm NSM (OpenSearch) | ✅ Live | 192.168.1.22:9200 | Suricata EVE + syslog indexed |
| MISP Threat Intel | ✅ Live | 192.168.1.22:8443 | 4,568 IOCs, 6h sync |
| TheHive Case Mgmt | ✅ Live | 192.168.1.22:9000 | Auto-cases from detections |
| Cortex (Analysers) | ✅ Live | 192.168.1.22:9001 | MISP connector wired |
| SpiderFoot OSINT | ✅ Live | 192.168.1.22:9002 | OSINT scan API |
| Zeek (SPAN) | ✅ Live | GMKtec/Malcolm | Netgear GS308E port 1→5 |
| Ollama LLM | ✅ Live | 127.0.0.1:11434 | qwen3:14b · CPU (GPU migration pending) |
| ChromaDB RAG | ✅ Live | 192.168.1.22:8200 | Remote vector store |

---

## Infrastructure

| Node | Hardware | Role |
|------|----------|------|
| Desktop | Core Ultra 9 285K · 96GB · RTX 5080 · 3.4TB | SOC Brain (primary) |
| GMKtec N100 | N150 · 16GB DDR5 | Malcolm NSM · MISP · TheHive · Cortex · SpiderFoot |
| IPFire | 192.168.1.1 | Firewall/router — syslog → Malcolm |
| Netgear GS308E | Port 1→5 SPAN | Network tap for Zeek |

---

## Compliance Alignment

| Framework | Coverage | Evidence |
|-----------|----------|---------|
| NIST SP 800-53 Rev 5.2.0 | Baseline elements (CM-2, CM-6, SI-4, AU-2, AU-12, CA-2, CA-7, SA-24) | See NIST_CONTROL_MATRIX.md (planned) |
| NIST CSF 2.0 | GV · DE · RS functions | Sigma rules · SOAR playbooks · reporting |
| MITRE ATT&CK | Tactic tagging throughout | detections/sigma/ + Phase 15 graph UI |
| AI RMF (Measure 1.1–4.2) | Trustworthiness measures | THREAT_MODEL.md · LLM audit log · confidence badges |
| NIST IR 800-61r2 | Incident lifecycle | SOAR playbooks · Phase 17 · enforcement gate |

---

## Tech Debt (Non-Blocking)

| Item | Impact | Notes |
|------|--------|-------|
| Ollama on CPU | Performance | RTX 5080 available — GPU migration not yet started |
| Malcolm auto-start on reboot | Ops | Requires manual `python3 scripts/start` after LUKS decrypt |
| Cortex analysers not configured | Feature gap | AbuseIPDB/VT/MaxMind keys needed via Cortex UI |
| Dead code in api.ts / ThreatGraph.svelte | Maintenance | Cleanup deferred to Phase 53+ |
| `STATE.md` — stale | Documentation | Superseded by this file; do not update |

---

## Reproducibility

See **REPRODUCIBILITY_RECEIPT.md** (VERIFIED 2026-04-09, updated 2026-04-16).

All claims are backed by CI, unit tests, and evidence artifacts in `.planning/phases/*/`.  
This file is the single source of truth — all other status documents defer to it.
