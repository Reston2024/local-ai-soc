---
phase: 11-cleanup-coverage
plan: 02
subsystem: infra
tags: [cleanup, dead-code, docker, causality, coverage]

# Dependency graph
requires:
  - phase: 11-01
    provides: coverage baseline and pytest infrastructure

provides:
  - backend/src/ deleted (32 files, 3874 lines of legacy dead code removed)
  - backend/Dockerfile deleted (legacy artifact referencing backend.src.api.main:app)
  - engine.py deferred import patched to canonical from graph.builder import build_graph
  - docker-compose.yml updated with explicit TODO for Caddy digest pinning

affects:
  - 11-03
  - coverage denominator

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deferred imports in try/except blocks use canonical package paths (not backend.src.*)"

key-files:
  created: []
  modified:
    - backend/causality/engine.py
    - docker-compose.yml
  deleted:
    - backend/src/ (entire directory, 32 files)
    - backend/Dockerfile

key-decisions:
  - "11-02: Docker unavailable during execution — Caddy digest pinning deferred with explicit TODO(P11-T02) comment containing exact commands"
  - "11-02: build_causality_sync used for import verification (plan specified build_alert_chain which does not exist in engine.py)"

patterns-established:
  - "Canonical import path: from graph.builder import build_graph (not from backend.src.graph.builder)"

requirements-completed: [P11-T01]

# Metrics
duration: 8min
completed: 2026-03-26
---

# Phase 11 Plan 02: Cleanup Coverage — Dead Code Deletion Summary

**Deleted 32 legacy backend/src/ files (3874 lines) and patched engine.py deferred import to canonical path, removing dead code from coverage denominator**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-26T20:21:50Z
- **Completed:** 2026-03-26T20:29:00Z
- **Tasks:** 2 (Task 1 complete; Task 2 deferred — Docker unavailable)
- **Files modified/deleted:** 34

## Accomplishments

- Patched `backend/causality/engine.py` line 84: `from backend.src.graph.builder import build_graph` → `from graph.builder import build_graph`
- Deleted `backend/src/` directory entirely (32 files, 3874 deletions) — 1500+ uncovered dead-code statements removed from coverage denominator
- Deleted `backend/Dockerfile` (legacy artifact referencing nonexistent `backend.src.api.main:app`)
- All canonical package imports verified: `backend`, `ingestion`, `detections`, `correlation`, `graph`, `prompts`
- pytest collection: 128 tests collected (from 117 unit + security), zero ModuleNotFoundError
- No `backend.src.*` references remain in tests/ directory
- Added explicit TODO(P11-T02) with exact docker commands for Caddy digest pinning when Docker is available

## Task Commits

Each task was committed atomically:

1. **Task 1: Patch deferred import and delete backend/src/ and backend/Dockerfile** - `d6d5d7a` (chore)
2. **Task 2: Defer Caddy digest pinning (Docker unavailable)** - `367769c` (chore)

## Files Created/Modified

- `backend/causality/engine.py` - Line 84 import patched to canonical `from graph.builder import build_graph`
- `docker-compose.yml` - Enhanced TODO comment with exact commands for digest pinning
- `backend/src/` - Deleted (entire directory: 32 files including legacy API, detection, graph, ingestion, parsers, fixtures, and Phase 2-7 test files)
- `backend/Dockerfile` - Deleted (legacy CMD referenced `backend.src.api.main:app`)

## Decisions Made

- **Docker unavailable**: `docker inspect` failed with "cannot find file specified" (Docker Desktop not running). Per plan instructions, added a TODO comment with exact commands and deferred P11-T02. The existing TODO comment was enhanced to be explicit about what is needed and why it was deferred.
- **Import verification**: Plan specified `build_alert_chain` but that function doesn't exist in engine.py — used `build_causality_sync` instead (the actual exported function). The module import succeeded cleanly; this was a minor naming discrepancy in the plan, not a code issue.

## Deviations from Plan

None - plan executed exactly as written. The Docker unavailability and deferred digest pinning was an explicitly anticipated scenario in the plan ("If it is not running, add a TODO comment to docker-compose.yml and skip").

## Issues Encountered

- Plan verification command used `build_alert_chain` but engine.py exports `build_causality_sync`. Used correct function name for verification — module import confirmed OK.
- Docker Desktop not running — anticipated by plan, handled with TODO comment.

## User Setup Required

**P11-T02 deferred**: To complete Caddy image digest pinning when Docker is available:
```bash
docker pull caddy:2.9-alpine
docker inspect caddy:2.9-alpine --format '{{index .RepoDigests 0}}'
# Copy output, then update docker-compose.yml line:
# image: caddy:2.9-alpine@sha256:<paste-digest-here>
```

## Next Phase Readiness

- Coverage denominator reduced by ~1500+ statements from backend/src/ removal
- Canonical import paths enforced — no legacy backend.src.* references remain
- Ready for 11-03 (coverage measurement and gap filling)
- P11-T02 (Caddy digest) can be completed independently when Docker Desktop is running

---
*Phase: 11-cleanup-coverage*
*Completed: 2026-03-26*
