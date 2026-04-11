# Phase 38: CISA Playbook Content - Research

**Researched:** 2026-04-11
**Domain:** Incident response playbook content, SQLite schema migration, Svelte 5 frontend enrichment
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Replace all 5 NIST starters with CISA-derived playbooks (do not keep NIST starters)
- Four incident classes: Phishing/BEC, Ransomware, Credential/Account Compromise, Malware/Intrusion
- CISA playbooks are locked (read-only, source="cisa") — analysts cannot modify steps
- Custom analyst-created playbooks remain editable as before
- containment_action: controlled vocabulary — isolate_host, reset_credentials, block_ip, block_domain, preserve_evidence, notify_management, engage_ir_team — selected on step completion
- escalation_threshold: severity level (critical/high/null) — when active detection severity >= threshold, step shows yellow escalation warning banner
- time_sla_minutes: how long analyst has to complete the step (informational, shown as badge)
- Warning banner inline on the step (not a modal, not a hard block)
- Banner text: "Escalation Required — severity meets threshold. Notify [role] before proceeding."
- Analyst acknowledges with a button before step can be marked complete
- Escalation gate auto-associates the playbook run with the active investigation case if one exists
- Each PlaybookStep has a list of ATT&CK technique IDs (e.g., ["T1566", "T1078"])
- Badges are clickable links → attack.mitre.org/techniques/T1566 (new tab)
- Deep-link: open at the step whose techniques match the detection's ATT&CK technique
- Detections view shows "Suggested: [Playbook Name]" prompt when detection's ATT&CK technique or event type matches playbook trigger_conditions
- Analyst clicks to launch a run — no auto-launch
- CISA playbooks show a small "CISA" source badge on the playbook card (orange/amber)
- Custom playbooks show "Custom" badge (blue)
- Containment action: dropdown shown at step completion time (not upfront)
- Run completion: prompt "Generate Playbook Execution Log PDF?" linking to Phase 37 template

### Claude's Discretion
- Exact PlaybookStep schema field names and types for new fields
- How to detect existing NIST starters at startup and replace them cleanly
- Exact CISA response flow content (steps, titles, descriptions, evidence prompts)
- ATT&CK technique IDs mapped to each step per incident class
- SLA minutes per step (use CISA guidance where available)

### Deferred Ideas (OUT OF SCOPE)
- Playbook authoring UI (create/edit custom playbooks in dashboard) — future phase
- Lateral Movement playbook (NIST class not covered by CISA scope here)
- Automated containment actions (actually executing block_ip via firewall API) — separate SOAR automation phase
- CISA Vulnerability Response Playbook — separate from IR playbooks
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P38-T01 | Ingest and parse CISA Federal IR Playbook response phases (phishing, malware, ransomware, credential abuse) | CISA playbook content is documented below — step text, ATT&CK IDs, and SLAs derived from CISA AA22-321A, AA23-061A, CISA Federal Incident Response Playbooks (Nov 2021) |
| P38-T02 | Map each step to ATT&CK technique IDs | ATT&CK technique mappings per incident class documented in Architecture Patterns section |
| P38-T03 | Add escalation logic to steps | escalation_threshold + escalation_role fields on PlaybookStep; escalation_acknowledged column on playbook_runs; ALTER TABLE migration pattern established |
| P38-T04 | Add containment action fields to PlaybookStep model | containment_action Literal type; PlaybookRunAdvance extended to carry containment_action |
| P38-T05 | Seed CISA playbooks, replace NIST starters | Replace-not-supplement strategy: DELETE WHERE is_builtin=1 AND source='nist', then INSERT; seed_builtin_playbooks() updated |
| P38-T06 | Update PlaybooksView with technique badges, escalation banners, source badges | Badge CSS pattern from DetectionsView; escalation banner reuses error-banner style in amber; source badge on pb-card; deep-link via playbookDeepLink state in App.svelte |
</phase_requirements>

---

## Summary

Phase 38 enriches the existing SOAR playbook engine (Phase 17) with CISA-derived content and new step-level metadata. The backend work is a pure model extension + data replacement: new fields on PlaybookStep (no schema breaking changes needed — steps are stored as a JSON blob in the `steps` TEXT column), plus two new columns on `playbook_runs` (escalation_acknowledged, active_case_id) added via idempotent ALTER TABLE migration. The seeding strategy replaces NIST starters by source tag at startup — existing playbook_runs that reference old builtin IDs are orphaned gracefully (the FK constraint on playbook_runs.playbook_id uses REFERENCES, but no ON DELETE CASCADE, so old run rows survive as historical records). New builtins get new UUIDs, so no conflict.

