# Phase 28: Dashboard Integration Fixes - Research

**Researched:** 2026-04-07
**Domain:** Svelte 5 / TypeScript dashboard ↔ FastAPI backend API contract alignment
**Confidence:** HIGH — all gaps verified directly from source files, no inference required

---

## Summary

Phase 28 closes six documented contract mismatches between the Svelte 5 dashboard
(`dashboard/src/`) and the FastAPI backend (`backend/api/`). All six gaps were
identified in the v1.0 milestone audit (`v1.0-MILESTONE-AUDIT.md`) and confirmed
by reading the actual source files.  No external libraries need to be added; every
fix is a targeted change to existing files.

Two gaps are HIGH severity (broken flows, runtime errors): the Query/RAG endpoint
mismatch (INT-01) and the Event search response shape mismatch (INT-02).  Two are
MEDIUM severity (missing UI path, silent progress failure): SettingsView routing
(INT-04) and ingest progress key mismatch (INT-03).  Two are LOW severity (silent
data mapping errors): pagination contract (INT-05) and TypeScript field name
inconsistency (INT-06).

**Primary recommendation:** Fix all six in one phase, starting with the two HIGH
items (INT-01, INT-02) to restore the primary user flows, then MEDIUM and LOW items.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INT-01 | api.query.ask() hits `/api/query/ask` (JSON), reads as SSE → empty string | Fix: change URL to `/api/query/ask/stream` in api.ts line 404 |
| INT-02 | EventsView.svelte calls `res.results.map(r => r.event)` but backend returns `{events:[...],total:N}` | Fix: change backend search response shape OR update EventsView to read `res.events` |
| INT-03 | IngestView.svelte reads `job.events_processed` / `job.events_total`; backend job store has no such keys | Fix: add translation layer in ingest.py `GET /ingest/status/{jobId}` OR update dashboard |
| INT-04 | SettingsView.svelte exists but is not imported or rendered in App.svelte | Fix: add `'settings'` to nav + import + route in App.svelte |
| INT-05 | api.ts `events.list()` sends `?offset=N&limit=N`; backend `GET /api/events` uses `?page=N&page_size=N` | Fix: translate in api.ts OR backend adds offset/limit aliases |
| INT-06 | api.ts `NormalizedEvent` declares `process_pid` / `raw_data`; backend model uses `process_id` / `raw_event` | Fix: correct field names in api.ts interface |
</phase_requirements>

---

## Standard Stack

No new dependencies.  The entire phase uses the existing stack.

### Core (already installed)
| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| Frontend | Svelte 5 | per package.json | Uses runes (`$state`, `$derived`, `$effect`) |
| Frontend typing | TypeScript | per package.json | `svelte-check` for type validation |
| Backend | FastAPI | per pyproject.toml | `StreamingResponse` already used for SSE |
| Backend models | Pydantic v2 | per pyproject.toml | `model_dump(mode="json")` in use |
| Backend testing | pytest + pytest-asyncio | per pyproject.toml | auto mode, `uv run pytest` |

### Type Checking (frontend)
```bash
# From dashboard/ directory
npx svelte-check --tsconfig ./tsconfig.json
```
This is the closest thing to a "test" for frontend TS errors; there is no vitest/jest
configured in this project.

---

## Architecture Patterns

### Backend job status shape (INT-03 root cause)

`loader.py` `_set_job()` stores this structure in `_JOBS`:
```python
{
    "job_id": job_id,
    "status": status,
    "result": {
        "parsed": ...,
        "loaded": ...,
        "embedded": ...,
        "edges_created": ...,
        "errors": [...],
        "duration_seconds": ...
    } if result else None,
    "error": error,
    "updated_at": ...,
}
```

`IngestView.svelte` expects (via `IngestJobStatus` interface):
```typescript
{
  job_id: string
  status: 'pending' | 'running' | 'complete' | 'error'
  filename: string
  events_processed: number   // ← NOT present in backend
  events_total: number       // ← NOT present in backend
  error: string | null
  started_at: string         // ← NOT present in backend
  completed_at: string | null // ← NOT present in backend
}
```

The correct fix is to update the `GET /ingest/status/{jobId}` response (currently
`GET /ingest/jobs/{jobId}`) — or add a `/ingest/status/{jobId}` alias — to translate
the internal `result.loaded` → `events_processed` and `result.parsed` → `events_total`,
and include `filename`. The `api.ts` calls `api.ingest.status(jobId)` → `/api/ingest/status/${jobId}`
but the backend route is `/api/ingest/jobs/{job_id}` (note "jobs" not "status"). This is
a SECOND mismatch within INT-03: the URL path is also wrong.

