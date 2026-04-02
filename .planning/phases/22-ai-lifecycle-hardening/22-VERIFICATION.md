---
phase: 22-ai-lifecycle-hardening
verified: 2026-04-02T17:30:00Z
status: gaps_found
score: 3/5 must-haves fully verified
re_verification: false
gaps:
  - truth: "GET /api/copilot/response/{audit_id} returns response + cited sources (P22-T01)"
    status: failed
    reason: "Endpoint does not exist. /api/provenance/llm/{audit_id} returns provenance metadata only (model_id, template SHA, grounding_event_ids list) — it does not return the response text plus cited source details as the ROADMAP requirement specifies."
    artifacts:
      - path: "backend/api/provenance.py"
        issue: "Provides /api/provenance/llm/{audit_id} but returns LlmProvenanceRecord (model/template metadata) — missing response text and cited-source enrichment"
    missing:
      - "Either a dedicated GET /api/copilot/response/{audit_id} endpoint returning response_text + grounding_event_ids enriched with source details, OR an explicit plan decision to accept /api/provenance/llm/{audit_id} as a deliberate scope substitution for this sub-requirement"

  - truth: "UI displays citations inline with response text; ungrounded responses flagged with visual warning (P22-T01)"
    status: failed
    reason: "InvestigationView copilot panel renders the AI Advisory banner and confidence badge, but grounding_event_ids are not displayed inline alongside the response text. There is no visual warning state for is_grounded=false."
    artifacts:
      - path: "dashboard/src/views/InvestigationView.svelte"
        issue: "msg.grounding_event_ids field is available (added to ChatHistoryMessage in 22-02) but never rendered. No conditional block checks is_grounded or msg.grounding_event_ids to show an 'ungrounded' warning."
      - path: "dashboard/src/lib/api.ts"
        issue: "ChatHistoryMessage has grounding_event_ids?: string[] field declared but it is unused in the view"
    missing:
      - "Render grounding_event_ids as inline citation tags below assistant message content (e.g. 'Sources: [evt-001] [evt-002]')"
      - "Add a visual warning badge/state when is_grounded is false or grounding_event_ids is empty"

  - truth: "Model drift detected on each LLM call (P22-T04 ROADMAP: 'on each LLM call, compare the active model_id')"
    status: failed
    reason: "Drift detection only runs when the analyst explicitly visits Settings → System tab and the /api/settings/model-status endpoint is called. It is not wired to the generate()/stream_generate() path. The ROADMAP requirement says drift should be detected 'on each LLM call'."
    artifacts:
      - path: "backend/services/ollama_client.py"
        issue: "generate() and stream_generate() do not call list_models() or check/update last_known_model — drift detection is absent from the hot path"
      - path: "backend/api/query.py"
        issue: "ask() and ask_stream() do not call get_kv/set_kv for model tracking"
    missing:
      - "Either wire drift check into generate()/stream_generate() or ask()/ask_stream() (checking Ollama model and comparing to stored last_known_model with a WARNING log on mismatch), OR explicitly scope-limit P22-T04 to manual-check-only via a plan decision record"

human_verification:
  - test: "Confirm advisory banner has no dismiss button in running UI"
    expected: "No X button, close button, or onclick handler on .ai-advisory-banner in InvestigationView"
    why_human: "Code inspection confirms no onclick/dismiss in Svelte template, but live DOM verification confirms browser rendering matches source"
  - test: "Confirm SettingsView System tab loads model-status card on tab activation"
    expected: "Navigating to Settings → System tab triggers API call and renders 'AI Model Status' card content (not placeholder text)"
    why_human: "Requires running frontend and backend — cannot verify $effect tab-switch trigger programmatically"
  - test: "Confirm confidence badge colour thresholds in live UI"
    expected: "Green badge for responses with 5+ grounded events and verified citations; amber for 1-4 events; red for zero context"
    why_human: "Colour threshold logic is in Svelte confidenceLevel() function — rendering is a visual check"
---

# Phase 22: AI Lifecycle Hardening — Verification Report

