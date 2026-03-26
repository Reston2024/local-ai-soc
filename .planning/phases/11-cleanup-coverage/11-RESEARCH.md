# Phase 11: Cleanup & Coverage - Research

**Researched:** 2026-03-26
**Domain:** Python test coverage, Docker image pinning, legacy directory removal, CI configuration
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P11-T01 | Delete `backend/src/` entirely; verify no import errors; update `docs/manifest.md` deprecated paths section | ADR-019 confirms deletion is safe; one deferred import of `backend.src.graph.builder` in `backend/causality/engine.py` must be patched first (see Critical Finding below) |
| P11-T02 | Pin Caddy image digest — run `docker inspect caddy:2.9-alpine`, update `docker-compose.yml` to `caddy:2.9-alpine@sha256:<digest>` | `docker-compose.yml` already has the TODO comment; exact `docker inspect` command documented |
| P11-T03 | Raise test coverage to ≥70% — add unit tests for ingestion pipeline, detection/matching, and store wrappers; update CI threshold from 25 to 70 | Current baseline is 27%; backend/src/ noise inflates miss-count; after deletion true baseline rises; gap analysis shows exactly which modules need tests |
| P11-T04 | Documentation update — remove `backend/src/` from `docs/manifest.md` deprecated paths; update ROADMAP.md Phase 11 status | `docs/manifest.md` line 69 already contains the deprecated entry; ROADMAP.md Phase 11 section needs status → COMPLETE |
</phase_requirements>

---

## Summary

Phase 11 is a four-task cleanup sprint. Three tasks are mechanical (directory deletion, image pin, doc update) and one is substantive (raising test coverage from 27% to 70%). The most important planning input is a **critical blocking dependency**: before `backend/src/` can be deleted, one live deferred import in `backend/causality/engine.py` line 84 must be redirected to the canonical `graph.builder` module (`from graph.builder import build_graph`). Without this patch, deletion will cause a silent runtime failure inside a `try/except` block — the exception will be swallowed but `build_graph` will never run.

The coverage gap is 43 percentage points. The fastest path is to add tests for the modules with the highest stmt-miss counts at low test difficulty: `backend/stores/` (duckdb_store, sqlite_store, chroma_store), `detections/matcher.py`, `ingestion/parsers/` (csv, evtx, osquery), and `ingestion/loader.py`. The `backend/src/` directory is currently being measured by `--cov=backend` and contributes ~1 500 uncovered statements that will disappear after deletion, giving roughly 3–4 percentage points for free.

**Primary recommendation:** Fix the `backend/causality/engine.py` deferred import, delete `backend/src/`, then write targeted unit tests for store wrappers and the detection matcher to cross the 70% line.

---

## Critical Finding: Live Import in backend/causality/engine.py

**BLOCKER for P11-T01.**

`backend/causality/engine.py` line 84 contains:

```python
# Step 8: Build graph (import deferred to avoid startup failure if builder absent)
try:
    from backend.src.graph.builder import build_graph
    ...
except Exception:
    nodes, edges, attack_paths = [], [], []
```

This import is deferred inside a `try/except Exception` block. After `backend/src/` is deleted the `ImportError` will be silently caught, and `nodes/edges/attack_paths` will always be empty lists. The system will not crash, but the causality graph will permanently stop being built without any visible error.

**Fix required before deletion:** Change the import to use the canonical module:
```python
from graph.builder import build_graph
```

The `graph/builder.py` canonical module exists at `C:\Users\Admin\AI-SOC-Brain\graph\builder.py` and is the module already documented in `docs/manifest.md`. This is a one-line change.

`backend/Dockerfile` also references `backend.src.api.main:app` in its CMD instruction — this Dockerfile appears to be a legacy artifact corresponding to the `backend/src/` layout and should be deleted together with `backend/src/` or updated to `backend.main:app`.

---

## Standard Stack

### Core (existing — confirmed by pyproject.toml)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| pytest | 9.0.2 | Test runner | Already installed |
| pytest-asyncio | 1.3.0 | Async test support | `asyncio_mode = "auto"` in pyproject.toml |
| pytest-cov | >=6.0.0 | Coverage measurement | In `[project.optional-dependencies] dev` — needs `uv sync --extra dev` |
| ruff | 0.15.6 | Linting | Already in CI |