### EventListResponse pagination contract (INT-05 root cause)

Backend `EventListResponse` (in `backend/models/event.py`):
```python
class EventListResponse(BaseModel):
    events: list[NormalizedEvent]
    total: int
    page: int
    page_size: int
    has_next: bool
```

Backend `GET /events` accepts `page` + `page_size` query params (1-indexed).

`api.ts` `events.list()` sends `offset` and `limit`.  The backend ignores `offset`
and `limit`; it always reads `page` and `page_size`.  `EventsView.svelte` tracks
`offset` locally and passes it to `api.events.list({ offset, limit })`.

Two valid fix strategies:
1. **Fix api.ts** — translate `offset/limit` → `page/page_size` before the HTTP call.
   `page = Math.floor(offset / limit) + 1`, `page_size = limit`.  Dashboard reads
   `res.events`, `res.total` (already correct field names).
2. **Fix backend** — add `offset/limit` query params as aliases in `GET /events`.

Strategy 1 (fix api.ts) is lower-risk: the backend model is already used by
other tests; changing it could cascade. The `EventsView` already uses `offset`
internally so keeping that local state is fine.

### NormalizedEvent TS interface (INT-06 root cause)

`api.ts` declares (lines 17-23):
```typescript
process_pid: number | null   // wrong — backend field is process_id
raw_data: Record<string, unknown>  // wrong — backend field is raw_event (string)
```

Backend `backend/models/event.py` (confirmed):
```python
process_id: Optional[int] = None
raw_event: Optional[str] = None
```

The dashboard `EventsView.svelte` does not currently display `process_pid` or
`raw_data`, so there is no runtime crash, but type safety is broken.

### SSE endpoint and api.query.ask (INT-01 root cause)

`api.ts` line 404:
```typescript
const res = await fetch('/api/query/ask', ...  // POST to JSON endpoint
```

But the code below reads the response body as an SSE stream.  The JSON endpoint
(`POST /query/ask`) returns `{"answer": "...", ...}` — no SSE `data:` lines.
The streaming endpoint is `POST /query/ask/stream`.

Fix: change the URL in `api.ts` from `/api/query/ask` → `/api/query/ask/stream`.
The request body format is the same (`AskRequest`).  The streaming endpoint
emits `data: {"token": "..."}` and `data: {"done": true, ...}`.

### Event search response shape (INT-02 root cause)

`api.ts` declares search returns `{ results: Array<{ event: NormalizedEvent; score: number }> }`.
`EventsView.svelte` line 33: `events = res.results.map(r => r.event)`

Backend `GET /events/search` returns (confirmed, `events.py` line 216-224):
```python
return JSONResponse(content={
    "events": [e.model_dump(mode="json") for e in events],
    "total": total,
    "query": q,
    "limit": limit,
    "offset": offset,
})
```

The dashboard expects `{results:[{event,score}]}`, backend returns `{events:[...]}`.
There is no score computed (full-text ILIKE search has no relevance score).

Two fix strategies:
1. **Fix backend** — change search response to `{results:[{event, score:1.0}]}` to match
   the TypeScript contract. Adds a constant `score:1.0` for text search hits.
2. **Fix dashboard** — update `api.ts` type and `EventsView.svelte` to read `res.events`.

Strategy 2 (fix dashboard) is cleaner since the backend already returns all the data;
adding a fake score field to the backend could mislead operators. Update:
- `api.ts` search return type to `{ events: NormalizedEvent[]; total: number; query: string }`
- `EventsView.svelte` line 33 to `events = res.events`

### SettingsView routing (INT-04)

`App.svelte` confirms: `SettingsView` is NOT imported anywhere. The `View` union type
does not include `'settings'`. The `navGroups` array has no settings entry.

Required changes to `App.svelte`:
1. Add `import SettingsView from './views/SettingsView.svelte'` at top
2. Add `'settings'` to the `View` type union
3. Add a nav item to the appropriate group (e.g. `Platform` or a new `Admin` group)
4. Add `{:else if currentView === 'settings'}<SettingsView />{/if}` to the template

