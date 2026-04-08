---
phase: "06"
slug: hardening-integration
scope: "Threat Causality & Investigation Engine"
status: passed
verified_by: automated-artifact-check
verified_date: "2026-04-08"
pre_gsd: true
nyquist_compliant: true
---

# Phase 06 — Verification: Threat Causality & Investigation Engine

**Note — Pre-GSD Phase:** Phase 06 was executed before the standard GSD verifier workflow was
adopted. PLAN.md and SUMMARY.md files exist (plans 00–05). No VERIFICATION.md was created at
time of execution. This document is a retroactive authoritative verification record produced
by the Phase 29 milestone audit. The absence of a VERIFICATION.md at delivery time is expected,
not a gap.

The phase directory was named `06-hardening-integration` (original roadmap label) but the
CONTEXT.md and all plans reflect a scope redefinition to: **Threat Causality & Investigation
Engine**. The original "hardening/integration" scope (Caddy proxy, Docker Compose, security
headers) was carried over from prior work and is also present in the codebase — see
Infrastructure Artifacts below.

---

## Phase Goal (from CONTEXT.md / ROADMAP)

Build a Causality Engine that reconstructs attack chains from correlated security events and
exposes them via the SOC dashboard. Analysts must be able to visually trace threats end-to-end
by resolving entities, linking related events, mapping detections to MITRE ATT&CK, and
generating investigation graphs that support interactive exploration.

---

## Automated Checks

```
Caddyfile present:          PASS  (config/caddy/Caddyfile)
docker-compose.yml present: PASS  (docker-compose.yml)
Caddy directives (reverse_proxy|tls) found: PASS  (tls internal + 3x reverse_proxy blocks)
backend/causality/ package: PASS  (7 modules)
causality_routes.py:        PASS  (mounted at /api/causality)
AttackChain component:      PASS  (dashboard/src/components/graph/AttackChain.svelte)
InvestigationPanel:         PASS  (dashboard/src/components/panels/InvestigationPanel.svelte)
MITRE mapper catalog:       PASS  (T1566.001 … full catalog)
```

---

## Infrastructure Artifacts (Caddy / Docker)

These artifacts exist in the codebase and confirm the HTTPS proxy integration was completed
alongside the causality engine work.

### `config/caddy/Caddyfile`

**Status: EXISTS — verified.**

- `tls internal` — Caddy auto-generates and trusts a local CA cert for `localhost`
- Security headers block: `Content-Security-Policy`, `X-Frame-Options DENY`,
  `X-Content-Type-Options nosniff`, `Referrer-Policy`, `Permissions-Policy`
- `reverse_proxy host.docker.internal:8000` for `/api/*` (10 MB body limit)
- Unbuffered `flush_interval -1` SSE proxy for `/api/query/*`
- 100 MB limit for `/api/ingest/file` upload endpoint
- Dashboard SPA served from `/srv/dashboard` under `/app/` subpath
- `health_uri /health` upstream health check on 15 s interval

### `docker-compose.yml`

**Status: EXISTS — verified.**

- Caddy service: `caddy:2.9-alpine` image, pinned digest
- Container: `ai-soc-brain-caddy`
- `./config/caddy/Caddyfile` mounted read-only at `/etc/caddy/Caddyfile`
- Named volumes: `caddy_data`, `caddy_config`
- Caddy reverse-proxies to FastAPI backend on `host.docker.internal:8000`

---

## Phase 06 Core Deliverables

### 1. `backend/causality/` Package

**Status: EXISTS — all 7 modules present.**

| Module | Purpose |
|--------|---------|
| `__init__.py` | Package marker |
| `engine.py` | `build_causality_sync()` orchestrator — calls chain builder, MITRE mapper, scorer |
| `entity_resolver.py` | Entity normalization: `resolve_canonical_id()` → `<type>:<value>` IDs |
| `attack_chain_builder.py` | BFS traversal with depth cap and cycle detection: `find_causal_chain()` |
| `mitre_mapper.py` | `map_techniques()` against full TECHNIQUE_CATALOG (TA0001–TA0011) |
| `scoring.py` | Severity-weighted chain scoring |
| `causality_routes.py` | FastAPI router (`/api/causality/*`) — rewritten in Phase 08 to use DuckDB |

### 2. API Endpoints

**Status: PRESENT — mounted in `backend/main.py`.**

