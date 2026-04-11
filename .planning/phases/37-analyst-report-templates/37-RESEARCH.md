# Phase 37: Analyst Report Templates - Research

**Researched:** 2026-04-11
**Domain:** PDF report generation, WeasyPrint, Svelte 5 tab UI, SQLite CRUD, multi-source data aggregation
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Pre-fill Depth**
- Fill everything computable — not just structured/tabular fields, but also narrative-adjacent fields where data exists
- Triage result text pasted verbatim from latest `triage_results` record (model output, severity_summary)
- Investigation summary text from Ollama/investigation records where available
- Playbook step outputs pulled from `playbook_runs` table rows verbatim
- Analyst-narrative fields (root cause, override rationale, analytical findings) left blank with placeholder text — analyst writes these
- LLM Inference Audit Trail rows (required in 4 of 6 templates) pre-filled from `triage_results` table: model name, prompt version (from content_json), severity_summary, result_text; Confidence and Disposition columns left blank for analyst
- Session Log timespan: rolling 24h from now
- Severity & Confidence Reference: Known Open Gaps section hardcoded in HTML template

**Case Selectors**
- Templates tied to a case (Incident Report, PIR): dropdown in Templates tab AND shortcut "Generate Report" button on each investigation record in InvestigationsView
- Playbook Log: dropdown in Templates tab AND shortcut button on each playbook run record
- TI Bulletin: actor dropdown sourced from AttackStore group data; template pre-fills with that actor's TTPs, matched techniques, and TIP IOCs matching the actor_tag
- Session Log: no selector — one-click, always generates for rolling 24h
- No records exist → generate blank template with placeholder text (never block/disable)

**Templates Tab Layout**
- 2×3 card grid (6 cards)
- Each card: template name, short description, inline selector where needed, Generate button
- Subtle data badge on each card: e.g. "3 investigations available", "0 playbook runs"
- Severity & Confidence Reference: 6th card, no selector, single "Download PDF" button
- After successful generation: card swaps Generate button for Download button; also appears in main Reports list
- Re-generate button available alongside Download

**Output & Persistence**
- Generated templates stored in SQLite `reports` table with types: `template_session_log`, `template_incident`, `template_playbook_log`, `template_pir`, `template_ti_bulletin`, `template_severity_ref`
- Appear in the main Reports tab list alongside executive/investigation reports — type badges distinguish them
- Generate → download immediately; analyst fills narrative fields post-download
- Preserve formal signature/approval lines from original docx templates
- PDF header: match existing SOC Brain style (dark header, AI-SOC-Brain branding, same CSS variables)

### Claude's Discretion
- Exact CSS layout of template cards (spacing, badge position, selector placement)
- HTML structure of each template section (heading hierarchy, table styles)
- How to handle playbook_runs table absence (graceful fallback to blank)
- Column order and exact field names in pre-filled tables

### Deferred Ideas (OUT OF SCOPE)
- In-browser template editing before PDF download
- Scheduled/automated template generation
- Email/export of generated templates
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P37-T01 | Session Log template — rolling 24h, one-click, pre-filled from DuckDB + SQLite | DuckDB normalized_events 24h queries confirmed in reports.py; triage_results.get_latest_triage() exists |
| P37-T02 | Security Incident Report template — case-tied, dropdown selector, pre-filled from investigation_cases + detections + ioc_store + attack_store | list_investigation_cases(status) confirmed; ioc_store has actor_tag column |
| P37-T03 | Playbook Execution Log template — per-run, dropdown selector, pre-filled from playbook_runs.steps_completed JSON | playbook_runs DDL fully confirmed; steps_completed is JSON array of step result dicts |
| P37-T04 | Post-Incident Review template — closed cases selector, multi-source | list_investigation_cases(status='closed') confirmed via case_status column |
| P37-T05 | Threat Intelligence Bulletin — actor dropdown from attack_groups, IOCs from ioc_store filtered by actor_tag | attack_groups table has name/aliases/stix_id; actor_matches() method confirmed; ioc_store.actor_tag column confirmed |
| P37-T06 | Severity & Confidence Reference — static HTML only, no queries | Pure static content; no data dependencies |
| P37-T07 | New "Templates" 5th tab in ReportsView.svelte — 2×3 card grid with badge counts and inline selectors | activeTab pattern fully confirmed; $effect() lazy-load pattern confirmed |
| P37-T08 | Shortcut "Generate Report" buttons in InvestigationsView and PlaybooksView routing to pre-selected template | api.ts extension pattern confirmed; URL param or prop approach viable |
</phase_requirements>

---

## Summary

Phase 37 adds six analyst report templates that are pre-populated from live SOC Brain data and rendered as PDF via the existing WeasyPrint pipeline. The research confirms that every data source needed by all six templates already exists in the codebase — no new tables, no new stores, no new infrastructure. The only new code is: six HTML builder functions in `backend/api/reports.py` (or a new `backend/api/report_templates.py`), six POST endpoints, new request models, `api.ts` extensions, and a 5th tab in `ReportsView.svelte`.

