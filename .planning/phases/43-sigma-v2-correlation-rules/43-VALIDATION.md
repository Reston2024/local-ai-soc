---
phase: 43
slug: sigma-v2-correlation-rules
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-12
---

# Phase 43 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x (existing, pyproject.toml configured) |
| **Config file** | `pyproject.toml` — `asyncio_mode = "auto"` |
| **Quick run command** | `uv run pytest tests/unit/test_correlation*.py -v` |
| **Full suite command** | `uv run pytest tests/unit/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_correlation*.py -v`
- **After every plan wave:** Run `uv run pytest tests/unit/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 43-01-01 | 01 | 0 | P43-T02 | unit stub | `uv run pytest tests/unit/test_correlation_engine.py -v` | ❌ W0 | ⬜ pending |
| 43-01-02 | 01 | 0 | P43-T03 | unit stub | `uv run pytest tests/unit/test_correlation_engine.py -v` | ❌ W0 | ⬜ pending |
| 43-01-03 | 01 | 0 | P43-T01 | unit stub | `uv run pytest tests/unit/test_correlation_engine.py -v` | ❌ W0 | ⬜ pending |
| 43-01-04 | 01 | 0 | P43-T04 | unit stub | `uv run pytest tests/unit/test_correlation_engine.py -v` | ❌ W0 | ⬜ pending |
| 43-01-05 | 01 | 0 | P43-T05 | unit stub | `uv run pytest tests/unit/test_correlation_engine.py -v` | ❌ W0 | ⬜ pending |
| 43-02-01 | 02 | 1 | P43-T02 | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_port_scan_detection -v` | ❌ W0 | ⬜ pending |
| 43-02-02 | 02 | 1 | P43-T03 | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_brute_force_detection -v` | ❌ W0 | ⬜ pending |
| 43-02-03 | 02 | 1 | P43-T01 | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_beaconing_cv_detection -v` | ❌ W0 | ⬜ pending |
| 43-02-04 | 02 | 1 | P43-T05 | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_detection_record_created -v` | ❌ W0 | ⬜ pending |
| 43-02-05 | 02 | 1 | P43-T05 | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_dedup_suppresses_repeat -v` | ❌ W0 | ⬜ pending |
| 43-03-01 | 03 | 2 | P43-T04 | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_chain_detection -v` | ❌ W0 | ⬜ pending |
| 43-03-02 | 03 | 2 | P43-T04 | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_chain_yaml_loading -v` | ❌ W0 | ⬜ pending |
| 43-03-03 | 03 | 2 | P43-T05 | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_ingest_hook_calls_correlation -v` | ❌ W0 | ⬜ pending |
| 43-04-01 | 04 | 3 | P43-T06 | TypeScript | `cd dashboard && npx tsc --noEmit` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_correlation_engine.py` — stubs for all 5 correlation behaviors (port scan, brute force, beaconing, chain, dedup)
- [ ] All stubs use `pytestmark = pytest.mark.skip(reason="stub")` pattern (same as Phase 42)
- [ ] One RED stub: `test_correlation_engine_exists` that imports `detections.correlation` — fails until Plan 02 creates the module

*Existing pytest infrastructure covers all other phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CORR filter chip appears in DetectionsView | P43-T06 | DOM rendering | Open dashboard, ingest events, click "CORR" filter chip, verify only correlation rows remain |
| Correlation row expands to show event IDs | P43-T06 | DOM interaction | Click a corr-portscan row, verify event ID list expands below |
| corr-beacon fires on real beaconing traffic | P43-T01 | Requires live Malcolm data with regular-interval connections | Wait for beaconing pattern to appear in Malcolm flow data, verify detection appears |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
