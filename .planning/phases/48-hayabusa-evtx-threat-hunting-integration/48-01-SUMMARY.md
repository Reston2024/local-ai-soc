---
phase: 48-hayabusa-evtx-threat-hunting-integration
plan: "01"
subsystem: testing
tags: [tdd, hayabusa, evtx, wave-0, stubs]
dependency_graph:
  requires: []
  provides:
    - tests/unit/test_hayabusa_scanner.py
    - tests/integration/test_hayabusa_e2e.py
  affects:
    - Plan 48-02 (provides RED phase pass criteria)
tech_stack:
  added: []
  patterns:
    - "pytest.importorskip at module level for absent-module file skip"
    - "per-test @pytest.mark.skip for wave-0 stub isolation"
    - "pytest.mark.skipif on shutil.which for binary-gated integration tests"
key_files:
  created:
    - tests/unit/test_hayabusa_scanner.py
    - tests/integration/test_hayabusa_e2e.py
  modified:
    - pyproject.toml
decisions:
  - "pytest.importorskip at module level (not per-test) so entire unit file skips atomically when ingestion.hayabusa_scanner absent"
  - "hayabusa marker added to pyproject.toml markers list to avoid PytestUnknownMarkWarning"
  - "HAYABUSA_AVAILABLE checks both 'hayabusa' and 'hayabusa.exe' for Windows compatibility"
metrics:
  duration: "4 minutes"
  completed: "2026-04-14T20:25:47Z"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
---

# Phase 48 Plan 01: Hayabusa EVTX Threat Hunting — Wave 0 Test Stubs Summary

Wave 0 TDD RED phase: 6 unit stubs (HAY-01..HAY-06) and 1 integration stub (HAY-08) that SKIP cleanly, defining contracts for Plan 48-02 implementation.

## Objective

Establish the TDD RED phase for Hayabusa EVTX integration. Write failing test stubs that skip cleanly now (no implementation exists) and define the exact behaviour Plan 48-02 must satisfy.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write unit test stubs HAY-01 through HAY-06 | aa58fd1 | tests/unit/test_hayabusa_scanner.py |
| 2 | Write integration test stub HAY-08 | 55b6d4c | tests/integration/test_hayabusa_e2e.py, pyproject.toml |

## What Was Built

### tests/unit/test_hayabusa_scanner.py
6 unit test stubs covering:
- **test_record_mapping** (HAY-01): hayabusa_record_to_detection() returns DetectionRecord with hayabusa- rule_id, correct severity, T#### attack_technique
- **test_level_normalization** (HAY-02): _LEVEL_MAP maps crit/high/med/medium/low/info to severity strings; unknown defaults to medium
- **test_mitre_tag_filter** (HAY-03): Only T#### tags extracted; G#### and S#### entries excluded
- **test_no_binary** (HAY-04): scan_evtx() yields 0 records and does not raise when HAYABUSA_BIN is absent
- **test_dedup_skip** (HAY-05): HayabusaScanner.scan() returns 0 findings without calling subprocess when SHA-256 already in hayabusa_scanned_files
- **test_migration_idempotent** (HAY-06): SQLiteStore._run_migrations() twice on same in-memory db is safe; detection_source column exists

Module-level `pytest.importorskip("ingestion.hayabusa_scanner")` skips the entire file when the module does not exist. Per-test `@pytest.mark.skip` prevents accidental early execution.

### tests/integration/test_hayabusa_e2e.py
1 integration stub:
- **test_hayabusa_e2e_scan** (HAY-08): Gated on `shutil.which("hayabusa") or shutil.which("hayabusa.exe")` via `@pytest.mark.skipif`. `pytestmark = pytest.mark.hayabusa` ensures collection only under `-m hayabusa`.

### pyproject.toml
Added `hayabusa` to `[tool.pytest.ini_options]` markers list to prevent `PytestUnknownMarkWarning`.

## Verification Results

```
tests/unit/test_hayabusa_scanner.py    — 1 skipped (importorskip), 0 errors
tests/integration/test_hayabusa_e2e.py — 1 SKIP (binary not on PATH), 0 errors
tests/unit/ full suite                 — pre-existing failures only (test_auth, playbooks), 0 new regressions
```

## Deviations from Plan

None — plan executed exactly as written.

## Decisions Made

- `pytest.importorskip` used at module level per plan instructions (same as Phase 44/45 pattern). The whole file skips as 1 collected/skipped item when `ingestion.hayabusa_scanner` is absent.
- `hayabusa` marker registered in pyproject.toml to keep test output warning-free.
- `shutil.which("hayabusa.exe")` added alongside `shutil.which("hayabusa")` for Windows PATH compatibility (the binary ships as hayabusa.exe on Windows).

## Self-Check: PASSED

- FOUND: tests/unit/test_hayabusa_scanner.py
- FOUND: tests/integration/test_hayabusa_e2e.py
- FOUND: commit aa58fd1 (Task 1)
- FOUND: commit 55b6d4c (Task 2)
