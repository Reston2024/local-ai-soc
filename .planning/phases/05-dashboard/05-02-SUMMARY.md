---
phase: 05-dashboard
plan: "02"
subsystem: detection
tags: [threat-scoring, mitre-attack, python, pydantic, tdd]

# Dependency graph
requires:
  - phase: 05-00
    provides: xfail test stubs for P5-T11 through P5-T15 in test_phase5.py
  - phase: 04-02
    provides: Alert model base definition in backend/src/api/models.py
provides:
  - score_alert: additive 0-100 threat scoring (severity + sigma_hit + recurrence + graph_connectivity)
  - map_attack_tags: static ATT&CK lookup with 4 lookup paths returning tactic/technique dicts
  - Alert.threat_score and Alert.attack_tags fields (added in 05-01 but depended on here)
affects:
  - 05-03 (route wiring — uses score_alert and map_attack_tags for /alerts enrichment)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Additive capped scoring model: each component is independent and score = min(sum, 100)"
    - "graph_data=None guard: skip graph_connectivity to avoid O(n²) build_graph() during batch ingest"
    - "Static dict-based ATT&CK mapping with first-match-wins priority order"

key-files:
  created: []
  modified:
    - backend/src/detection/threat_scorer.py
    - backend/src/detection/attack_mapper.py

key-decisions:
  - "graph_data=None default skips graph_connectivity (+0) to avoid O(n²) cost in batch ingestion"
  - "attack_mapper first-match-wins priority: category > event_type > rule > source+severity"
  - "UUID regex (stdlib re, no external deps) detects sigma-sourced rules for +20 sigma_hit"
  - "Recurrence lookup: graceful no-op when alert.event_id not found in events list"

patterns-established:
  - "Threat scorer components: each is independent additive; cap at 100 with min()"
  - "ATT&CK mapper: separate module-level dicts per lookup type, combined in single function"

requirements-completed:
  - FR-5S-3
  - FR-5S-4

# Metrics
duration: 8min
completed: 2026-03-16
---

# Phase 5 Plan 02: Threat Scorer + ATT&CK Mapper Summary

**Additive 0-100 threat scoring via score_alert (4 components) and static MITRE ATT&CK tagging via map_attack_tags (4 lookup paths), making P5-T11 through P5-T15 pass.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-16T08:00:00Z
- **Completed:** 2026-03-16T08:08:00Z
- **Tasks:** 4 (RED confirm, GREEN threat_scorer, GREEN attack_mapper, VERIFY)
- **Files modified:** 2

## Accomplishments
- Implemented score_alert with additive model: severity points (0/10/20/30/40) + sigma_hit (+20 UUID rule) + recurrence (+10 if >= 3 events same host/IP) + graph_connectivity (+10 with graph_data). Capped at 100.
- Implemented map_attack_tags with 4 static lookup paths (category > event_type > rule > source+severity). First match wins; returns [] when no match.
- P5-T11 through P5-T15 all XPASS (were xfail stubs). 41 prior regression tests still pass.

## Task Commits

1. **GREEN: threat_scorer + attack_mapper implementation** - `ac35477` (feat)

## Files Created/Modified
- `backend/src/detection/threat_scorer.py` - Full score_alert implementation with 4-component additive model (50+ lines)
- `backend/src/detection/attack_mapper.py` - Static mapping table + map_attack_tags function (60+ lines)

## Decisions Made
- graph_data=None default: skips graph_connectivity component entirely to avoid O(n²) build_graph() cost during batch ingest. When None, contributes +0 to score.
- attack_mapper imports Alert/NormalizedEvent attributes via getattr() (duck typing) to avoid potential circular import issues while keeping module-level dicts.
- UUID pattern uses stdlib re only — no external dependency.
- Recurrence check: when alert.event_id not found in events list, gracefully contributes +0 (no crash).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- score_alert and map_attack_tags are ready for integration in Plan 03 (route wiring)
- Plan 03 will wire score_alert/map_attack_tags into POST /events and GET /alerts
- Alert model already has threat_score and attack_tags fields (added in Plan 01)

---
*Phase: 05-dashboard*
*Completed: 2026-03-16*
