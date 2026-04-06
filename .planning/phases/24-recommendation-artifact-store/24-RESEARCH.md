# Phase 24: Recommendation Artifact Store and Approval API - Research

**Researched:** 2026-04-05
**Domain:** FastAPI CRUD API + DuckDB schema migration + Pydantic v2 model + JSON Schema validation + human-in-the-loop gate
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P24-T01 | DuckDB tables: `recommendations` (all artifact fields, status enum) and `recommendation_dispatch_log`; schema migration via existing store migration pattern | DuckDB migration pattern documented — try/except ALTER TABLE, `initialise_schema()` extension |
| P24-T02 | `RecommendationArtifact` Pydantic model mirroring `contracts/recommendation.schema.json` v1.0.0; `prompt_inspection` as nested model; full jsonschema validation on instantiation | jsonschema 4.26.0 confirmed installed; Pydantic v2 nested model pattern from existing codebase |
| P24-T03 | POST /api/recommendations (create draft); GET /api/recommendations/{id}; PATCH /api/recommendations/{id}/approve; GET /api/recommendations (list with filters) | APIRouter pattern with `request.app.state.stores.duckdb` confirmed |
| P24-T04 | PATCH /approve enforces gate: schema valid, analyst_approved only via this endpoint, approved_by non-empty, expires_at in future, override_log required for low/none confidence or failed inspection; 422 on gate failure | 422 via HTTPException; gate logic maps directly from ADR-030 §2 and §4 |
| P24-T05 | Unit tests for model validation; integration tests for all four API routes; gate enforcement tests; at least 10 test cases | pytest-asyncio auto mode; TestClient + dependency_overrides pattern from existing test suite |
</phase_requirements>

---

## Summary

Phase 24 implements the recommendation artifact lifecycle: draft creation, persistent storage in DuckDB, analyst approval via a governed gate endpoint, and list/retrieve access. The phase is governed by ADR-030 which is already fully specified in `docs/ADR-030-ai-recommendation-governance.md` and backed by a machine-readable JSON Schema at `contracts/recommendation.schema.json`. No technology decisions are open — the stack is fully determined by the existing project.

The two DuckDB tables follow the exact same migration pattern used throughout the codebase: `CREATE TABLE IF NOT EXISTS` in `initialise_schema()`, with additive `ALTER TABLE` migrations wrapped in `try/except` for idempotency. The Pydantic model mirrors the JSON Schema with a nested `PromptInspection` model and uses a `model_validator` to run `jsonschema.validate()` against the pinned `contracts/` file. The API routes use the existing `APIRouter` + `request.app.state.stores.duckdb` pattern with `await store.execute_write()` for writes and `await store.fetch_all()` for reads. The approval gate is a pure business-logic function that returns structured 422 errors on failure.

**Primary recommendation:** Implement in three layers — (1) DuckDB schema migration in `duckdb_store.py`, (2) `RecommendationArtifact` model in `backend/models/recommendation.py`, (3) API routes in `backend/api/recommendations.py` wired into `main.py`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| duckdb | 1.3.0 | Recommendation and dispatch log persistence | Project-wide analytical store, single-writer pattern |
| pydantic | 2.12.5 | `RecommendationArtifact` model + request/response bodies | Project-wide model library |
| jsonschema | 4.26.0 | Full JSON Schema Draft 2020-12 validation against `contracts/recommendation.schema.json` | Already installed in venv; confirmed via import |
| fastapi | 0.115.12 | API routing, 422 HTTPException | Project-wide web framework |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| uuid | stdlib | Generate `recommendation_id`, `model_run_id` sentinel | All new artifact creation |
| datetime | stdlib | `generated_at`, `expires_at`, `approved_at` UTC timestamps | All timestamp fields |
| json | stdlib | Serialize `rationale[]`, `evidence_event_ids[]`, `override_log{}` as TEXT in DuckDB | Storing array/object fields as JSON blobs |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| DuckDB TEXT for arrays | DuckDB LIST type | LIST is available in DuckDB 1.3 but TEXT+JSON matches the established pattern in existing tables (tags, matched_event_ids) — stick with TEXT+JSON |
| jsonschema validate on model_validator | Pydantic field validators only | Field validators cannot enforce `allOf`/`if-then` cross-field rules in JSON Schema; jsonschema handles the full spec |