**Phase Goal:** Harden the AI Copilot to NIST AI RMF standards — response grounding, confidence scoring, eval harness, model drift detection, advisory separation.
**Verified:** 2026-04-02T17:30:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /api/query/ask returns audit_id, grounding_event_ids, is_grounded in JSON | VERIFIED | query.py lines 278-280; test_grounding.py 3 passing tests |
| 2 | GET /api/copilot/response/{audit_id} returns response + cited sources | FAILED | Endpoint does not exist; /api/provenance/llm/{audit_id} exists but returns metadata only, not response text |
| 3 | UI displays citations inline and flags ungrounded responses visually | FAILED | grounding_event_ids unused in InvestigationView.svelte; no is_grounded=false visual state |
| 4 | Confidence score 0.0-1.0 computed, stored, displayed as badge | VERIFIED | sqlite_store.py DDL+method; query.py heuristic; InvestigationView badge; 4 passing tests |
| 5 | Eval harness: 6 prompt-template tests pass with mock LLM, no Ollama needed | VERIFIED | tests/eval/test_analyst_qa_eval.py (2), test_triage_eval.py (2), test_threat_hunt_eval.py (2) |
| 6 | Model drift detected on each LLM call with WARNING log | FAILED | Drift detection only runs at GET /api/settings/model-status — not wired to generate() hot path |
| 7 | GET /api/settings/model-status returns active_model, drift_detected, last_change | VERIFIED | backend/api/settings.py; main.py registration; 3 test_model_drift.py tests pass |
| 8 | analyst_qa.SYSTEM and triage.SYSTEM start with [AI Advisory — not a verified fact] | VERIFIED | prompts/analyst_qa.py line 10; prompts/triage.py line 10; test_advisory.py 2 passing tests |
| 9 | InvestigationView shows non-dismissable AI Advisory banner on every assistant message | VERIFIED | InvestigationView.svelte lines 161-174; no onclick/dismiss on banner; CSS comment confirms intent |
| 10 | SettingsView system tab renders model-status card replacing placeholder text | VERIFIED | SettingsView.svelte lines 132-149, 273-305; $effect wired to loadModelStatus() |

