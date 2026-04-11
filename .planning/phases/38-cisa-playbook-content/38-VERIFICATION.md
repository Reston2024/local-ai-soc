---
phase: 38-cisa-playbook-content
verified: 2026-04-11T00:00:00Z
status: human_needed
score: 8/8 must-haves verified
human_verification:
  - test: "Open https://localhost/playbooks and verify CISA playbooks show amber CISA badge on cards; custom playbooks show blue Custom badge"
    expected: "Amber badge (color #f59e0b) renders on the 4 CISA playbook cards; custom playbooks show blue badge"
    why_human: "Source badge CSS class is dynamically generated via source-{pb.source}; visual rendering cannot be verified programmatically"
  - test: "Start a run against a CISA playbook; on the first step verify ATT&CK technique chips appear (e.g. T1566.001); click a chip"
    expected: "Violet pill chips render; clicking opens https://attack.mitre.org/techniques/T1566/001 in a new tab"
    why_human: "New-tab navigation and chip rendering are UI behaviors that cannot be tested by grep"
  - test: "Navigate to a step with escalation_threshold (e.g. Phishing step 3, threshold=high); verify amber escalation banner appears with Acknowledge button; click Acknowledge"
    expected: "Banner renders with amber left border; Confirm/Skip buttons are disabled until acknowledged; after clicking Acknowledge, buttons enable"
    why_human: "DOM reactivity of acknowledgedSteps Set and button disabled state requires browser interaction"
  - test: "Acknowledge escalation with an active investigation ID set; inspect the run via curl -sk https://localhost/api/playbook-runs/{run_id} | grep active_case_id"
    expected: "active_case_id is set to the investigation ID in the DB response"
    why_human: "End-to-end PATCH flow requires a live backend with an active run"
  - test: "On a step with containment_actions, verify the dropdown appears at step completion with controlled-vocab options; select one and advance"
    expected: "Dropdown shows options like 'preserve evidence', 'block ip'; selection persists through advance; resets on next step"
    why_human: "Select dropdown rendering and selectedContainment state reset require browser interaction"
  - test: "Complete all steps of a playbook run; verify 'Generate Playbook Execution Log PDF?' prompt appears with Generate Report button"
    expected: "pdf-prompt div visible after run status becomes 'completed'"
    why_human: "Completion state requires a full playbook execution sequence"
  - test: "Open https://localhost/detections; expand a detection with attack_technique=T1566; verify 'Suggested: Phishing / BEC Response' CTA appears"
    expected: "CTA appears in the Actions column; clicking navigates to PlaybooksView"
    why_human: "Requires detections in DB with attack_technique set matching CISA trigger_conditions"
  - test: "Navigate from a detection suggestion to PlaybooksView; verify page scrolls to the matching step"
    expected: "PlaybooksView opens and scrolls to the step with attack_techniques containing the detection's T-number"
    why_human: "Deep-link scroll effect requires active run + scrollIntoView behavior in browser"
---

# Phase 38: CISA Playbook Content Verification Report

