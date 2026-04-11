---
phase: 39-mitre-car-analytics-integration
plan: "01"
subsystem: car-analytics
tags: [tdd, wave-0, car, sqlite, mitre]
dependency_graph:
  requires: []
  provides:
    - backend/data/car_analytics.json
    - tests/unit/test_car_store.py
  affects:
    - backend/services/car/car_store.py (plan 02 contract)
tech_stack:
  added: []
  patterns:
    - skipif-importerror guard for RED TDD stubs
    - yaml.safe_load for MITRE CAR YAML parsing
    - urllib.request for GitHub API + raw file fetching
key_files:
  created:
    - scripts/generate_car_bundle.py
    - backend/data/car_analytics.json
    - tests/unit/test_car_store.py
  modified: []
decisions:
  - "Bundle deduplication by (analytic_id, technique_id) pair removes 1 duplicate from 159→158 entries"
  - "urllib.request used instead of httpx to avoid extra dependency — httpx was not installed in project venv"
  - "All 8 stubs use @pytest.mark.skipif(not _AVAILABLE) — clean SKIP (not ERROR) when CARStore absent"
  - "test_detection_enrichment_field calls get_analytics_for_technique directly rather than a helper — simpler and sufficient for the detection enrichment contract"
metrics:
  duration: "224 seconds (~4 min)"
  completed_date: "2026-04-11"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 0
---

# Phase 39 Plan 01: CAR Bundle + TDD Stubs Summary

CAR analytics JSON bundle (158 entries) generated from 102 MITRE CAR YAML files via GitHub API, plus 8 RED TDD stubs defining the CARStore contract for Plan 02.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Generate CAR analytics JSON bundle | 8b32824 | scripts/generate_car_bundle.py, backend/data/car_analytics.json |
| 2 | Write 8 RED TDD stubs for CARStore | f295bd2 | tests/unit/test_car_store.py |

## Verification Results

1. `uv run python -c "import json; d=json.load(open('backend/data/car_analytics.json')); assert len(d) >= 90; print('bundle OK:', len(d), 'entries')"` — PASSED (158 entries)
2. `uv run pytest tests/unit/test_car_store.py -v` — 8 SKIPPED (CARStore not yet implemented)
3. `uv run pytest tests/unit/ -x -q` — 1012 passed, 9 skipped, no regressions

## Key Technical Decisions

- **urllib.request instead of httpx:** httpx not installed in the project venv. stdlib urllib sufficient for sync HTTP fetching. Script handles rate limits with exponential backoff.
- **Deduplication by (analytic_id, technique_id):** CAR-2013-04-002 covers T1055 twice in its coverage array — deduplicated to one entry (159 raw → 158 final).
- **All 8 stubs SKIP cleanly:** Using `@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — CARStore not yet implemented")` ensures tests appear as SKIPPED not ERROR/FAIL until Plan 02 ships.
- **test_detection_enrichment_field uses direct get_analytics_for_technique call** rather than a separate helper — the helper pattern would introduce unnecessary abstraction at this stage.

## Bundle Structure

Each of 158 entries in `backend/data/car_analytics.json` has:
- `analytic_id` — e.g., "CAR-2020-09-001"
- `technique_id` — ATT&CK technique (e.g., "T1053")
- `title` — human-readable name
- `description` — full text description
- `log_sources` — comma-joined data_model_references
- `analyst_notes` — first non-Pseudocode implementation description
- `pseudocode` — first Pseudocode implementation code
- `coverage_level` — "Low" / "Moderate" / "High"
- `platforms` — JSON array string

## TDD Stub Coverage

| Stub | Requirement |
|------|------------|
| test_car_store_table_exists | P39-T01 (DDL) |
| test_bulk_insert_seeding | P39-T01 (bulk_insert) |
| test_analytic_count | P39-T01 (analytic_count) |
| test_get_analytics_for_technique | P39-T02 (technique lookup) |
| test_subtechnique_normalization | P39-T02 (sub-technique T1059.001 → T1059) |
| test_no_match_returns_empty | P39-T02 (no-match returns []) |
| test_detection_enrichment_field | P39-T03 (detection enrichment contract) |
| test_detection_no_technique_null | P39-T03 (None/"" handled gracefully) |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| backend/data/car_analytics.json | FOUND |
| scripts/generate_car_bundle.py | FOUND |
| tests/unit/test_car_store.py | FOUND |
| .planning/phases/39-mitre-car-analytics-integration/39-01-SUMMARY.md | FOUND |
| Commit 8b32824 (Task 1) | FOUND |
| Commit f295bd2 (Task 2) | FOUND |
