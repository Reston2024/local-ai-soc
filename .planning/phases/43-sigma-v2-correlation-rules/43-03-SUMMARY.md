---
phase: 43-sigma-v2-correlation-rules
plan: "03"
subsystem: detections
tags: [correlation, chain-detection, sqlite, yaml, tdd, python]

requires:
  - phase: 43-02
    provides: CorrelationEngine with _detect_chains stub, load_chains, SQLite dedup, ingest hook

provides:
  - detections/correlation_chains.yml with scan-bruteforce and recon-to-exploit chains
  - _detect_chains() + _query_chain() fully implemented (rule_ids and rule_tactics paths)
  - test_chain_detection, test_chain_yaml_loading, test_ingest_hook_calls_correlation GREEN
  - Empty-batch correlation engine invocation for chain fire without new events

affects:
  - 43-04
  - detect API
  - ingest pipeline

tech-stack:
  added: []
  patterns:
    - "Chain YAML config: detections/correlation_chains.yml defines chains declaratively; no code change needed to add new chains"
    - "SQLite GROUP BY + HAVING COUNT(DISTINCT rule_id) = N pattern for multi-rule co-fire detection"
    - "asyncio.to_thread with check_same_thread=False for SQLite connection in tests"

key-files:
  created:
    - detections/correlation_chains.yml
  modified:
    - detections/correlation_engine.py
    - ingestion/loader.py
    - tests/unit/test_correlation_engine.py

key-decisions:
  - "Correlation engine runs on empty event batches so chain detection fires from historical SQLite detections without requiring new events"
  - "rule_tactics matching path in _query_chain uses COUNT(DISTINCT attack_tactic) for tactic-diversity chains (recon-to-exploit)"
  - "Windows SQLite thread-safety: test uses check_same_thread=False; production SQLiteStore already handles this via asyncio.to_thread"

patterns-established:
  - "Chain detection: chains.yml declares rule_ids or rule_tactics; _query_chain dispatches correct SQL path"
  - "Chain entity_key populated from matched SQLite detection rows; matched_event_ids contains detection IDs (not event IDs)"

requirements-completed:
  - P43-T04
  - P43-T05

duration: 20min
completed: 2026-04-12
---

# Phase 43 Plan 03: Chain Detection — YAML Config, Chain Matching, Pre-built Chains Summary

**YAML-driven multi-stage chain correlation using SQLite co-fire queries, with scan-bruteforce and recon-to-exploit chains firing corr-chain-* critical detections**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-04-12T12:00:00Z
- **Completed:** 2026-04-12T12:20:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created `detections/correlation_chains.yml` with two pre-built chains: `scan-bruteforce` (corr-portscan + corr-bruteforce, 15 min window) and `recon-to-exploit` (corr-portscan + tactic discovery/execution)
- Implemented `_detect_chains()` and `_query_chain()` in `correlation_engine.py` — SQLite GROUP BY / HAVING COUNT(DISTINCT rule_id) = N pattern for co-fire detection; tactic-diversity path for recon-to-exploit
- All 9 correlation engine tests GREEN (0 FAILED); full unit suite 1067 passed, 0 failed
- Fixed `IngestionLoader.ingest_events()` to call correlation engine even on empty batches

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): TDD failing tests** - `c36ce1d` (test)
2. **Task 1 (GREEN): YAML + _detect_chains() implementation** - `99522cd` (feat)
3. **Task 2: Wire ingest hook + empty-batch fix** - `1ca4ebf` (feat)

## Files Created/Modified
- `detections/correlation_chains.yml` - YAML chain config with scan-bruteforce and recon-to-exploit
- `detections/correlation_engine.py` - Added _detect_chains() and _query_chain() replacing stub
- `ingestion/loader.py` - Correlation engine invocation moved outside empty-batch early return
- `tests/unit/test_correlation_engine.py` - Enabled test_chain_detection, test_chain_yaml_loading, test_ingest_hook_calls_correlation

## Decisions Made
- Correlation engine runs on empty event batches so chain detection fires from historical SQLite detections without requiring new events in the current batch
- Used `check_same_thread=False` in test SQLite connections (asyncio.to_thread runs in worker thread); production SQLiteStore already handles this
- recon-to-exploit chain uses `rule_tactics` path querying `attack_tactic` column — allows matching any detection with matching tactic rather than requiring specific rule_ids

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Windows SQLite thread-safety in test**
- **Found during:** Task 1 (GREEN phase — test_chain_detection)
- **Issue:** `asyncio.to_thread` runs SQLite queries in a worker thread; `sqlite3.connect()` in test used default `check_same_thread=True`, raising `sqlite3.ProgrammingError`
- **Fix:** Added `check_same_thread=False` to test's `sqlite3.connect()` call
- **Files modified:** `tests/unit/test_correlation_engine.py`
- **Verification:** test_chain_detection PASSED after fix
- **Committed in:** `99522cd` (Task 1 feat commit)

**2. [Rule 1 - Bug] Empty-batch early return blocked correlation**
- **Found during:** Task 2 (test_ingest_hook_calls_correlation)
- **Issue:** `ingest_events([])` returned early before reaching Step 5 (correlation engine call), so mock_engine.run() was never called
- **Fix:** Added correlation engine invocation inside the `if not events` early-return guard before returning
- **Files modified:** `ingestion/loader.py`
- **Verification:** test_ingest_hook_calls_correlation PASSED
- **Committed in:** `1ca4ebf` (Task 2 feat commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both fixes necessary for test correctness. The empty-batch fix also improves production behavior — chains can fire from accumulated detections even when no new events arrive.

## Issues Encountered
None beyond the two auto-fixed deviations above.

## Next Phase Readiness
- Chain detection fully operational; chains fire corr-chain-* critical detections in SQLite
- correlation_chains.yml is the extension point — adding new chains requires only YAML edits
- Plan 43-04 can extend the correlation API or frontend to surface chain detections

---
*Phase: 43-sigma-v2-correlation-rules*
*Completed: 2026-04-12*
