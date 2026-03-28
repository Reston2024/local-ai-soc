# Phase 14: LLMOps Evaluation & Investigation AI Copilot - Research

**Researched:** 2026-03-27
**Domain:** LLMOps benchmarking, DuckDB telemetry schema, FastAPI SSE streaming, investigation timeline JOIN, Svelte 5 vertical timeline, SQLite chat persistence
**Confidence:** HIGH (stack is well-established in this codebase; patterns verified from existing code)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P14-T01 | Foundation-Sec-8B evaluation harness — scripts/eval_models.py that loads ≤100 rows from seeded SIEM dataset, runs both qwen3:14b and foundation-sec:8b on triage + summarisation prompts, scores responses (latency, token count, keyword recall against ground-truth labels), writes results to data/eval_results.jsonl, prints markdown report | seed_siem_data.py pattern + OllamaClient.generate() + asyncio.to_thread timing; fetch_all() for DuckDB rows; no GPU fine-tuning required |
| P14-T02 | LLMOps monitoring layer — extend OllamaClient to record every generate() call (model, prompt_tokens, completion_tokens, latency_ms, endpoint) to new DuckDB table `llm_calls`; expose aggregates via GET /api/metrics/kpis extension | DuckDB execute_write() write pattern; existing _audit_log in ollama_client.py; metrics.py APScheduler pattern |
| P14-T03 | Investigation unified timeline — GET /api/investigations/{id}/timeline returns events, detections, graph edges, and playbook runs sorted by timestamp; Svelte InvestigationView renders vertical timeline with severity colour-coding, entity badges, MITRE tactic tags | DuckDB fetch_all() + SQLite asyncio.to_thread() merge; pure-CSS vertical timeline (no D3); existing case model in sqlite_store.py |
| P14-T04 | AI Copilot streaming chat — POST /api/investigations/{id}/chat accepts user question + investigation context; streams foundation-sec:8b response via SSE; Svelte copilot panel renders streamed tokens in real time with stop button; chat history persisted in SQLite per investigation | stream_generate_iter() async generator; StreamingResponse pattern from query.py; SQLite chat_messages table; Svelte fetch ReadableStream pattern |
</phase_requirements>

---

## Summary

Phase 14 extends the AI-SOC-Brain platform in four complementary areas. The first two (P14-T01 and P14-T02) close the LLMOps evaluation loop established in Phase 13 by adding a scripted offline benchmark harness and a production telemetry table that records every LLM call. The second two (P14-T03 and P14-T04) transform the currently-stub `InvestigationView` into a production analyst workbench with a chronological evidence timeline and a streaming AI Copilot chat panel.

All four requirements use patterns already established and verified in this codebase. The evaluation harness (P14-T01) follows `seed_siem_data.py` for DuckDB row retrieval and `OllamaClient.generate()` for model calls — the only new element is a timing wrapper and keyword-recall scorer. The telemetry table (P14-T02) extends the existing `_audit_log` infrastructure in `ollama_client.py` with a DuckDB `execute_write()` call and a new `llm_calls` DDL block. The timeline endpoint (P14-T03) JOINs rows from two stores (`fetch_all()` from DuckDB normalized_events + `asyncio.to_thread()` from SQLite detections/edges) into a unified sorted list. The AI Copilot (P14-T04) reuses the `stream_generate_iter()` async generator and `StreamingResponse` pattern from `backend/api/query.py` verbatim, with a new SQLite `chat_messages` table for history.

**Primary recommendation:** Follow the `query.py` SSE pattern exactly for the chat endpoint; follow the `metrics.py` APScheduler pattern for KPI aggregates; use pure-CSS flex/border for the timeline (no D3 — it is not needed for a vertical event list).

---

## Standard Stack

### Core (already in pyproject.toml — no new installs required for P14-T01..T04)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| duckdb | pinned in uv.lock | llm_calls telemetry table; eval_models.py row retrieval | Already wired with execute_write / fetch_all patterns |
| httpx | pinned | OllamaClient HTTP calls with timing | Already used — wrap generate() call with time.monotonic() |
| fastapi | pinned | SSE chat endpoint; timeline endpoint | StreamingResponse pattern proven in query.py |
| sqlite3 (stdlib) | 3.12 stdlib | chat_messages persistence per investigation | Already used by SQLiteStore with asyncio.to_thread() |
| apscheduler | pinned | KPI aggregation background task (llm_calls metrics) | Already used in metrics.py for 60s refresh |

