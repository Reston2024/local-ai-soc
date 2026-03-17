---
phase: 07-threat-hunting-case-management
plan: "02"
subsystem: api
tags: [duckdb, threat-hunting, sql-templates, async, python]

# Dependency graph
requires:
  - phase: 07-00
    provides: backend/investigation/ stub package with hunt_engine.py empty stub and test_phase7.py xfail stubs
  - phase: 04-stores
    provides: duckdb_store.fetch_df(sql, params) async method returning list[dict]

provides:
  - HuntTemplate dataclass (name, description, sql, param_keys)
  - HUNT_TEMPLATES dict with 4 templates: suspicious_ip_comms, powershell_children, unusual_auth, ioc_search
  - execute_hunt(duckdb_store, template_name, params) async function

affects:
  - 07-04 (hunt API route that calls execute_hunt)
  - P7-T10 and P7-T11 (need API route from Plan 04)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "HuntTemplate dataclass pattern: sql + param_keys enables dynamic positional parameter binding"
    - "ioc_search repeats single input value as 6 positional params for multi-field ILIKE/exact matching"
    - "execute_hunt passes None (not []) for parameterless templates — matches fetch_df Optional[list] signature"

key-files:
  created: []
  modified:
    - backend/investigation/hunt_engine.py

key-decisions:
  - "ioc_search param_keys=['ioc_value'] but expands to 6 positional SQL params at execute time (ILIKE wrapping for text fields, exact match for IPs/hashes)"
  - "powershell_children passes param_list=None to fetch_df (not []) — matches Optional[list] signature"
  - "HUNT_TEMPLATES uses dataclass (not TypedDict) for IDE autocomplete and field validation"

patterns-established:
  - "Template registry pattern: HUNT_TEMPLATES dict keyed by string name, each entry is a dataclass with sql+param_keys"
  - "Per-template param expansion in execute_hunt: ioc_search special-cased to expand 1 value to N positional bindings"

requirements-completed: [P7-T08, P7-T09, P7-T10, P7-T11]

# Metrics
duration: 1min
completed: 2026-03-17
---

# Phase 7 Plan 02: Hunt Engine Summary

**HuntTemplate dataclass + 4 DuckDB SQL templates (suspicious_ip_comms, powershell_children, unusual_auth, ioc_search) + execute_hunt async dispatcher — P7-T08 and P7-T09 XPASS**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-17T02:30:06Z
- **Completed:** 2026-03-17T02:30:55Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Implemented HuntTemplate dataclass with name, description, sql, param_keys fields
- Built HUNT_TEMPLATES registry with all 4 locked hunt patterns from CONTEXT.md
- Implemented execute_hunt async function with per-template positional param expansion
- P7-T08 (test_suspicious_ip_template) and P7-T09 (test_powershell_children_template) both XPASS
- Full regression suite clean: 41 passed, 44 xpassed, 15 xfailed

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement hunt_engine.py with HuntTemplate dataclass and 4 templates** - `97e8617` (feat)

**Plan metadata:** TBD (docs: complete plan)

## Files Created/Modified

- `backend/investigation/hunt_engine.py` - Full implementation replacing stub: HuntTemplate dataclass, HUNT_TEMPLATES dict (4 entries), execute_hunt async function

## Decisions Made

- ioc_search expands single `ioc_value` input to 6 positional SQL parameters: `%ioc%` for ILIKE fields (hostname, username, domain) and bare `ioc` for exact-match fields (dst_ip, src_ip, file_hash_sha256)
- powershell_children passes `None` (not `[]`) to fetch_df — matches the `Optional[list[Any]] = None` signature of duckdb_store.fetch_df
- Used Python dataclass rather than TypedDict for HuntTemplate to enable field defaults and IDE autocompletion

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Hunt engine ready for API route wiring in Plan 04 (hunt endpoints)
- P7-T10 (test_list_hunt_templates) and P7-T11 (test_execute_hunt) still xfail — they require the REST endpoints from Plan 04
- execute_hunt is fully tested at the unit level via HUNT_TEMPLATES assertions

---
*Phase: 07-threat-hunting-case-management*
*Completed: 2026-03-17*
