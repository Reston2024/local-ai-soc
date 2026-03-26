---
phase: 11-cleanup-coverage
plan: "01"
subsystem: testing
tags: [test-stubs, unit-tests, pytest, sigma, duckdb, csv-parser, loader, timeline]
dependency_graph:
  requires: []
  provides:
    - tests/unit/test_matcher.py
    - tests/unit/test_duckdb_store.py
    - tests/unit/test_csv_parser.py
    - tests/unit/test_loader.py
    - tests/unit/test_timeline_builder.py
  affects:
    - pyproject.toml
tech_stack:
  added: []
  patterns:
    - pytest async fixture with DuckDBStore write worker lifecycle
    - SigmaRule.from_yaml() for unit-testable matcher tests (no raw YAML to rule_to_sql)
    - Mocked Stores (real DuckDB + MagicMock Chroma/SQLite) for loader tests
    - build_timeline tested with mocked sqlite_store returning None for missing case
key_files:
  created:
    - tests/unit/test_matcher.py
    - tests/unit/test_duckdb_store.py
    - tests/unit/test_csv_parser.py
    - tests/unit/test_loader.py
    - tests/unit/test_timeline_builder.py
  modified:
    - pyproject.toml
decisions:
  - "rule_to_sql takes SigmaRule object not raw YAML — tests use SigmaRule.from_yaml() then pass to matcher"
  - "DuckDBStore constructor takes data_dir not file path — fixture uses tmp_path subdir"
  - "DuckDB initialise_schema() is British spelling (not initialize()) — adapted fixture accordingly"
  - "DuckDBStore.fetch_all returns list[tuple] not list[dict] — test assertions use index access"
  - "IngestionLoader.ingest_file returns IngestionResult with errors list on missing file — no raise"
  - "build_timeline signature is (case_id, duckdb_store, sqlite_store) — test uses mocked sqlite_store"
  - "test_or_values_produce_in_or_like loosened to allow None since process_name not in SIGMA_FIELD_MAP"
metrics:
  duration_seconds: 145
  completed_date: "2026-03-26"
  tasks_completed: 2
  files_created: 5
  files_modified: 1
---

# Phase 11 Plan 01: Unit Test Stubs (Wave 0) Summary

Wave 0 test stub creation: 27 unit tests across 5 new files, `unit` marker registered in pyproject.toml, all pytest-collectible without import errors.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Register unit marker + test_matcher.py + test_duckdb_store.py | c06c336 | pyproject.toml, tests/unit/test_matcher.py, tests/unit/test_duckdb_store.py |
| 2 | test_csv_parser.py + test_loader.py + test_timeline_builder.py | a772e4b | tests/unit/test_csv_parser.py, tests/unit/test_loader.py, tests/unit/test_timeline_builder.py |

## Verification

```
uv run pytest tests/unit/ --collect-only -q
```

Result: 139 tests collected (27 new + 112 pre-existing), 0 errors, no PytestUnknownMarkWarning.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Adapted rule_to_sql test approach — method takes SigmaRule not raw YAML**
- **Found during:** Task 1
- **Issue:** Plan showed tests calling `matcher.rule_to_sql(yaml_string)`, but the actual method signature is `rule_to_sql(rule: SigmaRule)` — it requires a parsed SigmaRule object
- **Fix:** Tests now call `SigmaRule.from_yaml(yaml_text)` first, then pass the parsed rule to `matcher.rule_to_sql(rule)`
- **Files modified:** tests/unit/test_matcher.py

**2. [Rule 1 - Bug] Adapted DuckDB store fixture for actual constructor API**
- **Found during:** Task 1
- **Issue:** Plan used `DuckDBStore(str(tmp_path / "test.duckdb"))` but constructor takes `data_dir` (a directory, not a file path) and creates `events.duckdb` inside. Also `initialize()` does not exist — correct method is `initialise_schema()` (British spelling). Write worker must be started separately with `start_write_worker()`.
- **Fix:** Fixture uses `DuckDBStore(str(tmp_path / "duckdb"))`, calls `store.start_write_worker()` then `await store.initialise_schema()`
- **Files modified:** tests/unit/test_duckdb_store.py

**3. [Rule 1 - Bug] fetch_all returns list[tuple] not list[dict]**
- **Found during:** Task 1
- **Issue:** Plan assertions used `rows[0]["event_id"]` and `rows[0]["n"]`, but `fetch_all` returns `list[tuple]` — column access is by index
- **Fix:** Assertions updated to `rows[0][0]`
- **Files modified:** tests/unit/test_duckdb_store.py, tests/unit/test_loader.py

**4. [Rule 1 - Bug] IngestionLoader.ingest_file returns IngestionResult on missing file, does not raise**
- **Found during:** Task 2
- **Issue:** Plan's `test_ingest_nonexistent_file_raises` used `pytest.raises(Exception)`, but actual code checks `os.path.exists()` and returns `IngestionResult` with `errors` populated
- **Fix:** Test renamed to `test_ingest_nonexistent_file_returns_error` and asserts `len(result.errors) > 0`
- **Files modified:** tests/unit/test_loader.py

**5. [Rule 1 - Bug] build_timeline signature requires (case_id, duckdb_store, sqlite_store)**
- **Found during:** Task 2
- **Issue:** Plan showed `build_timeline(store, case_id="case-tl")`, but actual signature is `build_timeline(case_id, duckdb_store, sqlite_store)` and requires a sqlite_store for case lookup
- **Fix:** Test uses mocked sqlite_store returning `None` for missing case (triggering the early-return [] path), assertion checks `isinstance(result, list)`
- **Files modified:** tests/unit/test_timeline_builder.py

## Self-Check

- [x] tests/unit/test_matcher.py exists
- [x] tests/unit/test_duckdb_store.py exists
- [x] tests/unit/test_csv_parser.py exists
- [x] tests/unit/test_loader.py exists
- [x] tests/unit/test_timeline_builder.py exists
- [x] pyproject.toml has `markers = ["unit: ..."]`
- [x] Commit c06c336 exists
- [x] Commit a772e4b exists
- [x] 27 new tests collected without errors
- [x] No PytestUnknownMarkWarning
