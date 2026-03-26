---
phase: 09-intelligence-analyst-augmentation
plan: "01"
subsystem: intelligence
tags: [risk-scoring, anomaly-detection, mitre-attack, pure-functions, tdd]

# Dependency graph
requires:
  - phase: 09-00
    provides: xfail stub test files for intelligence modules (test_risk_scorer.py, test_anomaly_rules.py)
provides:
  - backend/intelligence/__init__.py package
  - score_entity(entity_id, events, detections, anomaly_flags) -> int 0-100
  - score_detection(severity, technique_id, anomaly_count) -> int 0-100
  - MITRE_WEIGHTS dict with critical/high/medium/low technique point values
  - enrich_nodes_with_risk_score(nodes, scored_entities) for Cytoscape graph nodes
  - ANOMALY_RULES list with ANO-001 through ANO-004 deterministic rules
  - check_event_anomalies(event) -> list[str] returning fired rule IDs
affects:
  - 09-03 (risk scoring API endpoint will call score_entity/score_detection)
  - 09-05 (dashboard will call enrich_nodes_with_risk_score for graph coloring)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Additive 0-100 integer scoring: component1 + component2 + ... capped with min(total, 100)"
    - "Pure-function intelligence modules: no I/O, no DB access, dict in / int or list out"
    - "Python dataclass for rule definitions: rule_id, name, description, check callable"
    - "TDD flow: xfail stubs exist first, implement to turn XPASS, then remove xfail markers"

key-files:
  created:
    - backend/intelligence/__init__.py
    - backend/intelligence/risk_scorer.py
    - backend/intelligence/anomaly_rules.py
  modified:
    - tests/unit/test_risk_scorer.py
    - tests/unit/test_anomaly_rules.py

key-decisions:
  - "Removed strict=True xfail markers after implementation — tests now pass cleanly rather than showing XPASS(strict) FAILED"
  - "MITRE_WEIGHTS as a plain dict (not enum/dataclass) — simple .get() lookup, easily extensible"
  - "ANO-003 masquerade check uses lowercase path substring match covering appdata, temp, tmp paths"

patterns-established:
  - "Pure intelligence modules: pure functions only, no I/O — enables unit testing without mocks"
  - "Additive scoring cap: each component capped individually, total capped at 100 via min()"

requirements-completed: [P9-T01, P9-T02, P9-T03, P9-T08]

# Metrics
duration: 3min
completed: 2026-03-26
---

# Phase 9 Plan 01: Intelligence Analyst Augmentation — Risk Scorer & Anomaly Rules Summary

**Additive 0-100 integer risk scorer with MITRE ATT&CK weights plus 4 deterministic anomaly rules (office-spawns-shell, process-masquerading, unusual-external-port) as pure Python functions**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-26T06:49:24Z
- **Completed:** 2026-03-26T06:51:49Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Implemented `backend/intelligence/risk_scorer.py` with MITRE_WEIGHTS dict, SEVERITY_BASE dict, `score_detection()`, `score_entity()`, and `enrich_nodes_with_risk_score()` — all pure functions returning integers or mutated node lists
- Implemented `backend/intelligence/anomaly_rules.py` with 4 AnomalyRule dataclasses (ANO-001 through ANO-004) and `check_event_anomalies()` returning fired rule IDs
- All 13 unit tests (8 risk scorer + 5 anomaly rules) pass; full unit suite shows 79 passed, 15 xfailed, 0 failed

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement risk_scorer.py** - `0618843` (feat)
2. **Task 2: Implement anomaly_rules.py** - `bd7aecc` (feat)

**Plan metadata:** (docs commit below)

_Note: TDD tasks — xfail stubs existed from 09-00 wave-0 baseline; implementation made them XPASS(strict), then xfail markers removed so tests pass cleanly._

## Files Created/Modified

- `backend/intelligence/__init__.py` - Package init (empty)
- `backend/intelligence/risk_scorer.py` - MITRE_WEIGHTS, SEVERITY_BASE, score_detection(), score_entity(), enrich_nodes_with_risk_score()
- `backend/intelligence/anomaly_rules.py` - AnomalyRule dataclass, ANOMALY_RULES list, check_event_anomalies()
- `tests/unit/test_risk_scorer.py` - Removed xfail markers (8 tests now pass)
- `tests/unit/test_anomaly_rules.py` - Removed xfail markers (5 tests now pass)

## Decisions Made

- Removed `strict=True` xfail markers after implementation rather than leaving as XPASS(strict)/FAILED — the stub contract is fulfilled, clean PASSED state is correct
- MITRE_WEIGHTS is a plain `dict[str, int]` — simplest structure for `.get()` lookups with default 0, easily extensible with more techniques
- ANO-003 (process masquerading) uses lowercase substring match on process_path covering `appdata`, `temp`, `tmp` — handles both `AppData\Local\Temp` and `AppData\Roaming` variants

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The xfail test files from 09-00 provided exact behavioral specifications. Implementation matched on first run.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `backend.intelligence` package fully importable and tested
- `score_entity()` and `score_detection()` ready for Plan 03 (API endpoint)
- `enrich_nodes_with_risk_score()` ready for Plan 05 (dashboard graph coloring)
- `check_event_anomalies()` ready for Plan 03 (event enrichment pipeline)

---
*Phase: 09-intelligence-analyst-augmentation*
*Completed: 2026-03-26*

## Self-Check: PASSED

- FOUND: backend/intelligence/__init__.py
- FOUND: backend/intelligence/risk_scorer.py
- FOUND: backend/intelligence/anomaly_rules.py
- FOUND: .planning/phases/09-intelligence-analyst-augmentation/09-01-SUMMARY.md
- FOUND commit: 0618843 (feat: risk_scorer.py)
- FOUND commit: bd7aecc (feat: anomaly_rules.py)
- FOUND commit: d7bd8f1 (docs: plan metadata)
