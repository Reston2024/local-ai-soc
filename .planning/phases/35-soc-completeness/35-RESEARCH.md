# Phase 35: SOC Completeness — Research

**Researched:** 2026-04-10
**Domain:** FastAPI background workers, SQLite schema migration, Svelte 5 UI patterns, DuckDB analytics queries
**Confidence:** HIGH (all findings verified by direct code inspection)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- AI Triage panel: collapsible top panel in DetectionsView; summary + expand; spinner while running; "Run Triage Now" manual button
- New OverviewView as landing page (replaces Detections as default); full telemetry dashboard with EVE counts + bar chart, scorecards, system health, triage result, top 5 rules
- BETA badge removal: remove from Threat Intel, ATT&CK Coverage, Hunting, Threat Map; keep on Playbooks, Recommendations
- Playbook timeline rows: "Playbook: [name] — [status]" with status chip (green/amber/grey)
- explain.py empty dict: return ExplainResponse with structured error fields (no silent pass-through)
- field_map.py: add dns.query.name → dns_query, http.user_agent → http_user_agent, tls.client.ja3 → tls_ja3
- EventsView chips: enable ZEEK_CHIPS (currently disabled as `chip-beta disabled`) — all 8 Zeek chips become active

### Claude's Discretion
- Exact Overview layout grid (CSS grid vs flex, breakpoints)
- Polling interval for triage panel refresh (suggest 15s)
- Triage panel collapse/expand persistence (sessionStorage or in-memory)
- Whether triage panel shows model name (yes, for provenance)
- SQL queries for Overview scorecard tiles (24h window boundary)

### Deferred Ideas (OUT OF SCOPE)
- Campaign clustering background worker
- Diamond Model view (CampaignView)
- UEBA baseline engine
- Actor profile cards
- ATT&CK sub-technique drill-down
- Trend arrows in telemetry (vs prior 24h comparison)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P35-T01 | Fix explain.py — structured error response when investigation context is empty | explain.py L76 returns {} on miss; _run_explanation calls generate_explanation({}) with no guard; fix adds early return before line 49 |
| P35-T02 | Wire playbook_runs into investigation timeline (real rows from SQLite) | timeline.py L296 always passes []; playbook_runs table confirmed in SQLite DDL; get_playbook_runs() method on sqlite_store returns list[dict] |
| P35-T03 | EventsView event_type filter chips from real NormalizedEvent.event_type values | ZEEK_CHIPS already defined in EventsView.svelte L26-35; currently disabled with `disabled` attr; enable by removing disabled attr + chip-beta class |
| P35-T04 | Remove BETA badges from Threat Intel, ATT&CK Coverage, Hunting, Threat Map | App.svelte navGroups L145-148: 4 Intelligence items have `beta: true`; Playbooks/Recommendations L154-155 keep `beta: true` |
| P35-T05 | New Overview view — Malcolm telemetry summary + system health + triage + stats | No GET /api/telemetry/summary endpoint exists; new DuckDB query needed; App.svelte needs 'overview' view type + OverviewView.svelte |
| P35-T06 | field_map.py covers dns_query, http_user_agent, tls_ja3 for Zeek-matched Sigma rules | field_map.py already maps dns.question.name → domain; missing dns.query.name → dns_query, http.user_agent → http_user_agent, tls.client.ja3 → tls_ja3 |
| P35-T07 | End-to-end smoke test (ingest → EVE chips → hunt → IOC → assets) | Manual verification checklist; no automated test |
| P35-T08 | triage_results SQLite table + triaged_at column on detections | Neither exists; IocStore DDL pattern applies; ALTER TABLE detections ADD COLUMN triaged_at TEXT; CREATE TABLE triage_results |
| P35-T09 | POST /api/triage/run — pulls untriaged detections, builds prompt, calls Ollama, stores result | prompts/triage.py build_prompt() confirmed; ollama_client.generate() signature confirmed; new backend/api/triage.py needed |
| P35-T10 | Auto-triage background worker (60s poll) + Triage panel in DetectionsView | asyncio.ensure_future(feodo_worker.run()) pattern in main.py L238-240; GET /api/triage/latest needed; DetectionsView needs panel |
</phase_requirements>

---

## Summary