`SettingsView.svelte` itself is fully implemented — it renders operators CRUD, key
rotation, TOTP, and model-status. No changes needed inside `SettingsView.svelte`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE parsing | Custom SSE parser | Existing pattern in api.ts `investigations.chatStream` | Already proven correct in this codebase |
| Pagination math | New pagination state | Translate offset→page in api.ts call | One-liner: `Math.floor(offset/limit)+1` |
| Job progress | New polling mechanism | Existing `pollJob` in IngestView.svelte | Just fix the key names and URL |

---

## Common Pitfalls

### Pitfall 1: The ingest status URL mismatch (INT-03 hidden bug)
**What goes wrong:** `api.ts` calls `/api/ingest/status/${jobId}` but the backend
route is `/api/ingest/jobs/{job_id}` — these are different paths. The upload
response returns a job_id, `pollJob` then calls `api.ingest.status(jobId)` which hits
a 404 silently (the `catch` in `pollJob` just clears the interval).
**How to avoid:** Fix the backend route: add `GET /ingest/status/{job_id}` as an
alias, OR rename the api.ts call to use `/api/ingest/jobs/{jobId}`.
**Recommendation:** Add a `/ingest/status/{job_id}` route in `ingest.py` that wraps
`get_job_status()` and maps internal keys to the dashboard's expected shape.

### Pitfall 2: EventListResponse offset field
**What goes wrong:** `EventListResponse` returns `offset` as part of the body via
`EventsView` after the pagination fix, but the backend model has `page`/`page_size`
not `offset`. The current `res.offset` reference in `api.ts`'s `EventsListResponse`
interface would be stale.
**How to avoid:** After fixing the pagination translation in `api.ts`, also update the
`EventsListResponse` TypeScript interface to match what the backend actually returns
(`page: number; page_size: number; has_next: boolean` instead of `offset: number; limit: number`).

### Pitfall 3: raw_event is a string not an object
**What goes wrong:** `api.ts` declares `raw_data: Record<string, unknown>` implying
an object, but the backend stores `raw_event: Optional[str]` — a JSON string.
**How to avoid:** Change TS to `raw_event: string | null`. Views that need structured
access should `JSON.parse(event.raw_event)` at display time.

### Pitfall 4: svelte-check won't catch runtime logic bugs
**What goes wrong:** TypeScript type checking verifies interface conformance but
doesn't test whether the correct URL is called or whether the SSE parsing actually
produces tokens.
**How to avoid:** Backend pytest tests verify the HTTP contract. After fixing INT-01,
add a unit test that confirms `POST /query/ask/stream` returns `text/event-stream`
content-type and emits `data:` lines.

### Pitfall 5: Svelte 5 runes — do not use writable stores
**What goes wrong:** Adding new reactive state with old `writable()` from `svelte/store`.
**How to avoid:** All new reactive state must use `$state()`. All derived state must
use `$derived()`. Effects must use `$effect()`. This is enforced by CLAUDE.md.

---

## Code Examples

### INT-01: Fix the query URL (api.ts)
```typescript
// Before (line 404 in api.ts):
const res = await fetch('/api/query/ask', {

// After:
const res = await fetch('/api/query/ask/stream', {
```

### INT-02: Fix event search (api.ts + EventsView.svelte)
```typescript
// api.ts — update search() return type
search: (query: string, limit = 10) =>
  request<{ events: NormalizedEvent[]; total: number; query: string }>(
    `/api/events/search?q=${encodeURIComponent(query)}&limit=${limit}`
  ),
```
```typescript
// EventsView.svelte line 33 — update map
events = res.events
total = res.total  // bonus: show total from search too
```

### INT-03: Fix ingest status (backend ingest.py — add status alias)
```python
# Add after GET /jobs/{job_id} in ingest.py
@router.get("/status/{job_id}")
async def get_job_status_compat(job_id: str) -> JSONResponse:
    """Dashboard-compatible status endpoint — maps internal keys to UI shape."""
    raw = get_job_status(job_id)
    if raw is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found.")
    result = raw.get("result") or {}
    return JSONResponse(content={
        "job_id": raw["job_id"],
        "status": raw["status"],
        "filename": raw.get("filename", ""),
        "events_processed": result.get("loaded", 0),
        "events_total": result.get("parsed", 0),
        "error": raw.get("error"),
        "started_at": raw.get("updated_at", ""),
        "completed_at": raw.get("updated_at") if raw["status"] in ("complete", "error") else None,
    })
```
Note: `filename` is not currently stored in `_JOBS`. Either store it at upload time
or accept that it returns empty string. The upload endpoint should call
`_set_job(job_id, "queued")` and then also store the filename — update `_set_job` or
store filename separately.