### Supporting (already present)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| time (stdlib) | stdlib | latency_ms measurement in eval harness and telemetry | Wrap `time.monotonic_ns()` around OllamaClient.generate() |
| json (stdlib) | stdlib | eval_results.jsonl output | One JSON object per line |
| asyncio (stdlib) | stdlib | asyncio.to_thread() for SQLite chat_messages writes | All SQLite sync calls in async context |

### New dependencies required

None. All Phase 14 requirements are served by existing installed packages.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pure-CSS vertical timeline | D3.js timeline | D3 is heavy (already installed for graph view but overkill for a vertical list of events); pure CSS flex + border-left line is 30 lines and renders instantly |
| SQLite chat_messages | DuckDB chat table | SQLite is the right store for structured case/chat records (existing pattern); DuckDB is reserved for events/telemetry analytical queries |
| fetch + ReadableStream (SSE) | EventSource API | EventSource cannot send a POST body; SSE chat endpoint needs a POST (investigation_id + question); must use fetch + ReadableStream — this is the same pattern already in api.ts query.ask() |

---

## Architecture Patterns

### Recommended File Additions

```
backend/
  api/
    chat.py              # POST /api/investigations/{id}/chat  (P14-T04)
    timeline.py          # GET  /api/investigations/{id}/timeline (P14-T03)
  stores/
    duckdb_store.py      # ADD: llm_calls DDL block + initialise_schema call (P14-T02)
  services/
    ollama_client.py     # ADD: telemetry write hook in generate() and stream_generate() (P14-T02)
    eval_harness.py      # (optional helper) or inline in scripts/
scripts/
  eval_models.py         # standalone CLI benchmark script (P14-T01)
data/
  eval_results.jsonl     # output of eval_models.py (runtime, gitignored)
dashboard/src/views/
  InvestigationView.svelte  # REPLACE stub with timeline + copilot panels (P14-T03, T04)
dashboard/src/lib/
  api.ts                 # ADD: timeline(), chat() typed methods
```

### Pattern 1: LLM Telemetry — DuckDB llm_calls Table (P14-T02)

**What:** Add DDL for `llm_calls` table to `duckdb_store.py`; in `OllamaClient.generate()` and `stream_generate()`, after the call completes, enqueue an `execute_write()` to insert one row. Latency is measured with `time.monotonic_ns()` around the httpx call.

**When to use:** Every non-embedding Ollama call (generate and stream_generate). Embed calls are high-volume and lower value for LLMOps; skip them.

**DuckDB DDL:**
```sql
-- Source: project pattern in duckdb_store.py _CREATE_EVENTS_TABLE
CREATE TABLE IF NOT EXISTS llm_calls (
    call_id          TEXT PRIMARY KEY,
    called_at        TIMESTAMP NOT NULL,
    model            TEXT NOT NULL,
    endpoint         TEXT NOT NULL,    -- 'generate' | 'stream_generate'
    prompt_chars     INTEGER,
    completion_chars INTEGER,
    latency_ms       INTEGER,
    success          BOOLEAN NOT NULL DEFAULT TRUE,
    error_type       TEXT              -- NULL on success
);
CREATE INDEX IF NOT EXISTS idx_llm_calls_model ON llm_calls (model);
CREATE INDEX IF NOT EXISTS idx_llm_calls_at    ON llm_calls (called_at);
```

**Critical:** The `execute_write()` call is async. It must be called with `await` and MUST NOT block the token stream. For `stream_generate()`, record telemetry AFTER the stream is fully consumed (in a `finally` block). Do not await it inside the per-token loop.

**OllamaClient integration sketch:**
```python
# Source: backend/services/ollama_client.py existing generate() pattern
import time, uuid

async def generate(self, prompt, ...) -> str:
    t0 = time.monotonic_ns()
    try:
        result = await self._do_generate(...)
        await self._write_telemetry(
            model=_effective_model, endpoint="generate",
            prompt_chars=len(prompt), completion_chars=len(result),
            latency_ms=(time.monotonic_ns() - t0) // 1_000_000,
            success=True,
        )
        return result
    except OllamaError as exc:
        await self._write_telemetry(..., success=False, error_type=type(exc).__name__)
        raise
```

**Note:** `OllamaClient` does not currently hold a reference to the DuckDB store. Two options:
- Option A (preferred): Accept an optional `duckdb_store` parameter at `__init__` time; write if store is not None. Zero breaking changes — existing instantiations pass no store and telemetry is silently skipped.
- Option B: Write to the existing `_audit_log` Python logger (already in place) and have a background task drain it to DuckDB. More complex; not recommended.

### Pattern 2: SSE Chat Endpoint (P14-T04)

**What:** `POST /api/investigations/{id}/chat` — identical to `query.py`'s `ask_stream` pattern. The only differences are: (a) model is routed with `use_cybersec_model=True` (foundation-sec:8b), (b) investigation context is assembled from the timeline endpoint rather than Chroma RAG, (c) each assistant message is persisted to SQLite `chat_messages` after streaming completes.