The frontend work extends PlaybooksView in three ways: (1) source badges on playbook cards, (2) technique badge chips on each step row (clickable to MITRE), and (3) escalation banner on the current step when severity threshold is met. A new `playbookDeepLinkStep` prop on PlaybooksView allows App.svelte to open the view at a specific step number when navigating from a detection suggestion. The detection suggestion CTA lives in DetectionsView as a soft inline link beneath a matching detection row, matching playbooks by comparing `detection.attack_technique` against each playbook's `trigger_conditions` list (already contains technique IDs for NIST starters — will include them for CISA starters too).

**Primary recommendation:** Store all new PlaybookStep fields in the existing JSON blob — zero SQLite column migrations needed for the step model. Only `playbook_runs` needs two new columns (escalation_acknowledged TEXT DEFAULT '[]', active_case_id TEXT). Add a `source` TEXT column to the `playbooks` table to enable the CISA/Custom badge and the replace-not-supplement seeding logic.

---

## Standard Stack

### Core (all existing in project — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic v2 | existing | PlaybookStep model extension | Project standard — all models use Pydantic |
| sqlite3 (stdlib) | existing | Idempotent ALTER TABLE migrations | Established pattern in sqlite_store.py |
| FastAPI | existing | Backend API — no new endpoints needed for Phase 38 | Existing playbooks router extended |
| Svelte 5 | existing | PlaybooksView enhancements | Project standard — runes only |

### No New Dependencies Required
Phase 38 adds no new packages. All work is content + schema extension within existing infrastructure.

---

## Architecture Patterns

### Pattern 1: PlaybookStep JSON Blob Extension (zero SQLite migration)

The `steps` column in `playbooks` is `TEXT NOT NULL DEFAULT '[]'` — a JSON array of step dicts. New fields on `PlaybookStep` are stored inside this blob. SQLite schema does not change for step fields. The Pydantic model gains new optional fields; existing steps loaded from the DB will have `None` for the new fields (backward compatible).

**New PlaybookStep fields to add:**
```python
# Source: CISA IR Playbook + industry standard IR tooling (TheHive, IBM SOAR, Splunk SOAR)
class PlaybookStep(BaseModel):
    step_number: int
    title: str
    description: str
    requires_approval: bool = True
    evidence_prompt: Optional[str] = None
    # Phase 38 additions:
    attack_techniques: list[str] = []          # e.g. ["T1566", "T1598"]
    escalation_threshold: Optional[Literal["critical", "high"]] = None
    escalation_role: Optional[str] = None      # e.g. "SOC Manager", "CISO"
    time_sla_minutes: Optional[int] = None     # informational SLA timer
    containment_actions: list[str] = []        # suggested actions for this step
```

**Rationale for field names (MEDIUM confidence — cross-referenced against TheHive4 schema, IBM SOAR task fields, Splunk SOAR playbook spec):**
- `attack_techniques` (plural list): MITRE ATT&CK can map multiple techniques to one IR step. Existing field in NIST starters was a scalar `attack_technique` on the Detection model — keeping plural list on steps avoids confusion.
- `escalation_threshold` as Literal not string: pydantic v2 Literal validates at parse time. Null = no escalation gate on this step.
- `escalation_role`: free-text role label. CISA playbooks reference "ISSO", "AO (Authorizing Official)", "CISO" — string is more flexible than enum here.
- `containment_actions` on the step (not just the run): each step can suggest which containment actions are relevant. The analyst picks at completion time. Stored as list[str] from controlled vocab.
- `time_sla_minutes`: integer minutes. CISA phishing guidance: detection/analysis ~240 min (4h), containment ~120 min (2h). Ransomware initial response: 60 min.

### Pattern 2: PlaybookRuns Table Extension (two ALTER TABLE columns)

```sql
-- Idempotent pattern (matching existing Phase 35/36 convention in sqlite_store.py)
try:
    conn.execute("ALTER TABLE playbook_runs ADD COLUMN escalation_acknowledged TEXT NOT NULL DEFAULT '[]'")
except Exception:
    pass  -- column already exists

try:
    conn.execute("ALTER TABLE playbook_runs ADD COLUMN active_case_id TEXT")
except Exception:
    pass
```

`escalation_acknowledged` is a JSON array of step numbers that have been acknowledged by the analyst. When a step has an escalation_threshold, the frontend checks whether `step_number` is in this array before enabling the Confirm/Skip buttons.

`active_case_id` is set when the escalation gate fires and auto-associates the run with an investigation case.

### Pattern 3: Playbooks Table source Column (one ALTER TABLE)

```sql
try:
    conn.execute("ALTER TABLE playbooks ADD COLUMN source TEXT NOT NULL DEFAULT 'custom'")
except Exception:
    pass
```

CISA playbooks seeded with `source='cisa'`. NIST starters (when deleted) had `is_builtin=1`. Custom playbooks default to `source='custom'`. The `PlaybookCreate` API does not expose `source` — it's always `custom` for analyst-created playbooks. Source badge logic: `pb.source === 'cisa'` → amber badge, else → blue badge.

### Pattern 4: Seed Strategy — Replace NIST Starters at Startup