The most important data structures to understand: `triage_results` (run_id, severity_summary, result_text, detection_count, model_name, created_at); `playbook_runs` (run_id, playbook_id, investigation_id, status, started_at, completed_at, steps_completed JSON array, analyst_notes); `investigation_cases` (case_id, title, description, case_status, related_alerts JSON, timeline_events JSON, analyst_notes, created_at, updated_at); `ioc_store` (ioc_value, ioc_type, actor_tag, malware_family, confidence, feed_source); `attack_groups` (stix_id, group_id, name, aliases JSON) joined to `attack_group_techniques`.

The `Report` Pydantic model's `type` field is currently a `Literal["investigation", "executive"]` — this must be widened to accept the six new template type strings. The frontend `Report` interface in `api.ts` has the same constraint. The `reports` table `type` column is plain `TEXT NOT NULL` with an index — it accepts any string, so no migration needed.

**Primary recommendation:** Implement all six template HTML builders + endpoints in a new `backend/api/report_templates.py` module, keeping `reports.py` untouched. Register the new router in `main.py` under the same `/api/reports` prefix.

---

## Standard Stack

### Core (all already installed — no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| WeasyPrint | existing | HTML → PDF rendering | Already used in reports.py; _render_pdf() is the pattern |
| FastAPI | existing | Route handlers | Same pattern as all other API modules |
| SQLite3 | stdlib | All report persistence | SQLiteStore.insert_report() already handles any type string |
| DuckDB | existing | normalized_events 24h queries | Same fetch_all() pattern as executive report |
| Svelte 5 runes | existing | Frontend tab + state | $state(), $effect() — same as other views |

### No New Dependencies
All six templates use only libraries already in pyproject.toml. `subprocess` (stdlib) handles `git rev-parse HEAD` for the Session Log git hash. No new npm packages are needed — the Templates tab uses the same CSS variables and layout primitives already in ReportsView.svelte.

---

## Architecture Patterns

### Recommended Project Structure
```
backend/api/
├── reports.py              # existing — do NOT modify
├── report_templates.py     # NEW — all 6 template builders + 6 POST endpoints
backend/models/
├── report.py               # extend Report.type Literal to include 6 new type strings
dashboard/src/
├── views/ReportsView.svelte # add 5th tab, TemplatesTab component inline or extracted
├── lib/api.ts              # extend api.reports with generateTemplate() + templateMeta()
tests/unit/
├── test_report_templates.py # NEW — unit tests for all 6 HTML builders
```

### Pattern 1: HTML Builder Function
**What:** Pure function that takes pre-fetched data dicts and returns an HTML string.
**When to use:** All six templates — same as `_investigation_html()` and `_executive_html()` in reports.py.
**Example:**
```python
# Pattern from backend/api/reports.py lines 75-162
def _session_log_html(
    title: str,
    generated_at: str,
    event_count_24h: int,
    event_type_breakdown: list[dict],
    source_types: list[dict],
    detection_count_24h: int,
    latest_triage: dict | None,
    git_hash: str,
) -> str:
    """Build HTML for Session Log template."""
    # CSS reuse: same body/h1/h2/table/th/td variables as existing templates
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>{title}</title>
<style>
  body {{ font-family: Arial, sans-serif; font-size: 12px; margin: 30px; }}
  h1 {{ color: #1a1a2e; }}
  h2 {{ color: #16213e; border-bottom: 1px solid #ccc; padding-bottom: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
  th {{ background: #16213e; color: #fff; padding: 6px; text-align: left; }}
  td {{ padding: 5px; vertical-align: top; }}
  tr:nth-child(even) {{ background: #f2f2f2; }}
  .meta {{ color: #666; font-size: 11px; margin-bottom: 20px; }}
  .classification {{ font-weight: bold; color: #d97706; }}
</style>
</head>
<body>
<p class="classification">INTERNAL USE ONLY</p>
<h1>{title}</h1>
...
</body>
</html>"""
```

