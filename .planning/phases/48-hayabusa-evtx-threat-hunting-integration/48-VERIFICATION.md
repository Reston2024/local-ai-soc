---
phase: 48-hayabusa-evtx-threat-hunting-integration
verified: 2026-04-14T21:10:00Z
status: passed
score: 12/12 must-haves verified
re_verification: false
human_verification:
  - test: "HAYABUSA chip renders amber and filters in browser"
    expected: "Chip bar shows HAYABUSA chip in amber; clicking it shows only Hayabusa-sourced rows; amber HAYABUSA badge on each row; SIGMA chip excludes hayabusa- prefixed rows"
    why_human: "Visual rendering and filter click-through cannot be verified without a running browser"
---

# Phase 48: Hayabusa EVTX Threat Hunting Integration — Verification Report

**Phase Goal:** Integrate Hayabusa as a scheduled EVTX analysis engine alongside the existing EVTX parser. Run Hayabusa on ingested EVTX files, import findings into detections table, and surface Hayabusa-sourced detections distinctly in DetectionsView.
**Verified:** 2026-04-14T21:10:00Z
**Status:** PASSED (automated) / human_needed for browser visual
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | HayabusaScanner maps JSONL records to DetectionRecord with correct field mappings | VERIFIED | `ingestion/hayabusa_scanner.py` L117-177: `hayabusa_record_to_detection()` maps RuleTitle, RuleFile, Level, MitreTags, MitreTactics, Details; test_record_mapping PASSED |
| 2 | Level normalization converts crit/high/med/low/info to schema severity values | VERIFIED | `_LEVEL_MAP` at L30-37; test_level_normalization PASSED with all 6 known mappings + unknown-default |
| 3 | MitreTags filtering excludes G#### and S#### entries, retains only T#### entries | VERIFIED | L146-149: `next(t for t in mitre_tags if t.upper().startswith("T") and len(t) >= 5)`; test_mitre_tag_filter PASSED |
| 4 | scan_evtx yields nothing (no crash) when HAYABUSA_BIN is None | VERIFIED | L61-62: `if not HAYABUSA_BIN: return`; test_no_binary PASSED via monkeypatch |
| 5 | Files already scanned by SHA-256 are skipped without subprocess invocation | VERIFIED | `is_already_scanned()` + `mark_scanned()` in sqlite_store.py L857-872; _run_hayabusa_scan L358-360 checks dedup first; test_dedup_skip PASSED |
| 6 | detection_source migration runs idempotently; column exists after second call | VERIFIED | sqlite_store.py L501-506: ALTER TABLE in try/except; test_migration_idempotent PASSED |
| 7 | insert_detection persists detection_source='hayabusa' for Hayabusa findings | VERIFIED | sqlite_store.py L809, L832, L841: `detection_source: str = "sigma"` param; `_run_hayabusa_scan` calls `insert_detection(detection_source="hayabusa")` |
| 8 | loader.py calls HayabusaScanner after EVTX parse, only for .evtx suffix | VERIFIED | loader.py L531-539: `if _Path(file_path).suffix.lower() == ".evtx"` → `asyncio.to_thread(_run_hayabusa_scan, ...)`, non-fatal |
| 9 | Detection TypeScript interface has detection_source field | VERIFIED | api.ts L106: `detection_source?: string | null  // Phase 48` |
| 10 | DetectionsView shows HAYABUSA chip with amber styling | VERIFIED | DetectionsView.svelte L419-421: chip button with chip-hayabusa class; CSS L1067-1068: `border-color: #d97706; color: #fbbf24` |
| 11 | HAYABUSA chip count derived from detections with detection_source==='hayabusa' | VERIFIED | DetectionsView.svelte L67: `let hayabusaCount = $derived(detections.filter(d => d.detection_source === 'hayabusa').length)` |
| 12 | Hayabusa detection rows show amber HAYABUSA badge | VERIFIED | DetectionsView.svelte L527-529: `{#if d.detection_source === 'hayabusa'}<span class="badge-hayabusa">HAYABUSA</span>`; CSS L1145-1154 |