Phase 35 is largely surgical: it wires up things that already exist (prompts/triage.py, merge_and_sort_timeline's playbook_rows param, ZEEK_CHIPS in EventsView) and adds two new backend features (triage_results table + background worker, GET /api/telemetry/summary endpoint). The existing code is well-structured and the patterns are consistent — every new piece has a template to copy.

The most complex work is the auto-triage system (T08–T10), which requires a new SQLite table, a new API router registered via the deferred-import try/except pattern in main.py, and a new background worker using the `asyncio.ensure_future(worker.run())` pattern already established by the feed workers. The explain.py fix (T01) and timeline wiring (T02) are low-risk one-file changes.

The Overview view (T05) requires a new DuckDB aggregate endpoint and a new Svelte component — the heaviest frontend work, but the patterns are mature from MapView (60s auto-refresh) and the sidebar health dots (reusing /health and /health/network).

**Primary recommendation:** Implement in dependency order: T01 + T04 + T06 (safe, isolated) → T02 (timeline wire) → T03 (chip activation) → T08 (schema) → T09 (triage API) → T10 (worker + panel) → T05 (overview view) → T07 (smoke test).

---

## Standard Stack

### Core (all already installed)
| Library | Version | Purpose |
|---------|---------|---------|
| FastAPI | current | API router for triage endpoints |
| SQLite3 | stdlib | triage_results table, triaged_at column |
| DuckDB | current | EVE type counts, scorecard queries |
| asyncio | stdlib | background worker pattern |
| Svelte 5 | current | OverviewView, triage panel |

### No new dependencies needed
All Phase 35 work uses libraries already installed. No new pip or npm packages required.

---

## Architecture Patterns

### Pattern 1: SQLite ALTER TABLE for new columns (used in sqlite_store.py __init__)
```python
# Exact pattern from sqlite_store.py lines 362-378
try:
    self._conn.execute(
        "ALTER TABLE detections ADD COLUMN triaged_at TEXT"
    )
    self._conn.commit()
except Exception:
    pass  # column already exists — idempotent
```

SQLite DOES support `ADD COLUMN IF NOT EXISTS` but the project's established pattern is try/except for idempotency. DuckDB does NOT support `IF NOT EXISTS` on ALTER TABLE (documented in duckdb_store.py L217: "DuckDB raises if column already exists (no IF NOT EXISTS support)"). For SQLite, both approaches work; use try/except to match project convention.

### Pattern 2: Background worker loop (from feed_sync.py _BaseWorker)
```python
async def run(self) -> None:
    self._running = True
    backoff = self._interval
    try:
        while True:
            await asyncio.sleep(backoff)
            success = await self._sync()
            if success:
                self._consecutive_failures = 0
                backoff = self._interval
            else:
                self._consecutive_failures += 1
                backoff = min(self._interval * (2 ** self._consecutive_failures), 3600)
    except asyncio.CancelledError:
        self._running = False
        raise
```

The auto-triage worker should use a simpler flat version (no backoff needed — triage failures are not network errors):
```python
async def _auto_triage_loop(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(60)
        try:
            await _run_triage_once(app)
        except Exception as exc:
            log.warning("Auto-triage loop error (non-fatal): %s", exc)
```

Registration in main.py lifespan, after stores are initialised:
```python
asyncio.ensure_future(_auto_triage_loop(app))
```

### Pattern 3: New router registration (deferred try/except in create_app)
```python
try:
    from backend.api.triage import router as triage_router
    app.include_router(triage_router, prefix="/api", dependencies=[Depends(verify_token)])
    log.info("triage router mounted at /api/triage")
except ImportError as exc:
    log.warning("triage router not available: %s", exc)
```

### Pattern 4: IocStore DDL pattern for TriageStore
```python
# From ioc_store.py — IocStore accepts sqlite3.Connection directly
class TriageStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        # DDL is in _DDL string in sqlite_store.py (executed via executescript at startup)
```

The triage_results table DDL must be added to `_DDL` in sqlite_store.py so it is created at SQLite store init. Do not create it in a separate store's __init__ — maintain the single-DDL pattern.

### Pattern 5: playbook_rows wiring in timeline.py
The `playbook_rows` parameter already exists in `merge_and_sort_timeline()` (line 57) and the endpoint (line 296 sets it to `[]`). The fix is:

```python
# In get_investigation_timeline(), replace the empty list assignment:
playbook_rows: list[dict] = await asyncio.to_thread(
    lambda: stores.sqlite._conn.execute(
        "SELECT run_id, playbook_id, investigation_id, status, started_at, completed_at "
        "FROM playbook_runs WHERE investigation_id = ? ORDER BY started_at ASC",
        (investigation_id,),
    ).fetchall()
)
playbook_rows = [dict(r) for r in playbook_rows]
```

Then in `merge_and_sort_timeline()`, add the playbook loop (currently lines 156-158 are a comment placeholder):
```python
for run in playbook_rows:
    pb_name = run.get("playbook_id") or "Unknown Playbook"
    status = run.get("status") or "unknown"
    ts = run.get("started_at") or run.get("completed_at") or ""
    items.append(TimelineItem(
        item_id=f"pb-{run.get('run_id', '')}",
        item_type="playbook",
        timestamp=str(ts),
        title=f"Playbook: {pb_name} — {status}",
        severity=None,
        attack_technique=None,
        attack_tactic=None,
        entity_labels=[],
        raw_id=str(run.get("run_id", "")),
    ))
```

Note: The title shows `playbook_id` (UUID). For human-readable names, the query needs to JOIN with the `playbooks` table to get `name`. Use JOIN:
```sql
SELECT pr.run_id, p.name AS playbook_name, pr.investigation_id, 
       pr.status, pr.started_at, pr.completed_at
FROM playbook_runs pr
LEFT JOIN playbooks p ON pr.playbook_id = p.playbook_id
WHERE pr.investigation_id = ?
ORDER BY pr.started_at ASC
```

### Pattern 6: explain.py empty-dict guard
Current code (line 49) calls `build_evidence_context(investigation)` even when `investigation = {}`. Then calls `generate_explanation({}, ollama_client)` which builds an empty prompt and wastes an Ollama call.

`build_evidence_context({})` returns `"GRAPH: 0 entities | 0 timeline events"` — not empty, but useless. `generate_explanation({}, ...)` makes a full Ollama call with no evidence.

Fix in `_run_explanation()` after assembling investigation:
```python
if not investigation:
    detection_id = body.detection_id or "unknown"
    return ExplainResponse(
        what_happened=f"No investigation context found for detection_id: {detection_id}",
        why_it_matters="Unable to retrieve evidence context.",
        recommended_next_steps="Verify the detection ID exists and events have been ingested.",
        evidence_context="",
        error=f"No investigation context found for detection_id: {detection_id}",
    )
```

### Pattern 7: field_map.py additions
Current state: `dns.question.name → domain` exists (line 106). Missing Zeek/ECS field mappings:
```python
# Add to SIGMA_FIELD_MAP after existing ECS section:
"dns.query.name":           "dns_query",      # Zeek DNS query field
"http.user_agent":          "http_user_agent",  # Zeek/Suricata HTTP UA
"tls.client.ja3":           "tls_ja3",        # Zeek TLS JA3 fingerprint
"tls.server.ja3s":          "tls_ja3s",       # Zeek TLS JA3S fingerprint
"tls.server_name":          "tls_sni",        # Zeek TLS SNI
"http.request.method":      "http_method",    # Suricata/Zeek HTTP method
"http.request.uri":         "http_uri",       # Zeek HTTP URI
```

Also update `FIELD_MAP_VERSION` from `"20"` to `"21"`.

### Pattern 8: ZEEK_CHIPS activation in EventsView
Current state (lines 26-35): ZEEK_CHIPS array is defined with correct values. Lines 111-119: rendered with `disabled` attribute and `chip-beta` class.

Fix: Move ZEEK_CHIPS into CHIPS array and remove the Phase 36 divider. The CONTEXT.md decision is to enable these chips now that the managed switch is active.

The CONTEXT.md specifies: `DNS, HTTP, TLS, Connection, Alert, Anomaly, Auth, File, SMB`. Current CHIPS has `alert`, `tls`, `dns_query`, `file_transfer`, `anomaly`, `syslog`. ZEEK_CHIPS has `conn`, `http`, `ssl`, `smb`, `auth`, `ssh`, `smtp`, `dhcp`.

New unified CHIPS:
```typescript
const CHIPS = [
  { label: 'All',        value: '' },
  { label: 'Alert',      value: 'alert' },
  { label: 'DNS',        value: 'dns_query' },
  { label: 'TLS',        value: 'tls' },
  { label: 'HTTP',       value: 'http' },
  { label: 'Connection', value: 'conn' },
  { label: 'Auth',       value: 'auth' },
  { label: 'File',       value: 'file_transfer' },
  { label: 'SMB',        value: 'smb' },
  { label: 'Anomaly',    value: 'anomaly' },
  { label: 'Syslog',     value: 'syslog' },
  { label: 'SSH',        value: 'ssh' },
  { label: 'SMTP',       value: 'smtp' },
  { label: 'DHCP',       value: 'dhcp' },
]
```

Remove the ZEEK_CHIPS const, remove the chip-divider span, remove the disabled loop.

### Pattern 9: DuckDB analytics queries for OverviewView

**EVE type counts (last 24h):**
```sql
SELECT event_type, COUNT(*) AS cnt
FROM normalized_events
WHERE timestamp >= NOW() - INTERVAL 24 HOURS
GROUP BY event_type
ORDER BY cnt DESC
```

**Scorecard row (last 24h):**
```sql
-- Total events
SELECT COUNT(*) FROM normalized_events
WHERE timestamp >= NOW() - INTERVAL 24 HOURS

-- Total detections (SQLite)
SELECT COUNT(*) FROM detections
WHERE created_at >= datetime('now', '-24 hours')

-- IOC matches
SELECT COUNT(*) FROM normalized_events
WHERE ioc_matched = TRUE
AND timestamp >= NOW() - INTERVAL 24 HOURS

-- Assets discovered
SELECT COUNT(DISTINCT ip_address) FROM assets
WHERE last_seen >= datetime('now', '-24 hours')
```

**Top 5 Sigma rules (last 24h, from SQLite):**
```sql
SELECT rule_name, severity, COUNT(*) AS detection_count
FROM detections
WHERE created_at >= datetime('now', '-24 hours')
GROUP BY rule_name, severity
ORDER BY detection_count DESC
LIMIT 5
```

### Pattern 10: BETA badge removal
In App.svelte navGroups (lines 145-148), change:
```typescript
{ id: 'intel',           label: 'Threat Intel',    color: '', beta: true },
{ id: 'attack-coverage', label: 'ATT&CK Coverage', color: '', beta: true },
{ id: 'hunting',         label: 'Hunting',          color: '', beta: true },
{ id: 'map',             label: 'Threat Map',        color: '', beta: true },
```
to the same without `beta: true`. Leave lines 154-155 (Playbooks, Recommendations) unchanged.

### Pattern 11: Overview view routing
Add to App.svelte:
1. `import OverviewView from './views/OverviewView.svelte'` in script block
2. `'overview'` to the `View` type union
3. `currentView = $state<View>('overview')` (change default from `'detections'`)
4. `{ id: 'overview', label: 'Overview', color: '' }` as first item in Monitor navGroup
5. `{:else if currentView === 'overview'}<OverviewView />{/if}` in the view-content block

### Pattern 12: triage_results DDL
Add to `_DDL` in sqlite_store.py (before final `"""`):
```sql
CREATE TABLE IF NOT EXISTS triage_results (
    result_id       TEXT PRIMARY KEY,
    run_at          TEXT NOT NULL,
    detection_count INTEGER NOT NULL DEFAULT 0,
    model_name      TEXT NOT NULL,
    severity_summary TEXT NOT NULL DEFAULT '',
    result_text     TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'complete'
);
CREATE INDEX IF NOT EXISTS idx_triage_results_run_at ON triage_results (run_at DESC);
```

### Pattern 13: OllamaClient.generate() signature
```python
# Confirmed from ollama_client.py lines 428-440
async def generate(
    self,
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.1,
    model: Optional[str] = None,
    use_cybersec_model: bool = False,
    operator_id: str = "system",
    ...
) -> str:
```
Returns a plain string. For triage, call:
```python
result_text = await ollama_client.generate(
    prompt=user_turn,
    system=SYSTEM + system_turn,  # from prompts/triage.py
    temperature=0.1,
    operator_id="auto_triage",
)
```

### Pattern 14: prompts/triage.build_prompt() signature
```python
# Confirmed from prompts/triage.py lines 31-87
def build_prompt(
    detections: list[str],          # list of detection summary strings
    case_id: str | None = None,
    context_events: list[str] | None = None,
) -> tuple[str, str]:               # returns (system_turn, user_turn)
```

The triage API endpoint should format each untriaged detection as a string:
```python
det_summary = (
    f"Rule: {det['rule_name']} | Severity: {det['severity']} | "
    f"Technique: {det.get('attack_technique', 'N/A')} | "
    f"Tactic: {det.get('attack_tactic', 'N/A')}"
)
```

### Anti-Patterns to Avoid
- **Do NOT call `generate_explanation({}, ...)` without the empty-dict guard** — wastes a full Ollama call (120s timeout) with no useful output
- **Do NOT add triaged_at column to DuckDB** — detections live in SQLite (sqlite_store); the column goes on the SQLite `detections` table only
- **Do NOT create triage_results in IocStore.__init__** — add DDL to `_DDL` in sqlite_store.py for consistency
- **Do NOT block the event loop in the auto-triage worker** — all SQLite reads/writes must use `asyncio.to_thread()`
- **Do NOT use writable stores in Svelte** — use `$state()`, `$effect()`, `$derived()` only

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Triage prompt construction | Custom string builder | `prompts.triage.build_prompt()` — already exists |
| LLM call | Raw httpx | `app.state.ollama.generate()` — handles audit, provenance, telemetry |
| SQLite async writes | Direct conn.execute in async | `asyncio.to_thread(lambda: ...)` — established pattern |
| Background loop backoff | Custom timer | Copy feed_sync._BaseWorker.run() pattern |
| Triage result storage | Raw SQLite in endpoint | New TriageStore class wrapping conn — matches IocStore pattern |

---

## Common Pitfalls

### Pitfall 1: DuckDB vs SQLite confusion for detections
**What goes wrong:** `triaged_at` column added to DuckDB normalized_events instead of SQLite detections table.
**Why it happens:** Both stores exist; detections are SQLite, events are DuckDB.
**How to avoid:** The `detections` table is in `sqlite_store.py` `_DDL` (line 64). `triaged_at TEXT` goes there via ALTER TABLE in `__init__`.

### Pitfall 2: playbook_rows query returns sqlite3.Row objects
**What goes wrong:** `dict(row)` on sqlite3.Row works but the row_factory must be set (it is — sqlite_store sets `self._conn.row_factory = sqlite3.Row`).
**How to avoid:** The pattern `[dict(r) for r in rows]` is already used in `_get_edge_rows_sync()` (timeline.py line 198). Copy it exactly.

### Pitfall 3: Triage panel polling creates N concurrent requests
**What goes wrong:** `setInterval` in Svelte runs every 15s but if the server is slow, requests pile up.
**How to avoid:** Use a boolean flag or check `loading` state before polling, same as existing views.

### Pitfall 4: Overview view not receiving health state from App.svelte
**What goes wrong:** OverviewView needs healthStatus and networkDevices which are in App.svelte scope.
**How to avoid:** Pass `healthStatus` and `networkDevices` as Svelte props to OverviewView, or let OverviewView call `/health` and `/health/network` independently (simpler — same pattern as App.svelte onMount).

### Pitfall 5: Auto-triage worker calling internal HTTP
**What goes wrong:** Worker tries to call `http://localhost:8000/api/triage/run` internally — adds HTTP overhead and auth complications.
**How to avoid:** Import the triage logic directly from `backend.api.triage` and call it as a function, passing `app.state` directly. The CONTEXT.md notes this preference: "imports the logic directly to avoid HTTP overhead."

### Pitfall 6: build_prompt() returns (system_turn, user_turn) not (system, prompt)
**What goes wrong:** Developer passes system_turn as `system` kwarg and user_turn as `prompt` to ollama_client.generate() — but system_turn is the evidence block that should be prepended to the system message, not be the system message itself.
**How to avoid:** `system = SYSTEM + system_turn` and `prompt = user_turn`. See prompts/triage.py: SYSTEM is the instruction, system_turn is the data context block.

### Pitfall 7: Overview auto-refresh 60s in $effect vs setInterval
**What goes wrong:** Using `$effect()` with a timer causes the effect to re-run on every state update, not just on timer tick.
**How to avoid:** Use `setInterval` in `onMount()` (same as MapView pattern), not `$effect()`.

---

## Code Examples

### triage_results INSERT pattern
```python
# Source: adapted from ioc_store.py upsert pattern
import uuid
from datetime import datetime, timezone

def save_triage_result(
    conn: sqlite3.Connection,
    detection_count: int,
    model_name: str,
    severity_summary: str,
    result_text: str,
) -> str:
    result_id = str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO triage_results
           (result_id, run_at, detection_count, model_name, severity_summary, result_text, status)
           VALUES (?, ?, ?, ?, ?, ?, 'complete')""",
        (result_id, now, detection_count, model_name, severity_summary, result_text),
    )
    conn.commit()
    return result_id
```

### triaged_at update pattern
```python
# After triage run completes, mark detections as triaged
def mark_detections_triaged(conn: sqlite3.Connection, detection_ids: list[str]) -> None:
    now = datetime.now(tz=timezone.utc).isoformat()
    placeholders = ",".join("?" * len(detection_ids))
    conn.execute(
        f"UPDATE detections SET triaged_at = ? WHERE id IN ({placeholders})",
        [now] + detection_ids,
    )
    conn.commit()
```

### Fetch untriaged detections
```python
def get_untriaged_detections(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM detections WHERE triaged_at IS NULL ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
```

### GET /api/triage/latest response shape
```python
# Source: confirmed triage_results DDL above
{
    "result_id": "uuid",
    "run_at": "2026-04-10T12:00:00+00:00",
    "detection_count": 7,
    "model_name": "qwen3:14b",
    "severity_summary": "3 high, 4 medium",
    "result_text": "## Critical Findings\n...",
    "status": "complete"
}
```

### Svelte triage panel polling
```typescript
// In DetectionsView.svelte — panel state
let triageResult = $state<TriageResult | null>(null)
let triageRunning = $state(false)

onMount(() => {
    loadTriageResult()
    setInterval(loadTriageResult, 15_000)
})

async function loadTriageResult() {
    try {
        triageResult = await api.triage.latest()
    } catch { /* non-fatal */ }
}

async function runTriageNow() {
    triageRunning = true
    try {
        await api.triage.run()
        await loadTriageResult()
    } finally {
        triageRunning = false
    }
}
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (pytest-asyncio mode: auto) |
| Config file | pyproject.toml |
| Quick run command | `uv run pytest tests/unit/ -x -q` |
| Full suite command | `uv run pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P35-T01 | explain.py returns structured error when detection_id not found | unit | `uv run pytest tests/unit/test_explain.py -x` | ❌ Wave 0 |
| P35-T02 | merge_and_sort_timeline() includes playbook rows when provided | unit | `uv run pytest tests/unit/test_timeline_merge_playbooks.py -x` | ❌ Wave 0 |
| P35-T03 | EventsView ZEEK_CHIPS enabled | manual-only | — | N/A |
| P35-T04 | BETA badges removed from 4 nav items | manual-only | — | N/A |
| P35-T05 | GET /api/telemetry/summary returns event_type_counts, scorecard, top_rules | unit | `uv run pytest tests/unit/test_telemetry_summary.py -x` | ❌ Wave 0 |
| P35-T06 | field_map dns_query, http_user_agent, tls_ja3 map to correct DuckDB columns | unit | `uv run pytest tests/unit/test_field_map.py -x` | ❌ Wave 0 |
| P35-T07 | End-to-end smoke (ingest → EVE chips → hunt → IOC → assets) | manual-only | — | N/A |
| P35-T08 | triage_results DDL created + triaged_at column on detections | unit | `uv run pytest tests/unit/test_triage_store.py -x` | ❌ Wave 0 |
| P35-T09 | POST /api/triage/run calls Ollama, stores result, marks detections triaged | unit | `uv run pytest tests/unit/test_triage_api.py -x` | ❌ Wave 0 |
| P35-T10 | Auto-triage worker polls every 60s, handles errors non-fatally | unit | `uv run pytest tests/unit/test_triage_worker.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_explain.py` — covers P35-T01 (mock empty detection lookup)
- [ ] `tests/unit/test_timeline_merge_playbooks.py` — covers P35-T02 (unit test of merge_and_sort_timeline with playbook_rows)
- [ ] `tests/unit/test_telemetry_summary.py` — covers P35-T05 (mock DuckDB + SQLite, verify response shape)
- [ ] `tests/unit/test_field_map.py` — covers P35-T06 (verify SIGMA_FIELD_MAP contains new keys with correct values)
- [ ] `tests/unit/test_triage_store.py` — covers P35-T08 (SQLite :memory: DDL creation, triaged_at column existence)
- [ ] `tests/unit/test_triage_api.py` — covers P35-T09 (FastAPI TestClient, mock ollama, verify result saved)
- [ ] `tests/unit/test_triage_worker.py` — covers P35-T10 (mock sleep, verify poll logic, verify non-fatal on error)

---

## Detailed Findings by Requirement

### T01: explain.py fix
**Current broken path:** `_assemble_investigation()` returns `{}` when detection_id not found (line 77). `_run_explanation()` then calls `build_evidence_context({})` which returns `"GRAPH: 0 entities | 0 timeline events"` — not empty, so no exception. Then `generate_explanation({}, ollama_client)` makes a real Ollama HTTP call that takes up to 120 seconds and returns a useless response. The response sections parse to "insufficient evidence" but no error field is set.

**Fix location:** `backend/api/explain.py` in `_run_explanation()`, after line 47 (after `investigation` is assembled).

**ExplainResponse model:** Already has `error: str | None = None` field (line 24). Use it.

### T02: playbook timeline wiring
**playbook_runs table columns:** `run_id TEXT PK, playbook_id TEXT, investigation_id TEXT, status TEXT, started_at TEXT, completed_at TEXT, steps_completed TEXT, analyst_notes TEXT`

**Status values:** `running`, `completed`, `cancelled` (from playbooks.py lines 272, 297, 342)

**Index exists:** `idx_playbook_runs_inv ON playbook_runs (investigation_id)` — query is fast.

**Timeline.py comment:** Line 156: "playbook_rows intentionally unused — deferred to future phase. When playbook_runs table is implemented, add a loop here similar to edge_rows above." — exact instruction for implementation.

**The `playbooks` table has a `name` column** (sqlite_store.py DDL line 146): `name TEXT NOT NULL`. JOIN on `playbook_id` to get human-readable name.

### T03: EventsView chips
**Current state:** ZEEK_CHIPS are rendered in a separate disabled section with a "Phase 36" divider label. The managed switch is now configured (confirmed in STATE.md: "Netgear GS308E switch arrived and configured — green LAN port 1 mirrored to port 5"). The hardware blocker is resolved.

**API support:** `GET /api/events` already accepts `event_type` query param and filters on it. No backend change needed.

**Backend event_type values in DuckDB:** The `event_type` column is TEXT. Zeek values like `conn`, `http`, `ssl`, `smb` are ingested via the Malcolm/Ubuntu normalization pipeline (Phase 31). The chips will simply show no results if no Zeek data is present — that is acceptable (empty result, not error).

### T05: Overview view — new endpoint needed
**No GET /api/telemetry/summary exists.** The existing `backend/api/telemetry.py` only has `/telemetry/osquery/status`.

**New endpoint:** `GET /api/telemetry/summary` — returns:
```json
{
  "event_type_counts": [{"event_type": "alert", "count": 1234}, ...],
  "scorecard": {
    "total_events": 1234,
    "total_detections": 56,
    "ioc_matches": 7,
    "assets_discovered": 12
  },
  "top_rules": [
    {"rule_name": "Mimikatz", "severity": "high", "detection_count": 8}
  ],
  "window_hours": 24
}
```

**Registration:** Add to `backend/api/telemetry.py` as a new route on the existing `router`. Or create `backend/api/overview.py` and register separately. Prefer adding to telemetry.py to avoid a new file.

**DuckDB query for assets_discovered:** The assets table is in SQLite (asset_store), not DuckDB. Score count uses `asyncio.to_thread(lambda: sqlite._conn.execute(...))`.

### T08: triage_results DDL
**Location for DDL:** `_DDL` string in `backend/stores/sqlite_store.py` (append before closing `"""`).

**triaged_at on detections:** Add via `ALTER TABLE` in `SQLiteStore.__init__()` following the `risk_score` migration pattern (lines 362-370). This is safe because SQLite supports adding nullable TEXT columns to existing tables.

### T09: POST /api/triage/run
**New file:** `backend/api/triage.py`
**Router prefix:** `/triage`
**Auth:** `dependencies=[Depends(verify_token)]` in main.py include_router call

**Endpoint logic:**
1. Query SQLite: `SELECT * FROM detections WHERE triaged_at IS NULL LIMIT 50`
2. If zero detections: return `{"status": "no_detections", "message": "No untriaged detections"}`
3. Format each detection as a summary string
4. Call `build_prompt(detection_summaries)` → `(system_turn, user_turn)`
5. Call `await app.state.ollama.generate(prompt=user_turn, system=SYSTEM + system_turn)`
6. Parse a severity_summary from result_text (count "critical"/"high" mentions, or use heuristic)
7. Save to triage_results via asyncio.to_thread
8. Mark detections triaged via asyncio.to_thread
9. Return the saved triage result

### T10: Auto-triage background worker
**Registration:** In `lifespan()`, after `app.state.ollama` is set (after line 229 in main.py):
```python
# Phase 35: Auto-triage background worker
from backend.api.triage import auto_triage_loop
asyncio.ensure_future(auto_triage_loop(app))
log.info("Auto-triage worker started (60s poll)")
```

**Worker function:** In `backend/api/triage.py`:
```python
async def auto_triage_loop(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(60)
        try:
            await _run_triage_once(app.state.stores.sqlite._conn, app.state.ollama)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Auto-triage iteration failed (non-fatal): %s", exc)
```

**Shutdown:** Add task handle and cancel in lifespan shutdown, same as osquery_task (lines 388-393 in main.py).

---

## State of the Art

| Old State | Current State After Phase 35 |
|-----------|------------------------------|
| AI sits idle until analyst calls /api/explain manually | Auto-triage worker polls every 60s, surfaces results in DetectionsView panel |
| explain.py silently passes {} to Ollama, wastes 120s timeout | Returns structured error immediately with actionable message |
| Playbook timeline rows always empty | Populated from playbook_runs table with name + status chip |
| EventsView Zeek chips disabled (Phase 36 preview) | All 14 chips active; no disabled section |
| Detections is landing view | Overview is landing view with full SOC telemetry picture |
| Intelligence nav items all have BETA badge | Only Playbooks + Recommendations retain BETA |

---

## Open Questions

1. **Severity summary extraction from triage result_text**
   - What we know: `result_text` is raw LLM output. No structured severity count exists.
   - What's unclear: How to populate `severity_summary` in triage_results meaningfully.
   - Recommendation: Use a simple heuristic — count detections by severity from the input list (not the LLM output): `f"{high_count} high, {med_count} medium, {low_count} low"`. This is deterministic and doesn't require LLM parsing.

2. **OverviewView layout on narrow screens**
   - What we know: Two-column grid is the decision. No specific breakpoint specified.
   - Recommendation: Use CSS grid `grid-template-columns: 1fr 1fr` with a `@media (max-width: 900px)` fallback to single column. Consistent with pattern in other views.

3. **GET /api/triage/latest when no triage has ever run**
   - What we know: The endpoint should return "No triage results yet" per CONTEXT.md.
   - Recommendation: Return HTTP 200 with `{"result": null, "message": "No triage results yet"}` rather than 404 — avoids error handling in the frontend.

---

## Sources

### Primary (HIGH confidence — direct code inspection)
- `backend/api/explain.py` — T01 fix location confirmed, ExplainResponse model confirmed
- `backend/api/timeline.py` — T02 playbook_rows parameter confirmed always-empty, JOIN query needed
- `backend/api/playbooks.py` — playbook_runs schema + status values confirmed
- `backend/stores/sqlite_store.py` — _DDL with playbook_runs table confirmed, ALTER TABLE migration pattern confirmed
- `backend/stores/duckdb_store.py` — _ECS_MIGRATION_COLUMNS: http_user_agent, tls_ja3, dns_query already in DuckDB normalized_events schema (lines 245, 231, 226)
- `detections/field_map.py` — SIGMA_FIELD_MAP confirmed, missing dns_query/http_user_agent/tls_ja3 entries confirmed
- `backend/services/ollama_client.py` — generate() signature confirmed
- `prompts/triage.py` — build_prompt() signature confirmed, returns (system_turn, user_turn)
- `backend/main.py` — create_app() deferred router pattern, lifespan worker registration pattern, asyncio.ensure_future() pattern
- `dashboard/src/App.svelte` — navGroups confirmed, beta: true on 4 Intelligence items + Playbooks/Recommendations, currentView default 'detections'
- `dashboard/src/views/EventsView.svelte` — CHIPS and ZEEK_CHIPS arrays confirmed, disabled rendering confirmed
- `backend/api/telemetry.py` — only osquery/status endpoint exists; no summary endpoint

### Secondary (HIGH confidence — project patterns)
- `backend/services/intel/feed_sync.py` — _BaseWorker.run() pattern for auto-triage worker
- `backend/services/intel/ioc_store.py` — SQLite store DDL pattern for TriageStore

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed present, no new installs needed
- Architecture: HIGH — all patterns verified by direct code inspection
- Pitfalls: HIGH — confirmed by reading actual implementation, not assumptions
- SQL queries: MEDIUM — DuckDB `NOW() - INTERVAL 24 HOURS` syntax is standard; SQLite datetime arithmetic uses `datetime('now', '-24 hours')`

**Research date:** 2026-04-10
**Valid until:** 2026-05-10 (stable codebase, no external dependencies changing)