**FastAPI endpoint sketch:**
```python
# Source: backend/api/query.py ask_stream() — reuse verbatim pattern
from fastapi.responses import StreamingResponse

@router.post("/investigations/{investigation_id}/chat")
async def chat_stream(
    investigation_id: str,
    body: ChatRequest,
    request: Request,
) -> StreamingResponse:
    ollama = request.app.state.ollama
    stores = request.app.state.stores

    # 1. Load investigation context (last N timeline items → brief context string)
    context = await _build_investigation_context(investigation_id, stores)

    # 2. Build prompt
    prompt = f"Investigation context:\n{context}\n\nAnalyst question: {body.question}"

    # 3. Stream tokens
    full_tokens: list[str] = []

    async def event_stream():
        async for token in ollama.stream_generate_iter(
            prompt,
            system=_COPILOT_SYSTEM,
            model=None,                  # use_cybersec_model via explicit model param
        ):
            full_tokens.append(token)
            yield f"data: {json.dumps({'token': token})}\n\n"
        # Persist to SQLite after stream completes
        asyncio.create_task(
            _persist_chat_message(investigation_id, body.question, "".join(full_tokens), stores)
        )
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

**Critical:** `stream_generate_iter()` currently only accepts `model` override — it does NOT have a `use_cybersec_model` parameter (unlike `generate()`). Either: (a) pass `model=ollama.cybersec_model` explicitly, or (b) add `use_cybersec_model` to `stream_generate_iter()` for consistency. Option (b) is cleaner.

### Pattern 3: Investigation Timeline JOIN (P14-T03)

**What:** The timeline is assembled from three sources — DuckDB `normalized_events` (filtered by `case_id`), SQLite `detections` (filtered by `case_id`), and SQLite `edges` (filtered by case entities). Each source is fetched independently then merged and sorted by timestamp in Python before returning.

**Why not a SQL JOIN:** DuckDB and SQLite are separate database files. Cross-store JOINs require loading both datasets into memory anyway. The Python merge is simpler and sufficient for investigation-scope datasets (hundreds of rows, not millions).

**Timeline response schema:**
```python
# One item per timeline entry
class TimelineItem(BaseModel):
    item_id: str
    item_type: Literal["event", "detection", "edge", "playbook"]
    timestamp: str          # ISO-8601, UTC
    title: str              # human-readable summary
    severity: Optional[str] # critical/high/medium/low/info
    attack_technique: Optional[str]
    attack_tactic: Optional[str]
    entity_labels: list[str]  # ["WORKSTATION-01", "lsass.exe"]
    raw_id: str             # original event_id / detection_id / edge_id
```

**DuckDB query (events):**
```sql
-- Source: duckdb_store.py fetch_all() pattern
SELECT event_id, timestamp, event_type, severity, hostname, process_name,
       attack_technique, attack_tactic, command_line
FROM normalized_events
WHERE case_id = ?
ORDER BY timestamp ASC
LIMIT 500
```

**SQLite query (detections):**
```python
# asyncio.to_thread wrapping — source: sqlite_store.py get_detections_by_case()
rows = store.get_detections_by_case(case_id)  # existing method
```

**Merge + sort:**
```python
items = []
# events from DuckDB
for row in event_rows:
    items.append(TimelineItem(item_type="event", timestamp=str(row[1]), ...))
# detections from SQLite
for det in detection_rows:
    items.append(TimelineItem(item_type="detection", timestamp=det["created_at"], ...))
