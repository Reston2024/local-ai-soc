---
phase: 10-compliance-hardening
plan: "05"
subsystem: dependencies
tags: [dependency-pinning, reproducibility, compliance, CIS-Controls-v8]
dependency_graph:
  requires: [10-02, 10-03, 10-04]
  provides: [exact-dep-pinning, reproducibility-receipt-verified, pytest-cov-available]
  affects: [pyproject.toml, uv.lock, REPRODUCIBILITY_RECEIPT.md]
tech_stack:
  added: [pytest-cov>=6.0.0 (dev optional dep)]
  patterns: [exact == version pinning from uv.lock, optional-dependencies dev group]
key_files:
  modified:
    - pyproject.toml
    - REPRODUCIBILITY_RECEIPT.md
  deleted:
    - backend/requirements.txt
decisions:
  - "Pinned pytest==9.0.2 (not 8.3.5 as in plan research — uv.lock is authoritative)"
  - "Pinned pySigma-backend-sqlite==1.1.3 (was >=0.1.0 — also pinned since it was loose)"
  - "Also pinned python-multipart==0.0.22 and sse-starlette==3.0.3 (both were >= and present in uv.lock)"
  - "qwen3:14b model not locally pulled; documented as 'see: ollama show --verbose qwen3:14b'"
  - "pip-audit not installed; documented baseline instructions instead of failing the task"
metrics:
  duration: ~10 minutes
  completed: 2026-03-26
  tasks_completed: 2
  files_modified: 2
  files_deleted: 1
---

# Phase 10 Plan 05: Dependency Pinning and Reproducibility Verification Summary

**One-liner:** Converted all 14 loose `>=` Python deps to `==` exact pins from uv.lock, deleted stale requirements.txt, and updated REPRODUCIBILITY_RECEIPT.md from BOOTSTRAPPING to VERIFIED with all TBD fields filled.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Pin dependencies in pyproject.toml, delete requirements.txt, add pytest-cov | 24bd9c6 | pyproject.toml (modified), backend/requirements.txt (deleted) |
| 2 | Update REPRODUCIBILITY_RECEIPT.md to VERIFIED status | bf5f9ca | REPRODUCIBILITY_RECEIPT.md |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Deviation] pytest version is 9.0.2, not 8.3.5**
- **Found during:** Task 1 — uv.lock lookup
- **Issue:** Plan research document listed pytest 8.3.5 but uv.lock contains 9.0.2 (already upgraded)
- **Fix:** Used uv.lock as authoritative source; pinned pytest==9.0.2
- **Files modified:** pyproject.toml

**2. [Rule 2 - Addition] pySigma-backend-sqlite also pinned**
- **Found during:** Task 1 — reviewing all dependencies
- **Issue:** pySigma-backend-sqlite was `>=0.1.0` (loose) and not listed in the plan's 12-package target
- **Fix:** Pinned to ==1.1.3 from uv.lock (same correctness goal applies to all direct deps)
- **Files modified:** pyproject.toml

**3. [Rule 2 - Addition] python-multipart and sse-starlette also pinned**
- **Found during:** Task 1 — reviewing all dependencies
- **Issue:** python-multipart (>=0.0.12) and sse-starlette (>=2.2.1) were loose and not in the plan's target list
- **Fix:** Pinned both to exact versions from uv.lock (0.0.22 and 3.0.3 respectively)
- **Files modified:** pyproject.toml

**4. [Expected] qwen3:14b not pulled locally**
- **Found during:** Task 2 — `ollama show --verbose qwen3:14b` returned "model not found"
- **Handled:** Documented as "see: ollama show --verbose qwen3:14b" per plan instructions
- **Files modified:** REPRODUCIBILITY_RECEIPT.md

**5. [Expected] pip-audit not installed**
- **Found during:** Task 2 — `uv run pip-audit` failed with "program not found"
- **Handled:** Added pip-audit baseline section with installation and usage instructions per plan instructions
- **Files modified:** REPRODUCIBILITY_RECEIPT.md

## Verification Results

```
uv run pytest tests/unit/ tests/security/ -q
99 passed, 2 xfailed, 16 xpassed, 7 warnings in 1.14s
```

All tests pass. Zero regressions from dependency pinning changes.

## Final State

- **pyproject.toml:** 14 packages now use `==` exact pins (was 12 loose `>=` specifiers; also pinned 2 additional loose deps found during review)
- **backend/requirements.txt:** Deleted (was stale, superseded by pyproject.toml + uv.lock)
- **REPRODUCIBILITY_RECEIPT.md:** Status = VERIFIED, date = 2026-03-26, zero TBD entries
- **uv sync:** Resolves cleanly with 114 packages, no conflicts

## Self-Check: PASSED

- pyproject.toml exists and has zero `>=` in dependencies: VERIFIED
- backend/requirements.txt does not exist: VERIFIED
- REPRODUCIBILITY_RECEIPT.md contains "VERIFIED" status: VERIFIED
- REPRODUCIBILITY_RECEIPT.md contains zero TBD entries: VERIFIED
- Commits 24bd9c6 and bf5f9ca exist in git log: VERIFIED
- Test suite: 99 passed, 0 failed: VERIFIED
