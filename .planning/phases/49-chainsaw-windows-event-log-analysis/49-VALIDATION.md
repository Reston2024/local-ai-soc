---
phase: 49
slug: chainsaw-windows-event-log-analysis
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-14
---

# Phase 49 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (pytest-asyncio auto mode) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/unit/test_chainsaw_scanner.py -x` |
| **Full suite command** | `uv run pytest tests/unit/ -x` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_chainsaw_scanner.py -x`
- **After every plan wave:** Run `uv run pytest tests/unit/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 49-01-01 | 01 | 1 | CHN-01, CHN-02, CHN-03, CHN-04 | unit stub | `uv run pytest tests/unit/test_chainsaw_scanner.py -x` | ❌ W0 | ⬜ pending |
| 49-01-02 | 01 | 1 | CHN-05, CHN-06 | unit stub | `uv run pytest tests/unit/test_chainsaw_scanner.py -x` | ❌ W0 | ⬜ pending |
| 49-01-03 | 01 | 1 | CHN-08 | integration stub | `uv run pytest tests/integration/test_chainsaw_e2e.py -x` | ❌ W0 | ⬜ pending |
| 49-02-01 | 02 | 2 | CHN-01, CHN-02, CHN-03, CHN-04 | unit | `uv run pytest tests/unit/test_chainsaw_scanner.py::test_record_mapping tests/unit/test_chainsaw_scanner.py::test_level_normalization tests/unit/test_chainsaw_scanner.py::test_mitre_tag_extraction tests/unit/test_chainsaw_scanner.py::test_no_binary -x` | ✅ W0 | ⬜ pending |
| 49-02-02 | 02 | 2 | CHN-05, CHN-06 | unit | `uv run pytest tests/unit/test_chainsaw_scanner.py::test_dedup_skip tests/unit/test_chainsaw_scanner.py::test_migration_idempotent -x` | ✅ W0 | ⬜ pending |
| 49-03-01 | 03 | 3 | CHN-07 | manual | Open UI → CHAINSAW chip appears, shows count, filters correctly | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_chainsaw_scanner.py` — stubs for CHN-01 through CHN-06 (6 unit tests, all SKIP initially)
- [ ] `tests/integration/test_chainsaw_e2e.py` — stub for CHN-08 (skipped if `shutil.which("chainsaw")` is None)

*Existing pytest infrastructure covers all other requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CHAINSAW chip renders in DetectionsView, filters by detection_source | CHN-07 | Svelte 5 reactivity and CSS chip rendering require browser | Open https://localhost/detections; ingest an EVTX with Chainsaw installed; verify CHAINSAW chip appears with count; click chip; verify only Chainsaw detections shown |
| Chainsaw badge (teal) on expanded detection row | CHN-07 | CSS rendering requires browser | Expand a Chainsaw-sourced detection; verify teal "CHAINSAW" badge visible on the row |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
