---
phase: 39
slug: mitre-car-analytics-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-11
---

# Phase 39 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/unit/test_car_store.py -x -q` |
| **Full suite command** | `uv run pytest tests/unit/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_car_store.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/unit/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 39-01-01 | 01 | 0 | P39-T01 | unit | `uv run pytest tests/unit/test_car_store.py::test_car_store_table_exists -x` | ❌ W0 | ⬜ pending |
| 39-01-02 | 01 | 0 | P39-T01 | unit | `uv run pytest tests/unit/test_car_store.py::test_bulk_insert_seeding -x` | ❌ W0 | ⬜ pending |
| 39-01-03 | 01 | 0 | P39-T01 | unit | `uv run pytest tests/unit/test_car_store.py::test_analytic_count -x` | ❌ W0 | ⬜ pending |
| 39-01-04 | 01 | 0 | P39-T02 | unit | `uv run pytest tests/unit/test_car_store.py::test_get_analytics_for_technique -x` | ❌ W0 | ⬜ pending |
| 39-01-05 | 01 | 0 | P39-T02 | unit | `uv run pytest tests/unit/test_car_store.py::test_subtechnique_normalization -x` | ❌ W0 | ⬜ pending |
| 39-01-06 | 01 | 0 | P39-T02 | unit | `uv run pytest tests/unit/test_car_store.py::test_no_match_returns_empty -x` | ❌ W0 | ⬜ pending |
| 39-01-07 | 01 | 0 | P39-T03 | unit | `uv run pytest tests/unit/test_car_store.py::test_detection_enrichment_field -x` | ❌ W0 | ⬜ pending |
| 39-01-08 | 01 | 0 | P39-T03 | unit | `uv run pytest tests/unit/test_car_store.py::test_detection_no_technique_null -x` | ❌ W0 | ⬜ pending |
| 39-02-01 | 02 | 1 | P39-T01,T02,T03 | unit | `uv run pytest tests/unit/test_car_store.py -x -q` | ❌ W0 | ⬜ pending |
| 39-03-01 | 03 | 2 | P39-T04,T05 | manual | — | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_car_store.py` — 8 stubs covering P39-T01, P39-T02, P39-T03
- [ ] `backend/data/car_analytics.json` — bundled CAR catalog (generated + committed in Wave 0)

*Existing `tests/unit/` infrastructure covers pytest runner and fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Expandable row appears in DetectionsView when detection has ATT&CK technique | P39-T04 | Svelte UI interaction | Click a detection row with an ATT&CK technique; verify CAR analytic panel expands below with ID, description, log sources, guidance, pseudocode |
| CAR analytic link opens car.mitre.org | P39-T04 | Browser navigation | Click CAR analytic ID link; verify new tab opens to correct CAR page |
| ATT&CK technique link opens attack.mitre.org | P39-T04 | Browser navigation | Click technique link in expanded panel; verify correct MITRE ATT&CK page opens |
| Multiple CAR analytics stack as cards when technique has >1 match | P39-T04 | Visual rendering | Open detection with T1059; verify multiple CAR analytic cards shown stacked |
| CAR analytics appear in investigation evidence panel | P39-T05 | Requires active investigation | Open an investigation linked to a detection with ATT&CK technique; verify CAR section in evidence panel |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