### No new test dependencies needed
All tools are already present. The coverage gap is a writing problem, not a tooling problem.

### Verification command (current)
```bash
uv run pytest tests/unit/ tests/security/ \
  --cov=backend \
  --cov=ingestion \
  --cov=detections \
  --cov-report=term-missing \
  --cov-fail-under=70 \
  -q
```

---

## Current State Assessment

### Test suite (as of 2026-03-26)
- **117 tests collected** in `tests/unit/` + `tests/security/`
- **99 passed, 2 xfailed, 16 xpassed** — 16 xpassed means some xfail markers are stale
- **Overall coverage: 27%** (5627 total stmts, 4123 missed)

### Coverage by module (canonical packages only, excl. backend/src/)

| Module | Stmts | Miss | Cover | Priority |
|--------|-------|------|-------|----------|
| `detections/matcher.py` | 331 | 316 | 5% | HIGH — largest miss count |
| `backend/causality/` (all) | ~314 | ~274 | ~13% | MEDIUM |
| `backend/stores/sqlite_store.py` | 203 | 141 | 31% | HIGH — already has partial tests |
| `ingestion/loader.py` | 194 | 151 | 22% | HIGH |
| `backend/stores/duckdb_store.py` | 92 | 66 | 28% | HIGH |
| `ingestion/parsers/evtx_parser.py` | 141 | 120 | 15% | MEDIUM (Windows-only) |
| `backend/api/detect.py` | 90 | 59 | 34% | MEDIUM |
| `backend/services/ollama_client.py` | 153 | 98 | 36% | LOW (requires mocking) |
| `ingestion/parsers/csv_parser.py` | 115 | 77 | 33% | MEDIUM |
| `backend/api/events.py` | 88 | 70 | 20% | MEDIUM |
| `ingestion/parsers/osquery_parser.py` | 126 | 61 | 52% | MEDIUM |
| `backend/stores/chroma_store.py` | 50 | 28 | 44% | MEDIUM |
| `backend/investigation/timeline_builder.py` | 76 | 64 | 16% | MEDIUM |

### backend/src/ pollution of coverage numbers
`backend/src/` contributes **at least 1 500 uncovered statements** to the total. After deletion:
- Total measured stmts drops by ~1 500
- Total missed drops by ~1 500
- Coverage rises by roughly 3–5 percentage points for free
- Estimated post-deletion baseline: ~30–32%

### Gap to close after deletion: ~38–40 percentage points

---

## Architecture Patterns

### Pattern 1: Synchronous unit tests for pure-logic modules
**What:** Most modules can be tested without I/O by providing minimal stubs/mocks.
**When to use:** `detections/matcher.py`, `detections/field_map.py`, `ingestion/normalizer.py`, `backend/intelligence/` modules.
**Example:**
```python
# tests/unit/test_matcher.py
from detections.matcher import SigmaMatcherBackend
from detections.field_map import FIELD_MAP

def test_field_map_contains_process_name():
    assert "ProcessName" in FIELD_MAP or "process_name" in FIELD_MAP.values()

def test_matcher_compiles_simple_rule():
    rule_yaml = """
title: Test Rule
status: test
logsource:
    product: windows
    category: process_creation
detection:
    selection:
        CommandLine|contains: 'mimikatz'
    condition: selection
"""
    backend = SigmaMatcherBackend()
    result = backend.convert_rule_from_yaml(rule_yaml)
    assert "mimikatz" in result[0].lower()
```

### Pattern 2: SQLite store tests with in-memory database
**What:** `sqlite_store.py` accepts a path argument; use `:memory:` for unit tests.
**When to use:** `tests/unit/test_sqlite_store.py` already exists and uses this pattern — extend it.
**Example:**
```python
# Extend existing tests/unit/test_sqlite_store.py
import pytest
from backend.stores.sqlite_store import SQLiteStore

@pytest.fixture
def store(tmp_path):
    s = SQLiteStore(str(tmp_path / "test.sqlite3"))
    yield s
    s.close()

def test_insert_and_retrieve_edge(store):
    store.insert_edge("process", "pid-1", "ran_on", "host", "host-1", {})
    edges = store.get_edges("process", "pid-1")
    assert len(edges) == 1
    assert edges[0]["target_id"] == "host-1"
```