**Installation:**
No new dependencies required — all libraries are already in pyproject.toml.

---

## Architecture Patterns

### Recommended Project Structure
```
backend/
├── models/
│   └── recommendation.py      # RecommendationArtifact, PromptInspection, ApproveRequest, etc.
├── api/
│   └── recommendations.py     # POST/GET/PATCH routes, gate logic
├── stores/
│   └── duckdb_store.py        # Extended: _CREATE_RECOMMENDATIONS_TABLE, _CREATE_DISPATCH_LOG_TABLE
contracts/
└── recommendation.schema.json  # Pinned — do not modify
tests/
├── unit/
│   └── test_recommendation_model.py   # Model validation, gate logic unit tests
└── integration/
    └── test_recommendations_api.py    # Full API route integration tests
```

### Pattern 1: DuckDB Schema Migration (additive)
**What:** New tables added in `initialise_schema()` using `CREATE TABLE IF NOT EXISTS`. New columns on existing tables use `try/except ALTER TABLE`.
**When to use:** Every time a new table or column is needed — never drop/recreate.
**Example:**
```python
# Source: backend/stores/duckdb_store.py (existing pattern)
_CREATE_RECOMMENDATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id   TEXT PRIMARY KEY,
    case_id             TEXT NOT NULL,
    schema_version      TEXT NOT NULL DEFAULT '1.0.0',
    type                TEXT NOT NULL,
    proposed_action     TEXT NOT NULL,
    target              TEXT NOT NULL,
    scope               TEXT NOT NULL,
    rationale           TEXT NOT NULL,          -- JSON array
    evidence_event_ids  TEXT NOT NULL,           -- JSON array
    retrieval_sources   TEXT NOT NULL,           -- JSON object
    inference_confidence TEXT NOT NULL,
    model_id            TEXT NOT NULL,
    model_run_id        TEXT NOT NULL,
    prompt_inspection   TEXT NOT NULL,           -- JSON object
    generated_at        TIMESTAMP NOT NULL,
    analyst_approved    BOOLEAN NOT NULL DEFAULT FALSE,
    approved_by         TEXT NOT NULL DEFAULT '',
    override_log        TEXT,                    -- JSON object, nullable
    expires_at          TIMESTAMP NOT NULL,
    status              TEXT NOT NULL DEFAULT 'draft',  -- draft | approved | dispatched
    created_at          TIMESTAMP NOT NULL
)
"""

_CREATE_DISPATCH_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS recommendation_dispatch_log (
    log_id              TEXT PRIMARY KEY,
    recommendation_id   TEXT NOT NULL,
    dispatched_at       TIMESTAMP NOT NULL,
    http_status         INTEGER,
    response_body       TEXT,
    failure_taxonomy    TEXT,
    FOREIGN KEY (recommendation_id) REFERENCES recommendations(recommendation_id)
)
"""
```

In `initialise_schema()`, call:
```python
await self.execute_write(_CREATE_RECOMMENDATIONS_TABLE)
await self.execute_write(_CREATE_RECOMMENDATIONS_INDEX)
await self.execute_write(_CREATE_DISPATCH_LOG_TABLE)
```