### INT-04: Wire SettingsView in App.svelte
```typescript
// Add import at top:
import SettingsView from './views/SettingsView.svelte'

// Add 'settings' to View type union:
type View = 'detections' | ... | 'recommendations' | 'settings'

// Add nav item to Platform group:
{ id: 'settings', label: 'Settings', color: '#a78bfa' }

// Add icon in nav template (or reuse existing gear icon pattern)

// Add route in main content:
{:else if currentView === 'settings'}
  <SettingsView />
```

### INT-05: Fix pagination translation (api.ts)
```typescript
// api.ts events.list — translate offset/limit to page/page_size
list: (params?: { offset?: number; limit?: number; hostname?: string; severity?: string }) => {
  const q = new URLSearchParams()
  const limit = params?.limit ?? 50
  const offset = params?.offset ?? 0
  const page = Math.floor(offset / limit) + 1
  q.set('page', String(page))
  q.set('page_size', String(limit))
  if (params?.hostname) q.set('hostname', params.hostname)
  if (params?.severity) q.set('severity', params.severity)
  return request<EventsListResponse>(`/api/events?${q}`)
},
```
Also update `EventsListResponse` TypeScript interface:
```typescript
export interface EventsListResponse {
  events: NormalizedEvent[]
  total: number
  page: number
  page_size: number
  has_next: boolean
}
```

### INT-06: Fix NormalizedEvent field names (api.ts)
```typescript
// Before:
process_pid: number | null
raw_data: Record<string, unknown>

// After:
process_id: number | null
raw_event: string | null
```

---

## Validation Architecture

`workflow.nyquist_validation` is `true` in `.planning/config.json`. Validation is required.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (auto mode) |
| Config file | `pyproject.toml` (already configured) |
| Quick run command | `uv run pytest tests/unit/test_ingest_api.py tests/unit/test_api_endpoints.py -x -q` |
| Full suite command | `uv run pytest tests/unit/ -q` |
| Frontend check | `cd dashboard && npx svelte-check --tsconfig ./tsconfig.json` |

### Phase Requirements → Test Map