### Pattern 3: DuckDB store tests with temp file
**What:** DuckDB requires a real file (not `:memory:`) when using the write-queue pattern; use `tmp_path` fixture.
**When to use:** `backend/stores/duckdb_store.py` — currently 28% coverage.
**Example:**
```python
import pytest
import asyncio
from backend.stores.duckdb_store import DuckDBStore

@pytest.fixture
async def store(tmp_path):
    s = DuckDBStore(str(tmp_path / "test.duckdb"))
    await s.initialize()
    yield s
    await s.close()

async def test_write_and_fetch_event(store):
    await store.execute_write(
        "INSERT INTO events (event_id, timestamp, source_type) VALUES (?, ?, ?)",
        ["test-id-1", "2026-01-01T00:00:00", "json"]
    )
    rows = await store.fetch_all("SELECT event_id FROM events WHERE event_id = 'test-id-1'")
    assert rows[0]["event_id"] == "test-id-1"
```

### Pattern 4: Parser tests with fixture files
**What:** Parsers accept file paths; use `fixtures/` directory files or write inline content to `tmp_path`.
**When to use:** `ingestion/parsers/csv_parser.py`, `ingestion/parsers/json_parser.py`.
**Example:**
```python
def test_csv_parser_basic(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("timestamp,hostname,process_name\n2026-01-01,host1,cmd.exe\n")
    from ingestion.parsers.csv_parser import CsvParser
    parser = CsvParser()
    events = list(parser.parse(str(csv_file)))
    assert len(events) == 1
    assert events[0].hostname == "host1"
```

### Pattern 5: FastAPI TestClient for API route tests
**What:** Use `fastapi.testclient.TestClient` to test routes without running a server.
**When to use:** `backend/api/detect.py`, `backend/api/events.py`, `backend/api/export.py`.
**Example:**
```python
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

def test_detect_endpoint_returns_200(tmp_path):
    with patch("backend.stores.sqlite_store.SQLiteStore") as mock_sqlite:
        mock_sqlite.return_value.get_detections.return_value = []
        from backend.main import create_app
        app = create_app(testing=True)
        client = TestClient(app)
        response = client.get("/api/detect", headers={"Authorization": "Bearer test-token"})
        assert response.status_code == 200
```

### Anti-Patterns to Avoid

- **Testing backend/src/ modules:** Do NOT add new tests that import from `backend.src.*`. Those modules are being deleted. Any existing tests that do so must be removed or redirected.
- **Chasing causality coverage without fixing the import:** Do NOT add tests for `backend/causality/engine.py` until the `backend.src.graph.builder` import is patched — test isolation is meaningless on a module with a dead import.
- **Overfitting to xpassed tests:** 16 xpassed tests indicate stale `@pytest.mark.xfail` markers. Do not remove `xfail` markers unless you understand why they were added.
- **Using `--cov=backend/src` in any new test run:** After P11-T01, `backend/src/` is gone; CI must not reference it.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Coverage measurement | Custom coverage scripts | `pytest-cov` (already installed) | Integrated with pytest, CI-ready |
| Docker image digest lookup | Manual digest extraction | `docker inspect <image> --format '{{index .RepoDigests 0}}'` | Single command, outputs the exact digest string needed |
| Import validation after deletion | Manual import checks | `uv run python -c "import backend; import ingestion; import detections"` + `uv run pytest --collect-only` | Collection failures will surface any broken imports immediately |
| Legacy test cleanup | Scanning by hand | `grep -r "backend.src" tests/` | One command identifies all test files referencing deleted modules |

---

## Common Pitfalls

### Pitfall 1: Silent failure from deferred import after backend/src/ deletion
**What goes wrong:** `backend/causality/engine.py` wraps `from backend.src.graph.builder import build_graph` in `try/except Exception`. After deletion the ImportError is swallowed, causality graphs stop being built, and no error appears anywhere.
**Why it happens:** The try/except was written to tolerate builder absence at startup. It was never updated when the module path changed.
**How to avoid:** Patch the import to `from graph.builder import build_graph` BEFORE deleting `backend/src/`. Verify with `uv run python -c "from backend.causality.engine import build_alert_chain"`.
**Warning signs:** After deletion, all investigation API responses show `nodes: [], edges: [], attack_paths: []`.