### Pattern 2: Template POST Endpoint
**What:** POST endpoint that fetches data, builds HTML, renders PDF, persists report, returns metadata.
**When to use:** All six templates follow this exact flow.
**Example:**
```python
# Based on generate_investigation_report() in reports.py lines 282-385
@router.post("/template/session-log", status_code=201)
async def generate_session_log(request: Request) -> JSONResponse:
    stores = request.app.state.stores
    now_utc = datetime.now(timezone.utc)
    cutoff = (now_utc - timedelta(hours=24)).isoformat()

    # Fetch from DuckDB (same pattern as executive report)
    count_rows = await stores.duckdb.fetch_all(
        "SELECT COUNT(*) AS cnt FROM normalized_events WHERE timestamp >= ?",
        [cutoff],
    )
    event_count_24h = int(count_rows[0][0] if count_rows else 0)

    # Fetch from SQLite (asyncio.to_thread pattern)
    latest_triage = await asyncio.to_thread(stores.sqlite.get_latest_triage)

    # git hash via subprocess
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, timeout=5
        ).strip()[:12]
    except Exception:
        git_hash = "unknown"

    # Build HTML → render PDF → persist → return
    html = _session_log_html(...)
    pdf_bytes = await asyncio.to_thread(_render_pdf, html)
    report_id = str(uuid4())
    await asyncio.to_thread(stores.sqlite.insert_report, {
        "id": report_id,
        "type": "template_session_log",
        "title": f"Session Log — {now_utc.strftime('%Y-%m-%d')}",
        ...
    })
    return JSONResponse(content={"id": report_id, ...}, status_code=201)
```

### Pattern 3: Template Meta Endpoint (badge counts)
**What:** GET endpoint returning counts for each template type (used for card badges).
**When to use:** Called once when Templates tab activates.
**Example:**
```python
@router.get("/template/meta")
async def get_template_meta(request: Request) -> JSONResponse:
    """Return counts for template card badges."""
    stores = request.app.state.stores

    def _fetch_meta(conn) -> dict:
        inv_count = conn.execute(
            "SELECT COUNT(*) FROM investigation_cases"
        ).fetchone()[0]
        closed_count = conn.execute(
            "SELECT COUNT(*) FROM investigation_cases WHERE case_status = 'closed'"
        ).fetchone()[0]
        pb_run_count = conn.execute(
            "SELECT COUNT(*) FROM playbook_runs"
        ).fetchone()[0]
        # actor count from attack_groups
        try:
            actor_count = conn.execute(
                "SELECT COUNT(*) FROM attack_groups"
            ).fetchone()[0]
        except Exception:
            actor_count = 0
        return {
            "investigations": inv_count,
            "closed_cases": closed_count,
            "playbook_runs": pb_run_count,
            "actors": actor_count,
        }

    meta = await asyncio.to_thread(_fetch_meta, stores.sqlite._conn)
    return JSONResponse(content=meta)
```

### Pattern 4: Svelte 5 Tab Extension
**What:** Add 'templates' as 5th tab to existing tab-bar array in ReportsView.svelte.
**When to use:** Matches existing 4-tab pattern exactly.
**Example:**
```svelte
<!-- ReportsView.svelte — extend tab-bar array at line 136 -->
{#each [
  ['reports','Reports'],
  ['mitre','ATT&CK Coverage'],
  ['trends','Trends'],
  ['compliance','Compliance Export'],
  ['templates','Templates']   <!-- ADD THIS -->
] as [id, label]}
  <button
    class="tab-btn"
    class:active={activeTab === id}
    onclick={() => activeTab = id as 'reports' | 'mitre' | 'trends' | 'compliance' | 'templates'}
  >{label}</button>
{/each}

<!-- Tab state additions -->
let activeTab = $state<'reports' | 'mitre' | 'trends' | 'compliance' | 'templates'>('reports')
let templateMeta = $state<TemplateMeta | null>(null)
let templateMetaLoading = $state(false)

$effect(() => {
  // existing tabs unchanged
  if (activeTab === 'templates' && !templateMeta && !templateMetaLoading) loadTemplateMeta()
})
```

### Pattern 5: TI Bulletin Actor Dropdown Source
**What:** Actor dropdown populated from `api.attack.actorMatches()` — same endpoint as AttackCoverageView.
**When to use:** TI Bulletin card selector.
**Note:** `api.attack.actorMatches()` returns `ActorMatch[]` from GET /api/attack/actor-matches. This endpoint already exists. The actor_tag value used to filter `ioc_store` is the group `name` field (not stix_id). Cross-reference: `ioc_store.actor_tag` is populated by ThreatFox feed workers and stores actor names as strings (e.g., "Lazarus", "APT28"). Match on `attack_groups.name` = `ioc_store.actor_tag` (case-insensitive LIKE).

**Alternative for actor list:** Query `attack_groups` directly — simpler for the template meta endpoint since we just need name + group_id.

### Anti-Patterns to Avoid
- **Modifying reports.py:** Adding 6 new endpoints there would bloat the file. Use `report_templates.py` with the same router prefix.
- **New report table:** The existing `reports` table with its `type TEXT` column already handles any type string. No migration needed.
- **Synchronous WeasyPrint:** Always wrap `_render_pdf()` in `asyncio.to_thread()`. WeasyPrint is CPU-bound blocking.
- **Widening Report Pydantic Literal without Union:** `Literal["investigation", "executive", "template_session_log", ...]` — just extend the Literal. The frontend `Report` interface type in api.ts also needs updating (or widen to `string`).
- **Blocking actor fetch on TI Bulletin generate:** Fetch attack_groups directly in the endpoint using the shared SQLite connection — do not call the HTTP actor-matches endpoint from within the FastAPI handler.

