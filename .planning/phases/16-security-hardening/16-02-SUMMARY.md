---
phase: 16-security-hardening
plan: "02"
subsystem: dependency-management
tags: [pyproject, uv, ci, dev-deps, gitignore]
dependency_graph:
  requires: []
  provides: [dependency-groups-dev, ci-group-dev-install]
  affects: [pyproject.toml, .github/workflows/ci.yml, .gitignore]
tech_stack:
  added: []
  patterns: [uv dependency-groups, PEP 735]
key_files:
  created: []
  modified:
    - pyproject.toml
    - .github/workflows/ci.yml
    - .gitignore
decisions:
  - "httpx retained in main [dependencies] — runtime dep for OllamaClient (per locked Decision 5)"
  - "Used [dependency-groups] (PEP 735) not [project.optional-dependencies] — uv native, uv sync --group dev syntax"
  - "All three CI jobs (lint, test, dependency-audit) use uv sync --group dev for consistency"
metrics:
  duration_minutes: 8
  completed_date: "2026-03-31"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 3
---

# Phase 16 Plan 02: Dev Dependency Separation Summary

**One-liner:** Moved pytest, pytest-asyncio, pytest-cov, ruff from main dependencies into `[dependency-groups] dev` via PEP 735 and updated all three CI jobs to `uv sync --group dev`.

## What Was Built

Separated runtime and development dependencies in `pyproject.toml` so production installs no longer include test/lint tooling. Updated GitHub Actions CI to install the dev group for lint, test, and dependency-audit jobs. Removed a duplicate `.gitignore` entry.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Move dev deps to [dependency-groups], fix .gitignore | e47d271 | pyproject.toml, .gitignore |
| 2 | Update CI to install dev group | 173a807 | .github/workflows/ci.yml |

## Changes Made

### pyproject.toml
- Removed from `[dependencies]`: `pytest==9.0.2`, `pytest-asyncio==1.3.0`, `ruff==0.15.6`
- Kept in `[dependencies]`: `httpx==0.28.1` (runtime dep for OllamaClient)
- Removed `[project.optional-dependencies]` block entirely
- Added `[dependency-groups]` section with dev group containing: pytest, pytest-asyncio, pytest-cov, ruff

### .github/workflows/ci.yml
- lint job: `uv sync` → `uv sync --group dev` (ruff now in dev group)
- test job: `uv sync --extra dev` → `uv sync --group dev` (pytest-cov moved from optional-deps)
- dependency-audit job: `uv sync` → `uv sync --group dev` (consistent)
- Updated test job install step comment

### .gitignore
- Removed duplicate `.claude/settings.local.json` entry (was on lines 89 and 91)

## Verification

- `uv sync --group dev` resolves 133 packages without errors
- `uv run pytest tests/unit/ -q --tb=no` executes (510 passed; pre-existing failures unrelated to this plan)
- `grep "dependency-groups" pyproject.toml` confirms section present
- `grep -c "group dev" .github/workflows/ci.yml` returns 3

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- pyproject.toml exists with [dependency-groups] section: FOUND
- .gitignore has single .claude/settings.local.json entry: FOUND
- .github/workflows/ci.yml has 3x --group dev: FOUND
- Commit e47d271 exists: FOUND
- Commit 173a807 exists: FOUND