# Sort by timestamp string (ISO-8601 sorts lexicographically)
items.sort(key=lambda x: x.timestamp)
```

### Pattern 4: Eval Harness Script (P14-T01)

**What:** Standalone Python CLI script (like `seed_siem_data.py`). Reads up to 100 seeded rows from DuckDB, constructs triage prompts, calls `OllamaClient.generate()` for each model, measures latency, computes keyword recall, writes JSONL.

**Keyword recall metric:** Given ground-truth labels from the dataset row (event_type, attack_technique), score the LLM response for presence of those keywords. Simple string match — no embedding comparison, no GPU. Produces a 0.0–1.0 score per call.

**Latency metric:** `time.monotonic_ns()` wrapping each `.generate()` call, divided by 1,000,000 for milliseconds.

**Token count:** Use `completion_chars` as a proxy (Ollama `/api/generate` response includes `eval_count` field — token count from the response JSON). The OllamaClient currently only returns the text string; the harness should make direct httpx calls or parse `data["eval_count"]` from the response JSON that `generate()` currently discards.

**Recommendation:** In `eval_models.py` only, use a thin local httpx call that reads the full Ollama JSON response including `eval_count` — don't modify `OllamaClient.generate()` just for the eval script.

**Output format (data/eval_results.jsonl):**
```json
{"model": "qwen3:14b", "prompt_id": "row-42", "latency_ms": 1240, "eval_count": 187, "keyword_recall": 0.75, "timestamp": "2026-03-27T14:00:00Z"}
```

### Pattern 5: Svelte 5 Vertical Timeline Component (P14-T03)

**What:** Pure CSS flex vertical timeline. No D3. No new libraries.

**Structure:**
```html
<!-- InvestigationView.svelte — timeline section -->
<div class="timeline">
  {#each timelineItems as item (item.item_id)}
    <div class="timeline-entry severity-{item.severity ?? 'info'}">
      <div class="timeline-dot"></div>
      <div class="timeline-line"></div>
      <div class="timeline-content">
        <span class="time">{fmtTime(item.timestamp)}</span>
        <span class="badge type-{item.item_type}">{item.item_type}</span>
        {#if item.attack_technique}
          <span class="badge mitre">{item.attack_technique}</span>
        {/if}
        <p class="title">{item.title}</p>
        {#each item.entity_labels as label}
          <span class="entity-badge">{label}</span>
        {/each}
      </div>
    </div>
  {/each}
</div>
```

**CSS pattern:**
```css
/* Svelte scoped CSS — no external lib needed */
.timeline { display: flex; flex-direction: column; gap: 0; }
.timeline-entry { display: grid; grid-template-columns: 1.5rem 1px 1fr; gap: 0 0.75rem; }
.timeline-dot { width: 10px; height: 10px; border-radius: 50%; margin-top: 4px; }
.timeline-line { width: 1px; background: var(--border); flex: 1; }
.severity-critical .timeline-dot { background: #ef4444; }
.severity-high .timeline-dot { background: #f97316; }
.severity-medium .timeline-dot { background: #eab308; }
.severity-low .timeline-dot { background: #22c55e; }
```

**Svelte 5 state pattern (matches DetectionsView.svelte):**
```typescript
// InvestigationView.svelte — follows DetectionsView $state/$effect pattern exactly
let timelineItems = $state<TimelineItem[]>([])
let loading = $state(true)
let chatMessages = $state<ChatMessage[]>([])
let chatInput = $state('')
let streaming = $state(false)

// Load timeline on mount
onMount(async () => {
  loading = true
  try {
    timelineItems = await api.investigations.timeline(investigationId)
  } finally {
    loading = false
  }
})
```

### Pattern 6: Svelte 5 SSE Chat Consumer (P14-T04)

**What:** Use `fetch` + `ReadableStream` for the POST-based SSE endpoint. This is the same approach as `api.ts` `query.ask()` but extended to support token-by-token display in a reactive state variable.

```typescript
// api.ts extension — chat streaming (POST-based SSE, same as query.ask)
investigations: {
  timeline: (id: string) =>
    request<TimelineItem[]>(`/api/investigations/${id}/timeline`),

  chatStream: async (
    id: string,
    question: string,
    onToken: (token: string) => void,
    signal?: AbortSignal,
  ): Promise<void> => {
    const res = await fetch(`/api/investigations/${id}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
      signal,
    })
    if (!res.ok) throw new Error(`Chat failed: ${res.status}`)
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      for (const line of decoder.decode(value).split('\n')) {
        if (line.startsWith('data: ')) {
          const msg = JSON.parse(line.slice(6))
          if (msg.token) onToken(msg.token)
          if (msg.done) return
        }
      }
    }
  },
},
```

**Stop button:** Use `AbortController` — pass `controller.signal` to `chatStream`; clicking stop calls `controller.abort()`.

```typescript
let abortController = $state<AbortController | null>(null)

async function sendMessage() {
  abortController = new AbortController()
  streaming = true
  let assistantMsg = { role: 'assistant', content: '' }
  chatMessages = [...chatMessages, { role: 'user', content: chatInput }, assistantMsg]
  chatInput = ''
  try {
    await api.investigations.chatStream(
      investigationId,
      assistantMsg.content,  // already appended
      (token) => {
        assistantMsg.content += token
        chatMessages = [...chatMessages]  // trigger reactivity
      },
      abortController.signal,
    )
  } finally {
    streaming = false
    abortController = null
  }
}
```

### Pattern 7: SQLite chat_messages Table (P14-T04)

**What:** Add to `sqlite_store.py` DDL (backward-compatible migration pattern already used for `risk_score`).

```sql
CREATE TABLE IF NOT EXISTS chat_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id TEXT NOT NULL,
    role            TEXT NOT NULL,    -- 'user' | 'assistant'
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_inv ON chat_messages (investigation_id);
```

**Why SQLite not DuckDB:** Chat history is structured relational data linked to an investigation case, not an analytical event stream. SQLite is the correct store (existing pattern: `investigation_cases`, `case_artifacts`, `detections`).

**Why NOT store in `investigation_cases.timeline_events` JSON array:** The JSON array approach doesn't support efficient ordered retrieval or append-only writes. A proper table is the right pattern.

### Anti-Patterns to Avoid

- **Blocking the event loop in stream_generate:** Never `await` DuckDB `execute_write()` inside the per-token `async for` loop. Persist telemetry AFTER the stream completes (in `finally` block, or via `asyncio.create_task()`).
- **Using EventSource for POST-based SSE:** `EventSource` only supports GET. The chat endpoint is POST because it carries a JSON body. Use `fetch + ReadableStream` as shown above.
- **D3 for vertical timeline:** D3 is for complex force-directed or zoomable layouts. A flat chronological list is pure CSS — adding D3 for this would double the complexity and introduce a render-blocking script.
- **Cross-store DuckDB-to-SQLite JOIN via `ATTACH`:** DuckDB can attach external SQLite files with `ATTACH 'graph.db' AS sqlite_db (TYPE sqlite)`, but this introduces a second code path that bypasses `execute_write()` safety. Use Python-level merge instead.
- **Token counting via text length:** Use `eval_count` from the Ollama raw response JSON for accurate token counts in the eval harness. `len(text)` is char count, not token count.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE streaming from FastAPI | Custom chunked encoding | `StreamingResponse` with `media_type="text/event-stream"` | Already proven in query.py; handles Keep-Alive and buffering correctly |
| Per-request DuckDB telemetry writes | Synchronous DuckDB write in request handler | `execute_write()` via asyncio.Queue | Write queue pattern is the only safe DuckDB write path; bypassing it causes corruption |
| Chat history in JSON blob | Append to `investigation_cases.timeline_events` | New `chat_messages` SQLite table | Append-only table is atomic; JSON array updates require read-modify-write |
| LLM latency measurement | Middleware-based timing | `time.monotonic_ns()` around the httpx call inside OllamaClient | Middleware timing includes framework overhead; in-client timing captures only model latency |
| Keyword recall scorer | External NLP library | Simple `token in response.lower()` substring match | No GPU, no install, 30ms; adequate for relative model comparison |
| Timeline sorting | SQL UNION across DuckDB + SQLite | Python-level sort on merged list | Cross-engine SQL is fragile; Python sort on ISO-8601 strings is correct and simple |
| Stop-generation for streaming | Server-side cancellation | Client-side `AbortController.abort()` | Aborting the fetch connection closes the httpx stream on the server side automatically |

**Key insight:** All four requirements are extensions of proven patterns. The highest risk is inadvertently blocking the asyncio event loop via synchronous DuckDB writes in a streaming context — every telemetry write must go through `execute_write()`.

---

## Common Pitfalls

### Pitfall 1: Telemetry Write Inside Token Stream
**What goes wrong:** Calling `await store.execute_write()` inside the `async for token in stream_generate_iter()` loop blocks the event loop on every token, degrading streaming performance from ~55 t/s to single digits.
**Why it happens:** `execute_write()` enqueues to `asyncio.Queue` and awaits completion — correct for batch writes but wrong inside a hot streaming loop.
**How to avoid:** Accumulate telemetry data in local variables. Write once after the stream is fully consumed, in a `finally` block or via `asyncio.create_task()`.
**Warning signs:** Token delivery latency increases; Ollama GPU utilization looks normal but client-visible throughput is low.

### Pitfall 2: stream_generate_iter Missing use_cybersec_model
**What goes wrong:** The AI Copilot calls the general `qwen3:14b` instead of `foundation-sec:8b` because `stream_generate_iter()` only accepts a raw `model` string override, not the `use_cybersec_model=True` flag.
**Why it happens:** `stream_generate_iter()` was added as a simpler variant (no audit logging, no cybersec routing) and was not updated when Phase 13 added the cybersec model.
**How to avoid:** Either add `use_cybersec_model: bool = False` to `stream_generate_iter()` (preferred, mirrors `generate()`), or pass `model=ollama.cybersec_model` explicitly in the chat endpoint.
**Warning signs:** Chat responses lack cybersecurity domain vocabulary; model name in telemetry shows `qwen3:14b`.

### Pitfall 3: Eval Harness Token Count Using Text Length
**What goes wrong:** `len(response_text)` returns character count; the eval report shows token counts that are systematically 20–30% higher than actual Ollama token counts, making the two models appear to differ in efficiency when they don't.
**Why it happens:** OllamaClient.generate() currently returns only the response text string, discarding `eval_count` from Ollama's JSON response.
**How to avoid:** In `eval_models.py`, make direct httpx calls or extract `eval_count` from the raw Ollama JSON. Alternatively, add an optional `return_metadata=False` flag to `generate()` that returns `(text, eval_count)`.
**Warning signs:** Token/char ratio differs significantly between models in the JSONL output.

### Pitfall 4: InvestigationView Case ID Not Available
**What goes wrong:** The timeline and chat endpoints require an `investigation_id`. The InvestigationView Svelte component is currently a stub with no routing parameter. Without a selected investigation, both API calls fail.
**Why it happens:** Phase 14 scope includes the Svelte view but not necessarily a full investigation selection flow.
**How to avoid:** Accept `investigation_id` as a `$props()` parameter passed from the parent App.svelte navigation state. Look at how `CasePanel.svelte` handles case selection for the pattern.
**Warning signs:** Timeline endpoint receives empty/undefined investigation_id; returns empty array.

### Pitfall 5: ISO-8601 Timestamp Sort Mix-Up (DuckDB vs SQLite Formats)
**What goes wrong:** DuckDB returns `timestamp` as a Python `datetime` object when using `fetch_all()`. SQLite returns `created_at` as an ISO-8601 string (`"2026-03-27T14:00:00+00:00"`). Sorting a mixed list of `datetime` and `str` raises `TypeError`.
**Why it happens:** The two stores have different return types for date columns.
**How to avoid:** Normalize all timestamps to ISO-8601 strings (`str(ts)` for DuckDB datetime objects) before building `TimelineItem` objects. Sort on the string — ISO-8601 lexicographic order equals chronological order for UTC timestamps.
**Warning signs:** `TypeError: '<' not supported between instances of 'datetime' and 'str'` in timeline endpoint.

### Pitfall 6: Svelte Streaming State Mutation Pattern
**What goes wrong:** Assigning `assistantMsg.content += token` does not trigger Svelte 5 reactivity because `assistantMsg` is a nested object reference inside `chatMessages` array — Svelte 5 runes track shallow assignments, not deep mutations.
**Why it happens:** `$state()` tracks assignments to the variable itself; mutating a property of an object inside a `$state` array is not automatically reactive.
**How to avoid:** After mutating `assistantMsg.content`, reassign the array: `chatMessages = [...chatMessages]`. This creates a new array reference and triggers the reactive update.
**Warning signs:** Chat panel appears frozen during streaming; tokens arrive server-side but DOM does not update.

---

## Code Examples

Verified patterns from existing codebase sources:

### SSE StreamingResponse (from backend/api/query.py lines 259-274)
```python
# Source: backend/api/query.py ask_stream() — VERIFIED in codebase
async def event_stream() -> AsyncIterator[str]:
    try:
        async for token in ollama.stream_generate_iter(prompt, system=system):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield f"data: {json.dumps({'done': True, 'context_event_ids': ids})}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'error': str(exc)})}\n\n"

return StreamingResponse(
    event_stream(),
    media_type="text/event-stream",
    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
)
```

### DuckDB execute_write pattern (from backend/stores/duckdb_store.py lines 171-187)
```python
# Source: backend/stores/duckdb_store.py — VERIFIED in codebase
await store.execute_write(
    "INSERT INTO llm_calls (call_id, called_at, model, endpoint, "
    "prompt_chars, completion_chars, latency_ms, success, error_type) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
    [call_id, called_at, model, endpoint,
     prompt_chars, completion_chars, latency_ms, success, error_type],
)
```

### asyncio.to_thread for SQLite (from backend/stores/sqlite_store.py pattern)
```python
# Source: sqlite_store.py usage pattern throughout codebase — VERIFIED
async def _persist_chat_message(inv_id: str, role: str, content: str, stores) -> None:
    await asyncio.to_thread(
        stores.sqlite._conn.execute,
        "INSERT INTO chat_messages (investigation_id, role, content, created_at) "
        "VALUES (?, ?, ?, ?)",
        (inv_id, role, content, _now_iso()),
    )
    await asyncio.to_thread(stores.sqlite._conn.commit)
```

### APScheduler KPI extension pattern (from backend/api/metrics.py)
```python
# Source: backend/api/metrics.py — VERIFIED in codebase
# Add llm_calls aggregates to MetricsService or directly in _refresh_kpis()
avg_latency = await stores.duckdb.fetch_all(
    "SELECT model, AVG(latency_ms) as avg_ms, COUNT(*) as total_calls, "
    "SUM(CASE WHEN success=FALSE THEN 1 ELSE 0 END) as errors "
    "FROM llm_calls GROUP BY model"
)
```

### Svelte 5 $effect + setInterval with cleanup (from DetectionsView.svelte lines 92-95)
```typescript
// Source: dashboard/src/views/DetectionsView.svelte — VERIFIED in codebase
$effect(() => {
    kpiPollingInterval = setInterval(loadKpis, 60_000)
    return () => { if (kpiPollingInterval) clearInterval(kpiPollingInterval) }
})
```

### Deferred task after stream completes (asyncio.create_task pattern)
```python
# Source: FastAPI background task pattern — standard Python asyncio
async def event_stream():
    full_tokens: list[str] = []
    try:
        async for token in ollama.stream_generate_iter(prompt, system=system):
            full_tokens.append(token)
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
    finally:
        # Fire-and-forget persistence — does NOT block the stream
        if full_tokens:
            asyncio.create_task(
                _persist_chat_message(inv_id, "assistant", "".join(full_tokens), stores)
            )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| stream_generate(on_token callback) | stream_generate_iter() async generator | Phase 3 | Async generator is the idiomatic FastAPI SSE pattern; callback approach requires manual async bridging |
| Separate cybersec model evaluation (manual) | Scripted offline eval harness with JSONL output | Phase 14 (this phase) | LLMOps maturity: decisions backed by reproducible benchmark data |
| No LLM call telemetry | llm_calls DuckDB table | Phase 14 (this phase) | Production observability: avg latency, error rate, cost proxy visible in dashboard |
| InvestigationView stub | Unified timeline + AI Copilot panel | Phase 14 (this phase) | Closes the most critical analyst UX gap |

**Deprecated/outdated patterns to avoid:**
- `on_token` callback in `stream_generate()`: use `stream_generate_iter()` instead for all new SSE endpoints
- `EventSource` for POST-based SSE: use `fetch + ReadableStream` (as established in api.ts `query.ask`)
- Svelte `writable()` stores: all state must use `$state()` runes (project convention)

---

## Open Questions

1. **chat_messages table migration vs create-if-not-exists**
   - What we know: `sqlite_store.py` uses `CREATE TABLE IF NOT EXISTS` in the `_DDL` block; backward-compat columns use `ALTER TABLE ... ADD COLUMN` in `__init__`.
   - What's unclear: Whether the planner should add `chat_messages` to the main `_DDL` string (cleaner) or as a `CREATE TABLE IF NOT EXISTS` in `__init__` (safer for existing deployments that already have the database).
   - Recommendation: Add to `_DDL` string — `CREATE TABLE IF NOT EXISTS` is idempotent; the table will be created on first run after update without affecting existing tables.

2. **eval_models.py token count: modify OllamaClient or inline httpx?**
   - What we know: `OllamaClient.generate()` discards `eval_count` from the Ollama JSON response; the eval script needs accurate token counts.
   - What's unclear: Whether to add an optional `return_eval_count=False` parameter to `generate()` or to make direct httpx calls in `eval_models.py` only.
   - Recommendation: Add `return_eval_count=False` to `generate()` — cleaner API, zero breaking changes (default=False), makes telemetry token counts accurate in P14-T02 as a side benefit.

3. **InvestigationView routing: props vs URL params**
   - What we know: No InvestigationView currently exists; other views receive data via `$props()` from App.svelte.
   - What's unclear: The current App.svelte routing mechanism (tab-based nav); whether investigation_id is passed via props or via a URL hash/query param.
   - Recommendation: Follow the existing `onInvestigate` callback pattern in `DetectionsView.svelte` — the parent App.svelte passes `investigationId` as a prop when the view becomes active. Check App.svelte nav state pattern before implementing.

---

## Validation Architecture

Nyquist validation is enabled (`workflow.nyquist_validation: true` in `.planning/config.json`).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio (auto mode) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/unit/test_phase14.py -x -q` |
| Full suite command | `uv run pytest -q --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P14-T01 | eval_models.py runs without error; writes JSONL with both models; markdown report has latency + recall columns | unit (mock httpx) | `uv run pytest tests/unit/test_eval_harness.py -x` | Wave 0 |
| P14-T01 | keyword_recall returns 0.0 for empty response, 1.0 for response containing all ground-truth tokens | unit | `uv run pytest tests/unit/test_eval_harness.py::test_keyword_recall -x` | Wave 0 |
| P14-T02 | llm_calls table exists in DuckDB after schema init | unit | `uv run pytest tests/unit/test_duckdb_store.py::test_llm_calls_table_exists -x` | Wave 0 (extend existing file) |
| P14-T02 | generate() writes one row to llm_calls with correct latency_ms type (int) | unit (mock DuckDB) | `uv run pytest tests/unit/test_ollama_client.py::test_telemetry_write -x` | Wave 0 (extend existing file) |
| P14-T02 | GET /api/metrics/kpis response includes `llm_stats` key with avg_latency_ms per model | unit | `uv run pytest tests/unit/test_metrics_api.py::test_kpis_llm_stats -x` | Wave 0 (extend existing file) |
| P14-T03 | GET /api/investigations/{id}/timeline returns 200 with sorted items list | unit (mock stores) | `uv run pytest tests/unit/test_timeline_api.py -x` | Wave 0 |
| P14-T03 | Timeline items from DuckDB and SQLite are merged and sorted by timestamp ascending | unit | `uv run pytest tests/unit/test_timeline_api.py::test_timeline_sort -x` | Wave 0 |
| P14-T04 | POST /api/investigations/{id}/chat returns 200 with text/event-stream content type | unit (mock ollama) | `uv run pytest tests/unit/test_chat_api.py::test_chat_stream_header -x` | Wave 0 |
| P14-T04 | chat_messages table accepts insert and retrieves messages ordered by id | unit | `uv run pytest tests/unit/test_sqlite_store.py::test_chat_messages -x` | Wave 0 (extend existing file) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/ -q --tb=short -x`
- **Per wave merge:** `uv run pytest -q --tb=short`
- **Phase gate:** Full suite green (547+ passing) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/test_eval_harness.py` — covers P14-T01 (keyword_recall, JSONL output, latency measurement)
- [ ] `tests/unit/test_timeline_api.py` — covers P14-T03 (GET /api/investigations/{id}/timeline, merge sort)
- [ ] `tests/unit/test_chat_api.py` — covers P14-T04 (SSE response headers, stop signal, message persistence)
- [ ] Extend `tests/unit/test_duckdb_store.py` — P14-T02: `test_llm_calls_table_exists`
- [ ] Extend `tests/unit/test_ollama_client.py` — P14-T02: `test_telemetry_write` (mock duckdb_store)
- [ ] Extend `tests/unit/test_metrics_api.py` — P14-T02: `test_kpis_llm_stats`
- [ ] Extend `tests/unit/test_sqlite_store.py` — P14-T04: `test_chat_messages`

---

## Sources

### Primary (HIGH confidence)
- `backend/services/ollama_client.py` — verified: `generate()`, `stream_generate()`, `stream_generate_iter()` signatures; existing `_audit_log` infrastructure; `use_cybersec_model` parameter pattern
- `backend/api/query.py` — verified: complete `StreamingResponse` SSE pattern including headers and async generator; `stream_generate_iter()` usage
- `backend/stores/duckdb_store.py` — verified: `execute_write()` async queue pattern; `fetch_all()` read pattern; DDL structure for new tables
- `backend/stores/sqlite_store.py` — verified: `_DDL` block structure; `asyncio.to_thread()` wrapping convention; `_now_iso()` helper; backward-compat `ALTER TABLE` migration pattern
- `backend/api/metrics.py` — verified: APScheduler singleton pattern; module-level cache; KPI extension point
- `dashboard/src/lib/api.ts` — verified: `fetch + ReadableStream` SSE consumer pattern; `request<T>()` generic helper; existing `investigations` namespace absent (new)
- `dashboard/src/views/DetectionsView.svelte` — verified: `$state()`, `$derived()`, `$effect()` rune patterns; `setInterval` with cleanup return; `onMount` async load
- `backend/main.py` — verified: deferred router mount pattern; `app.state.ollama`, `app.state.stores` injection
- `scripts/seed_siem_data.py` — verified: standalone script pattern with `sys.path` bootstrap; DuckDB store initialization outside lifespan

### Secondary (MEDIUM confidence)
- Ollama API docs (https://github.com/ollama/ollama/blob/main/docs/api.md) — `eval_count` field in `/api/generate` response JSON confirmed in OllamaClient docstring reference

### Tertiary (LOW confidence — verify if implementing)
- DuckDB SQLite ATTACH feature (`ATTACH 'path.db' AS alias (TYPE sqlite)`) — documented but not used in this codebase; avoid in favour of Python-level merge

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all patterns from existing codebase
- Architecture: HIGH — four patterns directly trace to verified existing code
- Pitfalls: HIGH — pitfalls 1, 2, 4, 5, 6 derive from actual code inspection; pitfall 3 from Ollama API docs reference in existing client code

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable stack; no fast-moving dependencies)