---

## Data Source Map (Per Template)

### Template 1: Session Log (`template_session_log`)
| Data | Source | Query |
|------|--------|-------|
| Event count 24h | DuckDB `normalized_events` | `COUNT(*) WHERE timestamp >= now-24h` |
| Event type breakdown | DuckDB `normalized_events` | `GROUP BY event_type ORDER BY cnt DESC LIMIT 20` |
| Source types | DuckDB `normalized_events` | `GROUP BY source_type ORDER BY cnt DESC` |
| Detection count 24h | SQLite `detections` | `COUNT(*) WHERE created_at >= now-24h` |
| Latest triage | SQLite `triage_results` | `sqlite.get_latest_triage()` |
| Git hash | subprocess | `git rev-parse HEAD` (first 12 chars) |

### Template 2: Security Incident Report (`template_incident`)
| Data | Source | Query/Method |
|------|--------|-------------|
| Case record | SQLite `investigation_cases` | `sqlite.get_investigation_case(case_id)` |
| Detections | SQLite `detections` | `sqlite.get_detections_by_case(case_id)` |
| IOC matches | SQLite `ioc_hits` | `SELECT * FROM ioc_hits ORDER BY matched_at DESC LIMIT 50` (case-linked via detection event IDs or unfiltered) |
| Triage result | SQLite `triage_results` | `sqlite.get_latest_triage()` |
| ATT&CK techniques | SQLite `detection_techniques` JOIN `attack_techniques` | Via AttackStore or direct query |
| Case selector | SQLite `investigation_cases` | `list_investigation_cases()` for dropdown |

### Template 3: Playbook Execution Log (`template_playbook_log`)
| Data | Source | Query/Method |
|------|--------|-------------|
| Run record | SQLite `playbook_runs` | `sqlite.get_playbook_run(run_id)` |
| Playbook definition | SQLite `playbooks` | `sqlite.get_playbook(playbook_id)` |
| Step results (verbatim) | `playbook_runs.steps_completed` | JSON array — each step: `{step_number, outcome, analyst_note, completed_at}` |
| Investigation case | SQLite `investigation_cases` | `sqlite.get_investigation_case(investigation_id)` |
| Triage result | SQLite `triage_results` | `sqlite.get_latest_triage()` |
| Run selector | SQLite `playbook_runs` | `SELECT run_id, playbook_id, status, started_at FROM playbook_runs ORDER BY started_at DESC` |

### Template 4: Post-Incident Review (`template_pir`)
| Data | Source | Query/Method |
|------|--------|-------------|
| Closed case | SQLite `investigation_cases` | `sqlite.get_investigation_case(case_id)` where `case_status = 'closed'` |
| Detections timeline | SQLite `detections` | `sqlite.get_detections_by_case(case_id)` |
| ATT&CK techniques | `detection_techniques` JOIN `attack_techniques` | Direct SQLite query |
| Playbook runs | SQLite `playbook_runs` | `WHERE investigation_id = case_id` (same query as reports.py line 321) |
| Closed case selector | SQLite `investigation_cases` | `list_investigation_cases(status='closed')` |

### Template 5: Threat Intelligence Bulletin (`template_ti_bulletin`)
| Data | Source | Query/Method |
|------|--------|-------------|
| Actor info | SQLite `attack_groups` | `SELECT name, group_id, aliases FROM attack_groups WHERE name = ?` |
| Group techniques | SQLite `attack_group_techniques` JOIN `attack_techniques` | `WHERE stix_group_id = ?` |
| Matched detections | SQLite `detection_techniques` | techniques that intersect with group techniques |
| IOCs for actor | SQLite `ioc_store` | `SELECT * FROM ioc_store WHERE actor_tag = ? AND ioc_status = 'active'` |
| Asset exposure | SQLite `asset_store` | `SELECT ip, hostname, tag, risk_score FROM asset_store ORDER BY risk_score DESC LIMIT 20` |
| Actor dropdown | SQLite `attack_groups` | `SELECT name, group_id FROM attack_groups ORDER BY name` |

**Note:** `asset_store` is managed by `AssetStore` in `backend/services/assets/` (Phase 34). Query via `stores.sqlite._conn` directly or add a method. Column names confirmed from Phase 34: `ip, hostname, tag, risk_score, last_seen, first_seen, alert_count`.

