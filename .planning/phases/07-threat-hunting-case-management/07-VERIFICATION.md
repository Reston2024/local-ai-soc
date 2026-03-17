---
phase: 07-threat-hunting-case-management
verified: 2026-03-17T02:52:06Z
status: passed
score: 16/16 must-haves verified
re_verification: false
---

# Phase 7: Threat Hunting & Case Management — Verification Report

**Phase Goal:** Full investigation workflow layer — structured cases, threat hunting queries, timeline reconstruction, and forensic artifact storage. Enables analysts to move from individual alerts to full investigations by supporting threat hunting, case tracking, timeline reconstruction, and forensic artifact collection.

**Verified:** 2026-03-17T02:52:06Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | CaseManager CRUD operations create, list, update investigation cases | VERIFIED | `case_manager.py` — full implementation with sqlite3.Connection delegation; 3 unit tests XPASS (P7-T01/T02/T03) |
| 2  | POST /api/cases returns 200 with case_id | VERIFIED | Route defined in `investigation_routes.py:84`; P7-T04 XPASS |
| 3  | GET /api/cases returns paginated cases list | VERIFIED | Route defined at line 108; P7-T05 XPASS |
| 4  | GET /api/cases/{case_id} returns case with case_status field | VERIFIED | Route at line 128; P7-T06 XPASS |
| 5  | PATCH /api/cases/{case_id} persists partial updates | VERIFIED | Route at line 144; P7-T07 XPASS |
| 6  | HUNT_TEMPLATES contains exactly 4 named templates | VERIFIED | `hunt_engine.py` defines 4 entries: suspicious_ip_comms, powershell_children, unusual_auth, ioc_search; P7-T08/T09 XPASS |
| 7  | GET /api/hunt/templates returns templates list | VERIFIED | Route at line 237; P7-T10 XPASS |
| 8  | POST /api/hunt executes hunt query and returns results | VERIFIED | Route at line 250; graceful empty-results fallback when DuckDB unavailable; P7-T11 XPASS |
| 9  | build_timeline returns list of dicts with 5 required keys (timestamp, event_source, entity_references, related_alerts, confidence_score) | VERIFIED | `timeline_builder.py` — full implementation with confidence scoring; P7-T12 XPASS |
| 10 | GET /api/cases/{case_id}/timeline returns ordered timeline | VERIFIED | Route at line 165; P7-T13 XPASS |
| 11 | save_artifact writes bytes to filesystem and stores metadata in SQLite | VERIFIED | `artifact_store.py` — asyncio.to_thread + pathlib write + sqlite_store.insert_artifact call; P7-T14 XPASS |
| 12 | POST /api/cases/{case_id}/artifacts returns artifact_id | VERIFIED | Route at line 184; P7-T15 XPASS |
| 13 | investigation_router mounted in main.py via deferred import guard | VERIFIED | `backend/main.py:231-236` — try/except ImportError pattern identical to causality_router mount |
| 14 | api.ts exports 8 Phase 7 functions and 7 TypeScript interfaces | VERIFIED | Functions getCases, createCase, getCase, patchCase, getCaseTimeline, uploadArtifact, getHuntTemplates, executeHunt confirmed at lines 297-370; interfaces CaseItem, TimelineEntry, CaseTimeline, HuntTemplate, HuntResult, HuntResponse, ArtifactUploadResponse at lines 245-295 |
| 15 | CasePanel.svelte and HuntPanel.svelte use Svelte 5 runes only | VERIFIED | Both components use $state, $derived, $effect exclusively; no writable() or svelte/store imports present |
| 16 | npm run build exits 0 | VERIFIED | Build confirmed: "built in 1.25s" with exit 0 (P7-T16 XFAIL is a Windows PATH/subprocess issue in pytest, not a build failure) |

