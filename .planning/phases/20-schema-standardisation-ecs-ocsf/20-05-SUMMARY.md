---
phase: 20-schema-standardisation-ecs-ocsf
plan: "05"
subsystem: ingestion
tags: [ecs, entity-graph, entity-extractor, graph-schema, unit-tests]

# Dependency graph
requires:
  - phase: 20-01
    provides: NormalizedEvent ECS fields (user_domain, process_executable, network_protocol, network_direction, event_outcome)
  - phase: 20-02
    provides: FieldMapper utility and loader SQL extension
provides:
  - entity_extractor.py propagates ECS fields into graph node attributes
  - graph/schema.py ENTITY_TYPES comments document ECS field alignment
  - test_entity_extractor_ecs.py verifies ECS field propagation (P20-T05)
affects:
  - graph layer (entity attributes enriched with ECS fields)
  - AI prompts that receive entity attribute context
  - future graph queries filtering on user_domain or network_protocol

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Conditional attribute inclusion: **({{field: value}} if value else {{}})" for optional ECS attributes in entity dicts"
    - "ECS alignment comments on schema constants for documentation without coupling"

key-files:
  created:
    - tests/unit/test_entity_extractor_ecs.py
  modified:
    - ingestion/entity_extractor.py
    - graph/schema.py

key-decisions:
  - "20-05: prompt files (analyst_qa, triage, threat_hunt, incident_summary) have no inline field-name documentation — left unchanged per plan spec"
  - "20-05: test uses extract_entities_and_edges() (actual function name) not extract_entities() (plan template name) — adapted test to match real API"
  - "20-05: network_direction also added to ip entity attributes alongside network_protocol (both are Optional ECS fields on NormalizedEvent)"

patterns-established:
  - "ECS attribute addition pattern: guarded by truthiness check, uses dict unpacking spread so absent fields produce zero keys"

requirements-completed: [P20-T05]

# Metrics
duration: 3min
completed: 2026-04-01
---

# Phase 20 Plan 05: ECS Field Propagation into Entity Graph Summary

**entity_extractor.py enriches user/process/ip graph nodes with ECS fields (user_domain, process_executable, network_protocol, network_direction) guarded by None-checks; graph/schema.py comments ECS field alignment; 4/4 new unit tests GREEN verifying end-to-end propagation**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-01T14:14:30Z
- **Completed:** 2026-04-01T14:17:30Z
- **Tasks:** 3
- **Files modified:** 3 (entity_extractor.py, graph/schema.py), 1 created (test_entity_extractor_ecs.py)

## Accomplishments

- entity_extractor.py user entity attributes now include `user_domain` when non-None
- entity_extractor.py process entity attributes now include `process_executable` when non-None
- entity_extractor.py ip entity attributes now include `network_protocol` and `network_direction` when non-None
- `connected_to` edge properties now include `network_protocol` and `event_outcome` when non-None
- graph/schema.py ENTITY_TYPES inline comments annotated with ECS field references (host.hostname, user.name/domain, process.name/pid/executable, network.protocol, dns.question.name, destination.ip)
- 4 new unit tests confirm ECS field propagation without requiring DuckDB or server stack (satisfies P20-T05)

## Task Commits

Each task was committed atomically:

1. **Task 1: Update entity_extractor.py to include ECS fields in attributes** - `52696bd` (feat)
2. **Task 2: Update graph/schema.py comments and prompt templates for ECS alignment** - `6f48c5b` (chore)
3. **Task 3: Add automated test for ECS field propagation into entity graph** - `7a1d4e4` (test)

## Files Created/Modified

- `ingestion/entity_extractor.py` - Added user_domain to user attrs, process_executable to process attrs, network_protocol/network_direction to ip attrs, network_protocol/event_outcome to connected_to edge props
- `graph/schema.py` - ECS field alignment comments on ENTITY_TYPES (comments only, no logic change)
- `tests/unit/test_entity_extractor_ecs.py` - 4 tests: user_domain, process_executable, network_protocol propagation, and absence-when-None guard

## Decisions Made

- Prompt files have no inline field-name documentation; left unchanged per plan instruction ("If a prompt file has NO field-name references in comments or docstrings, leave it unchanged")
- Test template in plan used `extract_entities()` but actual function is `extract_entities_and_edges()` — adapted test to match real API without changing implementation
- Added `network_direction` to ip entity attributes alongside `network_protocol` (both are Optional ECS fields; plan instruction listed both for the ip block)

## Deviations from Plan

None — plan executed exactly as written. The test function name adaptation (`extract_entities` to `extract_entities_and_edges`) was a template note in the plan itself ("adjust if the real return type differs").

## Issues Encountered

- Pre-existing test failures (90 failures in full suite) confirmed unchanged before and after this plan's changes — all related to unrelated API tests requiring running services.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ECS fields now flow from NormalizedEvent through entity_extractor into graph node attributes
- P20-T05 requirement satisfied with 4/4 automated tests
- graph/schema.py ECS comments provide documentation for future phases referencing entity types
- Phase 20 plan 05 complete — remaining plans in phase 20 may build on enriched entity attributes

---
*Phase: 20-schema-standardisation-ecs-ocsf*
*Completed: 2026-04-01*
