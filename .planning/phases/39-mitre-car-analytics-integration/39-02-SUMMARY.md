---
phase: 39-mitre-car-analytics-integration
plan: "02"
subsystem: car-analytics
tags: [tdd, wave-1, car, sqlite, mitre, matcher]
dependency_graph:
  requires:
    - backend/data/car_analytics.json
    - tests/unit/test_car_store.py
  provides:
    - backend/services/car/__init__.py
    - backend/services/car/car_store.py
  affects:
    - backend/stores/sqlite_store.py (car_analytics column migration)
    - backend/main.py (CARStore init + seed task)
    - detections/matcher.py (CAR lookup in _sync_save)
tech_stack:
  added: []
  patterns:
    - CARStore pattern mirrors AttackStore (conn param, DDL, synchronous CRUD)
    - Idempotent ALTER TABLE migration (try/except pass)
    - asyncio.ensure_future for non-blocking seed task
    - Inline CAR lookup in _sync_save() using self.stores.sqlite._conn (avoids constructor change)
key_files:
  created:
    - backend/services/car/__init__.py
    - backend/services/car/car_store.py
  modified:
    - backend/stores/sqlite_store.py
    - backend/main.py
    - detections/matcher.py
decisions:
  - "CARStore uses direct sqlite3.Connection param (same pattern as AttackStore) — testable without SQLiteStore wrapper"
  - "CAR lookup in matcher.py placed inside _sync_save() tech_ids block — runs after ATT&CK tagging, gracefully skips on car_analytics table absent"
  - "seed_car_analytics uses asyncio.ensure_future (fire-and-forget) — same pattern as bootstrap_attack_data"
  - "data_path resolved via Path(__file__).parent.parent.parent / data — robust path regardless of cwd"
metrics:
  duration: "129 seconds (~2 min)"
  completed_date: "2026-04-11"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 3
---

# Phase 39 Plan 02: CARStore + Startup Wiring + Matcher Integration Summary

CARStore SQLite CRUD class implementing the CAR analytics catalog with DDL, bulk_insert, analytic_count, and get_analytics_for_technique; wired into startup lifespan with idempotent JSON seeding; car_analytics TEXT column migrated onto detections table; CAR lookup added to matcher.py save_detections() after ATT&CK technique tagging.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | CARStore class + module init (TDD GREEN) | ba0096c | backend/services/car/__init__.py, backend/services/car/car_store.py |
| 2 | SQLite migration + main.py wiring + matcher.py CAR lookup | bba90a3 | backend/stores/sqlite_store.py, backend/main.py, detections/matcher.py |

## Verification Results

1. `uv run pytest tests/unit/test_car_store.py -v` — 8 passed (all GREEN, no longer SKIP)
2. `uv run pytest tests/unit/ -x -q` — 1020 passed, 1 skipped (no regressions)
3. `uv run python -c "from backend.services.car.car_store import CARStore, seed_car_analytics; print('import OK')"` — PASSED
4. `uv run python -c "...PRAGMA table_info(detections)... assert 'car_analytics' in cols..."` — PASSED (migration OK)

## Key Technical Decisions

- **CARStore mirrors AttackStore pattern:** Accepts `sqlite3.Connection` directly; runs DDL in `__init__`; all methods synchronous. This ensures testability with in-memory SQLite and consistency with Phase 34 patterns.
- **CAR lookup inline in _sync_save():** Plan RESEARCH.md Pitfall 5 Option (b) — inline query using `self.stores.sqlite._conn` rather than passing `car_store` as a constructor param. Avoids changing `SigmaMatcher.__init__` signature and any test breakage.
- **Graceful degradation in matcher:** CAR lookup wrapped in `try/except` with `log.debug` — if `car_analytics` table doesn't exist (first boot race condition) or the query fails, detection saving continues normally.
- **asyncio.ensure_future for seed task:** Matches `bootstrap_attack_data` pattern from Phase 34 — non-blocking fire-and-forget, idempotent if called multiple times.
- **data_path resolution via `Path(__file__).parent.parent.parent / "data"`:** Robust to working directory changes; resolves to `backend/data/car_analytics.json`.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| backend/services/car/__init__.py | FOUND |
| backend/services/car/car_store.py | FOUND |
| backend/stores/sqlite_store.py (car_analytics migration) | FOUND |
| backend/main.py (CARStore wiring) | FOUND |
| detections/matcher.py (CAR lookup) | FOUND |
| Commit ba0096c (Task 1) | FOUND |
| Commit bba90a3 (Task 2) | FOUND |
| 8 test_car_store.py tests GREEN | PASSED |
| 1020 total unit tests GREEN | PASSED |