### Template 6: Severity & Confidence Reference (`template_severity_ref`)
Pure static HTML — no data queries. Content: severity definitions (critical/high/medium/low/informational), confidence scoring rubric (0-100 scale used in ioc_store), LLM confidence interpretation, known open gaps (4 hardcoded items from docx template).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML → PDF rendering | Custom PDF library | `_render_pdf()` in reports.py | WeasyPrint already integrated, tested, thread-safe |
| Report persistence | New table or file system | `sqlite.insert_report()` + `reports` table | Already indexed by type; `idx_reports_type` index exists |
| Actor list for dropdown | New endpoint | Query `attack_groups` directly in `template/meta` | attack_groups already populated by STIX bootstrap; no HTTP overhead |
| IOC filtering by actor | Custom matching logic | `SELECT FROM ioc_store WHERE actor_tag = ?` | actor_tag column exists on ioc_store; indexed on bare_ip (not actor_tag, but table is small) |
| Closed case filter | New status field | `list_investigation_cases(status='closed')` | `case_status` column exists; `idx_inv_cases_status` index exists |
| playbook_runs fetch | New method | Direct `_conn.execute("SELECT * FROM playbook_runs WHERE investigation_id = ?")` | Pattern already in reports.py line 321; `_parse_playbook_run()` handles JSON deserialization |
| Git hash | Custom version tracking | `subprocess.check_output(["git", "rev-parse", "HEAD"])` | stdlib subprocess; no new dependency |

**Key insight:** All data sources exist. The work is entirely in building HTML templates and wiring the API — not in creating new data infrastructure.

---

## Common Pitfalls

### Pitfall 1: Report.type Literal Too Narrow
**What goes wrong:** Adding new template type strings to `reports` table works fine, but the `Report` Pydantic model validates `type` as `Literal["investigation", "executive"]` — deserialization of template records fails.
**Why it happens:** Models are written with known types at authoring time.
**How to avoid:** Widen `Report.type` to `str` or extend the Literal to include all 6 new type strings. Also update the TypeScript `Report` interface in `api.ts` (`type: string` or extended literal).
**Warning signs:** `ValidationError` in `/api/reports` GET endpoint after inserting template reports.

### Pitfall 2: playbook_runs Table May Not Exist on Fresh Instance
**What goes wrong:** Endpoints for Playbook Log and PIR templates crash with `OperationalError: no such table: playbook_runs` on fresh installs.
**Why it happens:** The table is in `_DDL` and created on first SQLiteStore init — it always exists. But `steps_completed` is `TEXT NOT NULL DEFAULT '[]'` — an empty run has `[]` array. The `playbooks` table must exist too (it does — same DDL).
**How to avoid:** Wrap playbook queries in try/except for graceful fallback to blank template sections. This matches CONTEXT.md "Claude's Discretion" guidance.

### Pitfall 3: actor_tag Mismatch Between ioc_store and attack_groups
**What goes wrong:** TI Bulletin generates with 0 IOC rows even though ioc_store has data.
**Why it happens:** `ioc_store.actor_tag` values come from ThreatFox feed (e.g., "Lazarus Group") while `attack_groups.name` may be "Lazarus" without "Group". String mismatch.
**How to avoid:** Use case-insensitive LIKE or fuzzy match: `WHERE LOWER(actor_tag) LIKE LOWER(?) || '%'`. Alternatively, show actor_tag values in the template and let the analyst see both. Document this as known limitation.
**Warning signs:** Template generates but IOC table section is empty despite populated ioc_store.

### Pitfall 4: Blocking Dropdown Population
**What goes wrong:** Template card dropdowns for cases/actors/runs need to be populated before user clicks Generate. If this requires a separate API call that isn't made until tab activation, the UX is slow.
**Why it happens:** `$effect()` lazy-load fires on tab switch, but a second API call is needed to populate each selector.
**How to avoid:** The `GET /api/reports/template/meta` endpoint (described above) returns counts for badges AND can also return the dropdown data (case list, run list, actor list) in a single call. Load all selectors when the Templates tab first activates.

### Pitfall 5: WeasyPrint Line Length for Pre-filled Text Blocks
**What goes wrong:** Verbatim triage result_text or playbook step outputs may contain very long lines with no whitespace — they overflow PDF page width and get clipped.
**Why it happens:** WeasyPrint respects CSS word-wrap but not overflowing pre-formatted text.
**How to avoid:** Wrap long-text fields in `<pre style="white-space: pre-wrap; word-break: break-all;">` or use `overflow-wrap: break-word` on `td` cells.

### Pitfall 6: DuckDB 24h Timestamp Comparison
**What goes wrong:** 24h cutoff query returns 0 events because timestamp column stores ISO-8601 strings and string comparison with timezone-aware `now()` gives wrong results.
**Why it happens:** DuckDB stores timestamps as TEXT in normalized_events (confirmed from executive report pattern).
**How to avoid:** Use the same `datetime.now(timezone.utc).isoformat()` cutoff pattern as executive report (lines 436-438 in reports.py). The existing pattern is `WHERE timestamp >= ? AND timestamp <= ?` with ISO-8601 strings — follow exactly.

---

## Code Examples

Verified patterns from existing source:

