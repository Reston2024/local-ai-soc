# Phase 22: AI Lifecycle Hardening - Research

**Researched:** 2026-04-02
**Domain:** LLM governance, response grounding, eval harness, model drift, AI advisory UI
**Confidence:** HIGH (all findings verified against live codebase)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P22-T01 | Response grounding — cite grounding_event_ids in API response + UI; flag ungrounded responses | `grounding_event_ids` already flows through `generate()`/`stream_generate()` into `llm_audit_provenance`; query.py already returns `context_event_ids`; need to thread audit_id back to API caller and add `is_grounded` flag |
| P22-T02 | Confidence scoring — heuristic 0.0–1.0 score stored in `llm_audit_provenance`; badge in UI | `llm_audit_provenance` table exists but has no `confidence_score` column; need ALTER TABLE migration + heuristic computation at call site; `LlmProvenanceRecord` in api.ts needs extension |
| P22-T03 | Eval harness — `tests/eval/` pytest suite, mock LLM, 5 fixtures for analyst_qa/triage/threat_hunt | Pattern established in `test_ollama_client.py` (patch `_client.post`); `tests/conftest.py` minimal; need new `tests/eval/` directory with fixtures + shared mock helper |
| P22-T04 | Model drift detection — compare active vs last-known model_id; SQLite `model_change_events`; `GET /api/settings/model-status`; SettingsView alert | No `model_change_events` table or settings KV store yet; need new DDL + migration pattern; `SettingsView.svelte` has 'system' tab placeholder that is currently empty |
| P22-T05 | Advisory separation — "AI Advisory" banner, confidence badge non-dismissable, visual style for AI content, prompt prefix instructions | `InvestigationView.svelte` copilot panel exists; chat messages render without advisory framing; `_DEFAULT_SYSTEM` in query.py and `SYSTEM` in prompt modules can receive prefix injection |
</phase_requirements>

---

## Summary

Phase 22 hardens the existing AI Copilot from a functional but ungoverned assistant into a trustworthy, NIST AI RMF-aligned component. The codebase already has substantial provenance infrastructure from Phase 21 — `llm_audit_provenance` table, `record_llm_provenance()` method, `grounding_event_ids` threading through both `generate()` and `stream_generate()` — but that infrastructure stops short of surfacing trust signals to the API consumer or the dashboard UI.

The five tasks in this phase build the user-visible trust layer on top of the Phase 21 audit foundation. P22-T01 threads the `audit_id` back to the query API response so callers can access provenance. P22-T02 adds a heuristic confidence score computed from grounding coverage and citation verification. P22-T03 creates a dedicated eval harness (`tests/eval/`) that tests prompt modules with mocked LLMs — distinct from unit tests. P22-T04 adds a lightweight model-change detection mechanism using a new `model_change_events` SQLite table and a `GET /api/settings/model-status` endpoint surfaced in SettingsView. P22-T05 adds non-dismissable advisory framing in the UI copilot panel.

**Primary recommendation:** Build each task as a narrow vertical slice — schema migration first, then API change, then UI change — within a single plan to keep diffs reviewable. Do not add new Python dependencies; everything needed already exists in the venv.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 (stdlib) | bundled | `model_change_events` DDL + KV store | Already used via SQLiteStore throughout codebase |
| pytest | 9.0.2 | Eval harness test runner | pinned in pyproject.toml |
| pytest-asyncio | 1.3.0 | Async test support | `asyncio_mode = "auto"` already set |
| unittest.mock | stdlib | Mock OllamaClient HTTP layer | Established pattern in `test_ollama_client.py` |
| FastAPI TestClient | bundled with fastapi | API endpoint testing | Used throughout `tests/unit/` |
| Svelte 5 runes | project standard | UI state + advisory framing | Project convention — no writable() |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | pinned | HTTP mock targets | Already patched via `patch.object(client._client, "post")` |
| pydantic | pinned | Response models for `model-status` endpoint | All API responses use pydantic models |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SQLite KV for model tracking | DuckDB table | DuckDB is OLAP; settings KV has no analytical need — SQLite is correct |
| Dedicated eval framework (promptfoo, RAGAS) | pytest fixtures | No network, no new deps, aligned with existing test infra |
| Dismissable advisory banner | Non-dismissable | NIST AI RMF requires persistent advisory labeling — non-dismissable is the requirement |