### Pitfall 2: Dockerfile CMD still references backend.src after deletion
**What goes wrong:** `backend/Dockerfile` CMD is `uvicorn backend.src.api.main:app`. If Docker is ever used with this Dockerfile after `backend/src/` deletion, the container fails to start with a ModuleNotFoundError.
**Why it happens:** Dockerfile was never updated when the project migrated from the `backend/src/` layout to the canonical `backend/` layout.
**How to avoid:** Either delete `backend/Dockerfile` (it is a legacy artifact — the project uses native uvicorn, not Docker for FastAPI) or update it to `uvicorn backend.main:app`. Document the decision.

### Pitfall 3: Coverage drop after deleting backend/src/ test files
**What goes wrong:** `backend/src/tests/` contains 5 test files (test_phase2 through test_phase7, plus smoke_test.py) totalling ~568 statements. These are NOT collected by CI (CI runs `tests/unit/` and `tests/security/`). However, they ARE counted as uncovered statements in the `--cov=backend` measurement. Deleting them will reduce total missed stmts and raise coverage. Do NOT move these files into `tests/` — they import from `backend.src.*` and will fail.
**How to avoid:** Delete all of `backend/src/` including the test files inside it. Do not migrate them.

### Pitfall 4: CI coverage threshold update timing
**What goes wrong:** If CI threshold is raised to 70 before the tests actually achieve 70%, every CI run fails until coverage closes the gap. This is disruptive on the feature branch.
**How to avoid:** Write all new tests locally, confirm `uv run pytest --cov-fail-under=70` passes, then update `.github/workflows/ci.yml` in the same commit.

### Pitfall 5: docker inspect requires Docker Desktop to be running
**What goes wrong:** `docker inspect caddy:2.9-alpine` fails with "Cannot connect to Docker daemon" if Docker Desktop is stopped.
**How to avoid:** Ensure Docker Desktop is running before running `docker inspect`. Alternatively, use `docker pull caddy:2.9-alpine && docker inspect caddy:2.9-alpine --format '{{index .RepoDigests 0}}'` to guarantee the image is local.

### Pitfall 6: pytest.mark.unit not registered
**What goes wrong:** Multiple test files use `pytestmark = pytest.mark.unit` which generates `PytestUnknownMarkWarning`. This is cosmetic but noisy.
**How to avoid:** Add `markers = ["unit: unit tests"]` to `[tool.pytest.ini_options]` in `pyproject.toml` when updating test infrastructure. This is a cheap fix that should be included in P11-T03 scope.

---

## Coverage Gap Analysis

### Modules to target for maximum coverage gain

To reach 70% from ~32% (post-deletion baseline), approximately 2 100 additional statements need coverage. Prioritized by stmt-miss count and test difficulty:

**Tier 1 — High gain, low difficulty (pure logic, no I/O):**
| Module | Miss | Strategy |
|--------|------|----------|
| `detections/matcher.py` | 316 | Unit tests: compile sigma rules to SQL, test condition parsing |
| `detections/field_map.py` | 3 | Trivial: one import test covers it |
| `ingestion/normalizer.py` | 7 | Already 92% — trivial top-up |
| `backend/intelligence/anomaly_rules.py` | 1 | Already 96% — trivial |

**Tier 2 — Medium gain, medium difficulty (I/O with fixtures):**
| Module | Miss | Strategy |
|--------|------|----------|
| `backend/stores/sqlite_store.py` | 141 | Extend existing test_sqlite_store.py with more method coverage |
| `ingestion/loader.py` | 151 | Test batch logic with in-memory DuckDB + mock Chroma |
| `backend/stores/duckdb_store.py` | 66 | Extend with write queue + fetch_all tests (tmp_path) |
| `ingestion/parsers/csv_parser.py` | 77 | Use tmp_path CSV fixture |
| `backend/investigation/timeline_builder.py` | 64 | Pure function — pass event dicts, assert output |
| `backend/api/detect.py` | 59 | TestClient with mock stores |
| `backend/stores/chroma_store.py` | 28 | Mock chromadb.PersistentClient |
| `backend/api/events.py` | 70 | TestClient with mock DuckDB |