### Fetching playbook_runs by investigation_id
```python
# Source: backend/api/reports.py lines 320-328
def _get_runs_for_investigation(sqlite_store: Any, inv_id: str) -> list[dict]:
    rows = sqlite_store._conn.execute(
        "SELECT * FROM playbook_runs WHERE investigation_id = ? ORDER BY started_at DESC",
        (inv_id,),
    ).fetchall()
    return [sqlite_store._parse_playbook_run(dict(r)) for r in rows]

playbook_runs = await asyncio.to_thread(
    _get_runs_for_investigation, stores.sqlite, investigation_id
)
```

### Fetching investigation_cases by status
```python
# Source: backend/stores/sqlite_store.py lines 841-852
# list_investigation_cases(status='closed') returns all cases with case_status = 'closed'
cases = await asyncio.to_thread(
    stores.sqlite.list_investigation_cases, "closed"
)
```

### Fetching ioc_store by actor_tag
```python
# Direct query — no method exists yet; use _conn directly (same pattern as compliance export)
def _fetch_iocs_for_actor(conn, actor_name: str) -> list[dict]:
    rows = conn.execute(
        "SELECT ioc_value, ioc_type, confidence, malware_family, feed_source, last_seen "
        "FROM ioc_store WHERE LOWER(actor_tag) LIKE LOWER(?) AND ioc_status = 'active' "
        "ORDER BY confidence DESC LIMIT 100",
        (f"%{actor_name}%",),
    ).fetchall()
    return [dict(r) for r in rows]
```

### Fetching attack_groups with their technique counts
```python
# Direct query — no method exists; use _conn (AttackStore tables are in same SQLite DB)
def _fetch_actor_list(conn) -> list[dict]:
    rows = conn.execute(
        """SELECT ag.name, ag.group_id,
               COUNT(agt.tech_id) AS tech_count
           FROM attack_groups ag
           LEFT JOIN attack_group_techniques agt ON ag.stix_id = agt.stix_group_id
           GROUP BY ag.stix_id ORDER BY ag.name"""
    ).fetchall()
    return [dict(r) for r in rows]
```

### DuckDB event_type breakdown (24h)
```python
# Source: pattern from executive report (reports.py lines 468-480)
type_rows = await stores.duckdb.fetch_all(
    """SELECT event_type, COUNT(*) AS cnt FROM normalized_events
       WHERE timestamp >= ? AND event_type IS NOT NULL
       GROUP BY event_type ORDER BY cnt DESC LIMIT 20""",
    [cutoff_iso],
)
breakdown = []
for r in type_rows:
    if isinstance(r, tuple):
        breakdown.append({"event_type": r[0], "count": int(r[1])})
    else:
        breakdown.append({"event_type": r.get("event_type"), "count": int(r.get("cnt", 0))})
```

### CSS for template PDF (reuse exactly from reports.py)
```css
/* Source: backend/api/reports.py lines 129-136 — copy verbatim */
body { font-family: Arial, sans-serif; font-size: 12px; margin: 30px; }
h1 { color: #1a1a2e; }
h2 { color: #16213e; border-bottom: 1px solid #ccc; padding-bottom: 4px; }
table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
th { background: #16213e; color: #fff; padding: 6px; text-align: left; }
td { padding: 5px; vertical-align: top; }
tr:nth-child(even) { background: #f2f2f2; }
.meta { color: #666; font-size: 11px; margin-bottom: 20px; }
/* Add for templates: */
.classification { font-weight: bold; color: #d97706; font-size: 11px; }
pre { white-space: pre-wrap; word-break: break-all; font-size: 11px; }
.placeholder { color: #9ca3af; font-style: italic; }
```

### Svelte 2×3 card grid CSS
```css
/* New CSS for Templates tab — add to ReportsView.svelte <style> block */
.template-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.template-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md, 6px); padding: 16px; display: flex; flex-direction: column; gap: 10px; }
.template-card h3 { font-size: 13px; font-weight: 600; margin: 0; }
.template-card p { font-size: 12px; color: var(--text-secondary); margin: 0; }
.template-badge { font-size: 11px; color: var(--text-secondary); background: var(--bg-secondary); padding: 2px 8px; border-radius: 10px; align-self: flex-start; }
.template-actions { display: flex; gap: 8px; margin-top: auto; flex-wrap: wrap; }
```

---

## Schema Reference

### playbook_runs table (confirmed from sqlite_store.py lines 155-165)
| Column | Type | Notes |
|--------|------|-------|
| run_id | TEXT PK | UUID |
| playbook_id | TEXT NOT NULL | FK → playbooks |
| investigation_id | TEXT NOT NULL | case_id from investigation_cases |
| status | TEXT | 'running' / 'completed' / 'cancelled' |
| started_at | TEXT | ISO-8601 |
| completed_at | TEXT | nullable |
| steps_completed | TEXT | JSON array of `{step_number, outcome, analyst_note, completed_at}` |
| analyst_notes | TEXT | free text |