### Pattern 2: Pydantic Model with Nested Sub-model and Cross-field Validation
**What:** `PromptInspection` as a nested `BaseModel`; `RecommendationArtifact` with a `model_validator(mode='after')` that calls `jsonschema.validate()`.
**When to use:** Any model where JSON Schema `allOf`/`if-then` cross-field rules must be enforced programmatically.
**Example:**
```python
# Source: backend/models/playbook.py pattern + jsonschema library
import json
from pathlib import Path
from typing import Literal, Optional
from uuid import UUID

import jsonschema
from pydantic import BaseModel, ConfigDict, Field, model_validator

_SCHEMA_PATH = Path(__file__).parent.parent.parent / "contracts" / "recommendation.schema.json"
_SCHEMA: dict = json.loads(_SCHEMA_PATH.read_text())


class PromptInspection(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    method: str
    passed: bool
    flagged_patterns: list[str] = Field(default_factory=list)
    audit_log_id: str  # UUID v4 as string


class RetrievalSources(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    count: int
    ids: list[str] = Field(default_factory=list)


class OverrideLog(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    approved_at: str
    approval_basis: str
    modified_fields: list[str] = Field(default_factory=list)
    operator_note: str = ""


class RecommendationArtifact(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    schema_version: Literal["1.0.0"] = "1.0.0"
    recommendation_id: str           # UUID v4
    case_id: str                     # UUID v4
    type: Literal["network_control_change", "alert_suppression", "asset_isolation", "no_action"]
    proposed_action: str
    target: str
    scope: str
    rationale: list[str]
    evidence_event_ids: list[str]
    retrieval_sources: RetrievalSources
    inference_confidence: Literal["high", "medium", "low", "none"]
    model_id: str
    model_run_id: str
    prompt_inspection: PromptInspection
    generated_at: str                # ISO-8601 date-time
    analyst_approved: bool = False
    approved_by: str = ""
    override_log: Optional[OverrideLog] = None
    expires_at: str                  # ISO-8601 date-time

    @model_validator(mode="after")
    def validate_against_json_schema(self) -> "RecommendationArtifact":
        """Full JSON Schema validation against contracts/recommendation.schema.json."""
        data = self.model_dump(mode="json")
        # Remove None values that are optional
        data = {k: v for k, v in data.items() if v is not None}
        try:
            jsonschema.validate(instance=data, schema=_SCHEMA)
        except jsonschema.ValidationError as exc:
            raise ValueError(f"JSON Schema validation failed: {exc.message}") from exc
        return self
```

### Pattern 3: API Route File Structure
**What:** `APIRouter` with prefix `/api/recommendations`, routes using `request.app.state.stores.duckdb`.
**When to use:** Every new API feature in this project.
**Example:**
```python
# Source: backend/api/playbooks.py + firewall.py patterns
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.post("", status_code=201)
async def create_recommendation(body: RecommendationCreate, request: Request) -> JSONResponse:
    stores = request.app.state.stores
    rec_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await stores.duckdb.execute_write(_INSERT_SQL, [rec_id, ...])
    return JSONResponse(content={"recommendation_id": rec_id}, status_code=201)


@router.get("/{recommendation_id}")
async def get_recommendation(recommendation_id: str, request: Request) -> JSONResponse:
    stores = request.app.state.stores
    rows = await stores.duckdb.fetch_all(
        "SELECT * FROM recommendations WHERE recommendation_id = ?",
        [recommendation_id]
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return JSONResponse(content=_row_to_dict(rows[0]))
```