**Tier 3 — Lower priority (complex mocking or Windows-specific):**
| Module | Miss | Strategy |
|--------|------|----------|
| `ingestion/parsers/evtx_parser.py` | 120 | Requires real .evtx fixture or mock pyevtx-rs |
| `backend/services/ollama_client.py` | 98 | Mock httpx responses |
| `backend/causality/engine.py` | 49 | Depends on P11-T01 import fix first |

**Estimated statements needed from Tier 1+2 to reach 70%:**
- Post-deletion baseline (approx): 4100 stmts, 2800 missed → 32%
- Target 70%: need 4100 * 0.70 = 2870 covered → need ~1670 more covered (from current ~1300 covered)
- Tier 1+2 provides ~900 coverable statements at reasonable test difficulty
- Combining Tier 1 + Tier 2 partially should be sufficient; Tier 3 adds buffer

---

## Code Examples

### Caddy image pinning (P11-T02)

Step 1 — Get the digest:
```bash
# Run this with Docker Desktop active
docker inspect caddy:2.9-alpine --format '{{index .RepoDigests 0}}'
# Output example: caddy@sha256:a1b2c3d4e5f6...
```

Step 2 — Update docker-compose.yml:
```yaml
services:
  caddy:
    image: caddy:2.9-alpine@sha256:<digest>
    # Replace <digest> with the full sha256 hex string from docker inspect
```

The digest is immutable — it identifies a specific layer hash, not a mutable tag. Future `docker pull caddy:2.9-alpine` updates will not affect a digest-pinned deployment.

### backend/src/ deletion (P11-T01)

Ordered sequence:
```bash
# Step 1: Patch the live import FIRST
# Edit backend/causality/engine.py line 84:
#   from backend.src.graph.builder import build_graph
# → from graph.builder import build_graph

# Step 2: Verify the fix imports cleanly
uv run python -c "from backend.causality.engine import build_alert_chain; print('OK')"

# Step 3: Delete backend/src/ and backend/Dockerfile
rm -rf backend/src/
rm -f backend/Dockerfile

# Step 4: Verify no broken imports across the entire package
uv run python -c "import backend; import ingestion; import detections; import correlation; import graph; import prompts"
uv run pytest tests/unit/ tests/security/ --collect-only -q

# Step 5: Update docs/manifest.md — remove backend/src/ from Deprecated Paths section
```

### CI threshold update (P11-T03)

