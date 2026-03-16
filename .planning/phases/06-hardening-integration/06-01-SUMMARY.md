---
phase: 06-hardening-integration
plan: "01"
subsystem: causality
tags: [python, entity-resolution, bfs, graph-traversal, normalization, causality]

# Dependency graph
requires:
  - phase: 06-00
    provides: "causality package stubs, test_phase6.py with 5 xfail tests for Plan 01"
provides:
  - "resolve_canonical_id — full entity normalization (host, user, process, ip, domain, file)"
  - "find_causal_chain — BFS traversal with depth cap and cycle detection"
affects:
  - 06-03-engine
  - 06-04-api-routes

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Entity canonical ID: <type>:<normalized_value> string (e.g. host:workstation01)"
    - "BFS with visited_event_ids set for O(n) cycle-safe traversal"
    - "FIELD_MAP + TYPE_PREFIX dicts for entity field lookup and prefix normalization"

key-files:
  created: []
  modified:
    - backend/causality/entity_resolver.py
    - backend/causality/attack_chain_builder.py

key-decisions:
  - "ip_src and ip_dst both normalize to ip: prefix — same host regardless of direction"
  - "host normalization: split on dot, take first segment (strips domain suffix WORKSTATION01.corp.com -> workstation01)"
  - "user normalization: backslash takes suffix (CORP\\jsmith -> jsmith), @ takes prefix (jsmith@corp.com -> jsmith)"
  - "BFS uses visited_event_ids set — prevents re-enqueueing events in circular graphs"
  - "ENTITY_FIELDS list drives _get_entity_ids — only 6 types used for chain linking (excludes file to avoid noise)"

patterns-established:
  - "Pattern 1: Canonical entity IDs enable case-insensitive matching without changing stored data"
  - "Pattern 2: BFS depth parameter allows attack chain builders to limit scope (max_depth=5 default)"

requirements-completed:
  - FR-6-entity-resolution
  - FR-6-attack-chain

# Metrics
duration: 5min
completed: 2026-03-16
---

# Phase 6 Plan 01: Entity Resolution + Attack Chain Builder Summary

**Canonical entity normalization (host/user/process/ip/domain/file) and BFS causal chain builder with depth cap and cycle detection replacing Phase 6 Wave 0 stubs**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-16T22:29:32Z
- **Completed:** 2026-03-16T22:34:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `resolve_canonical_id` implements 6 entity normalization rules with FIELD_MAP + TYPE_PREFIX lookup pattern
- Case folding: WORKSTATION01 and workstation01 both resolve to `host:workstation01`
- `find_causal_chain` BFS traverses events sharing canonical entity IDs, sorted by timestamp
- Depth cap (`max_depth`) and cycle detection (`visited_event_ids` set) both working — circular events complete in < 1s
- All 5 target tests (TestEntityResolver, TestEntityResolverCaseFolding, TestAttackChainBuilder, TestAttackChainDepthCap, TestAttackChainCycleDetection) XPASS
- Full suite: 41 passed + 35 xpassed + 8 xfailed (Plan 02-04 stubs) — no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement entity_resolver.py** - `f00e755` (feat)
2. **Task 2: Implement attack_chain_builder.py** - `a5d88df` (feat)

## Files Created/Modified
- `backend/causality/entity_resolver.py` - Full resolve_canonical_id with FIELD_MAP, TYPE_PREFIX, 6 normalization rules
- `backend/causality/attack_chain_builder.py` - find_causal_chain BFS with _get_entity_ids helper, depth cap, cycle detection

## Decisions Made
- `ip_src` and `ip_dst` both map to the `ip:` prefix so network events match regardless of direction
- File paths excluded from ENTITY_FIELDS in the chain builder to avoid over-linking unrelated events via common system files
- `visited_event_ids` set is the sole cycle-prevention mechanism — no separate cycle-detection algorithm needed because BFS with a visited set is inherently acyclic

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `resolve_canonical_id` and `find_causal_chain` are ready for Plan 02 (MITRE mapper + scoring) and Plan 03 (causality engine)
- The engine (Plan 03) calls `find_causal_chain` to build the ordered event sequence for `AttackChain` objects
- No blockers

---
*Phase: 06-hardening-integration*
*Completed: 2026-03-16*
