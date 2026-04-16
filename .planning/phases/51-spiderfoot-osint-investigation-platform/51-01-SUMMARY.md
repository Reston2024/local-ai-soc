---
phase: 51-spiderfoot-osint-investigation-platform
plan: 01
subsystem: testing
tags: [dnstwist, spiderfoot, osint, tdd, sqlite]

# Dependency graph
requires:
  - phase: 32-osint-enrichment
    provides: osint_cache SQLite schema, OsintService patterns
  - phase: 50-misp-threat-intelligence-integration
    provides: ioc_store table used in bulk_query_ioc_cache stub
provides:
  - dnstwist>=20250130 installed in project virtualenv
  - TDD stubs for SpiderFootClient (5 stubs)
  - TDD stubs for OsintInvestigationStore (8 stubs)
  - TDD stubs for OSINT investigate API routes (7 stubs)
affects: [51-02-PLAN, 51-03-PLAN]

# Tech tracking
tech-stack:
  added: [dnstwist==20250130]
  patterns: [importorskip-guard pattern for conditional TDD stubs (matches Phase 48/49/50 pattern)]

key-files:
  created:
    - tests/unit/test_spiderfoot_client.py
    - tests/unit/test_osint_store.py
    - tests/unit/test_osint_investigate_api.py
  modified:
    - pyproject.toml
    - uv.lock

key-decisions:
  - "dnstwist base package (not [full]) — py-tlsh C extension requires MSVC build tools not present on Windows host; base dnstwist covers all fuzzer algorithms needed for lookalike detection"
  - "sse-starlette already installed at 3.0.3 (plan spec said >=2.1); no change needed"
  - "All 20 stubs use per-test @_skip decorator with module-level ImportError guard — consistent with Phase 48/49/50 pattern"

patterns-established:
  - "Phase 51 TDD pattern: module-level try/except ImportError sets _*_AVAILABLE bool; _skip = pytest.mark.skipif(not _*_AVAILABLE) applied per-test"
  - "mem_store fixture uses sqlite3.connect(':memory:') directly — OsintInvestigationStore takes raw Connection, no SQLiteStore wrapper"

requirements-completed: []

# Metrics
duration: 15min
completed: 2026-04-16
---

# Plan 51-01: Wave 0 — TDD Stubs + DNSTwist Install Summary

**20 failing TDD stubs created across SpiderFootClient, OsintInvestigationStore, and OSINT API routes; dnstwist installed — all stubs SKIP cleanly, zero regressions in 1152-test suite**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-16
- **Completed:** 2026-04-16
- **Tasks:** 4 (1 dependency install + 3 test files)
- **Files modified:** 5

## Accomplishments
- `dnstwist==20250130` added to pyproject.toml and installed via uv sync
- 5 SpiderFootClient stubs define contracts for Plan 51-02 implementation (ping, start_scan, get_status, stop_scan, method presence)
- 8 OsintInvestigationStore stubs define SQLite schema contracts (investigations table, findings, dnstwist_findings, ioc_cache cross-join)
- 7 OSINT investigate API stubs define route contracts (POST/GET/DELETE investigate, dnstwist endpoint, SSE stream, health check)
- All 20 stubs SKIP cleanly; 1152 existing unit tests unaffected

## Task Commits

Each task was committed atomically:

1. **Tasks 1-4: dnstwist dep + all 3 test stub files** - `f661117` (feat)

## Files Created/Modified
- `pyproject.toml` - Added `dnstwist>=20250130` dependency
- `uv.lock` - Lockfile updated (dnstwist==20250130 resolved)
- `tests/unit/test_spiderfoot_client.py` - 5 stubs for SpiderFootClient (Plan 51-02 contracts)
- `tests/unit/test_osint_store.py` - 8 stubs for OsintInvestigationStore (Plan 51-02 contracts)
- `tests/unit/test_osint_investigate_api.py` - 7 stubs for OSINT investigation API routes (Plan 51-03 contracts)

## Decisions Made
- Used `dnstwist>=20250130` (not `dnstwist[full]`) because the `py-tlsh` C extension in `[full]` requires Microsoft Visual C++ 14.0+ build tools not present on this Windows host. The base package provides all fuzzer algorithms (homoglyph, transposition, addition, etc.) needed for Phase 51 lookalike detection.
- `sse-starlette` already at version 3.0.3 in pyproject.toml (plan spec said >=2.1) — no change needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] dnstwist[full] replaced with dnstwist base**
- **Found during:** Task 1 (dependency install)
- **Issue:** `dnstwist[full]` pulls in `py-tlsh==4.12.1` which requires MSVC C++ build tools; `uv sync` failed with `error: Microsoft Visual C++ 14.0 or greater is required`
- **Fix:** Changed `dnstwist[full]>=20250130` to `dnstwist>=20250130` in pyproject.toml; uv sync succeeded
- **Files modified:** pyproject.toml, uv.lock
- **Verification:** `uv sync` completed successfully; `dnstwist==20250130` present in .venv
- **Committed in:** f661117 (combined task commit)

---

**Total deviations:** 1 auto-fixed (1 blocking build failure)
**Impact on plan:** No functional impact — base dnstwist covers all lookalike fuzzer algorithms. TLSH similarity hashing (the only [full] extra) is an optional enhancement not in Phase 51 requirements.

## Issues Encountered
- `py-tlsh` C extension build failure on Windows — resolved by dropping `[full]` extra (see Deviations above)

## User Setup Required
None - no external service configuration required for Wave 0 stubs.

## Next Phase Readiness
- Plan 51-02 can proceed: implement `SpiderFootClient` (backend/services/spiderfoot_client.py) and `OsintInvestigationStore` (backend/services/osint_investigation_store.py) — all contracts defined by stubs
- Plan 51-03 can follow: register `/investigate`, `/investigations`, `/dnstwist` routes on `backend/api/osint_api.py`
- dnstwist module importable in backend code immediately

---
*Phase: 51-spiderfoot-osint-investigation-platform*
*Completed: 2026-04-16*
