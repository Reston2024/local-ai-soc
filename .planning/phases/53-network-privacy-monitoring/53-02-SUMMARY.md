---
phase: 53-network-privacy-monitoring
plan: "02"
subsystem: privacy-blocklist
tags: [tdd, wave-1, privacy, blocklist, schema-migration, zeek, sqlite]
dependency_graph:
  requires: [53-01]
  provides: [PRIV-01, PRIV-02, PRIV-03, PRIV-04, PRIV-11]
  affects: [53-03]
tech_stack:
  added: []
  patterns: [triple-fallback-zeek, sqlite-blocklist-store, sync-worker-pattern, module-level-wrapper-for-testability]
key_files:
  created:
    - backend/services/intel/privacy_blocklist.py
  modified:
    - backend/models/event.py
    - ingestion/loader.py
    - backend/stores/duckdb_store.py
    - backend/core/config.py
    - backend/stores/sqlite_store.py
    - ingestion/jobs/malcolm_collector.py
    - tests/unit/test_privacy_blocklist.py
    - tests/unit/test_normalized_event.py
    - tests/unit/test_normalized_event_ecs.py
decisions:
  - "to_duckdb_row() tuple is 80 elements (not 79 as plan stated) — [0]-[75] were already 76 elements (0-indexed), +4 new fields = 80; plan had off-by-one in its own count"
  - "_parse_disconnect() returns 2-tuples (domain, category) not 3-tuples — test stubs unpack with (d, _) / (_, c) pattern; plan pseudocode showing 3-tuples was inconsistent with stub expectations"
  - "_sync() is synchronous (not async) — Wave-0 stubs call worker._sync() without await; async run() wraps _safe_int via asyncio.to_thread for background operation"
  - "Module-level _normalize_http() wrapper added at bottom of malcolm_collector.py — test imports 'from ingestion.jobs.malcolm_collector import _normalize_http'; method doesn't use self so __new__ instantiation is safe"
  - "PRIV-11 test stub required source.ip in doc — _normalize_http returns None without src_ip; test updated to add minimal required field"
metrics:
  duration: "~15 minutes"
  completed_date: "2026-04-17"
  tasks_completed: 3
  tasks_total: 3
  files_created: 1
  files_modified: 8
---

# Phase 53 Plan 02: Blocklist Infrastructure and Schema Extension Summary

**One-liner:** Privacy blocklist SQLite store (EasyPrivacy + Disconnect.me), synchronous worker, 4-column DuckDB schema migration, and triple-fallback Zeek HTTP normalizer for cookie/pixel tracking detection.

## What Was Built

### Task 1: NormalizedEvent + DuckDB schema extension (commit de17312)

Four new Optional HTTP fields appended to `NormalizedEvent` after `anomaly_score`:

| Position | Field                  | Type          | Source                           |
|----------|------------------------|---------------|----------------------------------|
| [76]     | http_referrer          | Optional[str] | Referer header value             |
| [77]     | http_request_body_len  | Optional[int] | zeek.http.request_body_len       |
| [78]     | http_response_body_len | Optional[int] | zeek.http.response_body_len      |
| [79]     | http_resp_mime_type    | Optional[str] | zeek.http.resp_mime_types[0]     |

- `to_duckdb_row()` grows from 76 to 80 elements
- `_INSERT_SQL` in loader.py extended with 4 columns + 4 `?` placeholders (80 total)
- `_ECS_MIGRATION_COLUMNS` in duckdb_store.py gets 4 new `ALTER TABLE` entries

### Task 2: privacy_blocklist.py — PrivacyBlocklistStore + PrivacyWorker (commit ef88d0c)

New module `backend/services/intel/privacy_blocklist.py` (~190 lines):

- `_parse_easyprivacy(text)` — strips `!` comment lines and blanks, extracts `||domain^` rules via regex
- `_parse_disconnect(text)` — parses Disconnect services.json categories, returns `(domain, category)` 2-tuples
- `PrivacyBlocklistStore` — SQLite-backed store with `upsert_domain()`, `is_tracker()` (parent-domain walk), `get_feed_status()`
- `PrivacyWorker` — synchronous `_sync()` + async `run()` background loop with exponential backoff
- Privacy DDL also appended to `SQLiteStore.__init__` (`_PRIVACY_BLOCKLIST_DDL`) for shared-DB deployments
- 4 new `PRIVACY_*` settings added to `backend/core/config.py`

### Task 3: _normalize_http() extended with 4 new fields (commit f7b6a39)

