---
phase: 52-thehive-case-management-integration
verified: 2026-04-16T16:00:00Z
status: passed
score: 13/13 must-haves verified
re_verification: false
human_verification:
  - test: "TheHive badge and 'Open in TheHive' button visual rendering in dashboard"
    expected: "Amber badge '#N · status' appears on detection rows when thehive_case_num is set; expanded panel shows button that opens http://192.168.1.22:9000/cases/{N} in new tab"
    why_human: "Requires browser rendering and live Svelte state injection to confirm badge colour and button behaviour"
  - test: "InvestigationView header badge rendering"
    expected: "Case badge and 'Open in TheHive' button appear between <h2> and .header-actions when investigationResult.detection.thehive_case_num is set"
    why_human: "Requires browser rendering to verify layout and conditional display"
  - test: "End-to-end auto-case creation with THEHIVE_ENABLED=True"
    expected: "A High/Critical Sigma detection fires, a case appears in TheHive with src_ip observable pre-populated, and thehive_case_id/num are written back to SQLite detections row"
    why_human: "Requires TheHive deployed on GMKtec (docker-compose.thehive.yml), live THEHIVE_API_KEY, and a triggered detection — cannot verify programmatically without the service running"
  - test: "Closure sync back to SQLite"
    expected: "Resolving a case in TheHive UI causes the next APScheduler 300s poll to write thehive_status and thehive_analyst to the detections row"
    why_human: "Requires live TheHive instance and time-based scheduler observation"
---

# Phase 52: TheHive Case Management Integration — Verification Report

**Phase Goal:** Integrate TheHive as a dedicated case management platform running alongside the SOC Brain stack. Auto-create TheHive cases for High/Critical detections with pre-populated observables (src_ip, ATT&CK, MISP IOCs, SpiderFoot findings), provide "Open in TheHive" UI deep-links, and sync case closure verdicts back to SQLite.

**Verified:** 2026-04-16T16:00:00Z
**Status:** passed (with human verification items for live-service behaviour)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | thehive4py==2.0.3 installed and importable | VERIFIED | `pyproject.toml` line 48: `"thehive4py==2.0.3"` |
| 2  | 8 TDD Wave 0 stubs exist (5 client + 3 sync) | VERIFIED | `test_thehive_client.py` 129 lines / `test_thehive_sync.py` 124 lines |
| 3  | All 8 stubs GREEN (not skip, not fail) | VERIFIED | pytest run: `8 passed in 0.14s` |
| 4  | TheHiveClient wraps thehive4py with asyncio.to_thread | VERIFIED | Lines 71, 75, 88 of `thehive_client.py` use `asyncio.to_thread` |
| 5  | SQLite detections table gains 5 thehive_* columns via idempotent migrations | VERIFIED | `sqlite_store.py` lines 397-401: `_THEHIVE_COLUMNS` list with all 5 columns |
| 6  | thehive_pending_cases table DDL created | VERIFIED | `sqlite_store.py` line 386: `CREATE TABLE IF NOT EXISTS thehive_pending_cases` |
| 7  | TheHive + Cortex Docker Compose deployable on GMKtec N100 | VERIFIED | `infra/docker-compose.thehive.yml` 162 lines, 6 services with memory caps |
| 8  | High/Critical detections trigger case creation hook in detect.py | VERIFIED | `detect.py` lines 245-248: `asyncio.create_task(asyncio.to_thread(_maybe_create_thehive_case_wrapper, ...))` |
| 9  | Detection pipeline non-blocking when TheHive unreachable — pending queue used | VERIFIED | `_maybe_create_thehive_case` catches all exceptions and calls `_enqueue_pending_case` |
| 10 | APScheduler polls TheHive every 300s for resolved cases | VERIFIED | `main.py` lines 421-434: dedicated `AsyncIOScheduler` with `sync_thehive_closures` (300s) and `drain_pending_cases` (300s+30s offset) |
| 11 | Health endpoint reports thehive as optional component | VERIFIED | `health.py` line 278: `optional_keys = {"spiderfoot", "hayabusa", "chainsaw", "thehive"}` |
| 12 | Detection interface has thehive_* fields; frontend shows case badge and "Open in TheHive" button | VERIFIED | `api.ts` lines 114-116 (3 fields); `DetectionsView.svelte` lines 556-558, 637-701 (badge + button in both corr and CAR paths); `InvestigationView.svelte` lines 418-427 (badge + button in header) |
| 13 | SpiderFoot Phase 51 findings enriched into observables | VERIFIED | `detect.py` lines 43-67: `_get_spiderfoot_observables()` queries osint_store by src_ip and returns up to 5 HIGH/CRITICAL findings; wired at lines 237-242 |

