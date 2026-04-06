# Phase 25: Receipt Ingestion and Case-State Propagation — Research

**Researched:** 2026-04-06
**Domain:** FastAPI route + DuckDB storage + SQLite case-state mutation + JSON Schema authoring
**Confidence:** HIGH

---

## Summary

Phase 25 adds the inbound side of the firewall execution loop: the SOC receives execution receipts from the firewall executor, validates them against a pinned local JSON Schema, stores them in DuckDB with full audit linkage, propagates deterministic case-state transitions to SQLite `investigation_cases`, and emits structured notifications for conditions requiring human review.

The implementation follows established Phase 24 patterns exactly — same DuckDB write-queue pattern, same deferred-try/except router registration in `main.py`, same `AsyncMock`-based TestClient fixture approach. No new libraries or patterns are required.

Two DuckDB tables are added (`execution_receipts`, `notifications`). One SQLite method call is needed for case-state propagation (`sqlite_store.update_investigation_case`). One new router module is added for each concern (`backend/api/receipts.py`, `backend/api/notifications.py`), or they can coexist in a single file. One JSON Schema stub is added at `contracts/execution-receipt.schema.json`.

**Primary recommendation:** Model the new router and schema DDL directly after Phase 24's `backend/api/recommendations.py` and `duckdb_store.py` additions. All patterns are already established in the codebase.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P25-T01 | POST /api/receipts — validate against execution-receipt.schema.json stub; store in `execution_receipts` DuckDB table; return 202 Accepted | Schema fields derived from ADR-030 §6 + ADR-032; DuckDB table design documented below; router pattern from Phase 24 |
| P25-T02 | Case-state propagation — 5 failure_taxonomy values produce deterministic transitions; update case record atomically | Transition table from ADR-032; `investigation_cases.case_status` updated via `sqlite_store.update_investigation_case()`; wrapped in `asyncio.to_thread` |
| P25-T03 | Analyst notifications — validation_failed and rolled_back emit structured events; GET /api/notifications returns pending with required_action enum | `notifications` DuckDB table; enum values: `re_approve_required` (expired_rejected), `manual_review_required` (rolled_back + validation_failed) |
| P25-T04 | contracts/execution-receipt.schema.json stub — required fields; version "1.0.0-stub" | Schema fields catalogued from ADR-030 §6 + cross-reference with recommendation schema structure |
| P25-T05 | Unit tests for all 5 failure_taxonomy transitions; integration tests for POST /api/receipts; notification trigger tests; idempotency test | AsyncMock + TestClient pattern from Phase 24; pytest-asyncio auto mode |
</phase_requirements>

---

## Standard Stack

### Core (all already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | current | Route handlers | Already the app framework |
| pydantic v2 | current | Request body validation + Pydantic models | Already used for all models |
| jsonschema | current | JSON Schema Draft 2020-12 validation | Already used in `recommendation.py` |
| duckdb | 1.3+ | `execution_receipts` + `notifications` tables | Already the analytics store |
| sqlite3 (stdlib) | stdlib | `investigation_cases.case_status` update | Already the case store |
| pytest + pytest-asyncio 1.3.0 | pinned | Test suite | Already configured; asyncio_mode=auto |

### No new dependencies required.

**Installation:** No new packages — Phase 25 uses only already-installed libraries.

---

## Architecture Patterns

### Recommended File Structure
```
backend/api/
├── receipts.py          # POST /api/receipts (P25-T01, P25-T02, P25-T03)
├── notifications.py     # GET /api/notifications (P25-T03)
contracts/
└── execution-receipt.schema.json   # stub (P25-T04)
tests/unit/
├── test_receipt_transitions.py     # 5 taxonomy unit tests (P25-T05)
├── test_receipt_api.py             # POST + idempotency integration tests (P25-T05)
└── test_notifications_api.py       # GET /api/notifications tests (P25-T05)
```

### Pattern 1: DuckDB Table DDL — execution_receipts
Add to `duckdb_store.py` (follow the Phase 24 `_CREATE_RECOMMENDATIONS_TABLE` block exactly):

