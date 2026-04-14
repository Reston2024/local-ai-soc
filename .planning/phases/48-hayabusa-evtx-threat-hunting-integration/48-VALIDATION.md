---
phase: 48
slug: hayabusa-evtx-threat-hunting-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-14
---

# Phase 48 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (pytest-asyncio auto mode) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/unit/test_hayabusa_scanner.py -x` |
| **Full suite command** | `uv run pytest tests/unit/ -x` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_hayabusa_scanner.py -x`
- **After every plan wave:** Run `uv run pytest tests/unit/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 48-01-01 | 01 | 1 | HAY-01, HAY-02, HAY-03, HAY-04 | unit stub | `uv run pytest tests/unit/test_hayabusa_scanner.py -x` | ❌ W0 | ⬜ pending |
| 48-01-02 | 01 | 1 | HAY-05, HAY-06 | unit stub | `uv run pytest tests/unit/test_hayabusa_scanner.py -x` | ❌ W0 | ⬜ pending |
| 48-01-03 | 01 | 1 | HAY-08 | integration stub | `uv run pytest tests/integration/test_hayabusa_e2e.py -x` | ❌ W0 | ⬜ pending |
| 48-02-01 | 02 | 2 | HAY-01, HAY-02, HAY-03, HAY-04 | unit | `uv run pytest tests/unit/test_hayabusa_scanner.py::test_record_mapping tests/unit/test_hayabusa_scanner.py::test_level_normalization tests/unit/test_hayabusa_scanner.py::test_mitre_tag_filter tests/unit/test_hayabusa_scanner.py::test_no_binary -x` | ✅ W0 | ⬜ pending |
| 48-02-02 | 02 | 2 | HAY-05, HAY-06 | unit | `uv run pytest tests/unit/test_hayabusa_scanner.py::test_dedup_skip tests/unit/test_hayabusa_scanner.py::test_migration_idempotent -x` | ✅ W0 | ⬜ pending |
| 48-03-01 | 03 | 3 | HAY-07 | manual | Open UI → HAYABUSA chip appears, shows count, filters correctly | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_hayabusa_scanner.py` — stubs for HAY-01 through HAY-06 (6 unit tests, all SKIP initially)
- [ ] `tests/integration/test_hayabusa_e2e.py` — stub for HAY-08 (skipped if `shutil.which("hayabusa")` is None)

*Existing pytest infrastructure covers all other requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| HAYABUSA chip renders in DetectionsView, filters by detection_source | HAY-07 | Svelte 5 reactivity and CSS chip rendering require browser | Open https://localhost/detections; ingest an EVTX with Hayabusa installed; verify HAYABUSA chip appears with count; click chip; verify only Hayabusa detections shown |
| Hayabusa badge (amber) on expanded detection row | HAY-07 | CSS rendering requires browser | Expand a Hayabusa-sourced detection; verify amber "HAYABUSA" badge visible on the row |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