**Score:** 12/12 truths verified (all automated checks passed)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `ingestion/hayabusa_scanner.py` | HayabusaScanner with scan_evtx(), hayabusa_record_to_detection(), _LEVEL_MAP, HAYABUSA_BIN | VERIFIED | 178 lines (min 80), all 4 exports present, substantive implementation |
| `backend/stores/sqlite_store.py` | hayabusa_scanned_files DDL, is_already_scanned(), mark_scanned(), detection_source migration, insert_detection() with detection_source | VERIFIED | All 5 elements present; DDL executed at L498; migration at L501-506; methods at L857-872; insert_detection extended at L809-841 |
| `tests/unit/test_hayabusa_scanner.py` | 6 unit tests covering HAY-01..HAY-06 | VERIFIED | 176 lines; 6 tests; all PASSED in live run |
| `tests/integration/test_hayabusa_e2e.py` | Integration test gated on hayabusa binary | VERIFIED | 34 lines; pytestmark=hayabusa; skipif on HAYABUSA_AVAILABLE; skips cleanly when binary absent |
| `dashboard/src/lib/api.ts` | Detection interface with detection_source field | VERIFIED | L106: `detection_source?: string | null` |
| `dashboard/src/views/DetectionsView.svelte` | HAYABUSA chip, hayabusaCount $derived, updated SIGMA filter, amber badge | VERIFIED | All 4 elements at lines 22/48-53/67/419-421/527-529/1067-1068/1145 |
| `ingestion/loader.py` | _run_hayabusa_scan helper + ingest_file wiring | VERIFIED | L43 import; L294 IngestionResult.hayabusa_findings; L346-379 helper; L531-539 wiring |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `ingestion/loader.py` | `ingestion/hayabusa_scanner.py` | `asyncio.to_thread(_run_hayabusa_scan, ...)` | WIRED | L43 imports scan_evtx + hayabusa_record_to_detection; L534-535 calls to_thread(_run_hayabusa_scan); helper at L346 |
| `ingestion/hayabusa_scanner.py` | `backend/stores/sqlite_store.py` | `sqlite_store.insert_detection(..., detection_source='hayabusa')` | WIRED | loader.py _run_hayabusa_scan L364-375 calls insert_detection with detection_source="hayabusa" |
| `ingestion/hayabusa_scanner.py` | `subprocess.run` | generator + asyncio.to_thread wrapping | WIRED | hayabusa_scanner.py L80-85: `subprocess.run(cmd, ...)` inside scan_evtx; called via asyncio.to_thread in loader.py |
| `DetectionsView.svelte` | `api.ts Detection.detection_source` | `d.detection_source === 'hayabusa'` | WIRED | 3 uses: HAYABUSA filter branch (L49), SIGMA backward-compat filter (L52-53), badge render (L527); hayabusaCount derived (L67) |
| `DetectionsView typeFilter 'HAYABUSA'` | `displayDetections $derived` | `typeFilter === 'HAYABUSA'` branch | WIRED | L48: `typeFilter === 'HAYABUSA' ? detections.filter(d => d.detection_source === 'hayabusa')` |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| HAY-01 | 48-01, 48-02 | JSONL record mapped to DetectionRecord with rule_id 'hayabusa-{RuleFile}', severity, attack_technique | SATISFIED | hayabusa_scanner.py L117-177; test_record_mapping PASSED |
| HAY-02 | 48-01, 48-02 | _LEVEL_MAP maps crit/high/med/medium/low/info; unknown → medium | SATISFIED | hayabusa_scanner.py L30-37; test_level_normalization PASSED |
| HAY-03 | 48-01, 48-02 | MitreTags filtering: only T#### (len>=5) selected; G#### S#### excluded | SATISFIED | hayabusa_scanner.py L146-149; test_mitre_tag_filter PASSED |
| HAY-04 | 48-01, 48-02 | scan_evtx yields nothing when HAYABUSA_BIN is None | SATISFIED | hayabusa_scanner.py L61-62; test_no_binary PASSED |
| HAY-05 | 48-01, 48-02 | SHA-256 dedup prevents re-scanning same file | SATISFIED | sqlite_store.py L857-872; _run_hayabusa_scan L358-360; test_dedup_skip PASSED |
| HAY-06 | 48-01, 48-02 | detection_source migration idempotent; column exists after repeated calls | SATISFIED | sqlite_store.py L501-506; test_migration_idempotent PASSED |
| HAY-07 | 48-03 | HAYABUSA chip in DetectionsView; SIGMA filter corrected; amber badge | SATISFIED | DetectionsView.svelte fully wired; api.ts extended; tsc 0 errors |
| HAY-08 | 48-01, 48-02 | Integration test gated on binary; runs end-to-end when binary present | SATISFIED | test_hayabusa_e2e.py: skips cleanly on binary absence; real assertion when binary present |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | No anti-patterns found |

No TODO, FIXME, placeholder, or stub bodies detected in phase 48 files. All test functions contain real assertions (not `pytest.skip("Wave 0 stub")`).

---

### Human Verification Required

#### 1. HAYABUSA Chip Visual and Filter Behavior

**Test:** Open `https://localhost/detections` in the browser. Confirm chip bar shows All | CORR | ANOMALY | SIGMA | HAYABUSA. Click HAYABUSA chip — verify it activates (amber background). If Hayabusa binary is installed and EVTX has been ingested, confirm only Hayabusa-sourced rows appear and each row shows an amber HAYABUSA badge. Click SIGMA — confirm hayabusa- prefixed rows are absent.

**Expected:** HAYABUSA chip renders with amber border (#d97706) and text (#fbbf24); active state uses amber background (#92400e); SIGMA filter excludes any detection_source==='hayabusa' row; Hayabusa detection rows display amber HAYABUSA badge alongside TP/FP verdict badges.

**Why human:** CSS rendering, visual color accuracy, and filter click behavior cannot be verified by static grep inspection. Auto-advance was used for the Plan 03 human checkpoint — visual confirmation was not captured.

---

### Gaps Summary

No automated gaps found. All 12 observable truths are verified by direct code inspection and live test execution:

- 6/6 unit tests PASSED in live execution (`uv run pytest tests/unit/test_hayabusa_scanner.py -v`)
- 1/1 integration test SKIPPED cleanly (binary not on PATH — correct behavior)
- TypeScript check: 0 errors (`npx tsc --noEmit` produced no output)
- All key links confirmed by grep: loader imports scanner, scanner wires into sqlite insert_detection with detection_source='hayabusa', DetectionsView uses detection_source in 4 places
- Pre-existing test failures (test_auth, test_builtin_playbooks, test_playbooks_cisa, test_playbooks_seed) confirmed pre-Phase-48 — no new regressions introduced

One item is flagged for human verification only because the Plan 03 human checkpoint was auto-approved (workflow.auto_advance=true). The code is complete and correct; visual browser confirmation remains outstanding.

---

_Verified: 2026-04-14T21:10:00Z_
_Verifier: Claude (gsd-verifier)_