### Pattern 4: Human-in-the-Loop Gate (PATCH /approve)
**What:** The approve endpoint enforces all gate conditions from ADR-030 §2 and §4 before setting `analyst_approved=true`. Gate failures MUST return 422 with structured error detail.
**When to use:** This is the only path that sets `analyst_approved=true`. Never allow direct field updates.
**Example:**
```python
class ApproveRequest(BaseModel):
    approved_by: str
    override_log: Optional[OverrideLog] = None


@router.patch("/{recommendation_id}/approve")
async def approve_recommendation(
    recommendation_id: str, body: ApproveRequest, request: Request
) -> JSONResponse:
    stores = request.app.state.stores
    rows = await stores.duckdb.fetch_all(
        "SELECT * FROM recommendations WHERE recommendation_id = ?",
        [recommendation_id]
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec = _row_to_dict(rows[0])
    errors = _run_approval_gate(rec, body)
    if errors:
        raise HTTPException(status_code=422, detail={"gate_errors": errors})

    # Reconstruct updated artifact, validate full schema
    override_json = body.override_log.model_dump(mode="json") if body.override_log else None
    await stores.duckdb.execute_write(
        "UPDATE recommendations SET analyst_approved=true, approved_by=?, override_log=?, "
        "status='approved' WHERE recommendation_id=?",
        [body.approved_by, json.dumps(override_json), recommendation_id]
    )
    return JSONResponse(content={"status": "approved", "recommendation_id": recommendation_id})


def _run_approval_gate(rec: dict, body: ApproveRequest) -> list[str]:
    """
    Returns a list of error strings. Empty list = gate passes.
    Enforces ADR-030 §2 + §4.
    """
    errors: list[str] = []
    # Gate condition 1: approved_by must be non-empty
    if not body.approved_by.strip():
        errors.append("approved_by must be non-empty")
    # Gate condition 2: expires_at must be in the future
    expires_at = datetime.fromisoformat(rec["expires_at"].replace("Z", "+00:00"))
    if expires_at <= datetime.now(timezone.utc):
        errors.append("expires_at is in the past — artifact has expired")
    # Gate condition 3: override_log required for low/none confidence or failed inspection
    confidence = rec["inference_confidence"]
    inspection = json.loads(rec["prompt_inspection"])
    needs_override = confidence in ("low", "none") or not inspection.get("passed", True)
    if needs_override and body.override_log is None:
        errors.append(
            "override_log is required when inference_confidence is 'low'/'none' "
            "or prompt_inspection.passed is false"
        )
    return errors
```

### Anti-Patterns to Avoid
- **Setting `analyst_approved=true` outside the gate endpoint:** The POST (create draft) must always create with `analyst_approved=false`. Any route other than PATCH /approve that touches this field is a governance violation.
- **Mutable artifacts after approval:** ADR-030 §1 states the artifact is immutable once approved. The PATCH /approve should reject updates to an already-approved artifact (return 409 Conflict).
- **Using DuckDB BOOLEAN type for `analyst_approved` as a filter directly:** DuckDB stores BOOLEAN; use `WHERE analyst_approved = TRUE` not `= 1`.
- **Storing arrays natively in DuckDB as LIST:** Use TEXT + JSON serialization for arrays and objects, matching the existing `matched_event_ids`, `tags` pattern in the codebase.
- **Forgetting `enable_external_access = false`:** All new connections get this automatically via `get_read_conn()` and `_write_conn` constructor — no action needed in application code.
- **Blocking the event loop:** ALL DuckDB calls must go through `execute_write()` (for writes) or `fetch_all()` / `fetch_df()` (for reads) — never call `conn.execute()` directly in an async route.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON Schema cross-field `allOf`/`if-then` validation | Custom Python cross-field logic | `jsonschema.validate()` against `contracts/recommendation.schema.json` | JSON Schema Draft 2020-12 `if/then` on `analyst_approved` and `inference_confidence` is already specified; jsonschema handles it correctly |
| UUID generation | Custom ID schemes | `str(uuid4())` | UUIDs are required by the schema's `"format": "uuid"` constraint |
| ISO-8601 timestamp formatting | Custom strftime | `datetime.now(timezone.utc).isoformat()` | Matches pattern used throughout the codebase |
| Array/object field serialization | Custom encoding | `json.dumps()` / `json.loads()` | Matches existing `matched_event_ids`, `tags`, `steps` TEXT+JSON pattern |

**Key insight:** The JSON Schema already specifies the complete validation logic — implementing it twice in Python would create a divergence risk. The `model_validator` that calls `jsonschema.validate()` is the canonical approach.

---

## Common Pitfalls

### Pitfall 1: DuckDB BOOLEAN Column with Python bool Parameters
**What goes wrong:** DuckDB 1.3 can be finicky about Python `bool` vs `int` in parameterized queries. Passing `True`/`False` directly sometimes results in unexpected type coercion.
**Why it happens:** DuckDB's Python binding accepts `bool` but query results return them as Python `bool` which must be handled carefully in `_row_to_dict()`.
**How to avoid:** Explicitly cast in SELECT: `CAST(analyst_approved AS BOOLEAN)` and handle the Python `bool` result correctly when building response dicts.
**Warning signs:** Test assertions on `analyst_approved` returning `0`/`1` instead of `True`/`False`.