**Installation:** No new packages required.

---

## Architecture Patterns

### Recommended Project Structure Additions
```
backend/
  api/
    settings.py          # New: GET /api/settings/model-status
  stores/
    sqlite_store.py      # ALTER TABLE: add confidence_score to llm_audit_provenance
                         # New table: model_change_events
                         # New methods: record_model_change, get_last_known_model,
                         #              get_model_status, update_confidence_score
tests/
  eval/
    __init__.py
    conftest.py          # Shared mock LLM fixture
    fixtures/            # 5 NDJSON fixture files
    test_analyst_qa_eval.py
    test_triage_eval.py
    test_threat_hunt_eval.py
dashboard/src/views/
  SettingsView.svelte    # Add model-status alert to 'system' tab
  InvestigationView.svelte  # Add AI Advisory banner + confidence badge
```

### Pattern 1: SQLite Schema Migration via ALTER TABLE
**What:** Add new columns to existing tables using the project's established idempotent migration pattern.
**When to use:** When extending an existing table to avoid dropping data.
**Example:**
```python
# Source: backend/stores/sqlite_store.py lines 290-297 (existing pattern)
try:
    self._conn.execute(
        "ALTER TABLE llm_audit_provenance ADD COLUMN confidence_score REAL"
    )
    self._conn.commit()
except Exception:
    pass  # column already exists — idempotent
```

### Pattern 2: New DDL in the `_DDL` String
**What:** Add new tables to the `_DDL` constant in `sqlite_store.py`. `CREATE TABLE IF NOT EXISTS` makes it idempotent.
**When to use:** New tables that need to be created on first init.
**Example:**
```sql
-- Add to _DDL in backend/stores/sqlite_store.py
CREATE TABLE IF NOT EXISTS model_change_events (
    event_id        TEXT PRIMARY KEY,
    detected_at     TEXT NOT NULL,
    previous_model  TEXT,
    active_model    TEXT NOT NULL,
    change_source   TEXT NOT NULL DEFAULT 'startup_check'
);
CREATE INDEX IF NOT EXISTS idx_mce_detected_at ON model_change_events (detected_at);
```

### Pattern 3: Settings KV Table
**What:** A simple key-value table for single-value system settings that need persistence across restarts.
**When to use:** Storing last-known model ID. Avoid overloading existing tables.
**Example:**
```sql
CREATE TABLE IF NOT EXISTS system_kv (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
```
Getter/setter methods follow the existing `SQLiteStore` synchronous pattern, wrapped in `asyncio.to_thread()` at the call site.

### Pattern 4: Threading `audit_id` Back to API Response
**What:** `generate()`/`stream_generate()` currently return only the text string. The `audit_id` is created inside the method but never returned.
**When to use:** P22-T01 requires the query API to return `grounding_event_ids` and `audit_id` in the JSON response.
**Gap:** The current `query.py /ask` endpoint calls `await ollama.generate(prompt, ...)` and discards the audit context. Options:
1. Return a tuple `(response_text, audit_id)` from `generate()` — breaking change, requires updating all callers.
2. Add optional `out_dict: dict | None = None` parameter that `generate()` populates — no breaking change.
3. Store last-audit-id on the client instance — thread-unsafe in async context.

**Recommendation (Option 2):** Pass `out_context: dict | None = None` to `generate()` and `stream_generate()`. When provided, the method writes `{"audit_id": ..., "grounding_event_ids": [...]}` into it after provenance write. This is zero-breaking and testable.

### Pattern 5: Confidence Score Heuristic
**What:** A 0.0–1.0 score computed locally, not by the LLM.
**Algorithm:**
```
score = 0.0
if grounding_event_ids is not None and len(grounding_event_ids) > 0:
    score += 0.5   # has grounding context
if citation_verified is True:
    score += 0.3   # all citations resolved to known events
if len(grounding_event_ids) >= 5:
    score += 0.1   # rich context (5+ events)
if prompt_template_sha256 is not None:
    score += 0.1   # known template, not ad-hoc
score = min(score, 1.0)
```
This is computed in `query.py` after `generate()` returns and stored via `update_confidence_score(audit_id, score)`.