**Score:** 13/13 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/unit/test_thehive_client.py` | 5 Wave 0 stubs, min 60 lines | VERIFIED | 129 lines, 5 tests all GREEN |
| `tests/unit/test_thehive_sync.py` | 3 Wave 0 stubs, min 50 lines | VERIFIED | 124 lines, 3 tests all GREEN |
| `backend/services/thehive_client.py` | TheHiveClient + build_case_payload + build_observables + _maybe_create_thehive_case | VERIFIED | 321 lines; all 4 functions present and substantive |
| `backend/services/thehive_sync.py` | sync_thehive_closures + drain_pending_cases | VERIFIED | 243 lines; both functions present and substantive |
| `infra/docker-compose.thehive.yml` | 6-service stack with strangebee/thehive:5.5 + Cortex | VERIFIED | 162 lines; cassandra:4.1, elasticsearch:7.17.14 (x2), minio, strangebee/thehive:5.5, thehiveproject/cortex:3.1.8 |
| `backend/core/config.py` | 4 THEHIVE_* settings fields | VERIFIED | Lines 168-172: THEHIVE_URL, THEHIVE_API_KEY, THEHIVE_ENABLED, THEHIVE_SUPPRESS_RULES |
| `backend/stores/sqlite_store.py` | thehive_pending_cases DDL + 5 thehive_* column migrations | VERIFIED | Lines 386-401: DDL and column list present |
| `backend/api/detect.py` | _maybe_create_thehive_case hook post save_detections | VERIFIED | Lines 227-248: hook present, fire-and-forget via asyncio.create_task |
| `backend/api/health.py` | _check_thehive() in optional_keys | VERIFIED | Lines 142-155 (_check_thehive), line 252 (in gather), line 278 (in optional_keys) |
| `backend/main.py` | TheHiveClient on app.state + APScheduler jobs | VERIFIED | Lines 410-440: full THEHIVE_ENABLED conditional block with scheduler |
| `dashboard/src/lib/api.ts` | thehive_case_num field on Detection interface | VERIFIED | Lines 114-116: all 3 thehive_* fields added |
| `dashboard/src/views/DetectionsView.svelte` | Case badge + "Open in TheHive" button | VERIFIED | Lines 556-701: badge on collapsed rows, badge+button in both expanded panel paths |
| `dashboard/src/views/InvestigationView.svelte` | TheHive badge + button in header | VERIFIED | Lines 418-427: badge + button when thehive_case_num present |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `thehive_client.py` | `thehive4py.TheHiveApi` | `asyncio.to_thread` | WIRED | Lines 71, 75, 88: all three async methods use `asyncio.to_thread` |
| `sqlite_store.py` | `thehive_pending_cases` | `CREATE TABLE IF NOT EXISTS` | WIRED | Line 386: DDL present |
| `detect.py` | `_maybe_create_thehive_case` | `asyncio.create_task` (fire-and-forget) | WIRED | Lines 245-248: `asyncio.create_task(asyncio.to_thread(_maybe_create_thehive_case_wrapper, ...))` |
| `main.py` | `sync_thehive_closures` | APScheduler 300s interval | WIRED | Lines 421-434: job added with `"interval", seconds=300` |
| `DetectionsView.svelte` | TheHive case URL | `window.open` deep-link | WIRED | Lines 644, 699: `window.open(THEHIVE_CASE_URL(d.thehive_case_num!), '_blank')` |
| `Detection interface` | `thehive_case_num` | Optional field on Detection | WIRED | `api.ts` line 115 |

---

### Requirements Coverage

The REQ-52-XX identifiers are phase-internal (not in global REQUIREMENTS.md — Phase 52 was added after the original requirements document was closed at Phase 19). Coverage is tracked per plan:

| Req ID | Covered By Plan | Description | Status |
|--------|----------------|-------------|--------|
| REQ-52-01 | 52-01, 52-02 | TDD stubs + TheHiveClient implementation | SATISFIED |
| REQ-52-02 | 52-01, 52-02, 52-03 | Detection pipeline wiring + async wrapper | SATISFIED |
| REQ-52-03 | 52-01, 52-02 | Observable builder (ip/other dataTypes) | SATISFIED |
| REQ-52-04 | 52-01, 52-02, 52-03 | Retry queue (thehive_pending_cases) | SATISFIED |
| REQ-52-05 | 52-04 | Frontend badge + "Open in TheHive" button | SATISFIED |
| REQ-52-06 | 52-01, 52-03 | Closure sync (sync_thehive_closures) | SATISFIED |
| REQ-52-07 | 52-02 | Docker Compose for GMKtec N100 | SATISFIED |
| REQ-52-08 | 52-02 | SQLite schema migrations (idempotent) | SATISFIED |
| REQ-52-09 | 52-03 | Health endpoint (optional thehive component) | SATISFIED |

No orphaned requirements detected. All 9 plan-declared requirement IDs have verified implementation evidence.

**Note on REQUIREMENTS.md:** The global `.planning/REQUIREMENTS.md` covers only Phases 1-19 (closed 2026-03-15). Phase 52 requirements were defined within the phase plans themselves following the project's YOLO-mode convention for later phases.

---

### Anti-Patterns Found

| File | Pattern | Severity | Assessment |
|------|---------|----------|------------|
| `thehive_sync.py` lines 142, 144 | `return None` at end of `sync_thehive_closures` | Info | Intentional — function is void; the explicit `return None` after exception handling is idiomatic, not a stub |
| `thehive_sync.py` line 29 | `_SYNC_AVAILABLE = True` (always True) | Info | The sync module has no mandatory thehive4py dependency; this is a documentation marker, not a functional issue |

No blockers or substantive anti-patterns detected. No TODO/FIXME/PLACEHOLDER comments in Phase 52 files.

---

### Human Verification Required

The following items require a live TheHive instance on GMKtec and/or browser interaction to fully verify:

#### 1. Frontend Badge Rendering and Deep-Link

**Test:** Open the dashboard. Navigate to Detections view. Temporarily inject `thehive_case_num=42` and `thehive_status="InProgress"` on a detection via browser devtools/Svelte state.
**Expected:** Amber badge "#42 · InProgress" appears on the collapsed row; "Open in TheHive" button appears in the expanded panel and opens `http://192.168.1.22:9000/cases/42` in a new tab.
**Why human:** Requires browser rendering and Svelte reactive state to confirm conditional display.