| Req ID | Behavior to Verify | Test Type | Automated Command | File Exists? |
|--------|-------------------|-----------|-------------------|-------------|
| INT-01 | `POST /api/query/ask/stream` returns `text/event-stream` content-type | unit | `uv run pytest tests/unit/test_query_api.py -x -q` | ❌ Wave 0 — new file |
| INT-01 | SSE stream emits `data: {"token": ...}` lines then `data: {"done": true}` | unit | same | ❌ Wave 0 |
| INT-02 | `GET /api/events/search` response has `events` key (list), `total` key (int) | unit | `uv run pytest tests/unit/test_api_endpoints.py::TestEventsSearch -x -q` | ❌ Wave 0 — add class |
| INT-02 | Dashboard `EventsView` search reads `res.events` not `res.results` | svelte-check | `cd dashboard && npx svelte-check` | check after fix |
| INT-03 | `GET /api/ingest/status/{id}` returns `events_processed`, `events_total`, `filename` | unit | `uv run pytest tests/unit/test_ingest_api.py::TestJobStatusCompat -x -q` | ❌ Wave 0 — add class |
| INT-04 | `SettingsView` is importable from App.svelte; svelte-check passes | svelte-check | `cd dashboard && npx svelte-check` | check after fix |
| INT-05 | `GET /api/events?offset=50&limit=25` not a required backend change — verify api.ts translates | unit (mock) | `uv run pytest tests/unit/test_api_endpoints.py::TestEventsPagination -x -q` | ❌ Wave 0 — add class |
| INT-06 | `NormalizedEvent` TS interface has `process_id` and `raw_event` fields | svelte-check | `cd dashboard && npx svelte-check` | check after fix |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/ -x -q` (fast, ~10s)
- **Per wave merge:** `uv run pytest tests/unit/ -q && cd dashboard && npx svelte-check`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps (test files to create before implementing fixes)

- [ ] `tests/unit/test_query_api.py` — verify `/query/ask/stream` SSE contract (INT-01)
- [ ] Add `TestEventsSearch` class to `tests/unit/test_api_endpoints.py` — verify search response shape (INT-02)
- [ ] Add `TestJobStatusCompat` class to `tests/unit/test_ingest_api.py` — verify `/ingest/status/{id}` response shape (INT-03)
- [ ] Add `TestEventsPagination` class to `tests/unit/test_api_endpoints.py` — verify page/page_size params accepted (INT-05)

Frontend type correctness for INT-04 and INT-06 is validated by `svelte-check`, not by
a new pytest file. TypeScript interfaces are checked at compile time.

---

## Open Questions

1. **INT-03 — filename storage in _JOBS**
   - What we know: `_set_job(job_id, "queued")` is called in `upload_file()` before
     `background_tasks.add_task(...)`. The filename is available at that point.
   - What's unclear: Whether to store filename inside `_JOBS` (modifies `_set_job`
     signature) or alongside it in a separate dict.
   - Recommendation: Modify `_set_job` to accept an optional `filename` kwarg and
     store it in the job dict. This is cleaner and keeps all job state in one place.

2. **INT-02 — should score be added to search results?**
   - What we know: Current ILIKE search has no relevance score. The TypeScript
     interface the dashboard was written against expected `{score: number}`.
   - What's unclear: Whether future vector search (Chroma) would be wired to this
     endpoint, making a score field meaningful.
   - Recommendation: Update dashboard to not require a score (fix dashboard side),
     leaving backend response as `{events:[...], total:N}`. If vector search is
     added later, the shape can be revisited.

3. **INT-05 — EventsListResponse in api.ts needs updating too**
   - What we know: After fixing the pagination query params, the response shape will
     include `page`/`page_size`/`has_next` from backend, but `EventsListResponse`
     currently declares `offset`/`limit`.
   - Recommendation: Update `EventsListResponse` interface in api.ts as part of INT-05.

---

## Gap Summary Table (source-verified)

| ID | Severity | File to Change | Change |
|----|----------|---------------|--------|
| INT-01 | HIGH | `dashboard/src/lib/api.ts` line 404 | `/api/query/ask` → `/api/query/ask/stream` |
| INT-02 | HIGH | `dashboard/src/lib/api.ts` + `EventsView.svelte` line 33 | Change return type; `res.results.map(r=>r.event)` → `res.events` |
| INT-03 | MEDIUM | `backend/api/ingest.py` + `ingestion/loader.py` | Add `GET /ingest/status/{id}` mapping internal keys; store filename in `_JOBS` |
| INT-04 | MEDIUM | `dashboard/src/App.svelte` | Import SettingsView; add nav item + View type + route |
| INT-05 | LOW | `dashboard/src/lib/api.ts` | Translate `offset/limit` → `page/page_size` before HTTP call; update `EventsListResponse` interface |
| INT-06 | LOW | `dashboard/src/lib/api.ts` | `process_pid` → `process_id`; `raw_data: Record` → `raw_event: string \| null` |

---

## Sources

### Primary (HIGH confidence — source code read directly)
- `dashboard/src/lib/api.ts` — full TypeScript API client (read completely)
- `dashboard/src/App.svelte` — nav groups, View type, routing (read completely)
- `dashboard/src/views/EventsView.svelte` — search and pagination usage (read completely)
- `dashboard/src/views/IngestView.svelte` — job status keys used (read completely)
- `dashboard/src/views/QueryView.svelte` — `api.query.ask()` call (read completely)
- `dashboard/src/views/SettingsView.svelte` — fully implemented, not routed (read completely)
- `backend/api/query.py` — `/query/ask` and `/query/ask/stream` endpoints (read completely)
- `backend/api/events.py` — `/events` pagination params and `/events/search` response shape (read completely)
- `backend/api/ingest.py` — job status route path `/jobs/{job_id}` (read completely)
- `ingestion/loader.py` — `_JOBS` structure and `_set_job()` function (read completely)
- `backend/models/event.py` — `NormalizedEvent` field names, `EventListResponse` shape (read completely)
- `.planning/v1.0-MILESTONE-AUDIT.md` — INT-01 through INT-06 definitions
- `.planning/config.json` — `nyquist_validation: true`

### Secondary (HIGH confidence — cross-verified)
- `tests/unit/test_ingest_api.py` — confirmed mock pattern for ingest test authoring
- `CLAUDE.md` — Svelte 5 runes requirement, pytest conventions, DuckDB write patterns

---

## Metadata

**Confidence breakdown:**
- Gap identification: HIGH — every gap verified by reading both sides of the contract
- Fix strategy: HIGH — straightforward targeted changes, no new dependencies
- Test architecture: HIGH — existing pytest patterns well-established in this codebase

**Research date:** 2026-04-07
**Valid until:** 2026-05-07 (stable codebase, no external dependency changes)