### Pattern 6: Mock OllamaClient in Eval Harness
**What:** Established in `test_ollama_client.py` — patch `client._client.post` with `AsyncMock`.
**When to use:** Any test that exercises a prompt module end-to-end without real Ollama.
**Example:**
```python
# Source: tests/unit/test_ollama_client.py pattern
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def mock_ollama():
    """Returns OllamaClient with HTTP layer mocked to return a fixed response."""
    from backend.services.ollama_client import OllamaClient
    client = OllamaClient(base_url="http://mock", model="test-model")
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={"response": MOCK_RESPONSE_TEXT})
    client._mock_post = AsyncMock(return_value=mock_resp)
    return client

# In test body:
with patch.object(mock_ollama._client, "post", new=mock_ollama._mock_post):
    result = await mock_ollama.generate(prompt=built_prompt)
```

### Pattern 7: Svelte 5 Conditional Advisory Badge
**What:** Non-dismissable advisory label on every assistant message in InvestigationView.
**When to use:** All AI copilot responses.
**Example using existing codebase style:**
```svelte
<!-- In InvestigationView.svelte, inside the assistant message block -->
{#if msg.role === 'assistant'}
  <div class="ai-advisory-banner" aria-label="AI Advisory">
    <span class="advisory-label">AI Advisory</span>
    {#if msg.confidence !== undefined}
      <span
        class="confidence-badge confidence-{confidenceLevel(msg.confidence)}"
        title="Confidence: {(msg.confidence * 100).toFixed(0)}%"
      >{confidenceLevel(msg.confidence)}</span>
    {/if}
  </div>
{/if}
```
The `confidenceLevel()` helper maps `0.0–0.4` → `low`, `0.4–0.7` → `medium`, `0.7–1.0` → `high`.

### Anti-Patterns to Avoid
- **Dismissable advisory:** The P22-T05 requirement is explicit that the confidence badge must be non-dismissable. Do not add an `×` close button or any toggle to hide it.
- **Returning confidence from the LLM:** The LLM's own confidence is unreliable (hallucination). Use the heuristic computed from grounding metadata, not a self-reported value.
- **Global model-id comparison in memory only:** Model drift must persist across restarts. Store last-known model ID in `system_kv`, not in `app.state`.
- **New Python dependency for eval harness:** The project has pytest + unittest.mock. Do not introduce `pytest-mock`, `respx`, or RAGAS.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async-safe HTTP mocking | Custom fake HTTP server | `unittest.mock.AsyncMock` + `patch.object` | Already established in test_ollama_client.py |
| Schema versioning | Custom migration runner | `ALTER TABLE ... ADD COLUMN` + `except: pass` | Project's existing idempotent pattern |
| Citation extraction | Custom parser | `_CITATION_RE = re.compile(r"\[([^\]]{3,64})\]")` in query.py | Already implemented in `verify_citations()` |
| Model name fetching | New HTTP client | `ollama.list_models()` on OllamaClient | Already exists, returns `list[str]` |
| KV store persistence | DuckDB table | `system_kv` SQLite table | SQLite for operational settings, DuckDB for analytics |

**Key insight:** This phase is almost entirely plumbing — connecting existing components and adding thin instrumentation layers, not new subsystems.

---

## Common Pitfalls

### Pitfall 1: Breaking `generate()` callers by changing its return type
**What goes wrong:** `generate()` is called in `query.py`, `chat.py`, `explain.py`, and test files. Changing the return from `str` to `tuple[str, dict]` breaks every caller.
**Why it happens:** The audit_id needs to surface, but the method was designed for simple string returns.
**How to avoid:** Use the `out_context: dict | None = None` optional parameter pattern. Callers that don't need the audit_id pass nothing and are unaffected.
**Warning signs:** Any `TypeError` or `str has no attribute` errors in tests after the change.