**Phase Goal:** Replace NIST starter playbooks with CISA-derived IR flows. Enrich PlaybookStep model with containment actions, escalation gates, ATT&CK technique mappings. Surface all new fields in PlaybooksView.
**Verified:** 2026-04-11
**Status:** human_needed — all automated checks passed; 8 UI behaviors require browser verification
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | PlaybookStep model has attack_techniques, escalation_threshold, escalation_role, time_sla_minutes, containment_actions | VERIFIED | backend/models/playbook.py lines 30-34; all 4 model tests pass |
| 2 | BUILTIN_PLAYBOOKS contains exactly 4 CISA playbooks replacing all NIST starters | VERIFIED | 4 entries: Phishing/BEC, Ransomware, Credential/Account Compromise, Malware/Intrusion; source='cisa', is_builtin=True on all |
| 3 | seed_builtin_playbooks() deletes NIST rows (source='nist') and inserts CISA rows (source='cisa') | VERIFIED | backend/api/playbooks.py lines 78-99; UPDATE+DELETE+INSERT strategy confirmed |
| 4 | playbooks table has a source column; playbook_runs has escalation_acknowledged and active_case_id columns | VERIFIED | backend/stores/sqlite_store.py lines 401-413; 3 idempotent ALTER TABLE migrations present |
| 5 | Every CISA step has ATT&CK technique IDs, SLA minutes, and controlled-vocab containment actions | VERIFIED | All 30 steps across 4 playbooks have non-empty attack_techniques, positive time_sla_minutes, valid containment_actions; confirmed by test_playbooks_cisa.py (6 tests pass) |
| 6 | PlaybooksView shows source badges, technique chips, escalation banner with acknowledge-gate, containment dropdown, deep-link, PDF prompt | VERIFIED (code) | All markup and handlers present in PlaybooksView.svelte (600 lines); NEEDS HUMAN for rendering |
| 7 | DetectionsView shows 'Suggested: [Playbook Name]' CTA for TTP-matching detections | VERIFIED (code) | suggestPlaybook(), availablePlaybooks, suggest-cta markup present in DetectionsView.svelte; NEEDS HUMAN for runtime |
| 8 | Acknowledging escalation with active investigation PATCHes the run to set active_case_id | VERIFIED (code) | handleAcknowledgeEscalation calls api.playbookRuns.patchRun(); backend PATCH /api/playbook-runs/{run_id} route exists; NEEDS HUMAN for E2E |