**Score:** 6/10 observable truths verified (3 failed, 1 human-needed)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/eval/__init__.py` | Package marker | VERIFIED | Exists |
| `tests/eval/conftest.py` | mock_ollama fixture + load_event_fixtures() | VERIFIED | Substantive; OllamaClient import; AsyncMock pattern |
| `tests/eval/fixtures/analyst_qa_events.ndjson` | 2+ events with event_id | VERIFIED | 3 events (evt-001, evt-002, evt-003) |
| `tests/eval/fixtures/triage_events_a.ndjson` | 2+ events | VERIFIED | 2 sysmon events |
| `tests/eval/fixtures/triage_events_b.ndjson` | 2+ events | VERIFIED | 2 events |
| `tests/eval/fixtures/threat_hunt_events_a.ndjson` | 2+ events | VERIFIED | 2 events |
| `tests/eval/fixtures/threat_hunt_events_b.ndjson` | 2+ events | VERIFIED | 2 events |
| `tests/eval/test_grounding.py` | 3 passing tests, no skip decorators | VERIFIED | 3 active tests; _build_client helper; TestClient pattern |
| `tests/eval/test_confidence.py` | 4 passing tests | VERIFIED | 4 active tests; heuristic helper function |
| `tests/eval/test_analyst_qa_eval.py` | 2 passing tests | VERIFIED | 2 active tests using load_event_fixtures + patch.object |
| `tests/eval/test_triage_eval.py` | 2 passing tests | VERIFIED | 2 active tests |
| `tests/eval/test_threat_hunt_eval.py` | 2 passing tests | VERIFIED | 2 active tests |
| `tests/eval/test_model_drift.py` | 3 passing tests | VERIFIED | 3 active tests; test_status_endpoint checks route registration |
| `tests/eval/test_advisory.py` | 2 passing tests | VERIFIED | 2 active tests asserting SYSTEM.startswith("[AI Advisory") |
| `backend/services/ollama_client.py` | out_context param in generate() and stream_generate() | VERIFIED | Lines 312-313, 468-469; populates audit_id + grounding_event_ids |
| `backend/api/query.py` | audit_id/grounding_event_ids/is_grounded + confidence_score in ask() | VERIFIED | Lines 278-281; confidence_score heuristic at line 249 |
| `backend/stores/sqlite_store.py` | confidence_score in DDL + ALTER TABLE + update_confidence_score(); system_kv + model_change_events DDL + 4 methods | VERIFIED | Line 237 (DDL); line 315 (migration); line 1379 (method); lines 254-267 (tables); lines 1454-1489 (methods) |
| `backend/api/settings.py` | GET /settings/model-status with require_role + drift detection | VERIFIED | File exists; router prefix /settings; endpoint wired to stores.sqlite.get_model_status |
| `backend/main.py` | settings_router registered at /api prefix | VERIFIED | Lines 456-457; include_router with Depends(verify_token) |
| `dashboard/src/lib/api.ts` | ChatHistoryMessage with confidence?, audit_id?, grounding_event_ids?; ModelStatus interface; api.settings.modelStatus() | VERIFIED | Lines 112-120 (ChatHistoryMessage); lines 253-265 (ModelStatus); line 591-592 (modelStatus method) |
| `dashboard/src/views/InvestigationView.svelte` | ai-advisory-banner, confidence badge, ai-content style (non-dismissable) | VERIFIED | Lines 161-188 (banner + badge); line 263 CSS comment; no dismiss button present |
| `dashboard/src/views/SettingsView.svelte` | model-status card replacing placeholder; $effect auto-load | VERIFIED | Lines 132-149 ($state + $effect); lines 273-305 (card markup) |
| `prompts/analyst_qa.py` | SYSTEM starts with [AI Advisory — not a verified fact] | VERIFIED | Line 10 confirmed via grep |
| `prompts/triage.py` | SYSTEM starts with [AI Advisory — not a verified fact] | VERIFIED | Line 10 confirmed via grep |

**All skip decorators removed:** `grep -r "pytest.mark.skip" tests/eval/` returns no matches. All 18 original stubs are now active tests.

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| backend/api/query.py ask() | backend/services/ollama_client.py generate() | out_ctx dict passed as out_context kwarg | WIRED | query.py line 220; ollama_client.py writes audit_id to dict at line 408-410 |
| backend/api/query.py ask() | backend/stores/sqlite_store.py update_confidence_score() | asyncio.to_thread() after out_ctx populated | WIRED | query.py lines 252-258 |
| backend/api/settings.py get_model_status() | backend/stores/sqlite_store.py get_model_status() | asyncio.to_thread() | WIRED | settings.py line 232 |
| dashboard/src/views/SettingsView.svelte | dashboard/src/lib/api.ts api.settings.modelStatus() | $effect on tab activation | WIRED | SettingsView.svelte line 145 |
| dashboard/src/views/InvestigationView.svelte | dashboard/src/lib/api.ts ChatHistoryMessage | msg.confidence field typed access in confidenceLevel() | WIRED | InvestigationView.svelte line 164 |
| dashboard/src/views/InvestigationView.svelte | dashboard/src/lib/api.ts ChatHistoryMessage.grounding_event_ids | Inline citation rendering | NOT WIRED | grounding_event_ids field declared in api.ts but never read or rendered in InvestigationView |
| backend/api/query.py generate() hot path | model drift check (list_models + last_known_model compare) | Should trigger on each LLM call | NOT WIRED | Drift detection only in settings.py GET handler; ollama_client.py generate() has no drift check |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| P22-T01 | 22-01-PLAN.md | Response grounding enforcement | PARTIAL | audit_id/grounding_event_ids/is_grounded in API response — VERIFIED. GET /api/copilot/response/{audit_id} — MISSING. Inline UI citations and ungrounded visual warning — MISSING. |
| P22-T02 | 22-02-PLAN.md | Confidence scoring | PARTIAL | Heuristic scoring (grounding + citation_ok + count) stored and returned — VERIFIED. ROADMAP also requires "response length vs context size" and "hedging language patterns" in heuristic — simplified in implementation. Core badge display — VERIFIED. |
| P22-T03 | 22-03-PLAN.md | Evaluation harness | SATISFIED | 6 passing eval tests across analyst_qa, triage, threat_hunt; mock LLM; 5 NDJSON fixture files; runnable with `uv run pytest tests/eval/` |
| P22-T04 | 22-04-PLAN.md | Model drift detection | PARTIAL | SQLite tables + methods + endpoint + SettingsView card — VERIFIED. ROADMAP requires "on each LLM call" detection with WARNING log — NOT wired to generate() hot path. |
| P22-T05 | 22-05-PLAN.md | Advisory separation | SATISFIED | SYSTEM prefixes updated; non-dismissable banner; confidence badge; italic ai-content style; no dismiss controls |

**Requirements in REQUIREMENTS.md:** P22-T01 through P22-T05 are NOT present in `.planning/REQUIREMENTS.md` (file ends at Phase 19). These requirements exist only in ROADMAP.md and PLAN frontmatter. This is an ORPHANED requirement set — REQUIREMENTS.md must be updated to include Phase 22 entries for completeness.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `dashboard/src/views/InvestigationView.svelte` | 119-120 | `grounding_event_ids?: string[]` declared in ChatHistoryMessage but never rendered in view | Warning | grounding_event_ids is received from API but silently dropped — P22-T01 citation display requirement unmet |
| `tests/eval/test_model_drift.py` | 35-46 | `test_status_endpoint` verifies route registration only (not HTTP behaviour); does not test drift logic, KV store interaction, or response shape | Info | Test passes but provides minimal coverage for the endpoint's business logic |

### Human Verification Required

**1. AI Advisory banner non-dismissable in browser**
- **Test:** Start `uv run uvicorn backend.main:app --reload` and `npm run dev --prefix dashboard`, navigate to an Investigation, send a question to AI Copilot
- **Expected:** Yellow amber-bordered banner with "AI Advisory" label appears above response; no X/close button; clicking anywhere on the banner does nothing
- **Why human:** Svelte reactive DOM rendering and event propagation cannot be verified by static code inspection

**2. Confidence badge colour thresholds**
- **Test:** Observe badge colour on a response with no RAG context (red expected) vs. one with several retrieved events (amber or green expected)
- **Expected:** Red badge for ungrounded responses; green for highly-grounded responses with verified citations
- **Why human:** CSS class rendering and colour output require visual browser confirmation

**3. SettingsView System tab model-status card on live backend**
- **Test:** Navigate Settings → System tab with backend running (Ollama reachable or unreachable)
- **Expected:** "AI Model Status" card shown with active model or "Unknown (Ollama unreachable)" — NOT the old placeholder paragraph
- **Why human:** The $effect + $state interaction for tab-activation lazy loading requires a running Svelte app

### Gaps Summary

Three requirement areas have gaps between what ROADMAP specifies and what was implemented:

**P22-T01 (Response Grounding) — 2 sub-requirements unimplemented:**
The PLANs scoped P22-T01 to threading `audit_id`/`grounding_event_ids`/`is_grounded` into API responses — this was delivered. However, the ROADMAP additionally requires (1) a dedicated `GET /api/copilot/response/{audit_id}` endpoint returning response text plus cited sources, and (2) the UI rendering grounding_event_ids inline with response text with a visual warning when `is_grounded=false`. The `grounding_event_ids` field exists in `ChatHistoryMessage` but is never rendered in `InvestigationView.svelte`. No ungrounded warning state exists in the UI.

**P22-T04 (Model Drift Detection) — scope mismatch:**
The ROADMAP requires drift detection "on each LLM call" with a structured WARNING log. The implementation only checks drift when the analyst manually visits the Settings → System tab. The drift audit trail (model_change_events table, set_kv update) only executes on explicit `GET /api/settings/model-status` calls, not during normal LLM generation.

**REQUIREMENTS.md Orphan:**
Phase 22 requirements are absent from `.planning/REQUIREMENTS.md` (the file ends at Phase 19). The requirement IDs P22-T01 through P22-T05 exist in ROADMAP.md but are not cross-referenced from REQUIREMENTS.md. This administrative gap means the requirements file does not reflect the full scope of the delivered system.

The core AI lifecycle hardening infrastructure (eval harness, confidence scoring storage, advisory framing, settings endpoint) is substantively implemented. The gaps are in two specific behavioural contracts: inline citation display and per-call drift monitoring.

---
_Verified: 2026-04-02T17:30:00Z_
_Verifier: Claude (gsd-verifier)_