### Pitfall 2: `confidence_score` column missing on test SQLiteStore
**What goes wrong:** Unit tests for P22-T02 create an in-memory SQLiteStore. If `confidence_score` is added only via `ALTER TABLE` in `__init__` but NOT in `_DDL`, a fresh in-memory database won't have the column.
**Why it happens:** `_DDL` is applied on fresh init; `ALTER TABLE` in `__init__` only runs as a backward migration.
**How to avoid:** Add `confidence_score REAL` to the `llm_audit_provenance` DDL in `_DDL` AND keep the `ALTER TABLE` for backward compat with existing `data/graph.db` files.

### Pitfall 3: `stream_generate_iter()` does not call `record_llm_provenance`
**What goes wrong:** `query.py /ask/stream` uses `stream_generate_iter()`, not `stream_generate()`. The iter variant has no provenance write and no `grounding_event_ids` parameter.
**Why it happens:** `stream_generate_iter()` was created for SSE with a simpler interface that was never updated for Phase 21 provenance.
**How to avoid:** For P22-T01 grounding in the streaming endpoint, either (a) add `grounding_event_ids` and provenance to `stream_generate_iter()`, or (b) switch the streaming endpoint to use `stream_generate()` with `on_token` callback. Option (b) is cleaner.
**Warning signs:** Streaming responses show no `audit_id` in the SSE done-event.

### Pitfall 4: `system` tab in SettingsView is a stub
**What goes wrong:** The SettingsView `system` tab renders with no content currently (the tab button exists but the content block is empty/missing). P22-T04 needs to add the model-status card here.
**Why it happens:** The tab was scaffolded but never populated.
**How to avoid:** Read the full SettingsView before implementing — the `{#if activeTab === 'system'}` block may be present but empty, requiring only content addition, not structural changes.
**Warning signs:** The `activeTab` type union `'operators' | 'system'` — adding 'ai-model' would require widening this type.

### Pitfall 5: Eval fixture responses must not contain fabricated event IDs
**What goes wrong:** Eval test fixtures with hardcoded "event IDs" cited in LLM mock responses will trigger `verify_citations()` to return False because the IDs won't be in `context_ids`.
**Why it happens:** `verify_citations()` checks cited IDs against the `context_ids` list passed in from Chroma results.
**How to avoid:** In eval fixtures, either (a) set the mock response to cite the same IDs as the fixture events, or (b) test `verify_citations()` behavior deliberately by using IDs that do/don't match.

### Pitfall 6: Model drift check requires `ollama.list_models()` to succeed
**What goes wrong:** At startup, the model drift check calls `ollama.list_models()`. If Ollama is not running, this returns `[]`. The system may falsely record a "model removed" drift event.
**Why it happens:** Ollama is an external process; it may not be running at startup.
**How to avoid:** Only write a drift event if `list_models()` returns a non-empty list. If it returns empty, log a warning but do not update last-known model or write a change event.

---

## Code Examples

Verified patterns from the live codebase:

### Calling `generate()` with grounding and capturing audit context
```python
# Source: backend/api/query.py + backend/services/ollama_client.py
out_ctx: dict = {}
answer = await ollama.generate(
    prompt,
    system=system,
    grounding_event_ids=ids,          # list[str] from Chroma
    prompt_template_name="analyst_qa",
    prompt_template_sha256=prompts.analyst_qa.TEMPLATE_SHA256,
    operator_id=operator_ctx.operator_id,
    out_context=out_ctx,              # NEW: populated by generate()
)
audit_id = out_ctx.get("audit_id")
```

### `verify_citations()` — already implemented
```python
# Source: backend/api/query.py lines 35-46
_CITATION_RE = re.compile(r"\[([^\]]{3,64})\]")

def verify_citations(response_text: str, context_ids: list[str]) -> bool:
    cited = _CITATION_RE.findall(response_text)
    if not cited:
        return True   # vacuously true — no citations to verify
    context_set = set(context_ids)
    return all(c in context_set for c in cited)
```

### SQLiteStore synchronous method + asyncio.to_thread wrapping
```python
# Source: backend/services/ollama_client.py lines 391-403 (established pattern)
await asyncio.to_thread(
    self._sqlite.record_llm_provenance,
    audit_id,
    _effective_model,
    prompt_template_name,
    prompt_template_sha256,
    response_sha256,
    grounding_event_ids or [],
    operator_id,
)
```

