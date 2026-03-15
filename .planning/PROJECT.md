# AI-SOC-Brain

## What This Is

A Windows desktop-only, local-first AI cybersecurity brain that ingests host telemetry and analyst evidence, performs grounded retrieval and correlation, supports analyst Q&A, and provides a visual end-to-end threat trace dashboard. It is a human-in-the-loop investigation and triage system — not an autonomous response engine. Built to be credible to experienced SecOps practitioners: reproducible, modular, testable, explainable, and fast enough for daily use.

## Core Value

An analyst opens one local browser tab, asks a question about a suspicious event, and receives a grounded answer with a visual graph tracing the threat from origin through propagation to conclusion — all without sending data to the cloud.

## Requirements

### Validated

(None yet — ship to validate)

### Active

**A. Local AI / Retrieval**
- [ ] Ollama installed and running locally on Windows (native, not Docker)
- [ ] Local LLM selected and loaded based on RTX 5080 16 GB VRAM profile
- [ ] Local embedding model loaded for retrieval
- [ ] Chroma vector store serving grounded retrieval over evidence and notes
- [ ] FastAPI backend with `/query` endpoint returning cited local evidence
- [ ] Prompt templates: analyst Q&A, triage, threat hunt, incident summary, evidence explanation
- [ ] All LLM responses cite supporting local evidence in the response payload

**B. Telemetry / Evidence Ingestion**
- [ ] EVTX / structured Windows log export parser and normalizer
- [ ] JSON / CSV / NDJSON ingestion pipeline
- [ ] osquery result ingestion (installed and queryable on Windows)
- [ ] Process and network snapshot ingestion
- [ ] Sigma rule ingestion (via sigma-cli / pySigma conversion)
- [ ] Analyst notes and evidence bundle ingestion
- [ ] IOC / hash / URL / domain list ingestion
- [ ] Case metadata ingestion
- [ ] Normalized schema preserving: timestamp, host, user, process, file, network, detection source, ATT&CK mapping, provenance, confidence/severity

**C. Detection / Correlation**
- [ ] Contextual anomaly logic (point, group/collective, contextual — not naive thresholding)
- [ ] Event clustering and relatedness scoring
- [ ] Alert aggregation for related events
- [ ] Sigma rule matching against ingested events
- [ ] ATT&CK technique enrichment where evidence supports it
- [ ] Explainable correlations with evidence pointers (not opaque scores)

**D. Visual Investigation Surface**
- [ ] Local browser-based dashboard (React or Svelte, served via backend)
- [ ] Graph / node-link view with required entity types (host, user, process, file, network, domain/IP, detection, artifact, incident, ATT&CK technique)
- [ ] Timeline view of events
- [ ] Evidence panel with drilldown from finding → raw event
- [ ] Detection panel listing active findings
- [ ] Search / filter / pivot across entities
- [ ] Full trace: origin → propagation → related entities → analyst conclusion

**E. Security / Operations**
- [ ] Localhost HTTPS via Caddy (reverse proxy in Docker)
- [ ] All secrets in .env / config, never hardcoded
- [ ] Startup and shutdown scripts (PowerShell)
- [ ] Smoke tests for each major component
- [ ] Structured logs for backend and ingestion jobs
- [ ] Reproducibility receipt and restore documentation

### Out of Scope

- Autonomous blocking, quarantine, kill-process, or firewall rule changes — human-in-the-loop only; response is a later phase
- Linux collector, network appliance, or broader infrastructure — desktop brain scope only
- Cloud API calls for LLM inference — local-first, Ollama only
- PostgreSQL, Neo4j, Kafka, Elastic — banned unless proven necessary on this desktop
- Wazuh — only if justified; default reject for now
- Mobile or remote access — local desktop only

## Context

**Hardware (confirmed via inspection):**
- CPU: Intel Core Ultra 9 285K, 24 cores, 3.7 GHz
- RAM: 96 GB
- GPU: NVIDIA RTX 5080, 16 GB VRAM, CUDA 13.1
- Disk: 3.4 TB free on C:
- OS: Windows 11 Pro 26H2 (Build 26200.8037)

**Runtime (confirmed):**
- Docker 29.2.1 + Compose v5.0.2 — available, clean slate (no existing containers)
- WSL2 Ubuntu 22.04 — available (stopped)
- Python 3.14.3 + uv 0.10.6
- Node v24.14.0
- Ollama: NOT yet installed — Phase 1 task 1
- osquery: NOT yet installed — Phase 2 dependency
- Local HTTPS: NOT yet running — must be established in Phase 1

**Standards alignment:**
- NIST CSF 2.0: govern / identify / detect / respond structure
- NIST AI RMF 1.0: AI traceability, explainability, governance
- NIST SP 800-61: incident handling workflow concepts
- OWASP ASVS: local web app / API security controls
- MITRE ATT&CK: enrichment, technique mapping, investigation context
- Sigma: portable detections and hunting content ecosystem

**Key technical grounding:**
- Anomaly detection must handle point, group/collective, and contextual anomalies — not naive thresholding
- Context (time, location, team, activity, relation) must partition detections to avoid frivolous false positives
- Graph-based analysis supports communication graphs, attack graphs, threat similarity, and propagation tracing
- Deep learning is not automatically the right first tool — accuracy and explainability must both be handled

## Constraints

- **Target host**: Windows desktop only — no Linux server architecture
- **LLM runtime**: Native Ollama on Windows — primary local model runtime
- **Container rule**: Containerize only where it clearly helps (HTTPS proxy, Open WebUI if used) — prefer native for backend and Ollama
- **Ollama→Docker bridge**: Use `http://host.docker.internal:11434` for any containerized service reaching native Ollama
- **Storage stack**: DuckDB (structured events) + Chroma (vectors) — SQLite acceptable for early phases
- **No enterprise sprawl**: Postgres, Neo4j, Kafka, Elastic, Wazuh all require explicit justification before introduction
- **Verification rule**: Never claim something works until locally verified with test, receipt, or artifact
- **No silent downscoping**: All requested capabilities must be delivered or explicitly flagged as deferred with rationale

## Key Decisions

| Decision | Rationale | Outcome |
|---|---|---|
| Ollama native (not Docker) | Avoids WSL2/GPU passthrough complexity; RTX 5080 needs direct CUDA access | — Pending |
| DuckDB for structured events | Zero-server, columnar, fast analytics on 96GB RAM desktop, no Postgres needed | — Pending |
| Chroma for vector store | Lightweight, Python-native, no external server needed for desktop scale | — Pending |
| FastAPI backend (Python) | Python ecosystem has best SecOps / ML library coverage; uv available | — Pending |
| Caddy for localhost HTTPS | Simpler config than nginx for local dev, Docker-friendly, auto-cert for local CA | — Pending |
| Reject Wazuh (for now) | Heavy server infrastructure, not justified for single desktop brain scope | — Pending |
| Reject Velociraptor (for now) | Agent/server model designed for fleet management, overkill for single desktop | — Pending |
| Standard granularity (5-8 phases) | Matches 5 major capability areas from PROJECT.md spec | — Pending |

---
*Last updated: 2026-03-14 after initialization*
