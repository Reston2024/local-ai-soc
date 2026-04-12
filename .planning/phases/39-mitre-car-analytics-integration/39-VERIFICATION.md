---
phase: 39-mitre-car-analytics-integration
verified: 2026-04-11T18:30:00Z
status: human_needed
score: 12/12 automated must-haves verified
re_verification: false
human_verification:
  - test: "DetectionsView expandable CAR row — click a detection row with an ATT&CK technique"
    expected: "Row expands inline below to show CAR analytic cards with ID badge, title, coverage level badge, description, log sources, pseudocode, and CAR/ATT&CK external links"
    why_human: "UI interaction and visual rendering cannot be verified programmatically"
  - test: "DetectionsView no-analytics message — click a detection with no ATT&CK technique"
    expected: "Row expands but shows 'No CAR analytics available for this detection.' message"
    why_human: "Requires live detection data and UI interaction"
  - test: "DetectionsView expand/collapse toggle — click expanded row again"
    expected: "Row collapses (only one row expanded at a time)"
    why_human: "Stateful UI behavior requiring browser interaction"
  - test: "DetectionsView multiple CAR analytics for T1059"
    expected: "Expanded panel shows multiple stacked CAR analytic cards, each with distinct analytic_id and title"
    why_human: "Requires live data with T1059 detections and visual verification"
  - test: "InvestigationView CAR Analytics section — navigate to an investigation for a detection with ATT&CK technique"
    expected: "Evidence panel shows 'CAR Analytics' section heading, subtitle, and one or more CAR analytic cards with same card layout as DetectionsView"
    why_human: "Requires live backend, investigation flow, and visual rendering"
  - test: "External link correctness — click CAR and ATT&CK links in an analytic card"
    expected: "CAR link opens https://car.mitre.org/analytics/CAR-XXXX-XX-XXX/ and ATT&CK link opens https://attack.mitre.org/techniques/TXXXX/ in a new tab"
    why_human: "External URL navigation requires browser and live data"
  - test: "CAR data populated at detection time — run a Sigma rule that fires on T1059 events"
    expected: "GET /api/detect shows the detection with car_analytics field as a parsed list of CAR analytic dicts, not a raw JSON string"
    why_human: "Requires live event ingestion and detection pipeline execution"
---

# Phase 39: MITRE CAR Analytics Integration — Verification Report

**Phase Goal:** Integrate MITRE Cyber Analytics Repository (CAR) analytics as enrichment data for the detection triage workflow. When a Sigma rule fires, surface the matching CAR analytic (detection rationale, log-source requirements, triage guidance) alongside the detection so analysts have validated reasoning rather than just an alert.

**Verified:** 2026-04-11T18:30:00Z
**Status:** human_needed (all automated checks pass — visual/interactive items require human)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | CAR analytics bundle exists with 90+ entries, correct schema | VERIFIED | `backend/data/car_analytics.json` has 158 entries; all have analytic_id, technique_id, title, description, log_sources, analyst_notes, pseudocode, coverage_level, platforms |
| 2 | CARStore DDL creates car_analytics table with composite PK and indexes | VERIFIED | `car_store.py` lines 22–39: DDL with PRIMARY KEY (analytic_id, technique_id), idx_car_technique, idx_car_analytic |
| 3 | CARStore bulk_insert, analytic_count, get_analytics_for_technique implemented | VERIFIED | All 8 test_car_store.py tests pass GREEN (8 passed, 0 skipped) |
| 4 | Sub-technique normalization works (T1059.001 → T1059) | VERIFIED | car_store.py line 72: `parent_id = technique_id.split(".")[0].upper()` — test_subtechnique_normalization PASSED |
| 5 | seed_car_analytics() reads car_analytics.json at startup, idempotent | VERIFIED | car_store.py lines 84–95: checks analytic_count() > 0 before seeding, uses asyncio.to_thread |
| 6 | detections table has car_analytics TEXT column (idempotent migration) | VERIFIED | sqlite_store.py line 421: ALTER TABLE detections ADD COLUMN car_analytics TEXT in try/except |
| 7 | main.py wires CARStore and schedules seed task | VERIFIED | main.py lines 312–319: CARStore(sqlite_store._conn), app.state.car_store, asyncio.ensure_future(seed_car_analytics) |
| 8 | matcher.py enriches detections with CAR analytics at detection time | VERIFIED | matcher.py lines 820–843: inline car_analytics query after attack_technique tagging, UPDATE detections, graceful try/except |
| 9 | GET /api/detect returns car_analytics as parsed list (not raw JSON string) | VERIFIED | detect.py lines 98–103: json.loads(car_analytics) in _query() loop, same pattern as matched_event_ids |
| 10 | POST /api/investigate returns top-level car_analytics key | VERIFIED | investigate.py line 83: "car_analytics": [] in result dict; lines 97–116: CAR lookup after detection load |
| 11 | CARAnalytic TypeScript interface + Detection.car_analytics field typed in api.ts | VERIFIED | api.ts line 37: CARAnalytic interface; line 64: car_analytics?: CARAnalytic[] \| null on Detection |
| 12 | DetectionsView expandable row with CAR panel implemented | VERIFIED | DetectionsView.svelte line 18: `$state<string\|null>(null)` expandedId; line 441–471: conditional CAR panel row with cards, no-analytics message, CSS styles |
| 13 | InvestigationView CAR Analytics section implemented | VERIFIED | InvestigationView.svelte line 161: conditional section; lines 163–176: section title, subtitle, card loop with CAR/ATT&CK links |