```python
_CREATE_EXECUTION_RECEIPTS_TABLE = """
CREATE TABLE IF NOT EXISTS execution_receipts (
    receipt_id           TEXT PRIMARY KEY,
    recommendation_id    TEXT NOT NULL,
    case_id              TEXT NOT NULL,
    failure_taxonomy     TEXT NOT NULL,
    executed_at          TIMESTAMP NOT NULL,
    executor_version     TEXT,
    detail               TEXT,
    raw_receipt          TEXT NOT NULL,
    received_at          TIMESTAMP NOT NULL
)
"""

_CREATE_EXECUTION_RECEIPTS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_receipts_recommendation_id ON execution_receipts (recommendation_id)",
    "CREATE INDEX IF NOT EXISTS idx_receipts_case_id ON execution_receipts (case_id)",
    "CREATE INDEX IF NOT EXISTS idx_receipts_failure_taxonomy ON execution_receipts (failure_taxonomy)",
]
```

### Pattern 2: DuckDB Table DDL — notifications
```python
_CREATE_NOTIFICATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS notifications (
    notification_id  TEXT PRIMARY KEY,
    case_id          TEXT NOT NULL,
    receipt_id       TEXT NOT NULL,
    required_action  TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending',
    created_at       TIMESTAMP NOT NULL
)
"""

_CREATE_NOTIFICATIONS_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications (status)"
)
```

### Pattern 3: Schema Registration (duckdb_store.py initialise_schema)
Add calls at the bottom of `initialise_schema()` following the Phase 24 additions:

```python
# Phase 25: Receipt ingestion + notifications
await self.execute_write(_CREATE_EXECUTION_RECEIPTS_TABLE)
for idx_sql in _CREATE_EXECUTION_RECEIPTS_INDEXES:
    await self.execute_write(idx_sql)
await self.execute_write(_CREATE_NOTIFICATIONS_TABLE)
await self.execute_write(_CREATE_NOTIFICATIONS_INDEX)
```

### Pattern 4: Router Registration (main.py — deferred try/except)
```python
try:
    from backend.api.receipts import router as receipts_router
    app.include_router(receipts_router, dependencies=[Depends(verify_token)])
    log.info("Receipts router mounted at /api/receipts")
except ImportError as exc:
    log.warning("Receipts router not available: %s", exc)

try:
    from backend.api.notifications import router as notifications_router
    app.include_router(notifications_router, dependencies=[Depends(verify_token)])
    log.info("Notifications router mounted at /api/notifications")
except ImportError as exc:
    log.warning("Notifications router not available: %s", exc)
```