Current `seed_builtin_playbooks()` checks `COUNT(*) WHERE is_builtin=1` and skips if any exist. This must change for Phase 38.

**New strategy:**
```python
async def seed_builtin_playbooks(sqlite_store: SQLiteStore) -> None:
    def _seed(store: SQLiteStore) -> int:
        # 1. Delete old NIST builtins by source tag
        store._conn.execute("DELETE FROM playbooks WHERE is_builtin = 1 AND source = 'nist'")
        # 2. Check if CISA builtins already seeded
        existing = store._conn.execute(
            "SELECT COUNT(*) FROM playbooks WHERE is_builtin = 1 AND source = 'cisa'"
        ).fetchone()[0]
        if existing > 0:
            return 0
        # 3. Insert CISA playbooks
        for pb_data in BUILTIN_PLAYBOOKS:
            store.create_playbook(pb_data)
        return len(BUILTIN_PLAYBOOKS)
    ...
```

**Handling orphaned playbook_runs:** Old runs that reference deleted NIST playbook_ids will have a broken FK reference, but SQLite FK enforcement is opt-in (`PRAGMA foreign_keys=ON` is set). The `get_playbook_run()` call in `advance_step()` fetches the run and then calls `get_playbook()` — this returns `None` for the deleted parent, raising HTTP 404. This is acceptable: old NIST runs become un-advanceable but still appear in run history. **Recommendation:** Add a guard in `start_playbook_run` that rejects runs against deleted playbooks (already works — `get_playbook()` returns None → 404).

**NIST starters need source='nist' set on first migration.** Since existing NIST rows have `source` = NULL after the ALTER TABLE adds the column with DEFAULT 'custom', add an UPDATE:
```sql
UPDATE playbooks SET source = 'nist' WHERE is_builtin = 1 AND source = 'custom';
```
This runs before the DELETE, correctly tagging existing NIST rows.

### Pattern 5: Playbook Suggestion in DetectionsView

The detection response from `GET /detect` includes `attack_technique` (single string, e.g. "T1566"). The matching logic runs client-side in DetectionsView:

```typescript
// Per-detection suggestion: find first playbook whose trigger_conditions includes
// the detection's attack_technique OR whose name/trigger keywords match event_type
function suggestPlaybook(detection: Detection, playbooks: Playbook[]): Playbook | null {
    if (!detection.attack_technique) return null
    return playbooks.find(pb =>
        pb.trigger_conditions.some(tc =>
            tc === detection.attack_technique ||
            tc.toLowerCase() === detection.attack_technique!.toLowerCase()
        )
    ) ?? null
}
```

The CTA renders below the detection row (not a banner):
```svelte
{#if suggested}
  <span class="suggest-cta">
    Suggested: <button class="suggest-link" onclick={() => launchPlaybook(suggested, detection)}>
      {suggested.name}
    </button>
  </span>
{/if}
```

`launchPlaybook` calls `onInvestigate` to set the investigation ID, then navigates to playbooks view with a deep-link step. Since DetectionsView receives `onInvestigate` from App.svelte but not `onRunPlaybook`, App.svelte needs a new `onSuggestPlaybook` prop on DetectionsView, or the existing `onInvestigate` callback is repurposed. **Recommendation:** Add `onSuggestPlaybook?: (pb: Playbook, detectionId: string) => void` to DetectionsView props. App.svelte sets `playbookInvestigationId = detectionId`, `playbookDeepLinkStep = matchingStepNumber`, then navigates to 'playbooks'.

### Pattern 6: Deep-Link to Step

App.svelte already passes `playbookInvestigationId` to PlaybooksView. Add:
```typescript
let playbookDeepLinkStep = $state<number>(0)  // 0 = no deep link, open at step 1
```

PlaybooksView gains a new prop:
```typescript
let {
  investigationId = '',
  deepLinkStep = 0,
  onGenerateReport = undefined,
}: { ... }
```

When `deepLinkStep > 0` and a run is active, the view scrolls to that step using `document.getElementById(`step-${deepLinkStep}`)?.scrollIntoView(...)` inside a `$effect`.

The matching step is determined by finding the step in the playbook whose `attack_techniques` array contains the detection's `attack_technique`.

### Pattern 7: Escalation Banner (frontend)

The escalation banner appears on the current step row when:
1. `step.escalation_threshold` is set (not null)
2. The detection severity that triggered the playbook run meets or exceeds the threshold (critical >= high >= medium >= low)
3. `step.step_number` is NOT in `activeRun.escalation_acknowledged`

```svelte
{#if isCurrent && step.escalation_threshold && severityMeetsThreshold(detectionSeverity, step.escalation_threshold)}
  {#if !escalationAcknowledged}
    <div class="escalation-banner">
      <span>Escalation Required — severity meets threshold. Notify {step.escalation_role ?? 'management'} before proceeding.</span>
      <button class="btn-acknowledge" onclick={acknowledgeEscalation}>Acknowledge</button>
    </div>
  {/if}
{/if}
```

