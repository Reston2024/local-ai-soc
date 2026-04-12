---
phase: 41-threat-map-overhaul
plan: "03"
subsystem: backend-osint-classification
tags: [osint, sqlite, classification, tor, ipsum, ipapi, tdd]
dependency_graph:
  requires: [41-01]
  provides: [ipsum-blocklist-store, tor-exit-store, ip-classification-methods]
  affects: [41-04]
tech_stack:
  added: []
  patterns: [tdd-red-green, asyncio-to-thread, sqlite-migration, daily-rate-limit-counter]
key_files:
  created: []
  modified:
    - backend/stores/sqlite_store.py
    - backend/services/osint.py
    - tests/unit/test_osint_classification.py
decisions:
  - "_parse_ipsum_line_local added as module-level helper in osint.py to avoid circular import (map.py imports osint.py indirectly)"
  - "bulk_insert_ipsum guards against empty entries list before DELETE — avoids wiping valid cached data on network failure"
  - "_ipapiis_calls_today counter checked BEFORE acquiring lock — quota guard is lock-free for fast-path rejection"
  - "bulk_insert_tor_exits uses INSERT OR IGNORE — idempotent; bulk_insert_ipsum uses INSERT OR REPLACE — tier updates allowed"
  - "Phase 41 DDL constants (_IPSUM_DDL, _TOR_DDL) defined at module level after _DDL string — consistent with CREATE IF NOT EXISTS pattern"
metrics:
  duration_minutes: 10
  completed_date: "2026-04-12"
  tasks_completed: 2
  files_modified: 3
  tests_added: 12
  tests_total: 1044
---

# Phase 41 Plan 03: OSINT IP Classification Extension Summary

**One-liner:** SQLiteStore gains ipsum_blocklist/tor_exit_nodes tables + 5 classification methods; OsintService gains _ipapi_is/_tor_exit_check/_ipsum_check/_refresh_tor_exit_list/_refresh_ipsum plus proxy/hosting/mobile fields in _geo_ipapi.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| TDD RED | Write failing osint classification tests | b9694c1 | tests/unit/test_osint_classification.py |
| 1 GREEN | SQLiteStore — new tables, migration, lookup methods | 53c21f5 | backend/stores/sqlite_store.py |
| 2 GREEN | OsintService — ip-api proxy fields, ipapi.is, ipsum, Tor exit | c64c837 | backend/services/osint.py |

## What Was Built

### SQLiteStore Extensions (backend/stores/sqlite_store.py)

**New DDL constants:** `_IPSUM_DDL` (ipsum_blocklist table: ip TEXT PK, tier INTEGER, fetched_date TEXT) and `_TOR_DDL` (tor_exit_nodes: ip TEXT PK, fetched_date TEXT).

**Phase 41 migrations in `__init__`:**
- `CREATE TABLE IF NOT EXISTS ipsum_blocklist` and `tor_exit_nodes`
- Idempotent ALTER TABLE loop for 5 new osint_cache columns: `ip_type`, `ipsum_tier`, `is_tor`, `is_proxy`, `is_datacenter`

**New methods:**
- `get_ipsum_tier(ip)` — returns int tier (1-8) or None
- `get_tor_exit(ip)` — returns row tuple or None
- `bulk_insert_ipsum(entries)` — daily cache invalidation + upsert; guards empty list
- `bulk_insert_tor_exits(ips, fetched_date)` — clears stale entries, INSERT OR IGNORE
- `set_classification_cache(ip, ip_type, ipsum_tier, is_tor, is_proxy, is_datacenter)` — UPDATE osint_cache row classification columns

### OsintService Extensions (backend/services/osint.py)

**New module-level additions:**
- `_ipapiis_lock`, `_IPAPIIS_INTERVAL = 0.1` — burst prevention
- `_ipapiis_calls_today: int = 0`, `_ipapiis_last_reset: str = ""` — daily quota counter
- `_tor_refresh_lock`, `_ipsum_refresh_lock` — prevent concurrent daily fetches
- `_parse_ipsum_line_local(line)` — parses `ip\ttier` format, skips comments/blank lines

**Extended `_geo_ipapi()`:** fields param now includes `proxy,hosting,mobile`; return dict includes `"proxy": bool`, `"hosting": bool`, `"mobile": bool`.

**New instance methods:**
- `_ipapi_is(ip)` — queries https://api.ipapi.is/?q=IP, returns is_datacenter/is_tor/is_proxy/is_vpn/asn_type/company_type dict; caps at 900 calls/day
- `_tor_exit_check(ip)` — asyncio.to_thread wrapper on get_tor_exit(); returns bool
- `_refresh_tor_exit_list()` — fetches https://check.torproject.org/torbulkexitlist via _tor_refresh_lock; silent on network failure
- `_ipsum_check(ip)` — asyncio.to_thread wrapper on get_ipsum_tier(); returns int | None
- `_refresh_ipsum()` — fetches stamparm/ipsum GitHub raw, parses via _parse_ipsum_line_local, bulk inserts via _ipsum_refresh_lock; silent on network failure

## Decisions Made

1. `_parse_ipsum_line_local` added as module-level helper in osint.py to avoid circular import (map.py imports osint.py indirectly via services)
2. `bulk_insert_ipsum` guards against empty entries list before DELETE — avoids wiping valid cached data on network failure
3. `_ipapiis_calls_today` counter checked BEFORE acquiring lock — quota guard is lock-free for fast-path rejection
4. `bulk_insert_tor_exits` uses INSERT OR IGNORE — idempotent; `bulk_insert_ipsum` uses INSERT OR REPLACE — tier updates allowed
5. Phase 41 DDL constants defined at module level after main `_DDL` string — consistent with CREATE IF NOT EXISTS pattern

## Verification

- `test_osint_classification.py`: 12/12 tests GREEN
- Full unit suite: 1044 passed, 3 skipped, 0 failures (up from 1033 pre-plan)

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `backend/stores/sqlite_store.py` — EXISTS, contains ipsum_blocklist, tor_exit_nodes, get_ipsum_tier, get_tor_exit, bulk_insert_ipsum, bulk_insert_tor_exits, set_classification_cache
- `backend/services/osint.py` — EXISTS, contains _ipapi_is, _tor_exit_check, _refresh_tor_exit_list, _ipsum_check, _refresh_ipsum, _parse_ipsum_line_local, api.ipapi.is, torbulkexitlist
- Commits b9694c1 (RED), 53c21f5 (Task 1 GREEN), c64c837 (Task 2 GREEN) — all present