### Mock stream in tests
```python
# Source: tests/unit/test_llm_provenance.py lines 94-116
with patch.object(client._client, "stream") as mock_stream_ctx:
    async def _aiter_lines():
        yield json.dumps({"response": "hello", "done": False})
        yield json.dumps({"response": " world", "done": True})

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.aiter_lines = _aiter_lines
    mock_stream_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
```

### Svelte 5 conditional class binding (existing pattern)
```svelte
<!-- Source: InvestigationView.svelte line 121 -->
<div class="timeline-entry severity-{item.severity ?? 'info'}">
<!-- Same pattern works for confidence level -->
<span class="confidence-badge confidence-{confidenceLevel(msg.confidence)}">
```

### `require_role()` dependency on a new endpoint
```python
# Source: backend/api/operators.py lines 43-48 (established pattern)
@router.get(
    "/settings/model-status",
    dependencies=[Depends(require_role("analyst", "admin"))],
)
async def get_model_status(request: Request) -> JSONResponse:
    ...
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LLM responses returned as raw string | `grounding_event_ids` threaded through but not surfaced to API | Phase 21 | Audit exists internally; P22-T01 surfaces it to consumers |
| No citation verification | `verify_citations()` in query.py | Phase 14 | Already working; P22-T01 connects it to the audit record |
| No model tracking | Nothing persisted | Before Phase 22 | P22-T04 adds `model_change_events` + `system_kv` |
| `stream_generate_iter()` lacks provenance | Only `stream_generate()` writes provenance | Phase 21 | P22 must close this gap |

**Deprecated/outdated:**
- Using `stream_generate_iter()` for the `/ask/stream` endpoint is an incomplete pattern — it bypasses provenance. P22 should migrate the streaming endpoint to `stream_generate()` + `on_token`.

---

## Open Questions

1. **Should `query.py /ask` pass `operator_id` to `generate()`?**
   - What we know: `generate()` accepts `operator_id` but `query.py` does not currently resolve operator context — it reads from `request.app.state` but does not call `verify_token` with role extraction.
   - What's unclear: Whether the query router has `require_role` applied at route level (it does not; only `verify_token` is applied at router registration in `main.py`).
   - Recommendation: For P22-T01/T02, resolve `operator_id` from `request.state` if available, otherwise fall back to `"system"`. Do not block the task on a full RBAC refactor of the query router.

2. **What Svelte type for `confidence` on `ChatHistoryMessage`?**
   - What we know: `ChatHistoryMessage` in `api.ts` has `id`, `investigation_id`, `role`, `content`, `created_at`. No confidence field.
   - What's unclear: Whether to extend `ChatHistoryMessage` with `confidence?: number` or create a new `AIChatMessage` type.
   - Recommendation: Add `confidence?: number` and `audit_id?: string` and `grounding_event_ids?: string[]` to `ChatHistoryMessage` as optional fields. This is backward compatible.

3. **Where to store model-status polling on the frontend?**
   - What we know: SettingsView has `$effect()` auto-load pattern for the operators tab.
   - What's unclear: Whether to poll on tab activation only or also on initial load.
   - Recommendation: Load on tab activation only (same pattern as operators tab). One GET request per tab visit is sufficient for drift detection.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]` — `asyncio_mode = "auto"`) |