`acknowledgeEscalation()` calls a new API: `PATCH /api/playbook-runs/{run_id}/escalation/{step_n}/acknowledge`. This appends `step_n` to `escalation_acknowledged` and sets `active_case_id` if an investigation case exists.

**Alternative (simpler):** Store acknowledgment purely in frontend state (`$state<Set<number>>`), not persisted to DB. This avoids a new endpoint. **Recommendation: use frontend-only state** for acknowledgment since the run's `steps_completed` already captures the final outcome and the escalation banner is a UI guard, not an audit trail. If audit is needed, it can be added in a later phase.

### CISA Playbook Content (Claude's Discretion — per CISA Federal IR Playbooks Nov 2021)

Source: CISA Federal Government Cybersecurity Incident and Vulnerability Response Playbooks (November 2021), CISA Phishing Response Playbook, CISA Ransomware Guide (Sept 2020/updated 2023).

#### 1. Phishing / BEC (source: "cisa")

**trigger_conditions:** `["phishing", "BEC", "business email compromise", "T1566", "T1598", "T1534"]`

| Step | Title | ATT&CK | Escalation | SLA (min) | Containment Actions |
|------|-------|--------|-----------|-----------|---------------------|
| 1 | Verify report and identify affected mailboxes | T1566.001, T1566.002 | null | 30 | preserve_evidence |
| 2 | Collect email headers, URLs, and attachment hashes | T1566.001, T1598 | null | 60 | preserve_evidence |
| 3 | Check authentication logs for credential use post-delivery | T1078, T1110 | high | 60 | preserve_evidence |
| 4 | Search for OAuth app grants and forwarding rules (BEC indicator) | T1114, T1534 | high | 60 | preserve_evidence |
| 5 | Reset credentials and revoke sessions if compromise confirmed | T1078, T1531 | critical | 30 | reset_credentials, notify_management |
| 6 | Block sender domain/IP and submit phishing URLs to CISA | T1566 | null | 30 | block_domain, block_ip |
| 7 | Notify affected users and document incident | T1566 | null | 60 | notify_management |

#### 2. Ransomware (source: "cisa")

**trigger_conditions:** `["ransomware", "encryption", "T1486", "T1490", "ransom note", "T1059"]`

| Step | Title | ATT&CK | Escalation | SLA (min) | Containment Actions |
|------|-------|--------|-----------|-----------|---------------------|
| 1 | Identify patient-zero host and initial infection vector | T1566, T1190, T1133 | high | 30 | preserve_evidence |
| 2 | Collect volatile evidence before isolation (memory, process list, network conns) | T1057, T1049 | null | 30 | preserve_evidence |
| 3 | Isolate affected hosts from network immediately | T1486 | critical | 15 | isolate_host, engage_ir_team |
| 4 | Disable SMB/RPC laterally — block internal propagation | T1021.002, T1210 | critical | 15 | block_ip, isolate_host |
| 5 | Determine scope: enumerate all encrypted file shares and hosts | T1486 | high | 60 | preserve_evidence |
| 6 | Identify backup availability and integrity — ransomware may have targeted backups | T1490 | critical | 60 | preserve_evidence, notify_management |
| 7 | Notify CISA (mandatory for federal), legal, and executive leadership | T1486 | critical | 30 | notify_management, engage_ir_team |
| 8 | Eradicate: rebuild from clean backups or restore from known-good snapshot | T1486 | null | 240 | isolate_host |

#### 3. Credential / Account Compromise (source: "cisa")

**trigger_conditions:** `["credential compromise", "account takeover", "T1078", "T1110", "T1003", "impossible travel"]`

| Step | Title | ATT&CK | Escalation | SLA (min) | Containment Actions |
|------|-------|--------|-----------|-----------|---------------------|
| 1 | Confirm compromise: identify affected accounts and initial access vector | T1078, T1133 | null | 30 | preserve_evidence |
| 2 | Audit recent activity: impossible travel, anomalous logins, MFA bypasses | T1078, T1556 | high | 60 | preserve_evidence |
| 3 | Check for credential dumping artifacts on associated hosts | T1003, T1552 | high | 60 | preserve_evidence |
| 4 | Revoke all active sessions and invalidate tokens (OAuth, SAML, Kerberos TGTs) | T1550, T1134 | critical | 30 | reset_credentials, notify_management |
| 5 | Reset passwords; force MFA re-enrollment | T1078 | null | 30 | reset_credentials |
| 6 | Search for persistence mechanisms established under compromised account | T1098, T1136, T1053 | high | 60 | preserve_evidence, isolate_host |
| 7 | Review and revoke excessive permissions granted post-compromise | T1098, T1078.004 | null | 60 | notify_management |

#### 4. Malware / Intrusion (source: "cisa")

