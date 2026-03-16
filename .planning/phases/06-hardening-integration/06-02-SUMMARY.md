---
phase: 06-hardening-integration
plan: "02"
subsystem: detection
tags: [mitre-attck, sigma, scoring, causality, python]

# Dependency graph
requires:
  - phase: 06-00
    provides: causality stub modules + TDD red baseline for Phase 6
  - phase: 06-01
    provides: entity_resolver + attack_chain_builder implementations
provides:
  - TECHNIQUE_CATALOG with 27 ATT&CK entries covering all 11 tactics
  - map_techniques Sigma tag parser (attack.tXXXX) with event_type/category fallback
  - score_chain additive 0-100 model (severity + techniques + chain length + recurrence)
affects: [06-03, causality engine]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sigma tag parse: attack.tXXXX -> T-ID via string prefix stripping + TECHNIQUE_CATALOG lookup"
    - "Additive scoring with per-component caps (same pattern as threat_scorer.py Phase 5)"
    - "Graceful fallback: event_type/category lookup when no Sigma tags match"

key-files:
  created: []
  modified:
    - backend/causality/mitre_mapper.py
    - backend/causality/scoring.py

key-decisions:
  - "27-entry TECHNIQUE_CATALOG indexes by T-ID (not category) — supports direct Sigma tag lookups"
  - "Fallback map keyed by lowercase event_type/alert_category string — first match wins, consistent with attack_mapper.py Phase 5 pattern"
  - "score_chain: severity component uses max (not sum) across all chain alerts — worst threat wins"
  - "Recurrence threshold: entity in 3+ events earns +20 pts — same entity-recurrence signal as Phase 4 correlation engine"

patterns-established:
  - "Sigma tag parsing: tag.lower().startswith('attack.t') -> strip prefix -> uppercase -> catalog lookup"
  - "Additive capped scoring: each component capped independently before summing, then min(score, 100)"

requirements-completed: [FR-6-mitre-mapper, FR-6-scoring]

# Metrics
duration: 5min
completed: 2026-03-16
---

# Phase 6 Plan 02: MITRE ATT&CK Mapper + Chain Scoring Summary

**27-entry ATT&CK TECHNIQUE_CATALOG with Sigma tag parser and additive 0-100 chain scorer covering all 11 tactics**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-16T22:32:00Z
- **Completed:** 2026-03-16T22:33:44Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Replaced mitre_mapper.py stub with full TECHNIQUE_CATALOG (27 entries, all 11 ATT&CK tactics), Sigma tag parser, and event_type/category fallback map
- Replaced scoring.py stub with additive 0-100 score_chain (severity 40 + techniques 20 + chain length 20 + recurrence 20)
- TestMitreMapper, TestMitreMapperGraceful, TestScoring all XPASS (5/5 target tests); 41 passed + 37 xpassed + 6 xfailed in full suite (zero regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1 + 2: mitre_mapper.py + scoring.py** - `11246af` (feat)

**Plan metadata:** (docs commit follows)

_Note: TDD tasks implemented together in single GREEN commit since both stubs replaced in one implementation pass._

## Files Created/Modified

- `backend/causality/mitre_mapper.py` - TECHNIQUE_CATALOG (27 entries), _FALLBACK_MAP, map_techniques function
- `backend/causality/scoring.py` - score_chain additive 0-100 model with 4 components

## Decisions Made

- 27-entry TECHNIQUE_CATALOG indexed by T-ID: supports direct Sigma tag lookups and future engine.py composition
- Fallback map uses first-match-wins on lowercase event_type then alert_category: consistent with attack_mapper.py Phase 5
- score_chain severity component takes max across all chain alerts (not sum): worst threat in chain is the signal that matters
- Recurrence at 3+ events (+20 pts): mirrors Phase 4 correlation engine's entity-recurrence heuristic

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- mitre_mapper.py and scoring.py ready for consumption by causality/engine.py (Plan 03)
- engine.py calls map_techniques(alert.attack_tags + sigma_tags, event_type, category) and score_chain(chain_events, chain_alerts, techniques)
- No blockers for Plan 03

---
*Phase: 06-hardening-integration*
*Completed: 2026-03-16*