### Pitfall 2: `expires_at` Timezone Comparison
**What goes wrong:** `datetime.fromisoformat()` on a naive ISO string returns a naive datetime; comparing with `datetime.now(timezone.utc)` raises `TypeError`.
**Why it happens:** ISO-8601 strings without `+00:00` or `Z` are timezone-naive. DuckDB may strip timezone info on storage/retrieval.
**How to avoid:** Always store `expires_at` as a timezone-aware string (append `+00:00`). In the gate check, use `.replace("Z", "+00:00")` before `fromisoformat()`, and always compare against `datetime.now(timezone.utc)`.
**Warning signs:** `TypeError: can't compare offset-naive and offset-aware datetimes`.

### Pitfall 3: `jsonschema.validate()` on model_dump() Output
**What goes wrong:** `model_dump(mode="json")` on the Pydantic model may include `None` for optional fields (`override_log`). The schema has `"additionalProperties": false` — if `None`-valued keys are present, it may cause unexpected validation behavior.
**Why it happens:** `model_dump()` by default includes all fields including those set to `None`.
**How to avoid:** Use `model_dump(mode="json", exclude_none=True)` before passing to `jsonschema.validate()`. The schema's `allOf` `if-then` for `override_log` works correctly when the key is absent rather than `null`.
**Warning signs:** `jsonschema.ValidationError: None is not valid under any of the given schemas`.

### Pitfall 4: DuckDB `FOREIGN KEY` Constraint Not Enforced
**What goes wrong:** DuckDB 1.3 does not enforce `FOREIGN KEY` constraints by default — `recommendation_dispatch_log` rows can reference non-existent `recommendation_id` values.
**Why it happens:** DuckDB does not implement FK enforcement (unlike SQLite with `PRAGMA foreign_keys=ON`).
**How to avoid:** Enforce referential integrity at the application layer in the route handler: verify the recommendation exists before inserting a dispatch log row.
**Warning signs:** Silent data integrity violations in dispatch_log.

### Pitfall 5: Immutability After Approval
**What goes wrong:** A PATCH /approve on an already-approved recommendation silently overwrites the `approved_by` or `override_log`.
**Why it happens:** No guard on the approval endpoint against double-approval.
**How to avoid:** Check `rec["analyst_approved"]` in the gate function. If already `true`, return 409 Conflict: `"artifact is immutable after approval"`.
**Warning signs:** Audit log shows multiple approvals for the same `recommendation_id`.

### Pitfall 6: Missing Router Registration in main.py
**What goes wrong:** Routes 404 even though the file is correct.
**Why it happens:** `main.py` explicitly imports and includes each router — new routers are not auto-discovered.
**How to avoid:** Add `from backend.api.recommendations import router as recommendations_router` and `app.include_router(recommendations_router)` in `main.py`. Follow the exact import grouping pattern (import at top of lifespan section).
**Warning signs:** All recommendation endpoints return 404 in integration tests.

---

## Code Examples

Verified patterns from official sources and codebase:

### DuckDB Row to Dict (column name extraction)
```python
# Source: backend/stores/duckdb_store.py fetch_df pattern
async def fetch_recommendation(store, rec_id: str) -> dict | None:
    rows = await store.fetch_df(
        "SELECT * FROM recommendations WHERE recommendation_id = ?",
        [rec_id]
    )
    return rows[0] if rows else None
```

Note: `fetch_df()` returns `list[dict]` (column-name keyed) — prefer over `fetch_all()` which returns `list[tuple]` requiring manual column mapping.