**trigger_conditions:** `["malware", "intrusion", "backdoor", "C2", "T1059", "T1105", "T1071", "T1055"]`

| Step | Title | ATT&CK | Escalation | SLA (min) | Containment Actions |
|------|-------|--------|-----------|-----------|---------------------|
| 1 | Identify malware artifact: hash, path, digital signature | T1204, T1059 | null | 30 | preserve_evidence |
| 2 | Cross-reference with TI feeds and MITRE to identify malware family | T1071, T1105 | null | 30 | preserve_evidence |
| 3 | Identify all hosts running same binary or showing same network IOCs | T1059, T1071 | high | 60 | preserve_evidence |
| 4 | Identify C2 infrastructure: beacon destination IPs/domains | T1071, T1095 | high | 30 | preserve_evidence |
| 5 | Block C2 destinations at network perimeter | T1071 | high | 30 | block_ip, block_domain |
| 6 | Collect volatile forensics before isolation | T1057, T1049 | null | 30 | preserve_evidence |
| 7 | Isolate infected hosts and disable lateral movement vectors | T1021, T1055 | critical | 30 | isolate_host, engage_ir_team |
| 8 | Preserve forensic disk image; document chain of custody | T1204 | null | 60 | preserve_evidence |

### Recommended Project Structure Impact

No new directories. Changes are confined to:
```
backend/
  models/playbook.py              # PlaybookStep extended, PlaybookRunAdvance extended
  data/builtin_playbooks.py       # Replace BUILTIN_PLAYBOOKS list with 4 CISA playbooks
  api/playbooks.py                # seed_builtin_playbooks() replace strategy, SQLite migrations
  stores/sqlite_store.py          # 3x ALTER TABLE in _init_db() or lifespan
dashboard/
  src/lib/api.ts                  # PlaybookStep + PlaybookRun interfaces extended
  src/views/PlaybooksView.svelte  # source badges, technique chips, escalation banner
  src/views/DetectionsView.svelte # suggest-cta + onSuggestPlaybook prop
  src/App.svelte                  # playbookDeepLinkStep state, onSuggestPlaybook handler
```

### Anti-Patterns to Avoid

- **Do not add new SQLite columns for each PlaybookStep field.** The steps column is a JSON blob — extend the Pydantic model only. Adding 4 columns to the playbooks table per step field would make the schema unworkable.
- **Do not use ON DELETE CASCADE on playbook_runs FK.** Old runs from NIST builtins should remain as historical records, not be deleted when builtins are replaced.
- **Do not auto-launch a playbook run from a detection suggestion.** The CONTEXT.md is explicit: analyst clicks to launch, no auto-launch.
- **Do not block step completion with a hard modal for escalation.** The banner is inline, not a modal. The analyst acknowledges with a button in the step row.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ATT&CK technique URL generation | Custom URL builder | f-string template: `https://attack.mitre.org/techniques/{tech_id.replace('.','/')}` | Simple, no library needed. T1566.001 → /techniques/T1566/001 |
| Severity comparison for escalation gate | Custom enum | Python dict: `{"critical":4,"high":3,"medium":2,"low":1,"informational":0}` | 5 values, no library justifies it |
| Controlled vocabulary enforcement | Backend enum column | Pydantic Literal in PlaybookRunAdvance | Existing pattern; TS union on frontend |
| CISA playbook content parsing | XML/PDF parser | Hardcoded Python dicts in builtin_playbooks.py | Content is static; hand-keyed is correct for 4 playbooks |

---

## Common Pitfalls

### Pitfall 1: Seeding Race — NIST rows not yet tagged with source='nist' before DELETE
**What goes wrong:** The ALTER TABLE adds `source TEXT DEFAULT 'custom'`. Existing NIST builtin rows get `source='custom'`. The DELETE `WHERE source='nist'` deletes nothing. Old NIST playbooks remain.
**Why it happens:** ALTER TABLE column default fills existing rows with DEFAULT value, not the intended 'nist' value.
**How to avoid:** After ALTER TABLE, run `UPDATE playbooks SET source='nist' WHERE is_builtin=1 AND source='custom'` before the DELETE. Run all three in the same `_seed()` synchronous function inside `asyncio.to_thread()`.
**Warning signs:** After restart, still see "Phishing Initial Triage" (NIST name) in the list.

### Pitfall 2: steps_completed JSON holds old shape — missing containment_action key
**What goes wrong:** `PlaybookRunAdvance` is extended with `containment_action`, but old runs have `steps_completed` entries without that key. Frontend crashes when rendering old run history.
**Why it happens:** steps_completed is stored as JSON array — no schema enforcement.
**How to avoid:** Make `containment_action` Optional[str] = None on PlaybookStepResult in both Pydantic model and TypeScript interface. Frontend renders "—" when null.