**Score:** 16/16 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/investigation/__init__.py` | Package marker | VERIFIED | File exists; package imports cleanly |
| `backend/investigation/case_manager.py` | Full CaseManager CRUD | VERIFIED | 129 lines; CaseManager class with 4 methods — no NotImplementedError; delegates to raw sqlite3.Connection |
| `backend/investigation/hunt_engine.py` | HUNT_TEMPLATES (4 entries) + execute_hunt | VERIFIED | 99 lines; HuntTemplate dataclass, 4 templates, async execute_hunt with param mapping |
| `backend/investigation/timeline_builder.py` | build_timeline async function | VERIFIED | 97 lines; full confidence scoring, entity reference extraction, DuckDB query |
| `backend/investigation/artifact_store.py` | save_artifact + get_artifact | VERIFIED | 76 lines; filesystem write + SQLite insert; posix paths; graceful None handling |
| `backend/investigation/tagging.py` | add_tag, remove_tag, list_tags, add_tags_to_case | VERIFIED | 50 lines; full implementation with INSERT OR IGNORE idempotency |
| `backend/investigation/investigation_routes.py` | 8 API endpoints on investigation_router | VERIFIED | 275 lines; 8 routes confirmed (`len(investigation_router.routes)` = 8); module-level fallback SQLiteStore for test environments |
| `backend/stores/sqlite_store.py` | DDL with investigation_cases, case_artifacts, case_tags + 6 methods | VERIFIED | investigation_cases DDL at line 86; case_artifacts at 101; case_tags at 113; 6 CRUD methods present (lines 520-617) |
| `backend/main.py` | Deferred import + include_router for investigation_router | VERIFIED | Lines 231-236; try/except ImportError guard with log.info on success |
| `frontend/src/lib/api.ts` | 8 Phase 7 functions + 7 interfaces | VERIFIED | Phase 7 section appended after Phase 6; all 8 functions and 7 interfaces present |
| `frontend/src/components/panels/CasePanel.svelte` | Case list + create + detail + timeline (Svelte 5) | VERIFIED | Runes-only: $state, $derived, $effect; getCases, createCase, getCase, patchCase, getCaseTimeline imported |
| `frontend/src/components/panels/HuntPanel.svelte` | Template selector + results + pivot-to-case (Svelte 5) | VERIFIED | Runes-only; getHuntTemplates, executeHunt, createCase imported; pivot-to-case button implemented |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `test_phase7.py` | `case_manager.py` | deferred import inside test methods | VERIFIED | `from backend.investigation.case_manager import CaseManager` present in test methods |
| `sqlite_store.py` | investigation_cases table | `_DDL` string extension | VERIFIED | DDL at lines 86-124; CREATE TABLE IF NOT EXISTS investigation_cases confirmed |
| `case_manager.py` | `sqlite_store.py` | CaseManager delegates via sqlite3.Connection | VERIFIED | Direct sqlite3 connection operations; pattern diverges from plan (direct conn vs SQLiteStore instance) but is functionally equivalent and tested |
| `tagging.py` | case_tags table | INSERT OR IGNORE on conn | VERIFIED | Line 22: `INSERT OR IGNORE INTO case_tags` |
| `hunt_engine.py` | `duckdb_store.py` | `duckdb_store.fetch_df(sql, param_list)` | VERIFIED | Line 98: `return await duckdb_store.fetch_df(tmpl.sql, param_list)` |
| `timeline_builder.py` | `duckdb_store.py` | `duckdb_store.fetch_df('SELECT * FROM normalized_events WHERE case_id = ?', ...)` | VERIFIED | Lines 78-81: fetch_df call with normalized_events query |
| `artifact_store.py` | `sqlite_store.py` | `asyncio.to_thread(sqlite_store.insert_artifact, ...)` | VERIFIED | Lines 43-52: asyncio.to_thread wrapping insert_artifact call |
| `investigation_routes.py` | `sqlite_store.py` | `request.app.state.stores.sqlite` with fallback | VERIFIED | `_get_stores()` function at line 48; fallback to in-memory SQLiteStore for tests |
| `investigation_routes.py` | `hunt_engine.py` | `execute_hunt(duckdb, body.template, body.params)` | VERIFIED | Line 264: `results = await execute_hunt(duckdb, body.template, body.params)` |
| `investigation_routes.py` | `timeline_builder.py` | `build_timeline(case_id, duckdb, sqlite)` | VERIFIED | Line 176: `timeline = await build_timeline(case_id, duckdb, sqlite)` |
| `investigation_routes.py` | `artifact_store.py` | `save_artifact(data_dir, case_id, ...)` | VERIFIED | Line 209: `result = await save_artifact(...)` |
| `main.py` | `investigation_routes.py` | try/except ImportError deferred mount | VERIFIED | Lines 231-236: `from backend.investigation.investigation_routes import investigation_router; app.include_router(investigation_router)` |
| `CasePanel.svelte` | `api.ts` | `import { getCases, createCase, ... } from '$lib/api'` | VERIFIED | Line 2 of CasePanel.svelte |
| `HuntPanel.svelte` | `api.ts` | `import { getHuntTemplates, executeHunt, createCase } from '$lib/api'` | VERIFIED | Line 2 of HuntPanel.svelte |

---

## Requirements Coverage

Phase 7 requirement IDs (P7-T01 through P7-T16) are internal plan-tracking identifiers tied to xfail test stubs in `test_phase7.py`. These IDs do not appear in `REQUIREMENTS.md` (which formally covers Phases 1-6 only; Phase 7 was added post-approval). The requirement contract for Phase 7 is captured in the ROADMAP.md Definition of Done and plan frontmatter.

| Requirement ID | Description | Test | Status |
|----------------|-------------|------|--------|
| P7-T01 | CaseManager.create_investigation_case returns UUID string | TestCaseManager::test_create_case_returns_id | XPASS |
| P7-T02 | CaseManager.list_investigation_cases returns [] on empty DB | TestCaseManager::test_list_cases_empty | XPASS |
| P7-T03 | CaseManager.update_investigation_case persists status change | TestCaseManager::test_update_case_status | XPASS |
| P7-T04 | POST /api/cases returns 200 with case_id | TestCaseAPI::test_create_case_endpoint | XPASS |
| P7-T05 | GET /api/cases returns 200 | TestCaseAPI::test_list_cases_endpoint | XPASS |
| P7-T06 | GET /api/cases/{id} returns 200 with case_status | TestCaseAPI::test_get_case_detail | XPASS |
| P7-T07 | PATCH /api/cases/{id} returns 200 after update | TestCaseAPI::test_patch_case_status | XPASS |
| P7-T08 | suspicious_ip_comms template has dst_ip param_key | TestHuntEngine::test_suspicious_ip_template | XPASS |
| P7-T09 | powershell_children template SQL contains parent_process_name ILIKE | TestHuntEngine::test_powershell_children_template | XPASS |
| P7-T10 | GET /api/hunt/templates returns 4 templates | TestHuntAPI::test_list_hunt_templates | XPASS |
| P7-T11 | POST /api/hunt returns 200 with results | TestHuntAPI::test_execute_hunt | XPASS |
| P7-T12 | build_timeline is callable and returns list with correct shape | TestTimelineBuilder::test_timeline_entry_shape | XPASS |
| P7-T13 | GET /api/cases/{id}/timeline returns 200 with timeline | TestTimelineAPI::test_get_timeline | XPASS |
| P7-T14 | save_artifact writes file and returns dict with artifact_id | TestArtifactStore::test_save_artifact | XPASS |
| P7-T15 | POST /api/cases/{id}/artifacts returns 200 with artifact_id | TestArtifactAPI::test_upload_artifact | XPASS |
| P7-T16 | npm run build exits 0 | test_dashboard_build | XFAIL (Windows PATH issue in pytest subprocess; manual build verified as exit 0) |

**Note on P7-T16:** The test is marked XFAIL (strict=False) because `npm` is not on PATH in the `uv run pytest` subprocess environment on Windows. This is a test environment limitation, not a code defect. The frontend build was verified to exit 0 manually (1.25s build time). The test's `strict=False` means XFAIL is an acceptable outcome.

**Note on REQUIREMENTS.md orphans:** No P7-T## IDs appear in REQUIREMENTS.md (Phase 7 was added after the requirements document was approved). FR-5.8 (Case/Session Management, line 361) references case management concepts that Phase 7 implements, though it is formally attributed to Phase 5.

---

## Anti-Patterns Found

No blockers or warnings found.

| File | Pattern | Severity | Notes |
|------|---------|----------|-------|
| All investigation modules | No TODO, FIXME, PLACEHOLDER, or NotImplementedError present | Info | All stubs from Plan 00 were replaced with full implementations |
| `investigation_routes.py` | Module-level fallback SQLiteStore (`_fallback_sqlite`) | Info | Acceptable test-environment pattern; does not affect production behavior |
| `artifact_store.py` | `get_artifact` fetches empty string case_id then does direct `_conn` lookup | Info | Minor inefficiency; functionally correct; not a stub |

---

## Regression Check

Full backend test suite result: `41 passed, 2 xfailed, 57 xpassed` — no regressions from Phases 1-6.

The 2 xfailed tests are:
- `test_phase6.py::TestDashboardBuild::test_npm_build_exits_zero` (pre-existing Windows PATH issue)
- `test_phase7.py::test_dashboard_build` (same Windows PATH issue, new Phase 7 test)

Both use `strict=False` and represent the same root cause: npm unavailable in pytest subprocess on Windows.

---

## Human Verification Required

### 1. Case Management UI — End-to-End Workflow

**Test:** Open the dashboard, navigate to CasePanel. Create a new case. Select it, verify timeline and detail sections render. Close the case.
**Expected:** Case appears in list with status dot; detail pane shows case fields; timeline shows empty state; close button updates status to closed.
**Why human:** Component rendering and interactive event handling cannot be verified programmatically without a browser.

### 2. Hunt Query Pivot to Case

**Test:** Open HuntPanel. Select "powershell_children" template. Click "Run Hunt". If results appear, click "Open as Case".
**Expected:** Results table renders (may be empty if no data ingested). If results present, clicking "Open as Case" creates a case and shows success message with case_id.
**Why human:** Dynamic state transitions and user interaction sequence require browser verification.

### 3. Artifact Upload via API

**Test:** With backend running, POST a file to `/api/cases/{case_id}/artifacts` using curl or the dashboard (if upload UI is wired to a visible button).
**Expected:** File written to `data/artifacts/{case_id}/` directory; response contains artifact_id, filename, file_size.
**Why human:** Filesystem write verification and multipart form handling best confirmed with real server context.

---

## Gaps Summary

No gaps. All 16 must-have truths are verified. The phase goal is achieved.

The investigation workflow layer is complete: structured SQLite-backed cases, 4 DuckDB hunt templates, timeline reconstruction with confidence scoring, forensic artifact filesystem storage, 8 REST API endpoints, and two Svelte 5 dashboard panels (CasePanel, HuntPanel). The full backend test suite passes with no regressions.

---

_Verified: 2026-03-17T02:52:06Z_
_Verifier: Claude (gsd-verifier)_
