---
phase: 36-zeek-full-telemetry
plan: 01
subsystem: ingestion
tags: [zeek, duckdb, normalized-event, malcolm, schema-migration, conn, weird]

# Dependency graph
requires:
  - phase: 35-soc-completeness
    provides: NormalizedEvent 58-column schema with IOC fields
  - phase: 33-threat-intel
    provides: ioc_matched/ioc_confidence/ioc_actor_tag fields (positions 55-57)
provides:
  - NormalizedEvent 75-column schema with 17 Phase 36 Zeek fields (positions 58-74)
  - DuckDB _ECS_MIGRATION_COLUMNS with 17 new Zeek column entries
  - _INSERT_SQL extended to 75 ? placeholders
  - MalcolmCollector._normalize_conn() and _normalize_weird() methods
  - conn and weird poll blocks wired into _poll_and_ingest()
  - Wave 0 test stubs for all Plan 01 + Plan 02 normalizers
affects: [36-zeek-full-telemetry, plan-02]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Triple-fallback field access: nested dict -> dotted flat -> Arkime flat key"
    - "All 17 Zeek schema columns added in one plan to prevent INSERT_SQL desync"

key-files:
  created:
    - tests/unit/test_zeek_fields.py
    - tests/unit/test_zeek_normalizers.py
  modified:
    - backend/models/event.py
    - backend/stores/duckdb_store.py
    - ingestion/loader.py
    - ingestion/jobs/malcolm_collector.py
    - tests/unit/test_malcolm_collector.py
    - tests/unit/test_normalized_event.py
    - tests/unit/test_normalized_event_ecs.py

key-decisions:
  - "Triple-fallback pattern: zeek.conn.state nested -> zeek.conn.state dotted -> network.state Arkime flat (mandatory for all Zeek normalizers)"
  - "conn_orig_bytes uses source.bytes OR network.bytes (total fallback) since Arkime may not split by direction"
  - "conn_state: NULL when not present (not empty string) to distinguish missing from empty"
  - "All 17 Zeek columns added in single plan: prevents INSERT_SQL/to_duckdb_row desync discovered in prior phases"
  - "_normalize_weird always severity=high: unexpected protocol behavior is always high-priority"
  - "Legacy tests updated to 75-column count (Rule 1 auto-fix): test_normalized_event.py, test_normalized_event_ecs.py, test_malcolm_collector.py"

patterns-established:
  - "Triple-fallback field access for all Zeek normalizers"
  - "One plan adds all columns for a protocol family (prevents desync)"

requirements-completed: [P36-T01, P36-T02, P36-T03, P36-T09]

# Metrics
duration: 15min
completed: 2026-04-11
---

# Phase 36 Plan 01: Zeek Schema Foundation + conn/weird Normalizers Summary

**17-column DuckDB schema expansion (positions 58-74) with Zeek conn/weird normalizers using triple-fallback field access, _INSERT_SQL extended to 75 placeholders**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-11T04:55:00Z
- **Completed:** 2026-04-11T05:10:15Z
- **Tasks:** 3 (Task 0 + Task 1 + Task 2; Task 3 is human-action checkpoint)
- **Files modified:** 7

## Accomplishments
- NormalizedEvent expanded to 75 columns (17 new Zeek fields: conn, notice, weird, ssh, kerberos, ntlm, smb, rdp)
- _INSERT_SQL extended to 75 ? placeholders; to_duckdb_row() updated to return 75-element tuple
- _ECS_MIGRATION_COLUMNS extended with 17 Phase 36 ALTER TABLE entries; OCSF_CLASS_UID_MAP gets 22 Zeek event types
- _normalize_conn() and _normalize_weird() implemented with mandatory triple-fallback field access
- Both normalizers wired into _poll_and_ingest() with zeek_conn/zeek_weird cursor keys
- Wave 0 test stubs created: 8 zeek_fields tests (GREEN) + 16 normalizer tests (5 Plan 01 GREEN, 11 Plan 02 RED expected)

## Task Commits

Each task was committed atomically:

1. **Task 0: Wave 0 test stubs** - `e2a85e3` (test)
2. **Task 1: Schema expansion** - `437eca2` (feat)
3. **Task 2: conn/weird normalizers** - `1175178` (feat)

_Note: Tasks 1+2 are TDD (test RED → implementation GREEN)_

## Files Created/Modified
- `tests/unit/test_zeek_fields.py` - 8 schema sync tests (all GREEN after Task 1)
- `tests/unit/test_zeek_normalizers.py` - 16 normalizer stubs (5 GREEN after Task 2; 11 Plan 02 RED)
- `backend/models/event.py` - 17 new Zeek fields, 75-element to_duckdb_row(), 22 OCSF entries
- `backend/stores/duckdb_store.py` - 17 Phase 36 entries in _ECS_MIGRATION_COLUMNS
- `ingestion/loader.py` - _INSERT_SQL extended from 58 to 75 columns + placeholders
- `ingestion/jobs/malcolm_collector.py` - _normalize_conn(), _normalize_weird(), poll wiring, status counters
- `tests/unit/test_malcolm_collector.py` - Updated expected_keys from 6 to 8 cursor keys
- `tests/unit/test_normalized_event.py` - Updated len(row) from 58 to 75
- `tests/unit/test_normalized_event_ecs.py` - Updated len(row) from 58 to 75

## Decisions Made
- Triple-fallback pattern: `zeek.conn.state` nested dict → `zeek.conn.state` dotted flat → `network.state` Arkime flat (mandatory for all Zeek normalizers per plan spec)
- `conn_orig_bytes` uses `source.bytes` OR `network.bytes` as fallback (Arkime may not split by direction)
- All 17 Zeek columns added in single plan to prevent INSERT_SQL/to_duckdb_row desync
- `_normalize_weird` always severity=high (unexpected protocol behavior is always actionable)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated three legacy tests for 75-column tuple + 8 cursor keys**
- **Found during:** Task 2 (running full unit suite)
- **Issue:** test_normalized_event.py, test_normalized_event_ecs.py had hardcoded `len(row) == 58`; test_malcolm_collector.py expected only 6 cursor keys (now 8 with zeek_conn/zeek_weird)
- **Fix:** Updated all three tests to match the new 75-column schema and 8-cursor-key poll loop
- **Files modified:** tests/unit/test_malcolm_collector.py, tests/unit/test_normalized_event.py, tests/unit/test_normalized_event_ecs.py
- **Verification:** All 3 tests now pass (978 total unit tests green)
- **Committed in:** 1175178 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Necessary correctness fix for legacy tests broken by schema expansion. No scope creep.

## Issues Encountered
- Linter/formatter reverted `__init__` counter additions during Task 2 iteration; required re-applying edits separately. No functional impact.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Schema foundation complete; Plan 02 can implement http/ssl/notice/ssh/kerberos/ntlm/smb/rdp/dhcp/smtp/ftp normalizers
- Task 3 checkpoint (human-action): user must verify Malcolm SPAN port is active (curl to arkime_sessions3-* returns count > 0)
- Plan 02 test stubs already written and failing RED — ready for implementation
- 978 unit tests passing; 11 Plan 02 stubs remaining RED (expected)

---
*Phase: 36-zeek-full-telemetry*
*Completed: 2026-04-11*
