# Phase 12: API Hardening & Parser Coverage — Research

**Researched:** 2026-03-26
**Domain:** FastAPI rate limiting, Caddy request body limits, EVTX parser unit testing, git PR workflow
**Confidence:** HIGH

---

## Summary

Phase 12 has three independent attack surfaces to harden:

1. **API surface** — add per-endpoint rate limiting via `slowapi` (not yet in the project) and a request body size cap via the Caddy `request_body` directive. `slowapi` is the canonical FastAPI/Starlette rate limiter (v0.1.9 is the latest, verified on PyPI). The project currently has zero rate limiting and no body size guard.

2. **EVTX parser coverage** — `ingestion/parsers/evtx_parser.py` sits at exactly 15% coverage (141 stmts, 120 missed). The module is pure Python with no real-file I/O dependency in the hot path: `_parse_record`, `_flatten_event_data`, `_parse_timestamp`, `_extract_field`, `_safe_int`, and `_determine_event_type` are all testable by constructing the pyevtx-rs dict format directly — no `.evtx` file needed. Only `EvtxParser.parse()` itself calls `evtx.PyEvtxParser(file_path)` and requires mocking.

3. **PR workflow** — Phase 12 must run on a feature branch and land via pull request, establishing the first PR-merged phase in this repo. All previous phases committed directly to `master`. The repo has `main` as the remote default; `master` is local default. A clean `feature/phase-12-api-hardening` branch is the correct target.

**Primary recommendation:** Add `slowapi==0.1.9` to `pyproject.toml`, wire it in `backend/main.py` using `SlowAPIMiddleware` (not the decorator-only approach), add `request_body` to the Caddyfile, write unit tests for the EVTX parser private methods using hand-crafted dicts, and deliver the whole thing via a GitHub PR from `feature/phase-12-api-hardening` to `main`.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P12-T01 | Add rate limiting to the FastAPI API surface | `slowapi==0.1.9` via `SlowAPIMiddleware`; applied to `/api/ingest/*`, `/api/query/*`, `/api/detect/run`; key_func=get_remote_address; in-memory backend is sufficient for single-analyst tool |
| P12-T02 | Add request body size guard | Caddy `request_body { max_size 50MB }` directive on the `/api/*` handler; Caddy v2.11.1 is installed and supports this directive (available since v2.10.0) |
| P12-T03 | Raise EVTX parser coverage from 15% to ≥80% | All private helper functions are testable with hand-crafted dicts; `EvtxParser.parse()` needs `unittest.mock.patch("ingestion.parsers.evtx_parser.evtx.PyEvtxParser")`; target ~80% coverage by covering all dict shapes pyevtx-rs can produce |
| P12-T04 | Ensure overall coverage stays at ≥70% | Current baseline is 70% (466 passed). New EVTX tests will push evtx_parser.py from 15% → ~80% which adds ~105 covered stmts; no risk of regression |
| P12-T05 | Deliver Phase 12 via feature branch + PR | Branch from `master` as `feature/phase-12-api-hardening`; open PR against `main`; PR must pass CI (`uv run pytest --cov-fail-under=70`) before merge |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| slowapi | 0.1.9 | Rate limiting for FastAPI/Starlette | Only actively maintained ASGI rate limiter; direct Starlette integration; uses `limits` library backend |
| evtx (pyevtx-rs) | 0.11.0 (already installed) | EVTX parsing | Already pinned in pyproject.toml; Rust-backed, no changes needed |
| unittest.mock | stdlib | Mock `evtx.PyEvtxParser` in tests | No new dependency; standard approach for wrapping Rust extension types |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| limits | auto-installed by slowapi | Backend storage for rate counters | In-memory is correct for single-analyst local tool |
| pytest-cov | >=6.0.0 (already dev dep) | Coverage measurement | Already present; used by CI |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| slowapi | Custom Starlette middleware | Custom middleware is ~50 lines but reimplements sliding-window logic that has edge cases; slowapi is battle-tested |
| slowapi | fastapi-limiter (Redis-backed) | fastapi-limiter requires Redis; overkill for single-analyst tool; slowapi has in-memory backend |
| Caddy request_body | FastAPI middleware for size | Caddy check happens before FastAPI process, blocking oversized uploads at the proxy layer without memory allocation in Python |

