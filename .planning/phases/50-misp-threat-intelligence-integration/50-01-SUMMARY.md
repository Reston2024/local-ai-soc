---
phase: 50-misp-threat-intelligence-integration
plan: 01
subsystem: infra
tags: [misp, pymisp, threat-intelligence, docker, ioc, wave-0, tdd]

# Dependency graph
requires:
  - phase: 33-threat-intelligence-feeds
    provides: feed_sync.py worker pattern, ioc_store upsert_ioc interface
provides:
  - pymisp dependency in pyproject.toml
  - backend/services/intel/misp_sync.py MispSyncService stub (NotImplementedError)
  - MISP_TYPE_MAP (10 attribute types) and THREAT_LEVEL_CONFIDENCE (4 levels)
  - 6 Wave 0 unit test stubs (2 pass, 3 skip, 1 fail on 404)
  - infra/misp/ Docker Compose with mariadb/valkey/misp-core for GMKtec N100
affects:
  - 50-02-PLAN (Wave 1: implements fetch_ioc_attributes + MispWorker)
  - 50-03-PLAN (Wave 2: adds /api/intel/misp-events endpoint)

# Tech tracking
tech-stack:
  added: [pymisp==2.5.33.1]
  patterns:
    - importorskip at module level for atomic skip behavior (matches Phase 44/45/48 pattern)
    - Wave 0 / Wave 1 test stub pattern — failing stubs to turn green in next plan
    - Lazy PyMISP import inside fetch_ioc_attributes (allows stub import without live pymisp wheel)

key-files:
  created:
    - backend/services/intel/misp_sync.py
    - tests/unit/test_misp_sync.py
    - tests/unit/test_intel_api_misp.py
    - infra/misp/docker-compose.misp.yml
    - infra/misp/.env.misp.template
    - infra/misp/customize_misp.sh
  modified:
    - pyproject.toml (pymisp added)
    - uv.lock
    - .gitignore (infra/misp/.env.misp added)

key-decisions:
  - "50-01: MispSyncService stub uses lazy PyMISP import inside fetch_ioc_attributes — allows import without live pymisp at module level"
  - "50-01: MISP Docker Compose targets GMKtec N100 alongside Malcolm — NOT merged into root compose on Windows host"
  - "50-01: Memory-constrained compose: 256MB mariadb pool, 256MB valkey cap, minimal workers (0 email, 1 update)"
  - "50-01: customize_misp.sh is a guidance script (no auto feed-enable) — N100 memory prevents downloading all 80+ feeds"

patterns-established:
  - "Wave 0 stub pattern: create test stubs with MISP_TYPE_MAP/THREAT_LEVEL_CONFIDENCE constants that PASS immediately; worker stubs SKIP; API stubs FAIL — all turned GREEN in Wave 1"
  - "importorskip at module level: entire test file skips atomically when dependency unavailable"

requirements-completed: [DOCKER-01, PHASE33-01, VIEW-01]

# Metrics
duration: 12min
completed: 2026-04-15
---

# Phase 50 Plan 01: MISP Threat Intelligence Integration (Wave 0) Summary

**PyMISP dependency added, MispSyncService stub + MISP_TYPE_MAP/THREAT_LEVEL_CONFIDENCE constants created, 6 Wave 0 test stubs, and N100-optimized Docker Compose for MISP (mariadb + valkey + misp-core)**

## Performance