### triage_results table (confirmed from sqlite_store.py lines 326-335)
| Column | Type | Notes |
|--------|------|-------|
| run_id | TEXT PK | UUID |
| severity_summary | TEXT | First line of LLM output, max 200 chars |
| result_text | TEXT | Full LLM triage output (verbatim) |
| detection_count | INTEGER | Number of detections triaged |
| model_name | TEXT | e.g. "qwen3:14b" |
| created_at | TEXT | ISO-8601 DESC indexed |

### investigation_cases table (confirmed from sqlite_store.py lines 85-98)
| Column | Type | Notes |
|--------|------|-------|
| case_id | TEXT PK | |
| title | TEXT | |
| description | TEXT | |
| case_status | TEXT | 'open' / 'closed' / 'resolved' — indexed |
| related_alerts | TEXT | JSON array |
| analyst_notes | TEXT | |
| created_at / updated_at | TEXT | |

### ioc_store table (confirmed from sqlite_store.py lines 289-305)
| Column | Type | Notes |
|--------|------|-------|
| ioc_value | TEXT | |
| ioc_type | TEXT | |
| actor_tag | TEXT | Populated by ThreatFox worker; may not match attack_groups.name exactly |
| malware_family | TEXT | |
| confidence | INTEGER | 0-100 |
| feed_source | TEXT | 'feodo' / 'cisa_kev' / 'threatfox' |
| ioc_status | TEXT | 'active' / 'expired' |

### attack_groups table (confirmed from attack_store.py lines 35-40)
| Column | Type | Notes |
|--------|------|-------|
| stix_id | TEXT PK | STIX intrusion-set ID |
| group_id | TEXT | e.g. "G0016" |
| name | TEXT | e.g. "Lazarus Group" |
| aliases | TEXT | JSON array of alias strings |

### reports table type values (after Phase 37)
| Value | Template |
|-------|---------|
| `investigation` | existing |
| `executive` | existing |
| `template_session_log` | Session Log |
| `template_incident` | Security Incident Report |
| `template_playbook_log` | Playbook Execution Log |
| `template_pir` | Post-Incident Review |
| `template_ti_bulletin` | Threat Intelligence Bulletin |
| `template_severity_ref` | Severity & Confidence Reference |

---

## State of the Art

| Old Approach | Current Approach | Notes |
|--------------|------------------|-------|
| Single `reports.py` for all report types | New `report_templates.py` registered under same prefix | Keeps file sizes manageable; same router prefix means no URL changes |
| `Report.type` as narrow Literal | Widen to `str` or extend Literal | Required to avoid Pydantic ValidationError on list endpoint |
| 4-tab ReportsView | 5-tab with Templates | `activeTab` type union extended; $effect() lazy-load pattern unchanged |

---

## Open Questions

1. **actor_tag vs attack_groups.name mismatch**
   - What we know: `ioc_store.actor_tag` comes from ThreatFox feed which uses actor names like "Lazarus Group", "APT28"; `attack_groups.name` comes from STIX and may differ slightly.
   - What's unclear: Whether the overlap is good enough for useful TI Bulletin pre-fill, or whether the IOC section will commonly be empty.
   - Recommendation: Use LOWER() LIKE fuzzy match in query; document in the template as "IOCs where actor_tag matches actor name (approximate match)" — the analyst can verify.

2. **asset_store access pattern for TI Bulletin**
   - What we know: asset_store is managed by AssetStore in `backend/services/assets/` (Phase 34); tables are in the same SQLite DB as `investigation_cases`.
   - What's unclear: Whether `stores.sqlite._conn` has the asset_store tables — Phase 34 added AssetStore as a separate class but using the same `stores.sqlite._conn`.
   - Recommendation: Query `asset_store` table directly via `stores.sqlite._conn.execute(...)` with a try/except fallback — same pattern used for `attack_groups` in the TI Bulletin.