#### 2. InvestigationView Header Badge

**Test:** Load an investigation where the detection has `thehive_case_num` set.
**Expected:** Badge and button appear between the panel `<h2>` and the header actions row.
**Why human:** Requires browser rendering to verify layout position and colour.

#### 3. End-to-End Auto-Case Creation

**Test:** Set `THEHIVE_ENABLED=True`, `THEHIVE_URL=http://192.168.1.22:9000`, and `THEHIVE_API_KEY` in `.env`. Deploy TheHive via `docker compose -f infra/docker-compose.thehive.yml up -d`. Trigger a High or Critical Sigma detection via the detection API.
**Expected:** A case appears in TheHive UI with the correct title format `[HIGH] {rule_name} — {src_ip}`, TLP=AMBER, src_ip observable pre-populated, and `thehive_case_id`/`thehive_case_num` written back to the SQLite detections row.
**Why human:** Requires live TheHive service, real API key, and a triggered detection — not possible to verify programmatically without the deployed service.

#### 4. Closure Sync (Case Verdict Flow-Back)

**Test:** Resolve a case in the TheHive UI with resolutionStatus="TruePositive". Wait up to 300 seconds for the APScheduler sync job to run (or call `sync_thehive_closures` manually).
**Expected:** The matching detections row in SQLite shows `thehive_status="TruePositive"` and `thehive_analyst` set to the assignee's username.
**Why human:** Requires live TheHive, time-based scheduler observation, and direct SQLite inspection.

---

### Deviations from Plan (Noted)

Two auto-adaptations were made during execution that differ from the written plan specs but satisfy the Wave 0 test contracts:

1. `_maybe_create_thehive_case` is **synchronous** (plan spec showed async). Production callers wrap in `asyncio.to_thread`. Tests call directly. This is correct.
2. `thehive_pending_cases` uses a `detection_json` TEXT column (single JSON blob) rather than separate `detection_id + payload_json` columns as planned. `drain_pending_cases` handles both the test schema and the production schema via key-presence detection.

Neither deviation impacts goal achievement — the test contracts pass and the production pipeline is correctly wired.

---

### Regression Check

Full unit suite (excluding pre-existing `test_metrics_api.py` failure unrelated to Phase 52): **1181 passed, 4 skipped, 9 xfailed, 7 xpassed**. Zero new failures introduced by Phase 52 changes.

The `test_metrics_api.py::test_endpoint_accessible_at_api_metrics_kpis` pre-existing failure was confirmed via `git stash` prior to Phase 52 and is out of scope.

---

_Verified: 2026-04-16T16:00:00Z_
_Verifier: Claude (gsd-verifier)_