### Approval Gate Test Pattern
```python
# Source: tests/unit/test_api_endpoints.py pattern
def test_approve_requires_override_log_for_low_confidence():
    errors = _run_approval_gate(
        rec={"inference_confidence": "low", "prompt_inspection": '{"passed": true}',
             "expires_at": "2099-01-01T00:00:00+00:00", "analyst_approved": False},
        body=ApproveRequest(approved_by="analyst1", override_log=None)
    )
    assert "override_log is required" in errors[0]
```

### TestClient Integration Test Pattern
```python
# Source: tests/unit/test_api_endpoints.py
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from backend.main import create_app
from backend.core.auth import verify_token
from backend.core.rbac import OperatorContext
from backend.core.deps import Stores

def _build_app(duckdb_mock=None):
    app = create_app()
    duckdb = duckdb_mock or MagicMock()
    duckdb.execute_write = AsyncMock(return_value=None)
    duckdb.fetch_df = AsyncMock(return_value=[])
    duckdb.fetch_all = AsyncMock(return_value=[])
    app.state.stores = Stores(duckdb=duckdb, chroma=MagicMock(), sqlite=MagicMock())
    app.state.ollama = MagicMock()
    app.state.settings = MagicMock()
    _ctx = OperatorContext(operator_id="test-admin", username="test", role="admin")
    app.dependency_overrides[verify_token] = lambda: _ctx
    return TestClient(app, raise_server_exceptions=True)
```

### JSON Schema Validation (draft 2020-12)
```python
# Source: jsonschema 4.26.0 — confirmed installed
import json
from pathlib import Path
import jsonschema

_SCHEMA = json.loads(
    (Path(__file__).parent.parent.parent / "contracts" / "recommendation.schema.json").read_text()
)

def validate_artifact(data: dict) -> None:
    """Raises jsonschema.ValidationError on failure."""
    jsonschema.validate(instance=data, schema=_SCHEMA)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Boolean `analyst_approved` flag with no audit | Structured `override_log` required for low-confidence approvals | ADR-030 (2026-04-03) | Cannot distinguish "passed because ran" vs "passed because skipped" |
| Ad-hoc recommendation storage | Versioned JSON Schema artifact in DuckDB | Phase 24 (now) | Full audit trail with schema version pinning |

**Deprecated/outdated:**
- None applicable — this is a new capability.

---

## Open Questions

1. **`fetch_df()` vs `fetch_all()` for recommendations**
   - What we know: `fetch_df()` returns `list[dict]`, `fetch_all()` returns `list[tuple]`. `fetch_df()` is cleaner for complex multi-column tables.
   - What's unclear: Whether column ordering guarantees exist with `fetch_df()` given DuckDB's optimizer.
   - Recommendation: Use `fetch_df()` for all recommendation reads — column names are explicit and stable.

2. **`recommendation_dispatch_log` in Phase 24 scope**
   - What we know: P24-T01 requires both tables. P24-T03/T04 only mention recommendation CRUD and the approval gate. Dispatch itself (sending to firewall) is likely Phase 25+.
   - What's unclear: Whether the planner should include dispatch log write tests or stub the table only.
   - Recommendation: Create the table schema in P24-T01 and include it in tests as a "table exists" check. Actual dispatch log writes belong to the future dispatch phase.

3. **`main.py` router registration ordering**
   - What we know: Existing routers are imported in a specific order. Rate limiting via `slowapi` applies globally.
   - Recommendation: Add recommendations router in the same import block as other API routers; no special ordering needed.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `asyncio_mode = "auto"` |
| Quick run command | `uv run pytest tests/unit/test_recommendation_model.py -x -q` |
| Full suite command | `uv run pytest -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P24-T01 | DuckDB tables created on `initialise_schema()` | unit | `uv run pytest tests/unit/test_recommendation_model.py::test_duckdb_tables_exist -x` | Wave 0 |
| P24-T02 | `RecommendationArtifact` validates required fields | unit | `uv run pytest tests/unit/test_recommendation_model.py::test_model_required_fields -x` | Wave 0 |
| P24-T02 | `RecommendationArtifact` rejects invalid `type` enum | unit | `uv run pytest tests/unit/test_recommendation_model.py::test_model_invalid_type -x` | Wave 0 |
| P24-T02 | `PromptInspection` sub-model validates correctly | unit | `uv run pytest tests/unit/test_recommendation_model.py::test_prompt_inspection_model -x` | Wave 0 |
| P24-T02 | `jsonschema.validate()` catches cross-field violations | unit | `uv run pytest tests/unit/test_recommendation_model.py::test_json_schema_allof -x` | Wave 0 |
| P24-T03 | POST /api/recommendations creates draft | integration | `uv run pytest tests/unit/test_recommendation_model.py::test_post_creates_draft -x` | Wave 0 |
| P24-T03 | GET /api/recommendations/{id} returns 404 when missing | integration | `uv run pytest tests/unit/test_recommendation_model.py::test_get_not_found -x` | Wave 0 |
| P24-T03 | GET /api/recommendations with filters | integration | `uv run pytest tests/unit/test_recommendation_model.py::test_list_with_filters -x` | Wave 0 |
| P24-T04 | PATCH /approve passes for valid high-confidence artifact | integration | `uv run pytest tests/unit/test_recommendation_model.py::test_approve_gate_passes -x` | Wave 0 |
| P24-T04 | PATCH /approve fails (422) when override_log missing for low confidence | integration | `uv run pytest tests/unit/test_recommendation_model.py::test_approve_gate_requires_override -x` | Wave 0 |
| P24-T04 | PATCH /approve fails (422) when expires_at in past | integration | `uv run pytest tests/unit/test_recommendation_model.py::test_approve_gate_expired -x` | Wave 0 |
| P24-T04 | PATCH /approve fails (409) when already approved | integration | `uv run pytest tests/unit/test_recommendation_model.py::test_approve_idempotency -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_recommendation_model.py -x -q`
- **Per wave merge:** `uv run pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_recommendation_model.py` — covers P24-T02 model unit tests and P24-T03/T04 API integration tests
- [ ] `backend/models/recommendation.py` — new file (model definitions)
- [ ] `backend/api/recommendations.py` — new file (route definitions)

