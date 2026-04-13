---
phase: 45-agentic-investigation
plan: "02"
subsystem: agentic-investigation
tags: [smolagents, tools, duckdb, sqlite, chromadb, tdd-green]
dependency_graph:
  requires: [45-01]
  provides: [agent-tools-implementation]
  affects: [45-03, 45-04]
tech_stack:
  added: []
  patterns: [smolagents-Tool-subclass, synchronous-read-only-db, nullable-inputs-pattern, contextmanager-sqlite]
key_files:
  created:
    - backend/services/agent/__init__.py
    - backend/services/agent/tools.py
  modified: []
decisions:
  - "nullable: True added to all inputs with defaults (smolagents validates forward() signature against inputs dict — any Optional/defaulted param must have nullable: True in inputs)"
  - "contextmanager _sqlite_read() wraps sqlite3.connect to ensure close() on Windows file lock release"
  - "SearchSimilarIncidentsTool calls client._system.stop() in finally block to release chromadb SQLite file handles on Windows"
  - "SearchSigmaMatchesTool queries detections without hostname column (actual schema has no hostname on detections table) — returns all recent detections within 24h window"
  - "EnrichIpTool parses result_json blob from osint_cache (actual schema) plus Phase 41 classification columns (is_proxy, is_datacenter, is_tor, ipsum_tier)"
  - "GetGraphNeighborsTool uses entities.name (not entity_value) and edges table (not entity_edges) matching actual SQLite schema"
metrics:
  duration_minutes: 6
  completed_date: "2026-04-13T03:29:34Z"
  tasks_completed: 1
  tasks_total: 1
  files_created: 2
  files_modified: 0
---

# Phase 45 Plan 02: Agent Investigation Tools Summary

**One-liner:** 6 synchronous smolagents Tool subclasses implemented with read-only DuckDB/SQLite/Chroma connections, nullable inputs pattern, and Windows-safe file handle cleanup.

## What Was Done

### Task 1: Create backend/services/agent/__init__.py and tools.py with 6 Tool subclasses

Created package init and full tools.py (330+ lines):

**QueryEventsTool** (`db_path` arg):
- Builds DuckDB `WHERE` clause for hostname/process_name/event_type filters
- `duckdb.connect(read_only=True)` + `SET enable_external_access = false`
- Returns: `"N events found — type1: K, type2: M"` or graceful no-results message

**GetEntityProfileTool** (`db_path` arg):
- Queries event count, unique dst_ips, top 5 processes, anomaly score min/max/avg
- Returns: `"Entity profile for HOST: N total events, K unique IPs, top processes: ..."` 

**EnrichIpTool** (`sqlite_path` arg):
- Reads `osint_cache.result_json` blob + Phase 41 classification columns
- Returns: `"IP X.X.X.X: country=US | org=... | proxy=YES | ipsum_threat_tier=3"`
- Graceful: returns `"No OSINT data cached"` when table missing or no row

**SearchSigmaMatchesTool** (`sqlite_path` arg):
- Queries `detections` last 24h (no hostname column in actual schema — returns all recent)
- Returns: `"N Sigma detection(s):\n  * rule_id (severity=high, technique=T1234)"`

**GetGraphNeighborsTool** (`sqlite_path` arg):
- Looks up entity by `entities.name`, then traverses `edges` to `target_id`
- Returns: `"Graph neighbors for HOST (host):\n  -> IP (network) via network_connection"`

**SearchSimilarIncidentsTool** (`chroma_path` arg):
- `chromadb.PersistentClient(path=...)` + `get_collection("feedback_verdicts")`
- Returns top-3 similar incidents with verdict + similarity %
- Calls `client._system.stop()` in finally for Windows file handle release

**Deviations resolved (Rule 1 - auto-fix):**
- `nullable: True` missing from `limit` inputs — smolagents validates `Optional`/defaulted forward() params against inputs dict; added `nullable: True` to all `limit` inputs and changed `limit: int = N` to `limit: Optional[int] = None`
- sqlite3 file lock on Windows — replaced inline `connect()/close()` with `_sqlite_read()` context manager
- chromadb file lock on Windows — added `client._system.stop()` in `finally` block in `SearchSimilarIncidentsTool`

## Verification

```
tests/unit/test_agent_tools.py::TestQueryEventsTool::test_returns_string PASSED
tests/unit/test_agent_tools.py::TestQueryEventsTool::test_hostname_filter PASSED
tests/unit/test_agent_tools.py::TestGetEntityProfileTool::test_returns_string PASSED
tests/unit/test_agent_tools.py::TestEnrichIpTool::test_returns_string PASSED
tests/unit/test_agent_tools.py::TestSearchSigmaMatchesTool::test_returns_string PASSED
tests/unit/test_agent_tools.py::TestGetGraphNeighborsTool::test_returns_string PASSED
tests/unit/test_agent_tools.py::TestSearchSimilarIncidentsTool::test_returns_string PASSED

7 passed in 0.68s

Full suite: 1088 passed, 8 skipped, 9 xfailed, 7 xpassed, 8 warnings in 34.88s
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] smolagents nullable validation for defaulted inputs**
- **Found during:** Task 1 (first test run)
- **Issue:** smolagents `validate_arguments()` checks that any forward() param whose Python type generates `nullable` in JSON schema (i.e. Optional or has default) must also have `nullable: True` in the inputs dict. All `limit` params failed this check.
- **Fix:** Added `"nullable": True` to all `limit` input definitions; changed `limit: int = N` to `limit: Optional[int] = None` in all forward() signatures
- **Files modified:** backend/services/agent/tools.py
- **Commit:** 5da4ac6

**2. [Rule 1 - Bug] sqlite3 file lock on Windows in EnrichIpTool/SearchSigmaMatchesTool/GetGraphNeighborsTool**
- **Found during:** Task 1 (test cleanup failures on Windows temp dirs)
- **Issue:** `sqlite3.connect(); conn.close()` pattern left file locks on Windows; temp dir cleanup raised `PermissionError: [WinError 32]`
- **Fix:** Added `_sqlite_read()` context manager with guaranteed `conn.close()` in finally block
- **Files modified:** backend/services/agent/tools.py
- **Commit:** 5da4ac6

**3. [Rule 1 - Bug] chromadb file lock on Windows in SearchSimilarIncidentsTool**
- **Found during:** Task 1 (test cleanup failure in TestSearchSimilarIncidentsTool)
- **Issue:** `chromadb.PersistentClient` holds sqlite3 file handles; temp dir cleanup failed
- **Fix:** Added `client._system.stop()` in finally block to release all chromadb file handles
- **Files modified:** backend/services/agent/tools.py
- **Commit:** 5da4ac6

## Self-Check: PASSED

- backend/services/agent/__init__.py: FOUND
- backend/services/agent/tools.py: FOUND
- Commit 5da4ac6: FOUND