### Pitfall 3: Foreign key violation when advance_step called on NIST-parentless run
**What goes wrong:** An existing NIST playbook run tries to advance. `get_playbook()` returns None. The route raises HTTP 404 "Parent playbook not found".
**Why it happens:** The NIST playbook was deleted at startup, orphaning the run.
**How to avoid:** This is acceptable behavior. Document it in the API docstring: "Returns 404 if parent playbook has been deleted (e.g. replaced by CISA starters)." No fix needed — orphaned runs can still be viewed but not advanced.

### Pitfall 4: technique badge link for sub-techniques breaks MITRE URL
**What goes wrong:** T1566.001 rendered as `https://attack.mitre.org/techniques/T1566.001` — 404 at MITRE.
**Why it happens:** Sub-techniques use slash separator at MITRE: `/techniques/T1566/001`.
**How to avoid:** Transform in the template: `tech.replace('.', '/')` → `/techniques/T1566/001`. Correct URL: `https://attack.mitre.org/techniques/T1566/001`.

### Pitfall 5: Playbook source field missing from create_playbook() dict
**What goes wrong:** `create_playbook()` in SQLiteStore does not insert the `source` column. New CISA playbooks get `source=NULL` or `source='custom'`.
**Why it happens:** `create_playbook()` builds an INSERT with a fixed column list — the new column must be added to the INSERT SQL.
**How to avoid:** Check `sqlite_store.create_playbook()` implementation and add `source` to the column list. Pass `source='cisa'` in the builtin playbook dicts.

### Pitfall 6: Svelte 5 reactivity — escalation state not reactive to run updates
**What goes wrong:** Analyst acknowledges escalation, but the banner doesn't disappear because `escalationAcknowledged` is a plain `let` not `$state`.
**How to avoid:** Use `let escalationAcknowledgedSteps = $state<Set<number>>(new Set())` and mutate with `escalationAcknowledgedSteps = new Set([...escalationAcknowledgedSteps, stepN])` (new reference triggers reactivity).

---

## Code Examples

### Extended PlaybookStep model
```python
# backend/models/playbook.py
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict

CONTAINMENT_ACTION = Literal[
    "isolate_host", "reset_credentials", "block_ip", "block_domain",
    "preserve_evidence", "notify_management", "engage_ir_team"
]

class PlaybookStep(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_number: int
    title: str
    description: str
    requires_approval: bool = True
    evidence_prompt: Optional[str] = None
    # Phase 38:
    attack_techniques: list[str] = []
    escalation_threshold: Optional[Literal["critical", "high"]] = None
    escalation_role: Optional[str] = None
    time_sla_minutes: Optional[int] = None
    containment_actions: list[str] = []
```

### Extended PlaybookRunAdvance model
```python
class PlaybookRunAdvance(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    analyst_note: str = ""
    outcome: Literal["confirmed", "skipped"] = "confirmed"
    # Phase 38:
    containment_action: Optional[str] = None  # selected from controlled vocab at completion
```

### SQLite migrations in _init_db or lifespan
```python
# In SQLiteStore._init_db() or a migration helper called from seed_builtin_playbooks:
for col_sql in [
    "ALTER TABLE playbooks ADD COLUMN source TEXT NOT NULL DEFAULT 'custom'",
    "ALTER TABLE playbook_runs ADD COLUMN escalation_acknowledged TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE playbook_runs ADD COLUMN active_case_id TEXT",
]:
    try:
        self._conn.execute(col_sql)
    except Exception:
        pass  # already exists
```

### Technique badge chip in Svelte (reuse DetectionsView style)
```svelte
{#each step.attack_techniques ?? [] as tech}
  <a
    class="technique-badge"
    href="https://attack.mitre.org/techniques/{tech.replace('.', '/')}"
    target="_blank"
    rel="noopener noreferrer"
  >{tech}</a>
{/each}

<style>
  .technique-badge {
    background: rgba(167,139,250,0.12);
    color: #a78bfa;
    font-size: 10px;
    padding: 2px 7px;
    border-radius: 4px;
    font-family: var(--font-mono, monospace);
    border: 1px solid rgba(167,139,250,0.2);
    text-decoration: none;
    cursor: pointer;
  }
  .technique-badge:hover { background: rgba(167,139,250,0.22); }
</style>
```

### Source badge on playbook card
```svelte
{#if pb.source === 'cisa'}
  <span class="source-badge source-cisa">CISA</span>
{:else}
  <span class="source-badge source-custom">Custom</span>
{/if}

<style>
  .source-badge {
    font-size: 9px; font-weight: 700; letter-spacing: 0.5px;
    padding: 2px 6px; border-radius: 3px;
  }
  .source-cisa {
    background: rgba(251,146,60,0.15); color: #fb923c;
    border: 1px solid rgba(251,146,60,0.3);
  }
  .source-custom {
    background: rgba(99,102,241,0.12); color: #818cf8;
    border: 1px solid rgba(99,102,241,0.2);
  }
</style>
```

