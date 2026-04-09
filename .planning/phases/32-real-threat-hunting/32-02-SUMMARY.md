---
phase: 32-real-threat-hunting
plan: "02"
subsystem: osint
tags: [osint, ip-enrichment, rate-limiting, cache, sqlite, whois, geoip, virustotal, abuseipdb, shodan]

dependency_graph:
  requires:
    - "32-01"  # Hunt engine, SQLite hunts table, OSINT API key settings in config
  provides:
    - "backend/services/osint.py"         # OsintService, OsintResult, rate limiters
    - "backend/api/osint_api.py"          # GET /api/osint/{ip}
    - "osint_cache SQLite table"          # 24h TTL cache
  affects:
    - "backend/stores/sqlite_store.py"    # osint_cache table + get/set methods
    - "backend/main.py"                   # OSINT router registration
    - "pyproject.toml"                    # 3 new deps: python-whois, geoip2, shodan

tech_stack:
  added:
    - "python-whois==0.9.5"
    - "geoip2==4.8.1"
    - "shodan==1.31.0"
  patterns:
    - "asyncio.Lock module-level singletons for per-source rate limiting"
    - "asyncio.gather with return_exceptions=True for concurrent lookups"
    - "asyncio.to_thread for blocking library calls (whois, geoip2, shodan)"
    - "SQLite INSERT OR REPLACE for idempotent cache writes"

key_files:
  created:
    - backend/services/osint.py
    - backend/api/osint_api.py
    - tests/unit/test_osint_service.py
  modified:
    - backend/stores/sqlite_store.py
    - backend/main.py
    - pyproject.toml
    - uv.lock

decisions:
  - "_is_cache_valid uses timezone-aware datetime comparison — fromisoformat() with UTC fallback for naive timestamps"
  - "_sanitize_ip checks loopback before private to give loopback its own error message"
  - "Rate limiter sleeps inside the lock so concurrent callers queue and wait, not fail"
  - "enrich() runs all lookups via asyncio.gather; skipped sources use _async_none() coroutine for uniform gather interface"
  - "GeoIP mmdb absence logs warning once (module-level flag) then returns None silently on subsequent calls"
  - "OSINT router registered with graceful try/except in main.py — follows existing deferred-router pattern"

metrics:
  duration_seconds: 212
  completed_date: "2026-04-09"
  tasks_completed: 3
  files_created: 3
  files_modified: 4
  tests_added: 8
  unit_tests_total: 899
---

# Phase 32 Plan 02: OSINT Enrichment Service Summary

**One-liner:** Passive IP enrichment via WHOIS + AbuseIPDB + MaxMind GeoLite2 + VirusTotal + Shodan with 24h SQLite cache and per-source asyncio.Lock rate limiting.

## What Was Built

A read-only OSINT enrichment pipeline accessible at `GET /api/osint/{ip}`. Given any public IP address, the service concurrently queries up to five sources and returns aggregated enrichment data. Results are cached 24 hours in SQLite. All four external API keys are optional; missing keys cause that source to be gracefully skipped with no error propagation.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 0 | Write failing TDD stubs | 5e77bb6 | tests/unit/test_osint_service.py |
| 1 | OSINT service + dependencies + SQLite cache | f4932d6 | backend/services/osint.py, backend/stores/sqlite_store.py, pyproject.toml |
| 2 | OSINT API endpoint + router registration | d337477 | backend/api/osint_api.py, backend/main.py |

## Architecture

```
GET /api/osint/{ip}
  └─ osint_api.py → OsintService.enrich(ip)
       ├─ _sanitize_ip()   # reject private/loopback/invalid
       ├─ SQLiteStore.get_osint_cache()  # 24h TTL check
       ├─ asyncio.gather([_whois, _abuseipdb, _geo, _virustotal, _shodan])
       │    ├─ _whois: python-whois (no key)
       │    ├─ _abuseipdb: httpx + _abuse_lock (90s interval)
       │    ├─ _geo: geoip2 local mmdb (no API call)
       │    ├─ _virustotal: httpx + _vt_lock (15s interval)
       │    └─ _shodan: shodan SDK + _shodan_lock (1s interval)
       └─ SQLiteStore.set_osint_cache()  # persist result
```

## Key Decisions

1. **Rate limiters sleep inside the lock** — callers queue serially rather than failing on rate-limit errors. This prevents bursts from exhausting free-tier quotas while still serving every request.
2. **_async_none() coroutine for skipped sources** — allows `asyncio.gather` to receive a uniform list of awaitables regardless of which sources are configured.
3. **loopback checked before private** — `is_loopback` is a subset of `is_private` in Python's ipaddress module; checking loopback first ensures the correct error message.
4. **GeoIP missing-file warning deduplication** — module-level `_geo_warned_once` flag prevents log spam on every request when the mmdb file is absent.
5. **Deferred router pattern** — OSINT router follows the existing `try/except ImportError` pattern in main.py so the app starts even if the module has issues.

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

```
# All 8 OSINT unit tests pass
uv run pytest tests/unit/test_osint_service.py -q
8 passed in 0.05s

# Full unit suite — no regressions
uv run pytest tests/unit/ -q
899 passed, 1 skipped, 9 xfailed, 7 xpassed, 7 warnings in 22.29s

# Dependencies installed
import whois; import geoip2; import shodan  # all OSINT deps OK

# Rate limiters present
from backend.services.osint import _vt_lock, _abuse_lock, _shodan_lock  # OK
```

## Self-Check: PASSED

- [x] backend/services/osint.py exists
- [x] backend/api/osint_api.py exists
- [x] tests/unit/test_osint_service.py exists
- [x] Commits 5e77bb6, f4932d6, d337477 present in git log
- [x] osint_cache table in SQLiteStore DDL
- [x] get_osint_cache / set_osint_cache methods on SQLiteStore
- [x] OSINT router registered in backend/main.py
