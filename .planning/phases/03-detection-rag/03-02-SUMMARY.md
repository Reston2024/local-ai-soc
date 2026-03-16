---
phase: 03-detection-rag
plan: 02
subsystem: api, infra
tags: [opensearch, search, httpx, docker-compose, vector, fastapi]

# Dependency graph
requires:
  - phase: 03-01
    provides: Wave-0 TDD stubs for Phase 3 including P3-T1/T2/T8 tests

provides:
  - GET /search?q= endpoint backed by OpenSearch simple_query_string (returns [] gracefully)
  - Unconditional OPENSEARCH_URL env var in docker-compose backend service
  - OpenSearch healthcheck + backend depends_on service_healthy in docker-compose
  - Active opensearch_events sink in vector.yaml writing to fixed 'soc-events' index

affects:
  - 03-03 (Sigma integration, uses same routes.py)
  - 04-graph-correlation (OpenSearch search endpoint ready for cross-phase use)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "OpenSearch graceful degradation: /search returns [] when OS unavailable (connection error caught)"
    - "docker-compose healthcheck gates: backend depends_on opensearch condition: service_healthy"
    - "Fixed index name 'soc-events' (no date suffix) for consistent cross-time search"

key-files:
  created: []
  modified:
    - backend/src/ingestion/opensearch_sink.py
    - backend/src/api/routes.py
    - infra/docker-compose.yml
    - infra/vector/vector.yaml

key-decisions:
  - "Keep OPENSEARCH_URL guard in try_index — avoids broken URL construction when var absent; Phase 3 change is docker-compose now sets var unconditionally"
  - "Fixed index name 'soc-events' (no date suffix) ensures GET /search covers all events regardless of ingestion timestamp"
  - "OpenSearch healthcheck with start_period: 30s guards against JVM startup time causing premature backend startup"

patterns-established:
  - "Graceful degradation: all OpenSearch calls return [] / False on exception, never raise to caller"
  - "search_events uses module-level _get_client() from opensearch_sink — single shared httpx.Client"

requirements-completed: [FR-3.1, FR-3.5]

# Metrics
duration: 3min
completed: 2026-03-16
---

# Phase 3 Plan 02: OpenSearch Activation + Search Endpoint Summary

**OpenSearch live indexing activated via docker-compose OPENSEARCH_URL env var and healthcheck gate; GET /search?q= endpoint added using httpx + simple_query_string; Vector opensearch_events sink uncommented with fixed soc-events index**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-16T05:58:51Z
- **Completed:** 2026-03-16T06:01:56Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- GET /search?q= endpoint returns JSON array from OpenSearch, [] gracefully when unavailable or empty query
- docker-compose backend service now sets OPENSEARCH_URL unconditionally; opensearch gets healthcheck; backend depends_on opensearch service_healthy
- Vector pipeline opensearch_events sink active with fixed 'soc-events' index (no date suffix)
- opensearch_sink.py module/function docstrings updated to reflect Phase 3 unconditional status

## Task Commits

Each task was committed atomically:

1. **Task 1: Remove opensearch_sink.py SCAFFOLD wording + verify P3-T8** - `752f7a0` (feat)
2. **Task 2: Add GET /search endpoint to routes.py + wire docker-compose + vector.yaml** - `4f1d230` (feat)

## Files Created/Modified

- `backend/src/ingestion/opensearch_sink.py` - Updated module and function docstrings to remove Phase 2 SCAFFOLD wording; unconditional indexing behavior documented
- `backend/src/api/routes.py` - Added GET /search endpoint using httpx + OpenSearch simple_query_string; expanded opensearch_sink import to include OPENSEARCH_URL, INDEX_NAME, _get_client
- `infra/docker-compose.yml` - Uncommented OPENSEARCH_URL env var for backend; added opensearch healthcheck block; added backend depends_on opensearch service_healthy; updated header comment to Phase 3
- `infra/vector/vector.yaml` - Uncommented opensearch_events sink; changed index from 'soc-events-%Y-%m-%d' to 'soc-events'; updated header comment

## Decisions Made

- Keep OPENSEARCH_URL early-return guard in try_index to prevent broken URL construction (`f"{None}/soc-events/_doc/id"`). The plan clarifies the guard is valid; Phase 3's real change is docker-compose now sets the env var unconditionally.
- Fixed index name 'soc-events' ensures all events (regardless of ingestion date) are found by /search. Date-suffixed indices would require wildcard queries.
- OpenSearch healthcheck uses start_period: 30s to allow JVM startup before health probes begin.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Linter auto-injected `from backend.src.detection.sigma_loader import load_sigma_rules as _load_sigma_rules` into routes.py after editing. Removed immediately since this is Plan 03 scope and the import was unused. No functional impact.
- TestSigmaDetection/TestSigmaAlerts (P3-T6) were failing before Plan 02 started (sigma_loader exists but not yet integrated into _store_event — that is Plan 03's scope). Confirmed pre-existing by stash check. Not a Plan 02 regression.

## User Setup Required

None - no external service configuration required beyond docker-compose up.

## Next Phase Readiness

- GET /search endpoint ready; returns [] gracefully when OpenSearch is not running
- Docker-compose fully wired: OPENSEARCH_URL set, healthcheck present, depends_on gate active
- Vector sink active: fixture + syslog events will flow to soc-events index on docker compose up
- Plan 03 (Sigma loader integration) can proceed: routes.py is the correct integration point

---
*Phase: 03-detection-rag*
*Completed: 2026-03-16*

## Self-Check: PASSED

- FOUND: backend/src/ingestion/opensearch_sink.py
- FOUND: backend/src/api/routes.py
- FOUND: infra/docker-compose.yml
- FOUND: infra/vector/vector.yaml
- FOUND: .planning/phases/03-detection-rag/03-02-SUMMARY.md
- FOUND commit 752f7a0 (Task 1)
- FOUND commit 4f1d230 (Task 2)
- FOUND commit 5c54de4 (docs metadata)
