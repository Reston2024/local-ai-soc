# Phase 8: Production Hardening & Live Telemetry — Research

**Researched:** 2026-03-17
**Domain:** osquery Windows live collection, production hardening, one-command Windows setup, regression guard
**Confidence:** HIGH (architecture derived from codebase inspection + official osquery docs; see sources)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Windows desktop only — no server, no cloud, no Kubernetes
- Native Ollama on Windows is the primary and only LLM runtime (not Docker Ollama)
- RTX 5080 GPU acceleration must be preserved and validated on each start
- Backend: FastAPI (Python 3.12 via uv)
- Structured storage: DuckDB (events) + SQLite (graph, cases, artifacts)
- Vector retrieval: Chroma PersistentClient
- Graph: Lightweight in-app graph model (no Neo4j)
- LLM: Native Ollama on Windows (host.docker.internal bridge)
- Dashboard: Svelte 5 SPA served via FastAPI static files + Caddy HTTPS
- Localhost HTTPS via Docker + Caddy must be preserved; `curl -k https://localhost/health` must return 200
- No autonomous blocking, quarantine, or destructive response actions
- All analyst-facing conclusions must remain grounded in stored evidence
- No silent removals or placeholder-only completions
- osquery is the preferred Windows telemetry collection mechanism
- Live osquery collection must write into the existing DuckDB normalized_events table
- Fixture-driven ingestion remains valid alongside live ingestion
- REJECTED: Wazuh, Elastic, Kafka, Neo4j, Kubernetes, Velociraptor fleet, open-webui