In `.github/workflows/ci.yml`, change line 45:
```yaml
# Before:
--cov-fail-under=25 \
# After:
--cov-fail-under=70 \
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/unit/ tests/security/ -q` |
| Full suite command | `uv run pytest tests/unit/ tests/security/ --cov=backend --cov=ingestion --cov=detections --cov-fail-under=70 -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P11-T01 | No import errors after backend/src/ deletion | smoke | `uv run python -c "import backend; import ingestion; import detections"` | N/A — shell check |
| P11-T01 | pytest collection succeeds after deletion | smoke | `uv run pytest tests/unit/ tests/security/ --collect-only -q` | N/A — collection check |
| P11-T02 | docker-compose.yml references digest format | unit | `grep "sha256:" docker-compose.yml` | N/A — grep check |
| P11-T03 | Coverage ≥70% | suite | `uv run pytest tests/unit/ tests/security/ --cov=backend --cov=ingestion --cov=detections --cov-fail-under=70 -q` | Existing + new |
| P11-T03 | Detection matcher compiles sigma rules | unit | `uv run pytest tests/unit/test_matcher.py -x` | ❌ Wave 0 |
| P11-T03 | Store wrappers execute basic CRUD | unit | `uv run pytest tests/unit/test_duckdb_store.py tests/unit/test_sqlite_store.py -x` | partial ✅ |
| P11-T03 | CSV/JSON parsers produce NormalizedEvent | unit | `uv run pytest tests/unit/test_csv_parser.py tests/unit/test_json_parser.py -x` | partial ✅ |
| P11-T04 | manifest.md no longer lists backend/src/ as active | manual | `grep "DEPRECATED\|backend/src" docs/manifest.md` | ✅ |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/ tests/security/ -q`
- **Per wave merge:** `uv run pytest tests/unit/ tests/security/ --cov=backend --cov=ingestion --cov=detections --cov-fail-under=70 -q`
- **Phase gate:** Full suite green with ≥70% before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_matcher.py` — covers `detections/matcher.py` (currently 5%)
- [ ] `tests/unit/test_duckdb_store.py` — extend beyond current minimal coverage (currently 28%)
- [ ] `tests/unit/test_csv_parser.py` — covers `ingestion/parsers/csv_parser.py` (currently 33%)
- [ ] `tests/unit/test_loader.py` — covers `ingestion/loader.py` batch logic (currently 22%)
- [ ] `tests/unit/test_timeline_builder.py` — covers `backend/investigation/timeline_builder.py` (currently 16%)
- [ ] Register `unit` mark in `pyproject.toml` to eliminate PytestUnknownMarkWarning

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `backend/src/` layout (Phase 1-2) | Flat `backend/` layout (Phase 3+) | Phase 3 migration | `backend/src/` is now dead code; ADR-019 authorized deletion |
| `--cov-fail-under=25` (Phase 10 baseline) | `--cov-fail-under=70` (Phase 11 target) | This phase | CI gates become meaningful |
| Unpinned `caddy:2.9-alpine` tag | Digest-pinned `caddy:2.9-alpine@sha256:...` | This phase | Eliminates silent upstream image changes |

**Deprecated/outdated:**
- `backend/src/`: All files are legacy from Phase 1-2. No active code imports from these modules (except the one deferred import identified above). Deletion authorized by ADR-019.
- `backend/Dockerfile`: References `backend.src.api.main:app`. The project runs FastAPI natively via uvicorn, not inside Docker. This Dockerfile is a dead artifact.
- `backend/src/tests/test_phase*.py`: These are Phase 1-5 test files using the old `backend.src.*` import path. They are NOT collected by CI. Do not migrate them.

---

## Open Questions

1. **`backend/Dockerfile` disposition**
   - What we know: It references the deleted `backend.src.api.main:app` and was never used in production (FastAPI runs native)
   - What's unclear: Is it intentionally kept as a template for future containerization?
   - Recommendation: Delete it alongside `backend/src/`. If containerization is ever needed, a new Dockerfile should be written from scratch targeting the canonical `backend.main:app`.

2. **Exact post-deletion coverage number**
   - What we know: Current coverage is 27% with backend/src/ in scope; after deletion, the denominator shrinks by ~1500 stmts
   - What's unclear: Exact new baseline until deletion is performed
   - Recommendation: Delete first, run coverage, then write tests to close the gap. The math suggests ~30–32% post-deletion baseline is safe to assume for planning.

3. **xpassed test markers**
   - What we know: 16 tests marked `xfail` are now passing (xpassed), which means their anticipated failures have been fixed
   - What's unclear: Whether the `xfail` markers were `strict=True` (which would flip to failure) or loose
   - Recommendation: Audit `@pytest.mark.xfail` markers during P11-T03 work. Clean up stale ones to avoid future confusion.

---

## Sources

### Primary (HIGH confidence)
- Direct file reads: `pyproject.toml`, `.github/workflows/ci.yml`, `docker-compose.yml`, `DECISION_LOG.md` (ADR-019), `docs/manifest.md`
- Direct code scan: `backend/causality/engine.py` line 84 — confirmed live `backend.src` import
- Test run: `uv run pytest tests/unit/ tests/security/ --cov` — confirmed 27% baseline, 117 tests collected

### Secondary (MEDIUM confidence)
- ADR-019 decision: "No code imports `backend.src.*` — deletion risk is low" — partially incorrect (one deferred import found in engine.py); ADR was accurate for module-level imports but missed this deferred try/except import

### Tertiary (LOW confidence)
- Post-deletion coverage estimate of 30–32%: Calculated from statement counts, not measured directly

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all tooling confirmed from pyproject.toml and CI config
- Architecture (test patterns): HIGH — based on existing tests in the codebase and pytest conventions
- Coverage gap analysis: HIGH — measured live from running pytest --cov
- Pitfalls: HIGH — deferred import issue confirmed by direct code scan

**Research date:** 2026-03-26
**Valid until:** 2026-04-25 (stable tooling; coverage numbers are live and won't change until implementation)