- **Duration:** 12 min
- **Started:** 2026-04-15T05:13:00Z
- **Completed:** 2026-04-15T05:25:00Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- pymisp==2.5.33.1 added to pyproject.toml via `uv add pymisp`
- MispSyncService stub (misp_sync.py) importable with MISP_TYPE_MAP (10 types), THREAT_LEVEL_CONFIDENCE (4 levels), fetch_ioc_attributes() raising NotImplementedError
- 6 unit test stubs: test_attribute_type_mapping and test_confidence_mapping PASS immediately; 3 MispWorker stubs SKIP; test_misp_events_endpoint FAILS with 404 (endpoint pending Wave 2)
- MISP Docker Compose with memory-constrained config for GMKtec N100 (coexists with Malcolm's OpenSearch)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add pymisp dependency + create MispSyncService stub** - `3e6c80d` (feat)
2. **Task 2: Write failing unit stubs for MispSyncService + MispWorker** - `b12f13f` (test)
3. **Task 3: MISP Docker Compose + infra scaffold** - `6daf7bc` (chore)

## Files Created/Modified

- `backend/services/intel/misp_sync.py` - MispSyncService stub with MISP_TYPE_MAP, THREAT_LEVEL_CONFIDENCE, fetch_ioc_attributes (NotImplementedError)
- `tests/unit/test_misp_sync.py` - 5 Wave 0 stubs: 2 pass (constants), 3 skip (MispWorker pending)
- `tests/unit/test_intel_api_misp.py` - 1 Wave 0 stub: fails 404 until Plan 50-03 adds endpoint
- `infra/misp/docker-compose.misp.yml` - mariadb:10.11, valkey:7.2, misp-core:latest with N100 memory limits
- `infra/misp/.env.misp.template` - secrets template with GMKTEC_IP, MISP_DB_*, MISP_ADMIN_*, MISP_ENCRYPTION_KEY
- `infra/misp/customize_misp.sh` - first-start guidance script (placeholder for manual feed enable)
- `pyproject.toml` - pymisp==2.5.33.1 added to dependencies
- `uv.lock` - updated lockfile
- `.gitignore` - infra/misp/.env.misp added to prevent secrets commit

## Decisions Made

- MispSyncService stub uses lazy PyMISP import (import inside fetch_ioc_attributes, not at module level) — allows the module to import even in environments where pymisp wheel build is incomplete. Wave 1 adds the live import.
- MISP Docker Compose targets the GMKtec N100 alongside Malcolm, not merged into root Windows host compose — different deployment target, different memory constraints.
- Memory-constrained compose: 256MB innodb_buffer_pool_size, 256MB valkey maxmemory, NUM_WORKERS_EMAIL=0, NUM_WORKERS_UPDATE=1 — N100 is already taxed by Malcolm/OpenSearch.
- customize_misp.sh is a guidance script with echo instructions rather than automated feed-enable — prevents accidental download of all 80+ feeds on first start exhausting N100 memory.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — all three tasks executed cleanly. Docker compose config validated with warnings only about unset env vars (expected, filled from .env.misp at deploy time).

## User Setup Required

When ready to deploy MISP on the GMKtec N100:
1. Copy `infra/misp/.env.misp.template` to `infra/misp/.env.misp`
2. Generate secrets: `openssl rand -hex 24` (DB passwords), `openssl rand -hex 32` (encryption key)
3. Set `GMKTEC_IP` to the GMKtec's LAN IP
4. Deploy: `docker compose -f docker-compose.misp.yml --env-file .env.misp up -d`
5. Wait 2-3 minutes for PHP/DB migrations on N100
6. Log in at `http://192.168.1.22:8080` with MISP_ADMIN_EMAIL/PASSWORD
7. Enable 4-5 curated feeds manually (CIRCL OSINT, MalwareBazaar, Feodo, URLhaus)
8. Generate API key for Plan 50-02 MispSyncService configuration

## Next Phase Readiness

- Wave 1 (Plan 50-02) can immediately start implementing fetch_ioc_attributes(), MispWorker, and retroactive scan trigger — all stubs are in place
- test_attribute_type_mapping and test_confidence_mapping provide instant regression checks for the constant maps
- MISP Docker Compose ready to deploy on GMKtec when MISP API key is needed for integration testing

---
*Phase: 50-misp-threat-intelligence-integration*
*Completed: 2026-04-15*
