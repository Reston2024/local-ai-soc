---
phase: 26-graph-schema-versioning-and-perimeter-entities
plan: "04"
subsystem: testing
tags: [pytest, graph-schema, sqlite, perimeter-entities, ipfire]

# Dependency graph
requires:
  - phase: 26-graph-schema-versioning-and-perimeter-entities
    provides: "graph/schema.py with perimeter types, SQLiteStore.get_graph_schema_version(), extract_perimeter_entities(), loader wiring"
provides:
  - "15 active (non-skipped) unit tests covering P26-T01 through P26-T05"
  - "7 tests in test_graph_schema.py: entity/edge type constants, perimeter extraction"
  - "5 tests in test_graph_versioning.py: version seeding, endpoint, idempotency, column guard"
  - "3 tests in test_loader_ipfire_pipeline.py: full loader pipeline (verified passing)"
affects: [phase-27, future-graph-phases]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Stub activation pattern: remove pytestmark skip, fix test bodies to match actual production API"
    - "SQLiteStore system_kv manipulation in tests: use updated_at column and sentinel values not '1.0.0'"
    - "extract_perimeter_entities() returns (entities, edges) tuple — tests must unpack both"

key-files:
  created: []
  modified:
    - tests/unit/test_graph_schema.py
    - tests/unit/test_graph_versioning.py

key-decisions:
  - "Use sentinel value 'custom-version' (not '1.0.0') in test_system_kv_not_clobbered to avoid upgrade logic that fires when value='1.0.0' and entities count=0"
  - "In test_preexisting_install_gets_version_1: delete version key before re-opening store to simulate a pre-phase-26 DB that had no version seeding"
  - "test_graph_schema.py perimeter tests: pass tags as comma-separated string ('zone:red'), provide dst_ip and ingested_at, unpack (entities, edges) tuple"

patterns-established:
  - "When activating wave-0 stubs, cross-check expected API against actual production code before removing skip mark"
  - "system_kv table requires updated_at in all INSERT/REPLACE statements"

requirements-completed: [P26-T01, P26-T02, P26-T03, P26-T04, P26-T05]

# Metrics
duration: 15min
completed: 2026-04-07
---

# Phase 26 Plan 04: Test Activation Summary

**15 phase-26 unit tests activated and passing: graph schema constants, perimeter entity extraction, SQLite version seeding, and loader pipeline verified**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-07T02:00:00Z
- **Completed:** 2026-04-07T02:15:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Activated all 7 tests in test_graph_schema.py (removed pytestmark skip, rewrote perimeter tests to match production API)
- Activated all 5 tests in test_graph_versioning.py (removed pytestmark skip, fixed two test logic bugs revealed by actual seeding behavior)
- Verified 3 pipeline tests in test_loader_ipfire_pipeline.py already passing (written by plan 26-02)
- Full 930-test suite passes with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Activate test_graph_schema.py** - `e34c22f` (test)
2. **Task 2: Activate test_graph_versioning.py** - `962daed` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `tests/unit/test_graph_schema.py` - Removed skip mark; rewrote perimeter tests to unpack (entities, edges) tuple, use comma-separated tags string, provide required dst_ip and ingested_at fields
- `tests/unit/test_graph_versioning.py` - Removed skip mark and unused pytest import; fixed test_preexisting_install_gets_version_1 (delete version key before re-opening) and test_system_kv_not_clobbered (add updated_at column, use 'custom-version' sentinel)

## Decisions Made
- Used `'custom-version'` sentinel in `test_system_kv_not_clobbered` because the production upgrade logic specifically checks `WHERE value = '1.0.0'` — using `'1.0.0'` as the test value would be overwritten by the step-2 UPDATE when entities count is 0.
- Deleted the version key in `test_preexisting_install_gets_version_1` to simulate a pre-phase-26 database (one that existed before versioning was introduced); simply inserting an entity row after the first store init is insufficient because the first init already seeds `2.0.0`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Perimeter test tuple unpacking**
- **Found during:** Task 1 (test_graph_schema.py activation)
- **Issue:** Existing stubs called `edges = extract_perimeter_entities(event)` treating the result as a flat list, but the production function returns `(entities, edges)` two-tuple. Also stubs passed `tags` as a list and omitted required `dst_ip` and `ingested_at` fields.
- **Fix:** Rewrote both perimeter tests to unpack `entities, edges = extract_perimeter_entities(event)`, pass `tags` as a comma-separated string (`"zone:red"`), and include all required fields.
- **Files modified:** tests/unit/test_graph_schema.py
- **Verification:** 7/7 tests pass
- **Committed in:** e34c22f (Task 1 commit)

**2. [Rule 1 - Bug] system_kv INSERT missing required updated_at column**
- **Found during:** Task 2 (test_graph_versioning.py activation)
- **Issue:** `test_system_kv_not_clobbered` used `INSERT OR REPLACE INTO system_kv (key, value)` without `updated_at`, failing with `NOT NULL constraint failed: system_kv.updated_at`.
- **Fix:** Added `updated_at` to the INSERT OR REPLACE statement.
- **Files modified:** tests/unit/test_graph_versioning.py
- **Verification:** Test passes
- **Committed in:** 962daed (Task 2 commit)

**3. [Rule 1 - Bug] Pre-existing install test incorrect seeding simulation**
- **Found during:** Task 2 (test_graph_versioning.py activation)
- **Issue:** `test_preexisting_install_gets_version_1` created a store (which seeds version to `2.0.0` for an empty DB), then inserted an entity row, then re-opened — but the version was already `2.0.0`, not `1.0.0`, so the assertion failed.
- **Fix:** After first store init, delete the version key via sqlite3, then insert an entity row, then re-open. Re-opening runs `INSERT OR IGNORE` (inserts `1.0.0`), then entity count = 1 so step-2 upgrade is skipped.
- **Files modified:** tests/unit/test_graph_versioning.py
- **Verification:** Test passes with version `1.0.0`
- **Committed in:** 962daed (Task 2 commit)

**4. [Rule 1 - Bug] test_system_kv_not_clobbered used '1.0.0' as sentinel**
- **Found during:** Task 2 (test_graph_versioning.py activation)
- **Issue:** Using `'1.0.0'` as the value to "protect" from clobbering — but the production upgrade step does `UPDATE ... WHERE key = 'graph_schema_version' AND value = '1.0.0'` when entity count = 0. The sentinel was being overwritten to `2.0.0` by the upgrade path.
- **Fix:** Changed sentinel to `'custom-version'` which is immune to the upgrade UPDATE (only fires for `value = '1.0.0'`).
- **Files modified:** tests/unit/test_graph_versioning.py
- **Verification:** Test passes; sentinel preserved as `'custom-version'`
- **Committed in:** 962daed (Task 2 commit)

---

**Total deviations:** 4 auto-fixed (all Rule 1 - Bug)
**Impact on plan:** All fixes necessary for tests to correctly exercise the production behavior. No scope creep — the test intent was preserved, only the implementation corrected to match actual production APIs.

## Issues Encountered
- The wave-0 stub tests were written speculatively before the production code existed, so several API assumptions were wrong (tuple return, string vs list tags, missing required fields, seeding behavior). All resolved by reading production code before writing test bodies.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All P26 requirements (P26-T01 through P26-T05) have automated coverage
- Phase 26 is fully complete: schema extended, version seeding, perimeter extraction, loader wiring, GraphView rendering, and tests verified
- Phase 27 (Malcolm NSM integration) can proceed with confidence in graph infrastructure

---
*Phase: 26-graph-schema-versioning-and-perimeter-entities*
*Completed: 2026-04-07*