`ingestion/jobs/malcolm_collector.py`:

- `_safe_int()` module-level helper added (converts safely to int, returns None on failure)
- `_normalize_http()` method extended with `zeek_http` dict extraction + triple-fallback for all 4 new fields
- Module-level `_normalize_http()` wrapper added at end of file for unit test imports
- PRIV-11 stub `test_normalize_http_extended_fields` turned GREEN (6/6 stubs now GREEN)

## Verification Results

```
tests/unit/test_privacy_blocklist.py - 6 passed
  test_parse_easyprivacy_extracts_domains      PASSED (PRIV-01)
  test_parse_disconnect_extracts_all_categories PASSED (PRIV-02)
  test_store_upsert_and_lookup                 PASSED (PRIV-03)
  test_worker_populates_store                  PASSED (PRIV-04)
  test_feed_meta_updated_after_sync            PASSED (PRIV-04b)
  test_normalize_http_extended_fields          PASSED (PRIV-11)

Full unit suite: 1265 passed, 8 skipped, 10 xfailed, 8 xpassed
Pre-existing failures (integration/security/eval): unchanged
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tuple count off-by-one: plan said 79, correct answer is 80**
- **Found during:** Task 1 verification
- **Issue:** Plan stated "was 75, +4 = 79" but position [75] anomaly_score means 76 elements (0-indexed 0-75 inclusive). +4 new fields = 80 total.
- **Fix:** Used 80 throughout; updated plan's verification command `assert len(t)==79` to `assert len(t)==80`
- **Files modified:** backend/models/event.py, tests/unit/test_normalized_event.py, tests/unit/test_normalized_event_ecs.py
- **Commit:** de17312

**2. [Rule 1 - Bug] _parse_disconnect returns 2-tuples, not 3-tuples**
- **Found during:** Task 2 (reading test stubs)
- **Issue:** Plan pseudocode showed `_parse_disconnect` returning `(domain, category, company)` 3-tuples, but test stubs unpack with `(d, _)` and `(_, c)` patterns (2-tuple). Using 3-tuples would cause `ValueError: too many values to unpack`.
- **Fix:** `_parse_disconnect` returns `list[tuple[str, str]]` (domain, category). Company info dropped for simplicity.
- **Files modified:** backend/services/intel/privacy_blocklist.py
- **Commit:** ef88d0c

**3. [Rule 1 - Bug] _sync() must be synchronous, not async**
- **Found during:** Task 2 (reading test stubs)
- **Issue:** Plan showed `async def _sync()` but stubs call `worker._sync()` without `await`. Calling an async method without `await` returns a coroutine — nothing executes, `upsert_domain.assert_called()` fails.
- **Fix:** Made `_sync()` synchronous; added async `run()` that wraps `self._sync` via `asyncio.to_thread()`
- **Files modified:** backend/services/intel/privacy_blocklist.py
- **Commit:** ef88d0c

**4. [Rule 2 - Missing] Module-level _normalize_http() wrapper needed for testability**
- **Found during:** Task 3 (stub expects `from ingestion.jobs.malcolm_collector import _normalize_http`)
- **Issue:** `_normalize_http` is a method on `MalcolmCollector`; test expects a module-level importable function.
- **Fix:** Added `def _normalize_http(doc)` at module level using `MalcolmCollector.__new__(MalcolmCollector)` (safe since method doesn't use self)
- **Files modified:** ingestion/jobs/malcolm_collector.py
- **Commit:** f7b6a39

**5. [Rule 1 - Bug] PRIV-11 test required src_ip in doc**
- **Found during:** Task 3 test execution
- **Issue:** `_normalize_http()` returns None when `src_ip` is absent (guard at top of method). Test would assert on None.http_referrer → AttributeError.
- **Fix:** Added `"source": {"ip": "10.0.0.1"}` to test doc to satisfy the src_ip requirement.
- **Files modified:** tests/unit/test_privacy_blocklist.py
- **Commit:** f7b6a39

## Self-Check: PASSED

- backend/services/intel/privacy_blocklist.py: FOUND
- backend/models/event.py (http_referrer field): FOUND
- ingestion/loader.py (http_referrer in _INSERT_SQL): FOUND
- backend/stores/duckdb_store.py (Phase 53 migration columns): FOUND
- backend/core/config.py (PRIVACY_BLOCKLIST_REFRESH_INTERVAL_SEC): FOUND
- Commit de17312: FOUND
- Commit ef88d0c: FOUND
- Commit f7b6a39: FOUND