**Score:** 8/8 truths verified in code; 8 UI behaviors flagged for human verification

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/models/playbook.py` | Extended PlaybookStep and PlaybookRunAdvance | VERIFIED | 5 new Phase 38 fields on PlaybookStep; containment_action on PlaybookRunAdvance; active_case_id on PlaybookRun |
| `backend/data/builtin_playbooks.py` | 4 CISA IR playbooks with full step metadata | VERIFIED | 4 playbooks, 30 total steps, all with attack_techniques + time_sla_minutes + containment_actions |
| `backend/api/playbooks.py` | Updated seed function + PATCH route | VERIFIED | Replace-not-supplement seed strategy (lines 78-99); PlaybookRunPatch model + patch_playbook_run route (lines 333-369) |
| `backend/stores/sqlite_store.py` | 3 idempotent ALTER TABLE migrations | VERIFIED | Lines 401-413: source, escalation_acknowledged, active_case_id columns added with try/except pattern |
| `dashboard/src/lib/api.ts` | Extended PlaybookStep/Playbook/PlaybookRun interfaces + patchRun | VERIFIED | All 5 PlaybookStep fields (lines 134-138); source on Playbook (line 150); active_case_id on PlaybookRun (line 169); patchRun method (line 680) |
| `dashboard/src/views/PlaybooksView.svelte` | Source badges, technique chips, escalation banner, containment dropdown, deep-link, PDF prompt | VERIFIED (code) | 600 lines; all 10 Phase 38 features implemented; NEEDS HUMAN for visual/interactive verification |
| `dashboard/src/views/DetectionsView.svelte` | onSuggestPlaybook prop + suggest CTA | VERIFIED (code) | suggestPlaybook helper, availablePlaybooks state, suggest-cta markup confirmed |
| `dashboard/src/App.svelte` | playbookTriggerTechnique state, handleSuggestPlaybook handler, activeInvestigationId wiring | VERIFIED | Lines 55, 63-66, 311, 344-345 confirmed |
| `tests/unit/test_playbooks_model.py` | 4 passing tests for model fields | VERIFIED | 4/4 pass |
| `tests/unit/test_playbooks_seed.py` | 4 passing tests for CISA seeding | VERIFIED | 4/4 pass |
| `tests/unit/test_playbooks_cisa.py` | 6 passing tests for CISA content quality | VERIFIED | 6/6 pass |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/unit/test_playbooks_model.py` | `backend/models/playbook.py` | `from backend.models.playbook import` | WIRED | Import confirmed; all 4 tests pass |
| `tests/unit/test_playbooks_cisa.py` | `backend/data/builtin_playbooks.py` | `from backend.data.builtin_playbooks import` | WIRED | Import confirmed; all 6 content tests pass |
| `backend/api/playbooks.py` | `backend/stores/sqlite_store.py` | `UPDATE/DELETE WHERE source='nist'` | WIRED | Seed strategy uses store._conn.execute() directly; source column migration in sqlite_store ensures column exists |
| `backend/data/builtin_playbooks.py` | `backend/models/playbook.py` | Dict keys match PlaybookStep field names (attack_techniques present) | WIRED | All step dicts include attack_techniques key; PlaybookStep deserializes them correctly |
| `dashboard/src/App.svelte` | `dashboard/src/views/PlaybooksView.svelte` | `activeInvestigationId` prop passed from App.svelte | WIRED | Line 344: `activeInvestigationId={playbookInvestigationId}` |
| `dashboard/src/views/PlaybooksView.svelte` | `/api/playbook-runs/{runId}` | `api.playbookRuns.patchRun()` called on acknowledge | WIRED | handleAcknowledgeEscalation (line 114-123) calls patchRun when activeInvestigationId non-null |
| `dashboard/src/views/DetectionsView.svelte` | `dashboard/src/App.svelte` | `onSuggestPlaybook` callback | WIRED | App.svelte line 311 passes `onSuggestPlaybook={handleSuggestPlaybook}`; DetectionsView line 8 accepts it |
| `dashboard/src/views/PlaybooksView.svelte` | `attack.mitre.org` | Technique chip href | WIRED | Line 321: `href="https://attack.mitre.org/techniques/{tech.replace('.', '/')}"` |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| P38-T01 | 38-01, 38-02 | Ingest and parse CISA Federal IR Playbook response phases (phishing, malware, ransomware, credential abuse) | SATISFIED | BUILTIN_PLAYBOOKS contains 4 CISA playbooks covering all 4 incident classes; 30 steps with professional IR procedure text |
| P38-T02 | 38-01, 38-02, 38-03 | Map each CISA playbook step to ATT&CK technique IDs where applicable | SATISFIED | All 30 steps have non-empty attack_techniques; T-number format validated by test_technique_ids; technique chips in PlaybooksView link to MITRE |
| P38-T03 | 38-01, 38-02, 38-03 | Add escalation logic to playbook steps (severity thresholds to escalate vs contain) | SATISFIED | escalation_threshold Literal["critical","high"] on PlaybookStep; SEVERITY_RANK dict in PlaybooksView; escalation banner blocks step advance until acknowledged |
| P38-T04 | 38-01, 38-02, 38-03 | Add containment action fields to PlaybookStep model | SATISFIED | containment_actions: list[str] on PlaybookStep; controlled vocab enforced in test_containment_actions_vocab; dropdown rendered in PlaybooksView |
| P38-T05 | 38-01, 38-02 | Seed new CISA-derived playbooks into SQLite on startup (replace NIST starters) | SATISFIED | seed_builtin_playbooks() implements UPDATE source='nist' + DELETE + INSERT CISA strategy; idempotent; SQLite migrations add source column |
| P38-T06 | 38-03 | Update PlaybooksView to show ATT&CK technique badges per step and containment action labels | SATISFIED (code) | technique-chip elements per step (violet pill, clickable MITRE link); containment-section dropdown per step; NEEDS HUMAN for visual confirmation |

Note: P38-T01 through P38-T06 are defined only in ROADMAP.md (Phase 38 section). REQUIREMENTS.md only covers Phases 1-19; Phases 20-40 requirements live in ROADMAP.md. No orphaned requirements.

---

## Anti-Patterns Found

No TODOs, FIXMEs, placeholders, or empty implementations found in any Phase 38 modified files.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | — | — | — |

**TypeScript check:** 10 pre-existing errors in GraphView.svelte, InvestigationPanel.svelte, ProvenanceView.svelte — none introduced by Phase 38. Zero new errors from Phase 38 changes. This is consistent with what the 38-03-SUMMARY.md documents.

---

## Human Verification Required

### 1. CISA Source Badge Rendering

