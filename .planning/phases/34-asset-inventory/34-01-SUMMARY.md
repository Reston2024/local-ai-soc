---
phase: 34-asset-inventory
plan: 01
subsystem: database
tags: [mitre-attack, sqlite, sigma, stix, att&ck, tagging, detection]

# Dependency graph
requires:
  - phase: 33-real-threat-intelligence
    provides: IocStore SQLite CRUD pattern (exact template used for AttackStore)
  - phase: detections/matcher.py
    provides: SigmaMatcher with save_detections() and _rule_yaml cache

provides:
  - AttackStore: SQLite CRUD for attack_techniques, attack_groups, attack_group_techniques, detection_techniques
  - bootstrap_from_objects(): STIX JSON → SQLite (filters revoked, sub-techniques, no external_ref)
  - actor_matches(): top-3 groups by technique overlap with High/Medium/Low confidence
  - extract_attack_techniques_from_rule(): pySigma tag → normalised T-ID list (case-insensitive, sub-technique parent)
  - scan_rules_dir_for_coverage(): T-ID → [rule_title] coverage map
  - matcher.py ATT&CK tagging: detection_techniques table populated on every Sigma rule fire

affects:
  - 34-02: heatmap API uses attack_techniques + detection_techniques
  - 34-03: actor matching API calls actor_matches()
  - 34-04: asset view may correlate detections to techniques

# Tech tracking
tech-stack:
  added: []
  patterns:
    - AttackStore wraps sqlite3.Connection directly (same as IocStore) — in-memory testable
    - pySigma SigmaRuleTag has separate .namespace and .name fields — full tag = namespace + "." + name
    - Detection technique tagging uses _detection_techniques cache dict on SigmaMatcher — populated in match_rule(), consumed in save_detections()
    - INSERT OR IGNORE pattern for all ATT&CK upserts (idempotent bootstrap)

key-files:
  created:
    - backend/services/attack/__init__.py
    - backend/services/attack/attack_store.py
    - tests/unit/test_attack_store.py
    - tests/unit/test_attack_tagging.py
  modified:
    - detections/matcher.py

key-decisions:
  - "pySigma SigmaRuleTag splits 'attack.t1059' into namespace='attack', name='t1059' — regex must match tag.name alone when namespace=='attack', not the full string"
  - "Detection technique tagging uses in-memory cache dict (_detection_techniques) on SigmaMatcher rather than re-parsing rule YAML in save_detections()"
  - "AttackStore owns DDL for detection_techniques table — matcher.py writes to it via self.stores.sqlite._conn after insert_detection()"
  - "actor_matches() uses overlap = |input ∩ group_techs| / |group_techs| (recall-style) — groups with 0 techniques skipped"
  - "scan_rules_dir_for_coverage() silently skips malformed .yml files — non-fatal for coverage scan use case"

patterns-established:
  - "Service layer wraps sqlite3.Connection directly (not SQLiteStore) for in-memory unit testability"
  - "Wave 0 stubs: all tests use skipif guard on import flag — SKIP not FAIL before implementation"

requirements-completed: [P34-T01, P34-T02]

# Metrics
duration: 6min
completed: 2026-04-10
---

# Phase 34 Plan 01: ATT&CK Data Layer Summary

**AttackStore SQLite CRUD + STIX bootstrap parser + Sigma tag extractor + detection-time technique tagging in matcher.py**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-10T11:04:30Z
- **Completed:** 2026-04-10T11:10:19Z
- **Tasks:** 3 (TDD: Wave 0 stubs → implementation → matcher integration)
- **Files modified:** 5

## Accomplishments

- AttackStore class with full SQLite CRUD: upsert_technique/group/group_technique, technique_count/group_count, bootstrap_from_objects (STIX filter logic), actor_matches (top-3 by overlap_pct with confidence labels), tag_detection_techniques
- extract_attack_techniques_from_rule() handles pySigma's namespace-split tag structure, case-insensitive matching, sub-technique parent extraction
- scan_rules_dir_for_coverage() builds T-ID → [rule_title] coverage map for heatmap (Plan 02)
- matcher.py now writes ATT&CK technique IDs to detection_techniques table on every Sigma rule fire — 11 unit tests pass, 925 unit tests green (no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 ATT&CK test stubs** - `54a45a4` (test)
2. **Task 2: AttackStore + STIX parser + Sigma tag extractor** - `5d9991e` (feat)
3. **Task 3: ATT&CK tagging in matcher.py** - `b5692ca` (feat)

## Files Created/Modified

- `backend/services/attack/__init__.py` - Package init (empty)
- `backend/services/attack/attack_store.py` - AttackStore class, DDL, extract_attack_techniques_from_rule, scan_rules_dir_for_coverage
- `tests/unit/test_attack_store.py` - 7 unit tests for AttackStore CRUD and actor_matches
- `tests/unit/test_attack_tagging.py` - 4 unit tests for tag extraction and coverage scan
- `detections/matcher.py` - Import extract_attack_techniques_from_rule; _detection_techniques cache; tagging in save_detections()

## Decisions Made

- **pySigma tag structure:** SigmaRuleTag has `.namespace` (e.g. "attack") and `.name` (e.g. "t1059") fields separately — regex must match `tag.name` when `tag.namespace == "attack"`, not the full "attack.t1059" string as assumed in the plan. Auto-fixed (Rule 1 — bug discovered during GREEN phase).
- **Technique tagging integration point:** matcher.py does not receive a sqlite3.Connection directly — uses `self.stores.sqlite._conn` (SQLiteStore private attr). Added `_detection_techniques` cache dict on SigmaMatcher to pass tech IDs from `match_rule()` to `save_detections()` without re-parsing YAML.
- **actor_matches overlap formula:** `|input ∩ group_techs| / |group_techs|` (recall-style) — groups with zero techniques are skipped to avoid division-by-zero.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] pySigma SigmaRuleTag splits tag into namespace + name fields**
- **Found during:** Task 2 (GREEN phase — test_extract_techniques failed with result=[])
- **Issue:** Plan pseudocode used `_TECH_RE.match(tag.name)` where `tag.name == "t1059"` — but regex pattern was `^attack\.(t\d{4})` which expects the full "attack.t1059" string. Result: empty list.
- **Fix:** Added `_TECH_NAME_RE = re.compile(r"^(t\d{4})(?:\.\d+)?$", re.IGNORECASE)` and updated `extract_attack_techniques_from_rule()` to construct `full_tag = f"{namespace}.{name}"` for primary match, then fallback to name-only match when namespace == "attack".
- **Files modified:** `backend/services/attack/attack_store.py`
- **Verification:** test_extract_techniques, test_tag_case_insensitive, test_subtechnique_tag all pass
- **Committed in:** `5d9991e` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in plan's assumed pySigma API)
**Impact on plan:** Essential correctness fix. No scope creep.

## Issues Encountered

- Pre-existing test failure: `tests/unit/test_config.py::test_cybersec_model_default` (OLLAMA_CYBERSEC_MODEL env var mismatch) — confirmed pre-existing, logged to deferred-items, out of scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- AttackStore is ready for Plan 02 (heatmap: GET /api/attack/coverage endpoint using attack_techniques + detection_techniques tables)
- actor_matches() is ready for Plan 03 (actor matching API)
- detection_techniques table is populated on every Sigma detection fire — heatmap data will accumulate in real-time
- bootstrap_from_objects() awaits Plan 03's lifespan STIX download task to populate technique/group data from MITRE CTI feed

---
*Phase: 34-asset-inventory*
*Completed: 2026-04-10*