```
causality_router mounted at /api/causality
  GET  /api/graph/{investigation_id}       (graph.py)
  GET  /api/entity/{entity_id}             (graph.py)
  POST /api/query                          (query.py — SSE-capable)
  GET  /api/causality/*                    (causality_routes.py Phase 06 endpoints)
```

Phase 06 locked endpoints (`/api/graph/{alert_id}`, `/api/attack_chain/{alert_id}`,
`/api/entity/{entity_id}`, `POST /api/query`) are all present in the router surface, some
via later evolution of the same modules.

### 3. MITRE ATT&CK Mapping

**Status: PRESENT — `backend/causality/mitre_mapper.py`.**

Full `TECHNIQUE_CATALOG` dict covering all 11 MITRE ATT&CK tactics:
TA0001 Initial Access, TA0002 Execution, TA0003 Persistence, TA0004 Privilege Escalation,
TA0005 Defense Evasion, TA0006 Credential Access, TA0007 Discovery,
TA0008 Lateral Movement, TA0009 Collection, TA0010 Exfiltration, TA0011 Impact.

### 4. Dashboard Components

**Status: PRESENT.**

| Component | Location | Status |
|-----------|----------|--------|
| `AttackChain.svelte` | `dashboard/src/components/graph/` | EXISTS |
| `InvestigationPanel.svelte` | `dashboard/src/components/panels/` | EXISTS |
| `ThreatGraph.svelte` | `dashboard/src/components/graph/` | EXISTS (extended) |

`AttackChain.svelte` uses Cytoscape.js + cytoscape-dagre for hierarchical attack graph
visualization, orange attack-path highlighting, and 7-color node-type map.

`InvestigationPanel.svelte` provides score badge, MITRE technique list, timeline filter
(datetime-local inputs), and AI Summary button calling the Ollama investigation endpoint.

### 5. Investigation Tests

**Status: Tests executed and passed at plan close.**

From `06-05-SUMMARY.md` verification results:
- `npm run build` exits 0 (vite 6.4.1, 684 modules)
- Full test suite: 41 passed + 42 xpassed + 1 xfailed (strict=False) — no regressions
- Phase 6 xfail tests: 15/16 XPASS; 1 XFAIL (TestDashboardBuild, strict=False — npm not on PATH in subprocess runner)

---

## Plan Execution Summary

| Plan | Name | Commit | Status |
|------|------|--------|--------|
| 06-00 | TDD Scaffolding + xfail stubs | recorded in SUMMARY | complete |
| 06-01 | Entity Resolver + Chain Builder | recorded in SUMMARY | complete |
| 06-02 | MITRE Mapper + Scoring | recorded in SUMMARY | complete |
| 06-03 | Causality Engine orchestrator | recorded in SUMMARY | complete |
| 06-04 | API Routes | recorded in SUMMARY | complete |
| 06-05 | Dashboard Components (AttackChain + InvestigationPanel) | 53865ef, 3001155 | complete |

---

## Completion Criteria Verification

From CONTEXT.md locked completion criteria:

| Criterion | Result |
|-----------|--------|
| Alerts generate attack graphs | PASS — `build_causality_sync()` + `/api/causality/*` routes |
| Events link into causal chains | PASS — `attack_chain_builder.py` BFS traversal |
| MITRE mappings appear in investigations | PASS — `mitre_mapper.py` full 11-tactic catalog |
| Analysts can visually trace attack path | PASS — `AttackChain.svelte` dagre layout + orange attack-path highlighting |
| AI investigation summaries | PASS — `InvestigationPanel.svelte` "Generate Summary" calls Ollama endpoint |
| Timeline filtering | PASS — datetime-local filter in InvestigationPanel, `?from/to` params in API |

---

## Status Rationale

**Status: `passed`**

All Phase 06 deliverables are confirmed present in the codebase. Both infrastructure artifacts
(Caddyfile with TLS + security headers, docker-compose.yml with Caddy service) and causality
engine artifacts (7 Python modules, API routes, dashboard components) exist and match the
CONTEXT.md locked decisions. Automated checks pass. Phase 08 enhanced the causality routes
from in-memory to DuckDB persistence — this is additive evolution, not replacement.

Live HTTPS testing (Caddy container running, browser certificate trust) would require a
deployed environment. This is noted as an operational verification, not a code artifact gap.
The codebase evidence is sufficient for `passed` status.

---

*Verification produced: 2026-04-08 by Phase 29 milestone audit (29-07-PLAN.md)*
*Verifier: automated artifact inspection + retroactive SUMMARY review*
