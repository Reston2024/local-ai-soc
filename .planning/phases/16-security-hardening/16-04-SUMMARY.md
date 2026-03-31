---
phase: 16-security-hardening
plan: "04"
subsystem: ci
tags: [ci, frontend, typescript, svelte-check, build]
dependency_graph:
  requires: [16-02]
  provides: [frontend-ci-validation]
  affects: [.github/workflows/ci.yml]
tech_stack:
  added: [actions/setup-node@v4, Node 20]
  patterns: [parallel CI jobs, npm ci caching]
key_files:
  modified: [.github/workflows/ci.yml]
decisions:
  - "Node 20 chosen (LTS) over Node 18 minimum — better performance and longer support window"
  - "cache-dependency-path set to dashboard/package-lock.json for correct npm cache scoping"
  - "No needs: on frontend job — runs in parallel with lint, test, dependency-audit, secret-scan"
metrics:
  duration: "3m"
  completed: "2026-03-31"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
---

# Phase 16 Plan 04: Frontend CI Job Summary

Frontend CI validation job added — parallel npm ci + vite build + svelte-check on every push/PR using Node 20 and npm cache scoping.

## What Was Built

Added a `frontend` job to `.github/workflows/ci.yml` that runs in parallel with all existing jobs (lint, test, dependency-audit, secret-scan). The job installs Node 20, restores the npm cache keyed on `dashboard/package-lock.json`, runs `npm ci` for a clean install, `npm run build` (vite build), and `npm run check` (svelte-check with tsconfig). TypeScript errors and build failures now block PR merges.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add frontend CI job | 1a1b7d4 | .github/workflows/ci.yml |

## Verification Results

- `python -c "import yaml; ..."` confirms 5 jobs: `['lint', 'test', 'frontend', 'dependency-audit', 'secret-scan']`
- `frontend` job: name "Frontend (build + type-check)", runs-on ubuntu-latest, Node 20, no `needs:` field
- Steps verified: checkout, setup-node, Install dependencies, Build, Type-check (svelte-check)
- `dashboard/package.json` `"check"` script confirmed: `svelte-check --tsconfig ./tsconfig.json`
- ci.yml is valid YAML (yaml.safe_load succeeds)

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `.github/workflows/ci.yml` exists and contains `frontend` job
- Commit `1a1b7d4` verified in git log
- All success criteria met