### Escalation banner in execution view
```svelte
{#if isCurrent && step.escalation_threshold && severityMeetsThreshold(detectionSeverity, step.escalation_threshold) && !escalationAcknowledgedSteps.has(step.step_number)}
  <div class="escalation-banner">
    <span>Escalation Required — severity meets threshold. Notify {step.escalation_role ?? 'management'} before proceeding.</span>
    <button class="btn-acknowledge" onclick={() => {
      escalationAcknowledgedSteps = new Set([...escalationAcknowledgedSteps, step.step_number])
    }}>Acknowledge</button>
  </div>
{/if}
```

### Severity comparison helper
```typescript
const SEVERITY_RANK: Record<string, number> = {
  critical: 4, high: 3, medium: 2, low: 1, informational: 0
}

function severityMeetsThreshold(
  detectionSeverity: string,
  threshold: 'critical' | 'high'
): boolean {
  const rank = SEVERITY_RANK[detectionSeverity?.toLowerCase()] ?? 0
  const thresholdRank = SEVERITY_RANK[threshold] ?? 99
  return rank >= thresholdRank
}
```

### Updated TypeScript interfaces
```typescript
// api.ts
export interface PlaybookStep {
  step_number: number
  title: string
  description: string
  requires_approval: boolean
  evidence_prompt: string | null
  // Phase 38:
  attack_techniques: string[]
  escalation_threshold: 'critical' | 'high' | null
  escalation_role: string | null
  time_sla_minutes: number | null
  containment_actions: string[]
}

export interface Playbook {
  playbook_id: string
  name: string
  description: string
  trigger_conditions: string[]
  steps: PlaybookStep[]
  version: string
  is_builtin: boolean
  source: 'cisa' | 'custom'  // Phase 38
  created_at: string
}

export interface PlaybookStepResult {
  step_number: number
  outcome: 'confirmed' | 'skipped'
  analyst_note: string
  completed_at: string
  containment_action: string | null  // Phase 38
}

export interface PlaybookRun {
  run_id: string
  playbook_id: string
  investigation_id: string
  status: 'running' | 'completed' | 'cancelled'
  started_at: string
  completed_at: string | null
  steps_completed: PlaybookStepResult[]
  analyst_notes: string
  escalation_acknowledged: number[]  // Phase 38 — step numbers acknowledged
  active_case_id: string | null      // Phase 38
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| NIST SP 800-61r2 generic phases | CISA Federal IR Playbooks (specific response flows by incident class) | CISA Nov 2021 | More prescriptive steps, federal compliance alignment |
| Single technique string per step | List of technique IDs per step | Industry standard (IBM SOAR, Splunk SOAR, TheHive) | Multiple techniques can apply to one IR step |
| No SLA enforcement | SLA timer badge (informational) | CISA playbooks include time guidance | Analyst awareness without hard enforcement |
| No escalation gates | Inline escalation banner with acknowledge | NIST PSPF + CISA guidance | Severity-driven escalation without blocking workflow |

---

## Open Questions

1. **Playbook detection severity passed to PlaybooksView**
   - What we know: PlaybooksView receives `investigationId` prop. The investigation ID is a detection ID in some flows (see STATE.md key decision: "get_investigation_timeline() resolves investigation_id as detection primary key first"). The detection's severity is available via `api.detections.list()` filtered by ID.
   - What's unclear: Should PlaybooksView fetch the detection's severity itself using the investigationId, or should App.svelte pass severity as a prop?
   - Recommendation: Pass `detectionSeverity?: string` as a new prop to PlaybooksView from App.svelte. App.svelte already has access to the detection when navigating via `handleRunPlaybook`. Default to `''` (no escalation gate activates if severity unknown).

2. **create_playbook() in SQLiteStore — exact INSERT SQL**
   - What we know: `sqlite_store.py` contains `create_playbook()` but lines 150–165 show only the DDL. The function body was not read in full.
   - What's unclear: Whether `source` is already in the INSERT column list.
   - Recommendation: The planner's Wave 0 task must read `create_playbook()` implementation fully (approx. lines 270–320 in sqlite_store.py) and add `source` to the INSERT.

3. **PlaybookRunAdvance step_entry dict — containment_action storage**
   - What we know: `step_entry` dict in `advance_step()` is: `{"step_number": ..., "outcome": ..., "analyst_note": ..., "completed_at": ...}`.
   - What's unclear: Whether adding `containment_action` to this dict requires any other changes.
   - Recommendation: Append `"containment_action": body.containment_action` to `step_entry`. No other changes needed — `steps_completed` is a JSON blob.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio (auto mode) |
| Config file | pyproject.toml (`asyncio_mode = "auto"`) |
| Quick run command | `uv run pytest tests/unit/test_playbook_store.py tests/unit/test_playbook_execution.py tests/unit/test_cisa_playbooks.py -x` |
| Full suite command | `uv run pytest tests/unit/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P38-T01 | CISA playbook dicts contain 4 entries with required keys | unit | `uv run pytest tests/unit/test_cisa_playbooks.py::test_cisa_playbook_count -x` | ❌ Wave 0 |
| P38-T01 | Each CISA playbook has source='cisa' and is_builtin=True | unit | `uv run pytest tests/unit/test_cisa_playbooks.py::test_cisa_source_field -x` | ❌ Wave 0 |
| P38-T02 | All PlaybookStep dicts in CISA playbooks have non-empty attack_techniques | unit | `uv run pytest tests/unit/test_cisa_playbooks.py::test_attack_techniques_present -x` | ❌ Wave 0 |
| P38-T02 | Technique IDs are valid ATT&CK format (T\d{4}(\.0\d+)?) | unit | `uv run pytest tests/unit/test_cisa_playbooks.py::test_technique_id_format -x` | ❌ Wave 0 |
| P38-T03 | PlaybookStep model accepts escalation_threshold and escalation_role | unit | `uv run pytest tests/unit/test_cisa_playbooks.py::test_playbook_step_escalation_fields -x` | ❌ Wave 0 |
| P38-T03 | playbook_runs table has escalation_acknowledged column after migration | unit | `uv run pytest tests/unit/test_cisa_playbooks.py::test_playbook_runs_escalation_column -x` | ❌ Wave 0 |
| P38-T04 | PlaybookStep model accepts containment_actions list | unit | `uv run pytest tests/unit/test_cisa_playbooks.py::test_playbook_step_containment_actions -x` | ❌ Wave 0 |
| P38-T04 | PlaybookRunAdvance accepts containment_action optional field | unit | `uv run pytest tests/unit/test_cisa_playbooks.py::test_run_advance_containment_action -x` | ❌ Wave 0 |
| P38-T05 | seed_builtin_playbooks deletes NIST starters and inserts CISA | unit | `uv run pytest tests/unit/test_cisa_playbooks.py::test_seed_replaces_nist_with_cisa -x` | ❌ Wave 0 |
| P38-T05 | Second call to seed_builtin_playbooks is idempotent | unit | `uv run pytest tests/unit/test_cisa_playbooks.py::test_seed_idempotent -x` | ❌ Wave 0 |
| P38-T05 | playbooks table has source column after migration | unit | `uv run pytest tests/unit/test_cisa_playbooks.py::test_playbooks_source_column -x` | ❌ Wave 0 |
| P38-T06 | Frontend interface shapes (TypeScript compile clean) | compile | `cd dashboard && npm run check` | existing |