**Test:** Open https://localhost/playbooks — verify the 4 CISA playbook cards each show an amber "CISA" badge. Create or identify a custom playbook and verify it shows a blue "Custom" badge.
**Expected:** Amber badge (rgba(245,158,11,0.15) background, #f59e0b text) on CISA playbooks; blue badge on custom playbooks.
**Why human:** Dynamic class binding `source-{pb.source ?? 'custom'}` renders CSS at runtime; visual appearance cannot be verified programmatically.

### 2. ATT&CK Technique Chips and MITRE Navigation

**Test:** Start a run on a CISA playbook. On step 1, verify violet pill chip(s) render (e.g. "T1566.001"). Click one.
**Expected:** Chip renders with violet pill styling; clicking opens `https://attack.mitre.org/techniques/T1566/001` in a new browser tab (dot replaced with slash).
**Why human:** New-tab navigation and chip click behavior require browser interaction.

### 3. Escalation Banner Gate

**Test:** In a Phishing/BEC run, advance to step 3 (escalation_threshold="high"). Verify amber escalation banner appears inline. Confirm/Skip buttons should be disabled. Click Acknowledge.
**Expected:** Banner with amber left border renders; buttons disabled before acknowledgment; after clicking Acknowledge, buttons become enabled.
**Why human:** DOM reactivity of the acknowledgedSteps Set and button disabled state require browser observation.

### 4. Escalation PATCH to active_case_id

**Test:** With an active investigation ID flowing through App.svelte (navigate from an investigation to a playbook run), acknowledge an escalation step. Then: `curl -sk https://localhost/api/playbook-runs/{run_id} | python -m json.tool | grep active_case_id`
**Expected:** `active_case_id` is set to the investigation ID (not null).
**Why human:** Requires a live backend with an active run and investigationId state in App.svelte.

### 5. Containment Action Dropdown

**Test:** On any current step with containment_actions set, verify a "Containment action taken:" dropdown appears with the step's controlled-vocab options. Select one and advance the step. Move to the next step and verify the dropdown resets.
**Expected:** Options like "preserve evidence", "block ip" visible; selection passes through to advance call; selectedContainment resets to '' on step change.
**Why human:** Select element binding and reset behavior require browser interaction.

### 6. PDF Prompt on Run Completion

**Test:** Complete all steps of a playbook run. Verify a "Generate Playbook Execution Log PDF?" prompt appears with a "Generate Report" button.
**Expected:** pdf-prompt div visible; clicking Generate Report fires onGenerateReport callback.
**Why human:** Requires completing a full playbook run sequence to trigger status='completed'.

### 7. Suggested Playbook CTA in DetectionsView

**Test:** Open https://localhost/detections. Expand a detection where attack_technique matches a CISA playbook trigger_condition (e.g. attack_technique="T1566"). Verify "Suggested: Phishing / BEC Response" appears.
**Expected:** CTA rendered in Actions column with playbook name as a blue underlined link.
**Why human:** Requires detections in the DB with relevant attack_technique values.

### 8. Detection-to-Playbook Deep-Link Scroll

**Test:** Click a Suggested playbook CTA in DetectionsView. Verify navigation to PlaybooksView and scroll to the step matching the detection's T-number.
**Expected:** PlaybooksView opens; if a run is active and activePlaybook is set, the view scrolls to the matching step (element with id="step-N").
**Why human:** scrollIntoView() behavior and active run state require browser observation.

---

## Gaps Summary

No blocking gaps. All automated checks pass:
- 14/14 Phase 38 unit tests pass (test_playbooks_model.py, test_playbooks_seed.py, test_playbooks_cisa.py)
- Full unit suite: 1012 passed, 1 skipped, 9 xfailed, 7 xpassed
- All 6 requirement IDs (P38-T01 through P38-T06) satisfied in code
- All key links wired
- Zero new TypeScript errors introduced

Phase goal is structurally achieved: CISA playbooks replace NIST starters, PlaybookStep is enriched with all required fields, and PlaybooksView surfaces them. The 8 human verification items are UI rendering and interaction checks that cannot be resolved by static analysis.

---

_Verified: 2026-04-11_
_Verifier: Claude (gsd-verifier)_