### Claude's Discretion
- Exact scope decomposition into plans (what's done in parallel vs. sequential)
- Whether live osquery integration is achievable in Phase 8 or should be a sub-phase
- Test strategy for live telemetry (mock osquery vs. real daemon)
- Any additional hardening tasks identified by inspecting the current codebase
- Documentation updates required to reflect Phase 8 additions

### Deferred Ideas (OUT OF SCOPE)
- Velociraptor fleet management
- open-webui companion UI
- Multi-host osquery fleet
- Kubernetes deployment
</user_constraints>

---

## Summary

Phase 8 is a hardening and live-telemetry extension of a fully-functional 7-phase AI-SOC-Brain system. The core platform already works: FastAPI backend with 8+ route modules, Svelte 5 SPA, DuckDB + SQLite + Chroma stores, Sigma detection, causality engine, and case/hunt management.

The three concrete gaps this phase must close are: (1) **live osquery telemetry** — osquery is installed but not yet wired into a live collection loop (only a fixture parser exists); (2) **integration test failures** — 4 tests in `test_backend_health.py` fail due to pagination API mismatch (`page`/`page_size` in production vs. `total`/`offset`/`limit` expected by tests); (3) **documentation and receipt staleness** — ARCHITECTURE.md is dated 2026-03-15 and lists osquery as "Phase 6 (deferred)", REPRODUCIBILITY_RECEIPT.md has "TBD" versions throughout.

**Primary recommendation:** Implement live osquery via a filesystem-polling background service that reads `osqueryd.results.log` using the existing `OsqueryParser`, wired through the existing DuckDB write queue. This requires no new parser code — only a polling loop, a new FastAPI route for live-collection control, and config for osquery itself.

---

## Standard Stack

### Core (all already in pyproject.toml — no new dependencies needed)

| Library | Version (pinned) | Purpose | Why Standard |
|---------|--------|---------|--------------|
| fastapi | 0.115.12 | HTTP API and background tasks | Already in use |
| uvicorn | 0.34.3 | ASGI server | Already in use |
| duckdb | 1.3.0 | Event storage | Already in use; single-writer pattern in place |
| pydantic-settings | >=2.0 | Config management | Already in use |
| httpx | >=0.28.1 | Ollama client | Already in use |

### New for Phase 8 (zero new Python packages needed)

The live osquery collection loop can be built entirely from stdlib (`asyncio`, `pathlib`, `watchfiles` is NOT needed — simple `asyncio.sleep` polling is sufficient for a single log file).

**osquery itself** must be installed on the host Windows machine. This is a binary install, not a Python package:

```powershell
# Option A — winget (recommended, no admin for user-scoped install)
winget install osquery.osquery

# Option B — Chocolatey
choco install osquery

# Option C — MSI direct download
# https://github.com/osquery/osquery/releases/latest
# Download osquery-<version>.msi, run installer
```

**Confidence:** HIGH — osquery is available via all three Windows package managers.

### osquery Windows Paths (HIGH confidence — official docs)

| Item | Default Windows Path |
|------|---------------------|
| Executable | `C:\Program Files\osquery\osqueryd.exe` |
| Config file | `C:\Program Files\osquery\osquery.conf` |
| Results log | `C:\Program Files\osquery\log\osqueryd.results.log` |
| Snapshots log | `C:\Program Files\osquery\log\osqueryd.snapshots.log` |
| Flagfile | `C:\Program Files\osquery\osquery.flags` |
| Database | `C:\Program Files\osquery\osquery.db\` |

Source: [osquery Logging docs](https://osquery.readthedocs.io/en/stable/deployment/logging/) + [Configuration docs](https://osquery.readthedocs.io/en/stable/deployment/configuration/)

---

## Architecture Patterns

### Recommended Phase 8 Project Structure (additions only)

```
backend/
├── services/
│   └── osquery_collector.py     # NEW: log-tail polling loop
├── api/
│   └── telemetry.py             # NEW: GET/POST /api/telemetry/osquery
scripts/
├── smoke-test-phase8.ps1        # NEW: end-to-end smoke test
config/
└── osquery/
    ├── osquery.conf             # NEW: scheduled queries config
    └── osquery.flags            # NEW: flagfile for osqueryd
tests/
├── unit/
│   └── test_osquery_collector.py  # NEW: unit tests for collector
└── integration/
    └── test_osquery_pipeline.py   # NEW: mock-file integration test
```

### Pattern 1: Log File Polling (Tail-and-Ingest)

**What:** Background asyncio task reads new lines appended to `osqueryd.results.log` since last read position, parses with existing `OsqueryParser.parse_result()`, ingests via DuckDB write queue.

**When to use:** Single-host desktop; no TLS logger needed; filesystem logger is osquery default.

**Why not watchdog/inotify:** On Windows, `ReadDirectoryChangesW` is complex. Simple `asyncio.sleep(5)` polling of file size is sufficient for near-real-time (5-second latency acceptable for SOC analysis use case).

```python
# Source: pattern derived from existing backend/main.py lifespan model
# backend/services/osquery_collector.py

class OsqueryCollector:
    """
    Background asyncio task: tail osqueryd.results.log, parse, ingest.
    Lifecycle: start in FastAPI lifespan, cancel on shutdown.
    """
    def __init__(self, log_path: Path, duckdb_store, interval_sec: int = 5):
        self._log_path = log_path
        self._store = duckdb_store
        self._offset = 0          # byte offset of last-read position
        self._interval = interval_sec
        self._parser = OsqueryParser()

    async def run(self) -> None:
        """Loop: read new lines, parse, enqueue writes. Cancellation-safe."""
        while True:
            await asyncio.sleep(self._interval)
            await self._ingest_new_lines()

    async def _ingest_new_lines(self) -> None:
        if not self._log_path.exists():
            return
        # asyncio.to_thread wraps blocking file I/O per CLAUDE.md convention
        lines = await asyncio.to_thread(self._read_new_lines)
        for line in lines:
            try:
                record = json.loads(line)
                events = self._parser.parse_result(record, source_file="osquery_live")
                for evt in events:
                    row = evt.to_duckdb_row()
                    await self._store.execute_write(INSERT_SQL, row)
            except Exception:
                pass  # log and continue

    def _read_new_lines(self) -> list[str]:
        """Read file from current offset, return new lines, update offset."""
        with open(self._log_path, "r", encoding="utf-8", errors="replace") as fh:
            fh.seek(self._offset)
            data = fh.read()
            self._offset = fh.tell()
        return [l for l in data.splitlines() if l.strip()]
```

**Key insight:** `OsqueryParser.parse_result()` already exists and handles differential, snapshot, and data-list formats. The collector is purely a tail-and-dispatch wrapper.

### Pattern 2: osquery Configuration for Scheduled Queries

```json
{
  "options": {
    "host_identifier": "hostname",
    "schedule_splay_percent": 10,
    "logger_plugin": "filesystem",
    "logger_path": "C:\\Program Files\\osquery\\log"
  },
  "schedule": {
    "processes": {
      "query": "SELECT pid, name, path, cmdline, parent, uid FROM processes;",
      "interval": 30,
      "snapshot": true
    },
    "open_sockets": {
      "query": "SELECT pid, family, protocol, local_address, local_port, remote_address, remote_port, state FROM process_open_sockets;",
      "interval": 60,
      "snapshot": true
    },
    "listening_ports": {
      "query": "SELECT pid, port, protocol, family, address FROM listening_ports;",
      "interval": 120,
      "snapshot": true
    },
    "logged_in_users": {
      "query": "SELECT user, host, time, pid FROM logged_in_users;",
      "interval": 60,
      "snapshot": true
    }
  }
}
```

Source: [osquery Configuration docs](https://osquery.readthedocs.io/en/stable/deployment/configuration/) + [example.conf](https://github.com/osquery/osquery/blob/master/tools/deployment/osquery.example.conf)

**Why `snapshot: true`:** For a single-desktop use case, snapshot mode gives the full current state on each execution rather than only differential changes. This is safer for an analyst workstation — every poll returns a complete picture rather than requiring the daemon to track baseline state.

### Pattern 3: Lifespan Integration

The `OsqueryCollector` must be started and cancelled in `backend/main.py` lifespan — exactly the same pattern as the DuckDB write worker already uses:

```python
# In lifespan(): after all stores initialised
osquery_log = Path(settings.OSQUERY_LOG_PATH)
collector = OsqueryCollector(osquery_log, duckdb_store)
collector_task = asyncio.ensure_future(collector.run())
app.state.osquery_collector = collector

# In shutdown section:
if not collector_task.done():
    collector_task.cancel()
    try:
        await collector_task
    except asyncio.CancelledError:
        pass
```

**Config addition needed in `backend/core/config.py`:**
```python
OSQUERY_LOG_PATH: str = r"C:\Program Files\osquery\log\osqueryd.results.log"
OSQUERY_ENABLED: bool = False   # Default OFF; set True in .env when osquery installed
OSQUERY_POLL_INTERVAL: int = 5  # seconds
```

### Pattern 4: Fixing the Integration Test Mismatch (HIGH PRIORITY)

**Problem identified by codebase inspection:** `GET /api/events` returns `{events, total, page, page_size, has_next}` but `tests/integration/test_backend_health.py` asserts `{events, total, offset, limit}`. This causes 4 test failures.

**Fix approach:** Update the integration test assertions to match the actual API contract (tests are wrong, not the API). The `EventListResponse` model uses `page`/`page_size` consistently throughout the codebase.

```python
# BEFORE (failing):
assert "offset" in data
assert "limit" in data

# AFTER (correct):
assert "page" in data
assert "page_size" in data
assert "has_next" in data
```

### Anti-Patterns to Avoid

- **Do NOT use `--reload` with uvicorn:** The start.ps1 already avoids this (documented). DuckDB single-writer pattern requires single process.
- **Do NOT start OsqueryCollector when `OSQUERY_ENABLED=False`:** Net-new machines won't have osquery; the backend must start cleanly without it.
- **Do NOT use TLS logger plugin:** Requires a TLS server endpoint. Filesystem logger is the right choice for single-host desktop.
- **Do NOT use differential mode without baseline establishment:** Snapshot mode avoids the "first run is all adds" confusion for the ingestion pipeline.
- **Do NOT register osquery parser by file extension:** The existing `OsqueryParser.supported_extensions = []` is intentional — it should be called programmatically, not via the extension registry.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| osquery JSON parsing | Custom JSON parser for osquery output | `OsqueryParser.parse_result()` (already exists) | Handles all 3 formats: differential, snapshot, data-list |
| File tail / inotify | Custom Windows ReadDirectoryChangesW wrapper | `asyncio.sleep()` polling + file seek | Simpler, no new deps, 5s latency acceptable |
| osquery installation check | Custom registry scan | `shutil.which("osqueryd")` + `Path(settings.OSQUERY_LOG_PATH).exists()` | Standard pattern; no new deps |
| DuckDB write in collector | Direct `duckdb.connect()` in background thread | `store.execute_write(sql, params)` (existing write queue) | CRITICAL: violates single-writer pattern |
| GPU check | Manual CUDA API call | `subprocess.run(["nvidia-smi", ...])` + Ollama `/api/tags` GPU layer count | Already in smoke-test-phase1.ps1 |

---

## Common Pitfalls

### Pitfall 1: OSQUERY_ENABLED not guarded at startup
**What goes wrong:** Backend startup crashes or logs errors if `OSQUERY_LOG_PATH` doesn't exist on a machine without osquery installed.
**Why it happens:** `OsqueryCollector` tries to read a file that doesn't exist.
**How to avoid:** Gate on `settings.OSQUERY_ENABLED` before creating the collector; `_ingest_new_lines()` already has `if not self._log_path.exists(): return` safety.
**Warning signs:** `FileNotFoundError` in logs at startup.

### Pitfall 2: DuckDB write from background thread without write queue
**What goes wrong:** Concurrent writes deadlock DuckDB; the `data/events.duckdb` file is locked.
**Why it happens:** Background collector thread bypasses the asyncio write queue.
**How to avoid:** Always use `await store.execute_write(sql, params)` — the existing queue pattern.
**Warning signs:** `duckdb.IOException: Could not set lock on file`.

### Pitfall 3: osquery running as SYSTEM writes logs unreadable by user process
**What goes wrong:** `osqueryd.results.log` is created with SYSTEM-only ACLs; FastAPI (running as user) cannot read it.
**Why it happens:** When osquery is installed as a Windows service, it runs as SYSTEM by default.
**How to avoid:** Either (a) run osqueryd in interactive mode (not as service) for desktop use, or (b) after service install, grant the log directory read access to the current user: `icacls "C:\Program Files\osquery\log" /grant Users:R`.
**Warning signs:** `PermissionError` in collector logs.

### Pitfall 4: Integration test failures masking regressions
**What goes wrong:** 4 currently-failing integration tests (`test_events_list_has_pagination_fields`, `test_events_list_limit_param`, `test_detections_list_returns_200`, `test_detections_has_detections_field`) mean the CI baseline is already red before Phase 8 adds anything.
**Why it happens:** Tests assert `offset`/`limit` keys but API returns `page`/`page_size`. Also, `/api/detections` endpoint may not exist (detect.py uses a different path).
**How to avoid:** Fix these 4 tests in Phase 8 Wave 0 before adding new code.
**Warning signs:** `4 failed, 98 passed` — confirmed by codebase inspection.

### Pitfall 5: REPRODUCIBILITY_RECEIPT.md has "TBD" versions throughout
**What goes wrong:** A new developer following the receipt cannot reproduce the environment because dependency versions are all "TBD".
**Why it happens:** The receipt was written at project start (2026-03-15) and never updated through 7 phases.
**How to avoid:** In Phase 8 documentation plan, run `uv pip list --format=json` and fill in actual versions.

### Pitfall 6: `scripts/start.sh` reference in backend/main.py docstring
**What goes wrong:** Minor misleading comment — the actual script is `scripts/start.ps1` / `start.cmd`, not `start.sh`.
**Warning signs:** Developer confusion. Low severity but easy to fix.

### Pitfall 7: osquery `unixTime` field is a string, not integer
**What goes wrong:** The fixture file (`osquery_snapshot.json`) shows `"unixTime": "1741942523"` (string). The parser handles this via `_safe_int()`. Live daemon output may behave differently.
**Why it happens:** osquery emits numeric fields as strings in some output modes.
**How to avoid:** `_safe_int()` already handles string-to-int conversion. No change needed; document it.

---

## Code Examples

### osquery Result Log Line (Differential Format)
```json
{
  "name": "processes",
  "hostIdentifier": "WORKSTATION-01",
  "calendarTime": "Mon Mar 17 10:00:00 2026 UTC",
  "unixTime": 1742205600,
  "epoch": 0,
  "counter": 42,
  "numerics": false,
  "action": "added",
  "columns": {
    "pid": "4821",
    "name": "powershell.exe",
    "path": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
    "cmdline": "powershell.exe -nop -w hidden",
    "parent": "1234",
    "uid": "1000",
    "username": "jsmith"
  }
}
```

### osquery Result Log Line (Snapshot Format)
```json
{
  "name": "processes",
  "hostIdentifier": "WORKSTATION-01",
  "calendarTime": "Mon Mar 17 10:00:00 2026 UTC",
  "unixTime": 1742205600,
  "action": "snapshot",
  "snapshot": [
    {"pid": "4821", "name": "powershell.exe", "cmdline": "powershell.exe -nop", ...},
    {"pid": "9042", "name": "cmd.exe", "cmdline": "cmd.exe /c whoami", ...}
  ]
}
```

Source: [osquery Logging docs](https://osquery.readthedocs.io/en/stable/deployment/logging/)

Note: Both formats are already handled by `OsqueryParser._handle_record()`.

### Telemetry Control API Endpoint
```python
# backend/api/telemetry.py — new in Phase 8
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

@router.get("/osquery/status")
async def osquery_status(request: Request) -> JSONResponse:
    """
    Returns current osquery collector status.
    Always returns 200; 'enabled' reflects OSQUERY_ENABLED setting.
    """
    settings = request.app.state.settings
    collector = getattr(request.app.state, "osquery_collector", None)
    return JSONResponse({
        "enabled": settings.OSQUERY_ENABLED,
        "log_path": settings.OSQUERY_LOG_PATH,
        "log_exists": Path(settings.OSQUERY_LOG_PATH).exists(),
        "running": collector is not None and not collector._task_done(),
    })
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| osquery deferred (ROADMAP) | osquery USE NOW in Phase 8 | CONTEXT.md 2026-03-17 | Phase 8 must implement it |
| `scripts/start.sh` reference | `scripts/start.ps1` + `.cmd` wrapper | Phase 7 plan 08 | backend/main.py docstring needs update |
| REPRODUCIBILITY_RECEIPT.md "TBD" versions | Needs actual versions filled in | Phase 1 - never updated | Must be done in Phase 8 docs plan |
| ARCHITECTURE.md "osquery (Phase 6)" | osquery in Phase 8 | Phase 8 | ARCHITECTURE.md needs update |
| 4 failing integration tests | Need fix before Phase 8 additions | Inherited from Phase 7 | Must fix in Wave 0 |

**Deprecated/outdated:**
- `scripts/start.sh` reference in `backend/main.py` module docstring: replace with `scripts/start.cmd` or `scripts/start.ps1`

---

## Open Questions

1. **osquery service vs. interactive mode**
   - What we know: Running as Windows service requires ACL grant for log dir; running interactively avoids the permission issue.
   - What's unclear: Does the analyst want osquery always-on (service) or on-demand (start with `scripts/start.cmd`)?
   - Recommendation: Default to interactive/foreground mode started by `scripts/start.ps1`; provide service installation as optional step in docs.

2. **Smoke test for live osquery path without real daemon**
   - What we know: The collector can be unit-tested by writing mock log lines to a temp file and verifying DuckDB row count increases.
   - What's unclear: Whether to require actual osquery installed for the integration test.
   - Recommendation: Use a mock file (write test NDJSON lines to a temp path) for unit tests. Mark real-daemon test as `pytest.mark.skipif(not shutil.which("osqueryd"))`.

3. **`/api/detections` endpoint path**
   - What we know: `detect.py` exists in `backend/api/` and mounts at `/api`. The failing integration test hits `/api/detections`.
   - What's unclear: Whether the detect router exposes exactly `/detections` or a different path.
   - Recommendation: Inspect `detect.py` routes at start of Phase 8 plan 00 and align the integration test.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.5 + pytest-asyncio 0.25.0 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/unit/ -q --tb=short` |
| Full suite command | `uv run pytest -q --tb=short` |

### Current Test Baseline (confirmed by inspection)

```
103 tests collected
4 failed, 98 passed, 1 skipped
```

The 4 failures are in `tests/integration/test_backend_health.py` and must be fixed in Wave 0 before any Phase 8 code lands.

### Phase 8 Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P8-T01 | OsqueryCollector reads new lines from a file and parses them | unit | `uv run pytest tests/unit/test_osquery_collector.py -x` | Wave 0 create |
| P8-T02 | OsqueryCollector skips non-existent log file gracefully | unit | `uv run pytest tests/unit/test_osquery_collector.py::test_missing_log_graceful -x` | Wave 0 create |
| P8-T03 | OsqueryCollector uses DuckDB write queue (not direct write) | unit | `uv run pytest tests/unit/test_osquery_collector.py::test_uses_write_queue -x` | Wave 0 create |
| P8-T04 | OSQUERY_ENABLED=False means collector not started | unit | `uv run pytest tests/unit/test_osquery_collector.py::test_disabled_no_start -x` | Wave 0 create |
| P8-T05 | GET /api/telemetry/osquery/status returns 200 | integration | `uv run pytest tests/integration/test_backend_health.py::TestTelemetryAPI -x` | Wave 0 create |
| P8-T06 | Integration test: /api/events pagination fields correct | integration | `uv run pytest tests/integration/test_backend_health.py::TestEventsAPI -x` | Fix existing |
| P8-T07 | Integration test: /api/detections returns 200 | integration | `uv run pytest tests/integration/test_backend_health.py::TestDetectionsAPI -x` | Fix existing |
| P8-T08 | Full pipeline: write mock osquery NDJSON lines, verify DuckDB row count increases | integration | `uv run pytest tests/integration/test_osquery_pipeline.py -x` | Wave 0 create |
| P8-T09 | Smoke test: `curl -k https://localhost/health` returns 200 | smoke (PS) | `scripts/smoke-test-phase8.ps1` | New script |
| P8-T10 | Smoke test: Ollama GPU layers > 0 during inference | smoke (PS) | `scripts/smoke-test-phase8.ps1` | New script |
| P8-T11 | All Phase 1-7 tests still pass (regression guard) | regression | `uv run pytest -q --tb=short` | Existing |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit/ -q --tb=short`
- **Per wave merge:** `uv run pytest -q --tb=short`
- **Phase gate:** Full suite green (`4 failed` baseline fixed → `0 failed`) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/test_osquery_collector.py` — covers P8-T01 through P8-T04
- [ ] `tests/integration/test_osquery_pipeline.py` — covers P8-T08
- [ ] Fix `tests/integration/test_backend_health.py` assertions — covers P8-T06, P8-T07
- [ ] `scripts/smoke-test-phase8.ps1` — covers P8-T09, P8-T10

---

## Sources

### Primary (HIGH confidence)
- [osquery Logging documentation](https://osquery.readthedocs.io/en/stable/deployment/logging/) — log file paths, formats, logger plugins
- [osquery Configuration documentation](https://osquery.readthedocs.io/en/stable/deployment/configuration/) — config file format, scheduled queries, snapshot mode
- [osquery daemon documentation](https://osquery.readthedocs.io/en/stable/introduction/using-osqueryd/) — scheduled query mechanics, watchdog, intervals
- Codebase inspection (direct) — `ingestion/parsers/osquery_parser.py`, `backend/main.py`, `backend/core/config.py`, `backend/api/events.py`, `tests/integration/test_backend_health.py`, `scripts/start.ps1`, `pyproject.toml`

### Secondary (MEDIUM confidence)
- [osquery example.conf on GitHub](https://github.com/osquery/osquery/blob/master/tools/deployment/osquery.example.conf) — verified scheduled query schema format
- WebSearch: osquery Windows daemon live collection — confirmed service installation via `--install` flag, default log path

### Tertiary (LOW confidence)
- Windows ACL behavior for osquery service (SYSTEM account) — derived from general Windows service knowledge; should be verified during Phase 8 execution

---

## Metadata

**Confidence breakdown:**
- Standard stack (no new deps): HIGH — entire phase uses existing pyproject.toml dependencies
- osquery Windows paths and log format: HIGH — confirmed via official osquery docs
- OsqueryCollector architecture: HIGH — directly derived from existing codebase patterns
- Integration test fixes: HIGH — root cause confirmed by running `uv run pytest`
- osquery SYSTEM ACL pitfall: MEDIUM — derived from Windows service behavior knowledge
- Documentation gaps: HIGH — confirmed by reading REPRODUCIBILITY_RECEIPT.md (TBD throughout)

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (stable domain; osquery and FastAPI APIs are stable)