**Installation:**
```bash
uv add slowapi==0.1.9
```

---

## Architecture Patterns

### Pattern 1: SlowAPI with SlowAPIMiddleware (preferred over decorator-only)

**What:** Attach `SlowAPIMiddleware` to the FastAPI app so rate limits apply globally and can be tested without decorating every router file. Limiter state is stored on `app.state.limiter`.

**When to use:** When routers are spread across multiple files (as in this project). The middleware approach avoids having to import the limiter singleton into every router module.

```python
# Source: https://slowapi.readthedocs.io/en/latest/
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
```

**CRITICAL constraint for this project:** The `request` parameter must be explicitly declared in endpoint functions for the `@limiter.limit()` decorator to work. Most existing endpoints in this project already accept `request: Request` (ingest.py, query.py). Verify each endpoint before applying decorators.

### Pattern 2: Per-endpoint rate limits on mutation/expensive endpoints

**What:** Apply tighter limits to endpoints that are computationally expensive or write-heavy. Leave read-only lightweight endpoints at the default.

**When to use:** `POST /api/ingest/*` (file uploads — expensive), `POST /api/query/*` (Ollama inference — expensive), `POST /api/detect/run` (full DB scan — expensive).

```python
# Source: slowapi docs
@router.post("/file")
@limiter.limit("10/minute")  # above @router decorator
async def ingest_file(request: Request, file: UploadFile = File(...)) -> JSONResponse:
    ...
```

**Decorator order matters:** `@router.post(...)` MUST come before `@limiter.limit(...)`. This is the most common integration mistake.

### Pattern 3: Caddy request_body directive

**What:** Add `request_body { max_size 50MB }` inside the `/api/*` handler block in the Caddyfile. This rejects oversized uploads with HTTP 413 before the request reaches FastAPI.

**When to use:** File upload endpoints (`/api/ingest/file`). A 50MB limit is appropriate for a local SOC tool where EVTX files up to 100MB are expected — but the requirement FR-2.3 says "parse without memory spike above 2GB", so daily working files are typically smaller. 50MB at the Caddy layer gives protection against accidental multi-GB uploads while still allowing large-but-reasonable evidence files. Add a separate 100MB matcher specifically for `/api/ingest/file` if 50MB is too restrictive.

```
# Caddy v2 (v2.10.0+ required; installed version is v2.11.1 — confirmed)
handle /api/ingest/file {
    request_body {
        max_size 100MB
    }
    reverse_proxy host.docker.internal:8000 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
}

handle /api/* {
    request_body {
        max_size 10MB
    }
    reverse_proxy host.docker.internal:8000 { ... }
}
```

**Note:** Caddy uses first-match-wins routing. The `/api/ingest/file` specific handler must come BEFORE the generic `/api/*` handler — same pattern already used for `/api/query/*` in the current Caddyfile.

### Pattern 4: EVTX parser testing with hand-crafted dicts

**What:** pyevtx-rs `records_json()` yields Python dicts with a known structure. All parser logic beyond `evtx.PyEvtxParser(file_path)` is pure dict manipulation. Construct these dicts in tests directly.