**Score:** 12/12 automated truths verified (13th truth split across 2 component items, both verified)

---

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `tests/unit/test_car_store.py` | VERIFIED | 8 tests, all PASS GREEN; ImportError guard present (line 21–25); _make_conn() with row_factory (line 28–32); pytestmark = pytest.mark.unit |
| `backend/data/car_analytics.json` | VERIFIED | 158 entries (exceeds 90 minimum); all required fields present |
| `scripts/generate_car_bundle.py` | VERIFIED | Exists; yaml.safe_load present (line 111) |
| `backend/services/car/__init__.py` | VERIFIED | Exists (empty module init) |
| `backend/services/car/car_store.py` | VERIFIED | CARStore class + DDL + bulk_insert + analytic_count + get_analytics_for_technique + seed_car_analytics; 96 lines, substantive |
| `backend/stores/sqlite_store.py` | VERIFIED | car_analytics TEXT column migration at line 421, wrapped in try/except |
| `backend/main.py` | VERIFIED | CARStore init + seed_car_analytics + app.state.car_store at lines 312–319 |
| `detections/matcher.py` | VERIFIED | CAR lookup at lines 820–843 inside _sync_save(), graceful except with log.debug |
| `backend/api/detect.py` | VERIFIED | json.loads car_analytics at lines 98–103 in _query() loop |
| `backend/api/investigate.py` | VERIFIED | car_analytics: [] in initial result dict (line 83); CAR lookup block lines 97–116 |
| `dashboard/src/lib/api.ts` | VERIFIED | CARAnalytic interface (line 37); Detection.car_analytics (line 64) |
| `dashboard/src/views/DetectionsView.svelte` | VERIFIED | expandedId $state (line 18); CARAnalytic import (line 3); conditional panel row (lines 441–471); expand-chevron (line 417); CSS in `<style>` block (lines 816–835) |
| `dashboard/src/views/InvestigationView.svelte` | VERIFIED | CARAnalytic import (line 3); car_analytics in $state type (line 16); conditional CAR section (lines 161–180); CSS (lines 415–432) |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/unit/test_car_store.py` | `backend/services/car/car_store.py` | ImportError skipif guard | WIRED | try/except _AVAILABLE guard at lines 21–25; all 8 tests PASS (not SKIP) — CARStore is available |
| `backend/services/car/car_store.py` | `backend/data/car_analytics.json` | seed_car_analytics() pathlib.Path | WIRED | car_store.py line 89: `Path(__file__).parent.parent.parent / "data" / "car_analytics.json"` |
| `backend/main.py` | `backend/services/car/car_store.py` | CARStore(sqlite_store._conn) in lifespan | WIRED | main.py lines 313–317: CARStore init + app.state.car_store assigned |
| `detections/matcher.py` | `backend/stores/sqlite_store.py` | car_analytics UPDATE in _sync_save() | WIRED | matcher.py lines 820–843: inline SQL query + UPDATE detections SET car_analytics |
| `backend/api/detect.py` | `backend/stores/sqlite_store.py` | json.loads car_analytics TEXT column | WIRED | detect.py lines 98–103: reads car_analytics from dict(row), parses to list |
| `backend/api/investigate.py` | `backend/stores/sqlite_store.py` | asyncio.to_thread lambda SELECT from car_analytics | WIRED | investigate.py lines 100–113: parameterized query with parent_id, returns [dict(r)] |
| `DetectionsView.svelte` | `dashboard/src/lib/api.ts` | CARAnalytic type import + Detection.car_analytics | WIRED | line 3: `import { ..., type CARAnalytic } from '../lib/api.ts'`; line 444: `d.car_analytics` accessed |
| `InvestigationView.svelte` | `dashboard/src/lib/api.ts` | CARAnalytic type import + investigationResult.car_analytics | WIRED | line 3: `import type { ..., CARAnalytic }`; line 161: `investigationResult?.car_analytics` accessed |

---

### Requirements Coverage

| Requirement | Plans | Description | Status | Evidence |
|-------------|-------|-------------|--------|----------|
| P39-T01 | 39-01, 39-02 | Ingest CAR analytics catalog into new SQLite table | SATISFIED | car_analytics.json (158 entries), CARStore DDL, seed_car_analytics(), migration in sqlite_store.py |
| P39-T02 | 39-01, 39-02 | Map Sigma rule ATT&CK technique IDs to CAR analytic IDs at detection time | SATISFIED | get_analytics_for_technique() with sub-technique normalization; matcher.py CAR lookup in _sync_save(); all 8 unit tests pass |
| P39-T03 | 39-01, 39-03 | Enrich GET /api/detect response with matched CAR analytic | SATISFIED | detect.py json.loads car_analytics in _query(); car_analytics TEXT column on detections table |
| P39-T04 | 39-04 | Update DetectionsView to show CAR analytic panel when analytic is available | SATISFIED (automated) | expandedId $state, conditional CAR panel row, card layout, no-analytics message — HUMAN VERIFY for visual/interactive behavior |
| P39-T05 | 39-03, 39-04 | Add CAR analytic link to investigation evidence panel | SATISFIED (automated) | investigate.py top-level car_analytics key; InvestigationView CAR Analytics section — HUMAN VERIFY for visual rendering |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/api/investigate.py` | 102–112 | asyncio.to_thread(lambda: ...) captures `parent_id` from enclosing scope — valid but subtle closure | INFO | Works correctly here as `parent_id` is not reassigned; no functional issue |
| `backend/main.py` | 315 | Comment says "7d. Phase 39" but block appears after "7c. Phase 35" comment (ordering inconsistency) | INFO | Comment label only; code executes correctly |

