# Phase 40: Atomic Red Team Validation - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Ingest the Atomic Red Team test catalog, expose it via API, and let analysts browse tests by ATT&CK technique, generate PowerShell invocation commands, and validate whether the SOC Brain detected the simulated behavior. Closes the loop between threat simulation and detection validation. No autonomous execution — commands are copy-pasted by the analyst manually.

</domain>

<decisions>
## Implementation Decisions

### Catalog storage
- SQLite (not DuckDB) — consistent with every prior catalog (IOC, STIX, CAR, playbooks). Override P40-T01 spec. DuckDB remains for time-series events only.
- Full catalog (~1000+ tests across ~200 techniques) — same decision as CAR, full coverage means any technique is covered as Sigma rules expand.
- Pre-generated JSON bundle: run `scripts/generate_atomics_bundle.py` once, commit `backend/data/atomics.json`. No GitHub dependency at runtime. Same pattern as CAR (`scripts/generate_car_bundle.py` → `backend/data/car_analytics.json`).
- Seed into SQLite at startup — same startup-seed pattern as CARStore, AttackStore, PlaybookStore.

### PowerShell command generation
- Copy-to-clipboard button — single click, no modal. Fast for analyst workflow.
- Format: `Invoke-AtomicTest T1059.001 -TestNumbers 1` — standard ART format, requires Invoke-AtomicRedTeam PS module.
- Show all three commands per test: prerequisite check command, test command, cleanup command — each with its own copy button.
- Commands displayed inline in the test row/card (not a modal).

### Validation window and verdict
- Time window: 5 minutes — long enough for ingest + Sigma matching, short enough to feel interactive.
- PASS definition: a Sigma detection record exists with matching ATT&CK technique (parent technique, sub-technique stripped) within the 5-minute window. Highest confidence — proves the full pipeline fired.
- Trigger: manual Validate button per test row. Analyst clicks after running the command. Backend checks last 5 minutes. Inline pass/fail result appears in the row.
- No automatic polling.

### AtomicsView layout and coverage badges
- Coverage badges live in AtomicsView only — AttackCoverageView stays unchanged.
- Badge states: green = atomic validated (Sigma detection confirmed), yellow = Sigma rule exists for technique but not validated, red = no coverage.
- Primary browse layout: grouped by ATT&CK technique. Collapsible rows — technique header row (e.g. "T1059 — Command and Shell Interpreter") expands to reveal individual atomic tests beneath it.
- Per-test row shows: test name, supported platforms (Windows/Linux/macOS chips), coverage badge, and 3 copy buttons (Prereq / Test / Cleanup).

### Claude's Discretion
- Exact SQLite schema for atomics table (columns, indexes)
- JSON field mapping from ART YAML to storage schema
- How technique coverage status (yellow/green/red) is computed — whether via JOIN with detections table or a separate validation_results table
- Nav group placement for AtomicsView (Respond or Intelligence)
- Exact CSS for platform chips and coverage badge colors

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/services/car/car_store.py` — CARStore: exact pattern to follow for AtomicsStore (SQLite ref table, DDL, bulk_insert, seed function)
- `scripts/generate_car_bundle.py` — CAR bundle generation script: adapt for ART YAML parsing
- `backend/data/car_analytics.json` — bundled reference data pattern
- `AttackCoverageView.svelte` — technique/tactic heatmap with covered/uncovered badges — visual language for coverage status
- `DetectionsView.svelte` — expandable row pattern (Phase 39) — same expand/collapse for technique → test groups
- `dashboard/src/lib/api.ts` — typed client, all existing interface patterns

### Established Patterns
- Reference data → SQLite (IocStore, AttackStore, CARStore, PlaybookStore). Not DuckDB.
- Startup seed → check if table populated, if empty seed from bundled JSON file.
- Sync enrichment at detection time → `asyncio.to_thread` wrapper for SQLite reads.
- Svelte 5 runes: `$state`, `$derived`, `$effect` — no stores.
- Relative imports in Svelte (not `$lib` alias — see commit 233d007).
- Nav items added to App.svelte navGroups array.

### Integration Points
- `backend/stores/sqlite_store.py` — Add `AtomicsStore` class (or separate module under `backend/services/atomics/`)
- `backend/main.py` — Add AtomicsStore init + seed task in lifespan (after CARStore block)
- `backend/api/atomics.py` — New router: `GET /api/atomics` (catalog), `POST /api/atomics/validate`
- `backend/api/detect.py` or `backend/stores/sqlite_store.py` — Validation query: SELECT FROM detections WHERE attack_technique LIKE 'T%' AND created_at > now-5min
- `dashboard/src/lib/api.ts` — Add `AtomicTest`, `ValidationResult` interfaces + `api.atomics` group
- `dashboard/src/views/AtomicsView.svelte` — New view: grouped by technique, expand/collapse, per-test row with 3 copy buttons + Validate button
- `dashboard/src/App.svelte` — Add `atomics` to navGroups, handle view routing

</code_context>

<specifics>
## Specific Ideas

- Technique grouping in AtomicsView mirrors how red teamers think: "which techniques can I simulate, and are they detected?" — collapsible by technique ID matches AttackCoverageView's tactic grouping pattern.
- The three-button row (Prereq / Test / Cleanup) keeps safe red team ops first-class: cleanup is always visible alongside the test command.
- Inline pass/fail after Validate keeps the analyst in the same view — no navigation required to confirm detection.

</specifics>

<deferred>
## Deferred Ideas

- Automatic polling after copy (spinner until detection appears) — user chose manual Validate button instead
- Augmenting AttackCoverageView heatmap with validation badges — user kept AtomicsView standalone
- Scheduled/recurring atomic test runs — future phase
- Integration with AtomicsView in HuntingView (surface atomics for active hunt queries) — future phase

</deferred>

---

*Phase: 40-atomic-red-team-validation*
*Context gathered: 2026-04-12*