*(Existing `tests/unit/test_duckdb_store.py` and `tests/unit/test_duckdb_migration.py` do NOT cover the new tables — new test coverage required.)*

---

## Sources

### Primary (HIGH confidence)
- `contracts/recommendation.schema.json` — complete artifact schema, all fields, types, constraints, `allOf` rules
- `docs/ADR-030-ai-recommendation-governance.md` — governance rules for gate conditions, override_log requirements, immutability
- `docs/ADR-031-transport-contract-reference.md` — dispatch log obligation (record every dispatch attempt)
- `docs/ADR-032-executor-failure-reference.md` — failure_taxonomy enum values for dispatch_log
- `backend/stores/duckdb_store.py` — schema migration pattern (CREATE TABLE IF NOT EXISTS, try/except ALTER)
- `backend/models/event.py` — Pydantic BaseModel pattern, TEXT+JSON for arrays
- `backend/models/playbook.py` — nested BaseModel, ConfigDict, Literal, Optional patterns
- `backend/api/playbooks.py` — APIRouter + request.app.state.stores pattern for CRUD
- `backend/api/health.py` — asyncio.to_thread pattern, JSONResponse usage
- `tests/unit/test_api_endpoints.py` — TestClient + dependency_overrides test pattern
- jsonschema 4.26.0 — confirmed installed in `.venv`

### Secondary (MEDIUM confidence)
- `backend/api/firewall.py` — GET endpoint with app.state access pattern
- `backend/api/investigations.py` — PATCH-style endpoint structure
- `backend/core/deps.py` — Stores container, dependency injection pattern

### Tertiary (LOW confidence)
- None — all findings are verified against project source files.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed installed and in use in the project
- Architecture: HIGH — all patterns taken directly from existing production code
- Pitfalls: HIGH — derived from reading actual DuckDB store code, existing test patterns, and JSON Schema spec
- Gate logic: HIGH — directly specified in ADR-030 §2 and §4 with no ambiguity

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (stable stack, ADRs are locked)