**The pyevtx-rs dict format `_parse_record` expects:**
```python
# What records_json() actually yields (verified by reading evtx_parser.py lines 186-200)
record = {
    "event_record_id": 12345,
    "timestamp": "2023-01-15T14:23:01.123456Z",
    "data": '{"Event": {"System": {"TimeCreated": {"@SystemTime": "2023-01-15T14:23:01.123456Z"}, "EventID": 4624, "Channel": "Security", "Computer": "WORKSTATION01", "EventRecordID": 12345}, "EventData": {"Data": [{"@Name": "SubjectUserName", "#text": "jdoe"}, {"@Name": "NewProcessName", "#text": "C:\\\\Windows\\\\System32\\\\cmd.exe"}]}}}'
}
```

**What to mock for `EvtxParser.parse()` tests:**
```python
# Source: evtx_parser.py lines 139-166
from unittest.mock import MagicMock, patch

def test_parse_yields_events():
    mock_record = { ... }  # hand-crafted dict
    mock_parser_instance = MagicMock()
    mock_parser_instance.records_json.return_value = [mock_record]

    with patch("ingestion.parsers.evtx_parser.evtx.PyEvtxParser", return_value=mock_parser_instance):
        parser = EvtxParser()
        events = list(parser.parse("fake.evtx", case_id="test-case"))
    assert len(events) == 1
```

### Recommended Test Structure for EVTX Parser

```
tests/unit/test_evtx_parser.py
├── TestParseTimestamp          — _parse_timestamp() — 4 cases: valid ISO-Z, no-tz, empty, garbage
├── TestExtractField            — _extract_field() — multiple keys, first match, all None
├── TestSafeInt                 — _safe_int() — int/str/None/bad string
├── TestDetermineEventType      — sysmon channel, security channel, None event_id
├── TestFlattenEventData        — list-of-dicts, single-dict, already-flat, str, empty
├── TestParseRecord             — _parse_record() directly with hand-crafted records
│   ├── Sysmon process create (EventID 1)
│   ├── Security logon (EventID 4624)
│   ├── Network connect (EventID 3)
│   ├── SHA256 hash extraction
│   ├── Corrupt data (json.JSONDecodeError path)
│   └── Missing fields → None fields in NormalizedEvent
└── TestEvtxParserParse         — parse() with mocked evtx.PyEvtxParser
    ├── Happy path — yields events
    ├── File open failure — logs error, returns empty iterator
    └── Per-record exception — skips bad record, continues
```

This structure covers ~85%+ of the 141 statements. The uncoverable lines are `import evtx` itself and the `log.info` at module level.

### Anti-Patterns to Avoid

- **Importing the limiter singleton into every router file:** Use `SlowAPIMiddleware` approach so the limiter is centrally managed in `main.py`. Router files get limits via decorators that reference a shared limiter instance — but the instance can be in a `backend/core/rate_limit.py` module imported by both `main.py` and router files.
- **Applying rate limits in tests without disabling them:** Tests using `TestClient` will hit rate limits. Use `limiter.reset()` in test teardown or configure the limiter with `enabled=False` when `settings.TESTING`.
- **Using `evtx.PyEvtxParser` directly in tests:** It requires a real `.evtx` binary file. Always mock it for unit tests.
- **Putting `request_body` after `reverse_proxy` in Caddy:** `request_body` must appear as a directive in the handler block, not nested inside `reverse_proxy`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rate limiting | Custom Starlette middleware with time-window dict | slowapi | Sliding window, in-memory + Redis, header injection, 429 responses all handled |
| Request size limiting | FastAPI middleware reading Content-Length | Caddy `request_body` | Proxy-layer enforcement costs no Python memory; blocks before request body is streamed |
| EVTX record format mocking | Fixture `.evtx` binary files | Hand-crafted dicts matching pyevtx-rs output format | No binary test fixtures needed; dicts are readable and maintainable |

---

## Common Pitfalls

### Pitfall 1: slowapi decorator order
**What goes wrong:** `@limiter.limit("10/minute")` is placed ABOVE `@router.post(...)`, which silently breaks rate limiting (no error, no limiting).
**Why it happens:** Intuitive thinking puts the "modifier" decorator closest to the function.
**How to avoid:** Always: `@router.post(...)` first, then `@limiter.limit(...)` second.
**Warning signs:** Rate limits never trigger in testing even after many rapid requests.

