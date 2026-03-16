---
phase: 03-detection-rag
plan: "03"
subsystem: detection
tags:
  - sigma
  - detection
  - rules
  - python-callables
dependency_graph:
  requires:
    - 03-01
  provides:
    - sigma_loader.load_sigma_rules
    - _SIGMA_RULES integration in routes.py _store_event
    - suspicious_dns.yml Sigma rule
  affects:
    - backend/src/api/routes.py
    - backend/src/detection/
tech_stack:
  added:
    - PyYAML (sigma YAML parsing)
  patterns:
    - Sigma YAML -> Python callable compilation
    - field|contains modifier matching
    - Module-level rule pre-loading at import time
key_files:
  created:
    - backend/src/detection/sigma/suspicious_dns.yml
    - backend/src/detection/sigma_loader.py
  modified:
    - backend/src/api/routes.py
decisions:
  - "Direct Python attribute matching for Sigma rules (not pySigma DuckDB backend) — Phase 4 will add full SQL compilation"
  - "Alert.rule = YAML id UUID (not title) — enables stable rule references across renames"
  - "Module-level _SIGMA_RULES in routes.py with try/except — sigma failure must not crash ingestion"
  - "field|contains supports both list and scalar values — matches Sigma spec"
metrics:
  duration: "2m 23s"
  completed: "2026-03-16"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 1
  tests_passed: 41
  tests_added: 0
---

# Phase 3 Plan 03: Sigma Detection Layer Summary

Sigma detection layer delivering YAML-driven alert generation: suspicious_dns.yml rule compiled to a Python callable that fires Alert objects with UUID rule references, wired into routes.py _store_event alongside existing Python rules.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create sigma/ directory + suspicious_dns.yml | 71d810d | backend/src/detection/sigma/suspicious_dns.yml |
| 2 | Write sigma_loader.py + wire into routes.py | 768a279 | backend/src/detection/sigma_loader.py, backend/src/api/routes.py |

## What Was Built

### backend/src/detection/sigma/suspicious_dns.yml
Sigma rule file with:
- Fixed UUID id: `d4e5f6a7-b8c9-0d1e-2f3a-4b5c6d7e8f9a`
- `query|contains` matching against 3 domains from enricher.py SUSPICIOUS_DOMAINS
- level: high (maps to severity "high" in sigma_loader)
- condition: selection (only supported condition in Phase 3)

### backend/src/detection/sigma_loader.py
`load_sigma_rules()` scans the sigma/ directory and compiles each YAML rule to a `(NormalizedEvent) -> Alert | None` callable:
- Parses `field|modifier` syntax: supports `|contains` (list or scalar) and exact match
- `_FIELD_TO_ATTR` maps Sigma canonical names (e.g. `QueryName`) to NormalizedEvent attributes
- Alert.rule = YAML id UUID; Alert.severity = mapped from Sigma `level`
- Graceful degradation: missing directory or malformed YAML logs warning and skips, never raises
- Condition `selection` supported; unsupported conditions are logged and skipped

### backend/src/api/routes.py — _store_event integration
- Import added: `from backend.src.detection.sigma_loader import load_sigma_rules as _load_sigma_rules`
- Module-level `_SIGMA_RULES` populated once at import via `load_sigma_rules()` with try/except guard
- `_store_event` extended: after `evaluate(event)`, iterates `_SIGMA_RULES`, appends non-None results to `new_alerts` (individual rule exceptions swallowed to protect ingestion)

## Verification Results

```
uv run pytest backend/src/tests/test_phase3.py backend/src/tests/smoke_test.py backend/src/tests/test_phase2.py -v
41 passed in 0.26s
```

- P3-T3 (load_sigma_rules returns >= 1 callable): PASS
- P3-T4 (callable fires Alert for suspicious DNS query): PASS
- P3-T5 (alert.rule == UUID from YAML id): PASS
- P3-T6 (sigma alert visible in GET /alerts after POST /events): PASS
- P3-T6 alias (via /ingest batch): PASS
- All 32 pre-existing tests (smoke_test + test_phase2): PASS

```
1 sigma rules loaded
```

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Direct Python attribute matching (not pySigma DuckDB) | Phase 3 scope; full SQL compilation deferred to Phase 4 |
| Alert.rule = YAML UUID id field | Stable rule reference; survives title renames |
| Module-level _SIGMA_RULES with try/except | Sigma load failure must not crash backend startup |
| field|contains list support | Matches Sigma spec; suspicious_dns.yml uses list of 3 domains |

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- backend/src/detection/sigma/suspicious_dns.yml: FOUND
- backend/src/detection/sigma_loader.py: FOUND
- backend/src/api/routes.py contains _SIGMA_RULES: FOUND
- Commit 71d810d: FOUND
- Commit 768a279: FOUND
- 41 tests passing: VERIFIED