### Pattern 5: Router Prefix — set on router directly (not at include_router)
Phase 24 established the convention that `APIRouter(prefix="/api/receipts")` is set on the
router object itself, not added at `include_router` time (STATE.md decision "24-03: Prefix
/api/recommendations set on router directly"). Follow the same pattern.

### Pattern 6: Case-State Propagation Logic
The propagation must wrap the synchronous SQLite call in `asyncio.to_thread`:

```python
# In POST /api/receipts handler, after storing the receipt:
CASE_STATE_MAP = {
    "applied":             "containment_confirmed",
    "noop_already_present": "containment_confirmed",
    "validation_failed":   "containment_failed",
    "expired_rejected":    "containment_failed",
    "rolled_back":         "containment_rolled_back",
}

new_status = CASE_STATE_MAP[body.failure_taxonomy]
await asyncio.to_thread(
    stores.sqlite.update_investigation_case,
    body.case_id,
    {"case_status": new_status},
)
```

### Pattern 7: Idempotency (receipt_id uniqueness = 409)
The `execution_receipts` PRIMARY KEY on `receipt_id` causes a DuckDB exception on duplicate
insert. Catch `duckdb.ConstraintException` (or broad `Exception`) and raise `HTTPException(409)`:

```python
try:
    await stores.duckdb.execute_write(_INSERT_RECEIPT_SQL, params)
except Exception as exc:
    if "PRIMARY KEY" in str(exc) or "Constraint" in str(exc):
        raise HTTPException(status_code=409, detail="receipt_id already exists")
    raise
```

### Pattern 8: TestClient fixture with AsyncMock (from Phase 24)
```python
@pytest.fixture()
def mock_duckdb() -> AsyncMock:
    db = AsyncMock()
    db.execute_write = AsyncMock(return_value=None)
    db.fetch_all = AsyncMock(return_value=[])
    return db

@pytest.fixture()
def mock_sqlite() -> MagicMock:
    store = MagicMock()
    store.update_investigation_case = MagicMock(return_value=None)
    return store

@pytest.fixture()
def app(mock_duckdb, mock_sqlite) -> FastAPI:
    from backend.api.receipts import router as receipts_router
    _app = FastAPI()
    stores = MagicMock()
    stores.duckdb = mock_duckdb
    stores.sqlite = mock_sqlite
    _app.state.stores = stores
    _app.include_router(receipts_router)
    return _app
```

### Pattern 9: Notification trigger — emit only for validation_failed and rolled_back
```python
NOTIFICATION_TRIGGERS = {"validation_failed", "rolled_back", "expired_rejected"}

REQUIRED_ACTION_MAP = {
    "validation_failed": "manual_review_required",
    "rolled_back":       "manual_review_required",
    "expired_rejected":  "re_approve_required",
}
```

### Anti-Patterns to Avoid
- **Calling sqlite methods directly from async handlers without asyncio.to_thread:** SQLiteStore is synchronous; all calls must be wrapped.
- **Using INSERT OR REPLACE for idempotency:** DuckDB does not support this syntax. Use INSERT + catch PRIMARY KEY constraint violation instead.
- **Adding prefix at include_router time:** Phase 24 convention sets prefix on the router object.
- **Fetching DuckDB with params=None when there ARE params:** Phase 24 decision — `params=None` only when no filter params exist; non-empty lists must be passed directly.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON Schema validation | Custom field validation logic | `jsonschema.validate()` | Already used in recommendation.py; handles Draft 2020-12 |
| Case-state update | Direct SQL on SQLite | `sqlite_store.update_investigation_case()` | Method already exists; handles JSON serialization + updated_at |
| Async SQLite calls | threading.Thread manually | `asyncio.to_thread()` | Project convention from CLAUDE.md; all blocking I/O uses this |
| Write serialization | Manual locks | `store.execute_write()` via write queue | DuckDB single-writer constraint; existing queue handles this |

---

## Key Design Decisions to Honour

### 1. "Case record" = `investigation_cases` in SQLite, not `cases`
The SQLite schema has TWO case tables: `cases` (legacy, graph-oriented) and `investigation_cases` (the live case management table). The `case_status` field and `update_investigation_case()` method live on `investigation_cases`. Phase 25 MUST update `investigation_cases`.

### 2. `failure_taxonomy` enum — exactly 5 values (from ADR-032)
```
applied | noop_already_present | validation_failed | expired_rejected | rolled_back
```
The schema stub and Pydantic model must enumerate exactly these 5 values.

### 3. Atomicity is best-effort across two stores
DuckDB and SQLite are separate stores with no shared transaction. The implementation should:
1. Insert receipt to DuckDB first (durable evidence)
2. Update case state in SQLite second
3. Insert notification to DuckDB if triggered

If SQLite update fails, log the error but do NOT roll back the receipt — the receipt is evidence and must be preserved regardless of downstream propagation failure. This matches the audit-first principle from ADR-030 §6.

### 4. Return 202 Accepted (not 201 Created)
P25-T01 explicitly specifies 202 Accepted. This signals async-style processing (state propagation happens after receipt is accepted).

### 5. Notification status lifecycle
Notifications start as `pending`. The GET /api/notifications endpoint returns all `pending` notifications. There is no PATCH to mark them resolved in Phase 25 scope (deferred). Return them as a flat list.

---

## execution-receipt.schema.json Stub Fields

Based on ADR-030 §6, ADR-032, and the parallel structure of `recommendation.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/Reston2024/local-ai-soc/contracts/execution-receipt.schema.json",
  "title": "Firewall Execution Receipt",
  "description": "Receipt returned by the firewall executor after processing a recommendation. SOC local stub. Canonical: firewall repo. Version: 1.0.0-stub.",
  "version": "1.0.0-stub",
  "type": "object",
  "required": [
    "schema_version",
    "receipt_id",
    "recommendation_id",
    "case_id",
    "failure_taxonomy",
    "executed_at"
  ],
  "additionalProperties": false,
  "properties": {
    "schema_version": { "type": "string", "const": "1.0.0-stub" },
    "receipt_id":         { "type": "string", "format": "uuid" },
    "recommendation_id":  { "type": "string", "format": "uuid" },
    "case_id":            { "type": "string", "format": "uuid" },
    "failure_taxonomy": {
      "type": "string",
      "enum": ["applied","noop_already_present","validation_failed","expired_rejected","rolled_back"]
    },
    "executed_at":    { "type": "string", "format": "date-time" },
    "executor_version": { "type": "string" },
    "detail":           { "type": "string" }
  }
}
```

---

## Common Pitfalls

### Pitfall 1: DuckDB "Constraint" string vs exception type
**What goes wrong:** `duckdb.ConstraintException` may or may not be importable depending on the DuckDB version. String-matching on `str(exc)` is more robust.
**How to avoid:** Use `"PRIMARY KEY" in str(exc) or "Constraint" in str(exc)` for idempotency detection.
**Warning signs:** `AttributeError: module 'duckdb' has no attribute 'ConstraintException'`.

### Pitfall 2: SQLite is synchronous — blocking the event loop
**What goes wrong:** Calling `sqlite_store.update_investigation_case()` directly in an async handler blocks the event loop.
**How to avoid:** Always wrap in `await asyncio.to_thread(...)`.
**Warning signs:** Slow response times; test hanging.

### Pitfall 3: investigation_cases row may not exist for the given case_id
**What goes wrong:** The receipt references a `case_id` that has no corresponding `investigation_cases` row. SQLite UPDATE on a non-existent row silently succeeds (0 rows affected).
**How to avoid:** Log a warning but do not fail the receipt ingest — the receipt is valid evidence regardless. The case may be in the legacy `cases` table or not yet created in `investigation_cases`.

### Pitfall 4: params=None vs empty list in fetch_all
**What goes wrong:** `await store.fetch_all(sql, None)` vs `await store.fetch_all(sql, [])` — DuckDB's Python client behaves differently.
**How to avoid:** Follow Phase 24 decision: pass `None` (not `[]`) when there are no filter params.

### Pitfall 5: jsonschema format validators not active by default
**What goes wrong:** `jsonschema.validate()` does not enforce `"format": "uuid"` or `"format": "date-time"` unless `format_checker` is provided.
**How to avoid:** For the receipt schema stub, rely on Pydantic field types for format validation rather than jsonschema `format` keywords. Use `jsonschema.validate(instance=data, schema=_SCHEMA)` without a format_checker (consistent with recommendation.py).

---

## Code Examples

### Verified pattern — POST route returning 202
```python
# Source: established pattern from backend/api/recommendations.py
@router.post("", status_code=202)
async def ingest_receipt(body: ReceiptIngest, request: Request) -> JSONResponse:
    stores = request.app.state.stores
    # 1. Store receipt
    try:
        await stores.duckdb.execute_write(_INSERT_RECEIPT_SQL, [...])
    except Exception as exc:
        if "PRIMARY KEY" in str(exc) or "Constraint" in str(exc):
            raise HTTPException(status_code=409, detail="receipt_id already exists")
        raise
    # 2. Propagate case state
    new_status = CASE_STATE_MAP[body.failure_taxonomy]
    try:
        await asyncio.to_thread(
            stores.sqlite.update_investigation_case,
            body.case_id,
            {"case_status": new_status},
        )
    except Exception as exc:
        log.warning("Case state propagation failed", case_id=body.case_id, error=str(exc))
    # 3. Emit notification if required
    if body.failure_taxonomy in NOTIFICATION_TRIGGERS:
        notif_id = str(uuid4())
        await stores.duckdb.execute_write(_INSERT_NOTIFICATION_SQL, [
            notif_id, body.case_id, body.receipt_id,
            REQUIRED_ACTION_MAP[body.failure_taxonomy],
            "pending", datetime.now(timezone.utc).isoformat(),
        ])
    return JSONResponse(content={"receipt_id": body.receipt_id}, status_code=202)
```

### Verified pattern — sqlite update_investigation_case call
```python
# Source: backend/stores/sqlite_store.py:725 — existing method
sqlite_store.update_investigation_case(case_id, {"case_status": "containment_confirmed"})
# Always wrap: await asyncio.to_thread(stores.sqlite.update_investigation_case, ...)
```

### Verified pattern — Pydantic model with schema validation at import time
```python
# Source: backend/models/recommendation.py — established pattern
_SCHEMA_PATH = Path(__file__).parent.parent.parent / "contracts" / "execution-receipt.schema.json"
_SCHEMA: dict = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

class ReceiptIngest(BaseModel):
    schema_version: Literal["1.0.0-stub"] = "1.0.0-stub"
    receipt_id: str
    recommendation_id: str
    case_id: str
    failure_taxonomy: Literal[
        "applied", "noop_already_present",
        "validation_failed", "expired_rejected", "rolled_back"
    ]
    executed_at: str
    executor_version: Optional[str] = None
    detail: Optional[str] = None

    @model_validator(mode="after")
    def validate_against_schema(self) -> "ReceiptIngest":
        data = self.model_dump(mode="json", exclude_none=True)
        try:
            jsonschema.validate(instance=data, schema=_SCHEMA)
        except jsonschema.ValidationError as exc:
            raise ValueError(f"Receipt schema validation failed: {exc.message}") from exc
        return self
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` — `asyncio_mode = "auto"` |
| Quick run command | `uv run pytest tests/unit/test_receipt_transitions.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P25-T01 | POST /api/receipts returns 202 with valid body | integration | `uv run pytest tests/unit/test_receipt_api.py -x` | ❌ Wave 0 |
| P25-T01 | POST /api/receipts returns 422 with invalid body | integration | `uv run pytest tests/unit/test_receipt_api.py::test_post_receipt_invalid_body -x` | ❌ Wave 0 |
| P25-T01 | execute_write called with INSERT INTO execution_receipts | unit | `uv run pytest tests/unit/test_receipt_api.py::test_post_receipt_stores_in_duckdb -x` | ❌ Wave 0 |
| P25-T02 | applied → containment_confirmed | unit | `uv run pytest tests/unit/test_receipt_transitions.py::test_applied_transition -x` | ❌ Wave 0 |
| P25-T02 | noop_already_present → containment_confirmed | unit | `uv run pytest tests/unit/test_receipt_transitions.py::test_noop_transition -x` | ❌ Wave 0 |
| P25-T02 | validation_failed → containment_failed | unit | `uv run pytest tests/unit/test_receipt_transitions.py::test_validation_failed_transition -x` | ❌ Wave 0 |
| P25-T02 | expired_rejected → containment_failed | unit | `uv run pytest tests/unit/test_receipt_transitions.py::test_expired_rejected_transition -x` | ❌ Wave 0 |
| P25-T02 | rolled_back → containment_rolled_back | unit | `uv run pytest tests/unit/test_receipt_transitions.py::test_rolled_back_transition -x` | ❌ Wave 0 |
| P25-T02 | update_investigation_case called with correct status | unit | `uv run pytest tests/unit/test_receipt_api.py::test_case_state_propagated -x` | ❌ Wave 0 |
| P25-T03 | validation_failed emits notification with manual_review_required | unit | `uv run pytest tests/unit/test_notifications_api.py::test_validation_failed_emits_notification -x` | ❌ Wave 0 |
| P25-T03 | rolled_back emits notification with manual_review_required | unit | `uv run pytest tests/unit/test_notifications_api.py::test_rolled_back_emits_notification -x` | ❌ Wave 0 |
| P25-T03 | expired_rejected emits notification with re_approve_required | unit | `uv run pytest tests/unit/test_notifications_api.py::test_expired_rejected_emits_notification -x` | ❌ Wave 0 |
| P25-T03 | applied/noop do NOT emit notifications | unit | `uv run pytest tests/unit/test_notifications_api.py::test_applied_no_notification -x` | ❌ Wave 0 |
| P25-T03 | GET /api/notifications returns pending notifications | integration | `uv run pytest tests/unit/test_notifications_api.py::test_get_notifications -x` | ❌ Wave 0 |
| P25-T04 | contracts/execution-receipt.schema.json is valid JSON Schema | unit | `uv run pytest tests/unit/test_receipt_transitions.py::test_schema_file_valid -x` | ❌ Wave 0 |
| P25-T04 | schema version field is "1.0.0-stub" | unit | included in schema_file_valid test | ❌ Wave 0 |
| P25-T05 | Same receipt_id posted twice returns 409 | integration | `uv run pytest tests/unit/test_receipt_api.py::test_duplicate_receipt_returns_409 -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_receipt_transitions.py tests/unit/test_receipt_api.py tests/unit/test_notifications_api.py -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_receipt_transitions.py` — covers P25-T02, P25-T04 (5 taxonomy unit tests + schema file validation)
- [ ] `tests/unit/test_receipt_api.py` — covers P25-T01, P25-T02 (POST route + idempotency + state propagation)
- [ ] `tests/unit/test_notifications_api.py` — covers P25-T03 (notification trigger + GET endpoint)
- [ ] `backend/api/receipts.py` — POST /api/receipts implementation
- [ ] `backend/api/notifications.py` — GET /api/notifications implementation
- [ ] `backend/models/receipt.py` — Pydantic model with schema validation
- [ ] `contracts/execution-receipt.schema.json` — stub schema file

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual schema validation | `jsonschema.validate()` at model_validator | Phase 24 | Consistent schema enforcement; use same pattern |
| Direct SQLite in async | `asyncio.to_thread(sqlite_store.method)` | Phase 1 convention | Prevents event loop blocking |
| Global router prefix | Prefix on APIRouter object | Phase 24 (24-03 decision) | Consistent mounting pattern |

---

## Open Questions

1. **Does the case_id in the receipt always correspond to an `investigation_cases` row?**
   - What we know: `recommendation.case_id` is a UUID that may or may not have a matching `investigation_cases` row (the recommendation schema does not enforce this FK)
   - What's unclear: Whether Phase 25 should create an `investigation_cases` row if one does not exist
   - Recommendation: Log a warning and continue; do not fail receipt ingest on missing case. This matches the audit-first principle — the receipt is evidence regardless.

2. **Does `required_action` on notifications need a PATCH /acknowledge endpoint in Phase 25?**
   - What we know: P25-T03 specifies only GET /api/notifications returning pending; no mention of acknowledgment
   - Recommendation: Scope to read-only GET in Phase 25; defer PATCH to a future phase.

---

## Sources

### Primary (HIGH confidence)
- `docs/ADR-030-ai-recommendation-governance.md` §6 — receipt ingestion obligations, case-state transitions
- `docs/ADR-032-executor-failure-reference.md` — failure taxonomy table (5 values), per-taxonomy SOC actions
- `backend/stores/duckdb_store.py` — Phase 24 DDL pattern, write-queue interface, schema migration idiom
- `backend/api/recommendations.py` — route structure, prefix convention, _row_to_dict pattern
- `backend/models/recommendation.py` — Pydantic + jsonschema validation pattern, schema loading at import time
- `backend/stores/sqlite_store.py` — `investigation_cases` schema, `update_investigation_case()` method signature
- `backend/main.py` — deferred try/except router registration convention
- `tests/unit/test_recommendation_api.py` — AsyncMock + TestClient fixture pattern
- `contracts/recommendation.schema.json` — JSON Schema structure to mirror for receipt stub
- `.planning/config.json` — nyquist_validation: true (confirmed)

### Secondary (MEDIUM confidence)
- `.planning/STATE.md` decisions block — Phase 24 conventions (prefix on router, params=None, 409 for double-approval)

### Tertiary (LOW confidence — none required)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in use with verified versions in pyproject.toml
- Architecture: HIGH — all patterns directly sourced from Phase 24 implementation in this repo
- DuckDB table design: HIGH — columns derived directly from ADR-032 required fields
- SQLite propagation: HIGH — `update_investigation_case()` method exists and is fully documented
- Pitfalls: HIGH — verified from Phase 24 STATE.md decisions and DuckDB docs in codebase

**Research date:** 2026-04-06
**Valid until:** 2026-05-06 (stable internal patterns; no external dependencies to expire)