No blocker or warning-level anti-patterns found in Phase 39 files. All implementations are substantive — no placeholders, empty returns, or TODO stubs.

---

### TypeScript Compile Status

`npm run check` reports 10 errors and 6 warnings across 6 files. **Zero errors exist in Phase 39 files** (api.ts, DetectionsView.svelte, InvestigationView.svelte). All 10 errors are in pre-existing files:
- `GraphView.svelte` — 8 errors (cytoscape-fcose/dagre missing @types, .hide/.show Cytoscape API, oncynodetap prop) — pre-Phase-15
- `InvestigationPanel.svelte` — 1 error (Cytoscape PropertyValue type) — pre-Phase-9
- `ProvenanceView.svelte` — 1 error (function union type mismatch) — pre-Phase-21

Phase 39 TypeScript is clean.

---

### Test Suite Status

Full unit suite: **1020 passed, 1 skipped, 9 xfailed, 7 xpassed** — no regressions introduced. The 8 new CARStore tests all pass GREEN.

---

### Human Verification Required

#### 1. DetectionsView — Expandable CAR analytic panel

**Test:** Open the dashboard DetectionsView. Click any detection row that has an ATT&CK technique value.
**Expected:** Row expands inline below with a CAR analytic panel. Cards show: monospace ID badge (e.g. CAR-2020-09-001), title, coverage level badge (colored amber/blue/green), description text, log sources, pseudocode block, and two links — "CAR ↗" and "ATT&CK ↗" that open correct URLs in new tabs.
**Why human:** Visual rendering and click interaction cannot be verified without a browser.

#### 2. DetectionsView — No-analytics message

**Test:** Click a detection row that has no attack_technique value.
**Expected:** Row expands but panel shows "No CAR analytics available for this detection." message instead of cards.
**Why human:** Requires live data filtering and UI interaction.

#### 3. DetectionsView — Toggle and single-expand behavior

**Test:** Click an expanded row again; then click a different row.
**Expected:** First click collapses the row. Second click collapses the previous row and expands only the new one (only one expanded at a time).
**Why human:** Stateful UI behavior requiring browser interaction.

#### 4. DetectionsView — Multiple CAR analytics for T1059

**Test:** If any detection fires for T1059 (Command and Scripting Interpreter), click that row.
**Expected:** Multiple CAR analytic cards stacked vertically — each with distinct analytic_id and content.
**Why human:** Depends on live detection data with T1059 technique.

#### 5. InvestigationView — CAR Analytics section

**Test:** Navigate to an investigation for a detection that has an ATT&CK technique. Scroll to the evidence panel.
**Expected:** "CAR Analytics" section heading appears with subtitle "MITRE Cyber Analytics Repository — validated detection guidance for [technique]". One or more CAR cards rendered with same card layout as DetectionsView.
**Why human:** Requires live backend, investigation flow, and visual rendering.

#### 6. End-to-end enrichment — run detection pipeline

**Test:** Ingest events that trigger a Sigma rule with an ATT&CK technique (e.g. T1059). Check `GET /api/detect` response JSON.
**Expected:** Each triggered detection object has `car_analytics` as a parsed list of dicts (not a raw JSON string, not null), with correct CAR analytic data for the technique.
**Why human:** Requires live event ingestion, Sigma matching, and CAR enrichment pipeline to complete.

---

## Gaps Summary

No gaps found. All automated must-haves verified across all 5 requirements (P39-T01 through P39-T05). The 7 human verification items are interactive/visual behaviors that require a running system — they are not evidence of implementation gaps but normal gate checks for UI-heavy deliverables.

The one notable observation: `car_analytics.json` has 158 entries (the plan required 90+) — this is because the actual CAR catalog has more entries than the minimum estimate, indicating a more complete bundle was successfully generated.

---

_Verified: 2026-04-11T18:30:00Z_
_Verifier: Claude (gsd-verifier)_