### Pitfall 2: Missing `request: Request` in endpoint signature
**What goes wrong:** slowapi cannot inject rate limit context; silently skips limiting.
**Why it happens:** Some endpoints in this project may have removed `request` if it was unused.
**How to avoid:** Audit all endpoints before adding `@limiter.limit()`. Confirm `request: Request` is a parameter. `ingest.py`, `query.py`, `detect.py` all currently accept `request: Request` — verified in the source.
**Warning signs:** No 429 responses even after threshold exceeded.

### Pitfall 3: `request_body` directive in wrong Caddy block
**What goes wrong:** `request_body` placed inside the `reverse_proxy` block instead of alongside it.
**Why it happens:** Confusion about Caddy directive scoping.
**How to avoid:** `request_body` is a site-level directive within a `handle` block, not a sub-directive of `reverse_proxy`.

### Pitfall 4: Caddy handler order for `/api/ingest/file`
**What goes wrong:** Generic `/api/*` handler matches `/api/ingest/file` before the specific handler.
**Why it happens:** Caddy is first-match-wins. If the specific handler is defined after the generic one, it never executes.
**How to avoid:** Place the `/api/ingest/file` handler (with 100MB limit) BEFORE the generic `/api/*` handler — same pattern already used for `/api/query/*` in the current Caddyfile.

### Pitfall 5: Rate limiting breaks existing tests
**What goes wrong:** `TestClient` in pytest hits the in-memory rate limiter. Tests making 10+ requests fail with 429.
**Why it happens:** In-memory limiter state persists across test function calls in the same pytest session.
**How to avoid:** Add `app.state.limiter.reset()` in a pytest fixture teardown, or pass `enabled=False` when `TESTING=True` is set. Alternatively, set the default limit high enough that no test hits it (e.g., `"1000/minute"`) for the test client.

### Pitfall 6: EVTX test imports circular dependency
**What goes wrong:** `from ingestion.parsers.evtx_parser import EvtxParser` triggers `import evtx` at module level; if `evtx` is not installed, the test file fails to import.
**Why it happens:** pyevtx-rs (`evtx`) is a C extension that must be installed.
**How to avoid:** `evtx==0.11.0` is already in `pyproject.toml` and installed. No issue in practice.

### Pitfall 7: Git branch target — master vs main
**What goes wrong:** PR is opened targeting `master` when the remote default branch is `main`.
**Why it happens:** Local branch is `master`; remote has both `master` and `main` (origin/main is the remote default per git status output).
**How to avoid:** Create `feature/phase-12-api-hardening` from `master` (current HEAD), open PR targeting `main` (the remote default). The PR merge will land on `main`. After merge, local `master` can be synced with `main` if desired.

---

## Code Examples

### slowapi integration in main.py (create_app function)

```python
# Source: https://slowapi.readthedocs.io/en/latest/
# Add to backend/main.py create_app() after CORSMiddleware

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Create limiter instance (module-level, importable by router files)
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

def create_app() -> FastAPI:
    ...
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    ...
```

### Per-endpoint decorator in ingest.py

```python
# Source: slowapi docs + evtx_parser.py pattern
from backend.main import limiter  # or from backend.core.rate_limit import limiter

@router.post("/file", status_code=202)
@limiter.limit("10/minute")
async def ingest_file(
    request: Request,  # REQUIRED for slowapi
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    case_id: str | None = None,
) -> JSONResponse:
    ...
```

### Caddyfile modification (complete updated structure)

```
# Handle file upload with larger body limit (specific handler first)
handle /api/ingest/file {
    request_body {
        max_size 100MB
    }
    reverse_proxy host.docker.internal:8000 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
}

# General API — 10MB body limit
handle /api/* {
    request_body {
        max_size 10MB
    }
    reverse_proxy host.docker.internal:8000 {
        ...existing config...
    }
}
```