3. **Shortcut button routing from InvestigationsView**
   - What we know: CONTEXT.md requires shortcut buttons on investigation records that route to the Templates tab with pre-selected case.
   - What's unclear: The exact routing mechanism — URL query params vs. Svelte prop passing vs. a shared $state in App.svelte.
   - Recommendation: Add `?tab=templates&case_id=X` URL query params to the ReportsView route, or use a module-level $state in App.svelte as a cross-view selection store. The simplest approach is `window.location.href = '/reports?tab=templates&case_id=X'` which ReportsView reads on mount via URLSearchParams.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing, pyproject.toml) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` asyncio_mode = "auto" |
| Quick run command | `uv run pytest tests/unit/test_report_templates.py -x` |
| Full suite command | `uv run pytest tests/unit/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P37-T01 | `_session_log_html()` produces valid HTML with all expected sections | unit | `pytest tests/unit/test_report_templates.py::test_session_log_html_structure -x` | ❌ Wave 0 |
| P37-T01 | Session Log endpoint with empty DB returns 201 with placeholder content | unit | `pytest tests/unit/test_report_templates.py::test_session_log_empty_db -x` | ❌ Wave 0 |
| P37-T02 | `_incident_report_html()` includes case_id, LLM audit trail section, signature lines | unit | `pytest tests/unit/test_report_templates.py::test_incident_report_html_structure -x` | ❌ Wave 0 |
| P37-T02 | Incident report endpoint returns 404 when case not found | unit | `pytest tests/unit/test_report_templates.py::test_incident_report_404 -x` | ❌ Wave 0 |
| P37-T03 | `_playbook_log_html()` renders steps_completed verbatim (step_number, outcome, analyst_note) | unit | `pytest tests/unit/test_report_templates.py::test_playbook_log_html_steps -x` | ❌ Wave 0 |
| P37-T03 | Playbook log endpoint returns blank template when no runs exist | unit | `pytest tests/unit/test_report_templates.py::test_playbook_log_blank_fallback -x` | ❌ Wave 0 |
| P37-T04 | `_pir_html()` renders timeline detections, ATT&CK techniques, playbook runs | unit | `pytest tests/unit/test_report_templates.py::test_pir_html_structure -x` | ❌ Wave 0 |
| P37-T05 | `_ti_bulletin_html()` renders ATT&CK TTP table and IOC rows (may be empty) | unit | `pytest tests/unit/test_report_templates.py::test_ti_bulletin_html_structure -x` | ❌ Wave 0 |
| P37-T06 | `_severity_ref_html()` contains all 4 severity levels and known-gaps section | unit | `pytest tests/unit/test_report_templates.py::test_severity_ref_html_completeness -x` | ❌ Wave 0 |
| P37-T07 | Template type strings round-trip through SQLiteStore insert_report/get_report | unit | `pytest tests/unit/test_report_templates.py::test_template_type_persistence -x` | ❌ Wave 0 |
| P37-T07 | GET /api/reports returns template_* type records without ValidationError | unit | `pytest tests/unit/test_report_templates.py::test_list_reports_includes_templates -x` | ❌ Wave 0 |
| P37-T08 | GET /api/reports/template/meta returns expected keys (investigations, closed_cases, playbook_runs, actors) | unit | `pytest tests/unit/test_report_templates.py::test_template_meta_keys -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_report_templates.py -x`
- **Per wave merge:** `uv run pytest tests/unit/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_report_templates.py` — all 12 unit tests listed above
- [ ] No new conftest.py needed — existing `tmp_path` fixture pattern covers SQLiteStore tests

*(All new tests; existing test infrastructure covers SQLiteStore and report CRUD patterns — see `tests/unit/test_report_store.py`)*

---

## Sources

### Primary (HIGH confidence)
- `backend/api/reports.py` (read in full) — `_render_pdf()`, `_investigation_html()`, `_executive_html()`, endpoint patterns, DuckDB query style
- `backend/stores/sqlite_store.py` (read in full) — all DDL including `playbook_runs`, `triage_results`, `reports`, `ioc_store`, `investigation_cases` tables; `insert_report()`, `list_reports()`, `get_latest_triage()`, `list_investigation_cases(status)` methods
- `backend/services/attack/attack_store.py` (read in full) — `attack_groups`, `attack_group_techniques`, `detection_techniques` DDL; `actor_matches()` method
- `dashboard/src/views/ReportsView.svelte` (read in full) — 4-tab pattern, `activeTab` $state, `$effect()` lazy-load, CSS variable usage
- `dashboard/src/lib/api.ts` (read in full) — `api.reports`, `Report` interface, `PlaybookRun`/`PlaybookStepResult` interfaces
- `backend/models/report.py` (read in full) — `Report.type` Literal constraint
- `.planning/phases/37-analyst-report-templates/37-CONTEXT.md` (read in full)

### Secondary (MEDIUM confidence)
- `tests/unit/test_report_store.py` — confirmed `_make_report()` fixture pattern and `store.insert_report()` test approach
- `.planning/STATE.md` — Phase 34/35 completion entries confirm AssetStore, AttackStore, triage_results all exist

### Tertiary (LOW confidence)
- actor_tag / attack_groups.name fuzzy match recommendation — based on structural analysis; actual data values not inspected at runtime

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed in-place; no new dependencies
- Architecture: HIGH — all data sources read directly from source; patterns confirmed from existing code
- Pitfalls: HIGH for Pydantic type widening (Literal confirmed), playbook_runs confirmed in DDL, DuckDB timestamp pattern confirmed; MEDIUM for actor_tag mismatch (runtime data not inspectable)
- Test strategy: HIGH — follows established `test_report_store.py` pattern exactly

**Research date:** 2026-04-11
**Valid until:** 2026-05-11 (stable codebase — all dependencies internal to project)