| Quick run command | `uv run pytest tests/eval/ -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P22-T01 | `grounding_event_ids` returned in `/api/query/ask` response JSON | unit | `uv run pytest tests/eval/test_grounding.py -x` | Wave 0 |
| P22-T01 | Ungrounded response flagged (`is_grounded: false`) | unit | `uv run pytest tests/eval/test_grounding.py::test_ungrounded_response -x` | Wave 0 |
| P22-T02 | `confidence_score` column exists in `llm_audit_provenance` | unit | `uv run pytest tests/eval/test_confidence.py::test_column_exists -x` | Wave 0 |
| P22-T02 | Heuristic score correct for grounded vs ungrounded | unit | `uv run pytest tests/eval/test_confidence.py::test_score_heuristic -x` | Wave 0 |
| P22-T03 | analyst_qa eval: mock LLM, fixture events, response checked | eval | `uv run pytest tests/eval/test_analyst_qa_eval.py -x` | Wave 0 |
| P22-T03 | triage eval: mock LLM, 3 detection fixtures, response checked | eval | `uv run pytest tests/eval/test_triage_eval.py -x` | Wave 0 |
| P22-T03 | threat_hunt eval: mock LLM, hypothesis fixture | eval | `uv run pytest tests/eval/test_threat_hunt_eval.py -x` | Wave 0 |
| P22-T04 | `model_change_events` table exists after SQLiteStore init | unit | `uv run pytest tests/eval/test_model_drift.py::test_table_exists -x` | Wave 0 |
| P22-T04 | Model change written when active != last-known | unit | `uv run pytest tests/eval/test_model_drift.py::test_drift_recorded -x` | Wave 0 |
| P22-T04 | `GET /api/settings/model-status` returns 200 + `active_model` field | unit | `uv run pytest tests/eval/test_model_drift.py::test_status_endpoint -x` | Wave 0 |
| P22-T05 | Advisory prompt prefix present in `analyst_qa` SYSTEM prompt | unit | `uv run pytest tests/eval/test_advisory.py::test_advisory_prefix -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/eval/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/eval/__init__.py` — marks as package
- [ ] `tests/eval/conftest.py` — shared `mock_ollama` fixture + event fixture loader
- [ ] `tests/eval/fixtures/` directory — 5 NDJSON fixture files (analyst_qa, triage x2, threat_hunt x2)
- [ ] `tests/eval/test_grounding.py` — covers P22-T01
- [ ] `tests/eval/test_confidence.py` — covers P22-T02
- [ ] `tests/eval/test_analyst_qa_eval.py` — covers P22-T03 (analyst_qa)
- [ ] `tests/eval/test_triage_eval.py` — covers P22-T03 (triage)
- [ ] `tests/eval/test_threat_hunt_eval.py` — covers P22-T03 (threat_hunt)
- [ ] `tests/eval/test_model_drift.py` — covers P22-T04
- [ ] `tests/eval/test_advisory.py` — covers P22-T05

---

## Sources

### Primary (HIGH confidence)
- `backend/services/ollama_client.py` — full `generate()` and `stream_generate()` signatures; `grounding_event_ids` parameter exists; `record_llm_provenance()` called non-fatally
- `backend/api/query.py` — full `/ask` and `/ask/stream` implementations; `verify_citations()` defined; current response fields confirmed
- `backend/stores/sqlite_store.py` — `llm_audit_provenance` DDL; `record_llm_provenance()` method; `ALTER TABLE` migration pattern; `system_kv` does NOT yet exist
- `prompts/analyst_qa.py`, `prompts/triage.py`, `prompts/threat_hunt.py` — prompt module structure; `TEMPLATE_SHA256` / `TEMPLATE_NAME` pattern
- `dashboard/src/views/InvestigationView.svelte` — copilot panel DOM structure; chat message rendering; Svelte 5 rune usage
- `dashboard/src/views/SettingsView.svelte` — two-tab structure; `system` tab confirmed present; `$state` / `$effect` patterns
- `dashboard/src/lib/api.ts` — `ChatHistoryMessage` interface; `LlmProvenanceRecord` interface
- `tests/unit/test_ollama_client.py` — mock HTTP pattern (AsyncMock + patch.object)
- `tests/unit/test_llm_provenance.py` — stream mock pattern; in-memory SQLiteStore fixture
- `pyproject.toml` — pytest 9.0.2, pytest-asyncio 1.3.0, asyncio_mode=auto

### Secondary (MEDIUM confidence)
- NIST AI RMF 1.0 principle: AI outputs used in high-stakes decisions must be clearly labeled as AI-generated, maintain human oversight, and include uncertainty disclosure — supports non-dismissable advisory banner requirement

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified against pyproject.toml and live imports
- Architecture: HIGH — all patterns traced to existing production code in the repo
- Pitfalls: HIGH — identified from direct code inspection (stream_generate_iter gap, ALTER TABLE vs DDL conflict, breaking return type change)

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (stable codebase; 30-day window)