### EVTX parser unit test pattern

```python
# tests/unit/test_evtx_parser.py
from unittest.mock import MagicMock, patch
from ingestion.parsers.evtx_parser import (
    EvtxParser, _parse_timestamp, _extract_field,
    _safe_int, _determine_event_type
)

class TestFlattenEventData:
    def test_list_of_dicts(self):
        parser = EvtxParser()
        data = {"Data": [
            {"@Name": "SubjectUserName", "#text": "jdoe"},
            {"@Name": "Image", "#text": "cmd.exe"},
        ]}
        result = parser._flatten_event_data(data)
        assert result["SubjectUserName"] == "jdoe"
        assert result["Image"] == "cmd.exe"

class TestParseRecord:
    def test_sysmon_process_create(self):
        parser = EvtxParser()
        record = {
            "event_record_id": 1,
            "timestamp": "2023-01-15T14:23:01Z",
            "data": '{"Event": {"System": {"EventID": 1, "Channel": "Microsoft-Windows-Sysmon/Operational", "Computer": "WORKSTATION01", "EventRecordID": 1, "TimeCreated": {"@SystemTime": "2023-01-15T14:23:01Z"}}, "EventData": {"Data": [{"@Name": "Image", "#text": "C:\\\\Windows\\\\System32\\\\cmd.exe"}, {"@Name": "CommandLine", "#text": "cmd.exe /c whoami"}, {"@Name": "ProcessId", "#text": "4321"}]}}}'
        }
        from datetime import datetime, timezone
        event = parser._parse_record(record, "test.evtx", "case-1", datetime.now(tz=timezone.utc))
        assert event.process_name == "C:\\Windows\\System32\\cmd.exe"
        assert event.process_id == 4321
        assert event.event_type == "process_create"
        assert event.source_type == "evtx"

class TestEvtxParserParse:
    def test_parse_happy_path(self):
        record = { ... }  # as above
        mock_instance = MagicMock()
        mock_instance.records_json.return_value = [record]
        with patch("ingestion.parsers.evtx_parser.evtx.PyEvtxParser", return_value=mock_instance):
            events = list(EvtxParser().parse("fake.evtx"))
        assert len(events) == 1

    def test_parse_file_open_failure(self):
        with patch("ingestion.parsers.evtx_parser.evtx.PyEvtxParser", side_effect=OSError("not found")):
            events = list(EvtxParser().parse("missing.evtx"))
        assert events == []  # returns empty iterator, does not raise
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No rate limiting (current state) | slowapi + Caddy request_body | Phase 12 | Protects against accidental self-DoS during large evidence ingestion |
| evtx_parser.py at 15% coverage | target 80%+ via unit tests | Phase 12 | Parser bugs become catchable; field mapping regressions detected |
| All phases land directly on master | Feature branch + PR → main | Phase 12 | Establishes code review checkpoint; CI required to pass before merge |

**Deprecated/outdated:**
- `evtx==0.11.0`: No `__version__` attribute on the module (verified). Use `pip show evtx` or `uv pip show evtx` to confirm version. This is normal for pyevtx-rs.

---

## Open Questions

1. **Rate limit values for expensive endpoints**
   - What we know: This is a single-analyst local tool. `POST /api/ingest/file` is the heaviest (Rust EVTX parsing + DuckDB writes + Chroma embedding). `POST /api/query/*` involves Ollama inference.
   - What's unclear: The analyst's actual workflow rate — how many queries per minute is normal vs. suspicious?
   - Recommendation: Use `10/minute` for `/api/ingest/file` (file uploads are slow anyway), `30/minute` for `/api/query/*` (streaming SSE, analyst can queue queries), `200/minute` for read-only endpoints. These protect against runaway scripts but never affect human usage.

2. **Should the limiter be disabled in test mode?**
   - What we know: The in-memory limiter state persists across test calls in the same pytest session. Current test suite has 466 passing tests; some make multiple calls to the same endpoint.
   - What's unclear: Exact count of tests that would hit rate limits.
   - Recommendation: In `create_app()`, check `if os.getenv("TESTING") == "1": limiter = Limiter(key_func=get_remote_address, enabled=False)`. Set `TESTING=1` in conftest.py. This is the cleanest approach.

3. **PR target branch: main vs master**
   - What we know: Local default is `master`; remote default is `main` (confirmed from git status header). They share recent history.
   - Recommendation: Branch from `master`, PR targets `main`. After merge, run `git checkout master && git pull origin main` to sync local master.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/unit/test_evtx_parser.py -x -q` |
| Full suite command | `uv run pytest tests/ --cov --cov-fail-under=70 -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P12-T01 | Rate limiter returns 429 after threshold | unit | `uv run pytest tests/unit/test_rate_limiting.py -x` | Wave 0 |
| P12-T02 | Caddy rejects body > limit with 413 | manual-only | Manual: `curl -X POST https://localhost/api/ingest/file -F "file=@bigfile"` | N/A |
| P12-T03 | EVTX parser helper functions | unit | `uv run pytest tests/unit/test_evtx_parser.py -x -q` | Wave 0 |
| P12-T04 | Coverage stays >= 70% | coverage gate | `uv run pytest tests/ --cov --cov-fail-under=70` | Existing CI |
| P12-T05 | PR CI passes | CI / manual | GitHub Actions on PR push | N/A |

P12-T02 is manual-only because testing Caddy body limits requires a running Docker Caddy instance (not available in unit test environment). The implementation can be verified with a one-line curl command.

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_evtx_parser.py -x -q`
- **Per wave merge:** `uv run pytest tests/ --cov --cov-fail-under=70 -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_evtx_parser.py` — covers P12-T03 (all helper functions + parse() with mock)
- [ ] `tests/unit/test_rate_limiting.py` — covers P12-T01 (slowapi 429 behavior, decorator order, disabled-in-test mode)

---

## Sources

### Primary (HIGH confidence)
- PyPI `slowapi` — version 0.1.9 confirmed via `uv run pip index versions slowapi`
- `ingestion/parsers/evtx_parser.py` — read directly; all function signatures and dict shape expectations verified
- `backend/main.py` — read directly; current middleware chain and router structure confirmed
- `config/caddy/Caddyfile` — read directly; current handler structure confirmed; Caddy v2.11.1 confirmed via `caddy version`
- `pyproject.toml` — read directly; `slowapi` is absent; `evtx==0.11.0` is present
- `uv run python -m coverage report` — 15% evtx_parser.py coverage confirmed; 70% overall confirmed
- Caddy docs https://caddyserver.com/docs/caddyfile/directives/request_body — `request_body` directive syntax confirmed; available since v2.10.0

### Secondary (MEDIUM confidence)
- https://slowapi.readthedocs.io/en/latest/ — integration pattern, decorator order requirement, `SlowAPIMiddleware` approach
- GitHub `laurentS/slowapi` — confirms active maintenance, WebSocket limitation

### Tertiary (LOW confidence)
- Rate limit values (10/min, 30/min, 200/min) are judgment calls based on single-analyst use case, not benchmarked

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — slowapi version verified on PyPI; evtx already installed and confirmed; Caddy version confirmed
- Architecture: HIGH — all patterns verified against actual source files in the repo; no assumptions
- Pitfalls: HIGH — decorator order and request parameter pitfalls are documented in slowapi official docs; Caddy handler order verified against existing Caddyfile structure
- Rate limit values: LOW — judgment call for single-analyst tool, not measured

**Research date:** 2026-03-26
**Valid until:** 2026-04-26 (slowapi is stable; Caddy directive is stable; evtx is pinned)
