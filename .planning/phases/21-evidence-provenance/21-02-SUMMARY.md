---
phase: 21-evidence-provenance
plan: "02"
subsystem: database
tags: [sqlite, sigma, pysigma, sha256, provenance, detection, fastapi]

# Dependency graph
requires:
  - phase: 21-evidence-provenance/21-00
    provides: SQLiteStore skeleton, DetectionProvenanceRecord Pydantic model, DetectionRecord dataclass
  - phase: 21-evidence-provenance/21-01
    provides: ingest_provenance DDL pattern already established in sqlite_store.py
provides:
  - detection_provenance SQLite table with rule_sha256, pysigma_version, field_map_version
  - SQLiteStore.record_detection_provenance() and get_detection_provenance() methods
  - PYSIGMA_VERSION / FIELD_MAP_VERSION constants in detections/matcher.py
  - SigmaMatcher._rule_yaml cache for reproducible rule hashing
  - save_detections() writes provenance row per detection (non-fatal on failure)
  - GET /api/provenance/detection/{detection_id} endpoint
  - GET /api/provenance/ingest/{event_id} endpoint
affects:
  - 21-evidence-provenance/21-03
  - 21-evidence-provenance/21-04
  - detections/matcher.py consumers

# Tech tracking
tech-stack:
  added: [hashlib (stdlib), importlib.metadata (stdlib)]
  patterns:
    - "Non-fatal provenance writes: try/except around each provenance INSERT so detection pipeline is never blocked"
    - "YAML caching in _rule_yaml dict keyed by str(rule.id) for O(1) SHA-256 lookup at save time"
    - "INSERT OR IGNORE for idempotent provenance rows"

key-files:
  created:
    - backend/api/provenance.py
  modified:
    - backend/stores/sqlite_store.py
    - detections/matcher.py
    - backend/main.py
    - tests/unit/test_detection_provenance.py

key-decisions:
  - "Cache YAML text in _rule_yaml dict during load (not re-read from disk at save time) for performance and correctness"
  - "Provenance write is non-fatal — detection pipeline must not fail if SQLite provenance INSERT fails"
  - "operator_id not threaded through DetectionRecord; stored as NULL in detection_provenance for now"
  - "Rule SHA-256 falls back to 'unknown' string if YAML not cached, with warning log"
  - "Provenance router protected by verify_token (same auth as all other API routers)"

patterns-established:
  - "Pattern: _rule_yaml[str(rule.id)] = yaml_text in both load_rules_dir and load_rule_yaml"
  - "Pattern: PYSIGMA_VERSION + FIELD_MAP_VERSION as module-level constants — frozen at import time"

requirements-completed: [P21-T02]

# Metrics
duration: 4min
completed: 2026-04-02
---

# Phase 21 Plan 02: Detection Provenance Summary

**Sigma rule SHA-256 + pySigma/field-map version stored per detection in SQLite, with GET /api/provenance/detection/{id} read endpoint**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-02T12:44:05Z
- **Completed:** 2026-04-02T12:48:00Z
- **Tasks:** 2 (TDD: RED + GREEN for each)
- **Files modified:** 5

## Accomplishments

- `detection_provenance` SQLite table created by `SQLiteStore.__init__` DDL with index on `detection_id`
- `record_detection_provenance()` and `get_detection_provenance()` methods added to SQLiteStore
- `PYSIGMA_VERSION` and `FIELD_MAP_VERSION` module-level constants in `detections/matcher.py`
- `SigmaMatcher._rule_yaml` dict caches raw YAML text during rule loading for reproducible SHA-256 hashing
- `save_detections()` writes one provenance row per detection (non-fatal on failure)
- `backend/api/provenance.py` router with GET endpoints for detection and ingest provenance
- 3/3 unit tests GREEN; all pre-existing failures unaffected

## Task Commits

Each task was committed atomically:

1. **RED tests** - `9ca55d1` (test: 3 failing tests for detection provenance)
2. **Task 1: SQLiteStore DDL + methods** - `e1df544` (feat: detection_provenance table + record/get methods)
3. **Task 2: SigmaMatcher provenance + API router** - `2533b90` (feat: YAML cache, constants, save_detections provenance, API router)
4. **Auto-fix: register router in main.py** - `287ae66` (feat: mount provenance router in app factory)

## Files Created/Modified

- `backend/stores/sqlite_store.py` - Added detection_provenance DDL block and two new methods
- `detections/matcher.py` - Added hashlib/importlib.metadata imports, PYSIGMA_VERSION, FIELD_MAP_VERSION, _rule_sha256(), _rule_yaml cache, provenance writes in save_detections()
- `backend/api/provenance.py` - New router: GET /api/provenance/detection/{id} and /api/provenance/ingest/{event_id}
- `backend/main.py` - Registered provenance router with verify_token dependency
- `tests/unit/test_detection_provenance.py` - 3 unit tests (table existence, field values, API endpoint)

## Decisions Made

- Cached YAML text in `_rule_yaml` dict at load time — avoids re-reading disk at detection save time and ensures we hash the exact bytes that produced the rule object
- Provenance writes are non-fatal — the detection pipeline must never be blocked by a SQLite provenance INSERT failure
- `operator_id` stored as NULL in detection_provenance (not in DetectionRecord dataclass yet)
- SHA-256 falls back to literal string `"unknown"` when YAML is not cached (e.g., rules loaded before this code shipped); logged as warning

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Registered provenance router in main.py**
- **Found during:** Task 2 (after creating backend/api/provenance.py)
- **Issue:** A router not mounted in create_app() is unreachable; endpoints would silently 404
- **Fix:** Added `app.include_router(provenance_router, dependencies=[Depends(verify_token)])` in main.py inside try/except ImportError block, consistent with all other routers
- **Files modified:** backend/main.py
- **Verification:** Router block follows exact same pattern as operators_router; test_detection_provenance_api passes without main.py (uses isolated FastAPI app)
- **Committed in:** 287ae66

---

**Total deviations:** 1 auto-fixed (Rule 2 missing critical — router registration)
**Impact on plan:** Required for the endpoint to be reachable in production. No scope creep.

## Issues Encountered

None — plan executed cleanly. Pre-existing 401 failures in `test_api_endpoints.py` confirmed pre-existing via `git stash` verification.

## Next Phase Readiness

- Detection provenance is now fully operational: every `save_detections()` call writes a row
- Plans 21-03 (LLM provenance) and 21-04 (playbook provenance) can follow the same pattern
- The GET /api/provenance/ingest/{event_id} endpoint is wired and functional (plan 21-01 delivered the underlying store method)

---
*Phase: 21-evidence-provenance*
*Completed: 2026-04-02*