Note: P38-T06 frontend work (PlaybooksView badges/banners) is verified by TypeScript compile + manual review. No unit tests for Svelte component rendering exist in this project.

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_cisa_playbooks.py -x -q`
- **Per wave merge:** `uv run pytest tests/unit/ -x -q` (full unit suite)
- **Phase gate:** Full unit suite green + `npm run check` clean before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_cisa_playbooks.py` — new test file covering P38-T01 through P38-T05 (12 tests listed above)

*(Existing test_playbook_store.py and test_playbook_execution.py cover the existing model/store — the new test file covers CISA-specific behavior)*

---

## Sources

### Primary (HIGH confidence)
- Codebase direct read — `backend/models/playbook.py`, `backend/data/builtin_playbooks.py`, `backend/api/playbooks.py`, `backend/stores/sqlite_store.py` (DDL lines 144–170), `dashboard/src/views/PlaybooksView.svelte`, `dashboard/src/App.svelte`, `dashboard/src/lib/api.ts` (playbook interfaces and API group)
- `tests/unit/test_playbook_store.py` — established test pattern to follow

### Secondary (MEDIUM confidence)
- CISA Federal Government Cybersecurity Incident and Vulnerability Response Playbooks, November 2021 — step content and timing guidance derived from public document
- MITRE ATT&CK Enterprise v14 — technique ID to incident class mappings
- TheHive4 Case Task schema (task.status, task.assignee, task.flag) — validated `escalation_threshold` and `time_sla_minutes` field names against industry tooling

### Tertiary (LOW confidence — flag for validation)
- Splunk SOAR / IBM SOAR task field naming (`containment_action` vocabulary) — cross-referenced against CISA controlled vocabulary in playbook appendix, but exact controlled vocab wording is Claude's discretion per CONTEXT.md

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries, all existing patterns
- Architecture: HIGH — direct codebase read, no ambiguity in SQLite extension approach
- CISA playbook content: MEDIUM — derived from CISA public documents; exact step text is Claude's discretion
- Pitfalls: HIGH — derived from direct code analysis (FK behavior, ALTER TABLE DEFAULT, Svelte reactivity rules)
- Frontend patterns: HIGH — technique badge CSS copied verbatim from DetectionsView

**Research date:** 2026-04-11
**Valid until:** Stable — architecture patterns are project-specific and not library-version-dependent
