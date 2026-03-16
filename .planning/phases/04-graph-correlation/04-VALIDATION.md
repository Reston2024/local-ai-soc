---
phase: 4
slug: graph-correlation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-15
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (uv managed) |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest backend/src/tests/ -x -q` |
| **Full suite command** | `uv run pytest backend/src/tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest backend/src/tests/ -x -q`
- **After every plan wave:** Run `uv run pytest backend/src/tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green (all tests pass)
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | Graph models | unit | `uv run pytest backend/src/tests/test_phase4.py::TestGraphModels -v` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | Node extraction | unit | `uv run pytest backend/src/tests/test_phase4.py::TestNodeExtraction -v` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | Edge extraction | unit | `uv run pytest backend/src/tests/test_phase4.py::TestEdgeExtraction -v` | ❌ W0 | ⬜ pending |
| 04-01-04 | 01 | 1 | Correlation logic | unit | `uv run pytest backend/src/tests/test_phase4.py::TestCorrelation -v` | ❌ W0 | ⬜ pending |
| 04-01-05 | 01 | 1 | Attack paths | unit | `uv run pytest backend/src/tests/test_phase4.py::TestAttackPaths -v` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | GET /graph API | integration | `uv run pytest backend/src/tests/test_phase4.py::TestGraphAPI -v` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 2 | Alert-to-event link | integration | `uv run pytest backend/src/tests/test_phase4.py::TestAlertGraph -v` | ❌ W0 | ⬜ pending |
| 04-02-03 | 02 | 2 | Regression | regression | `uv run pytest backend/src/tests/ -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/src/tests/test_phase4.py` — stubs for all TestGraph* classes above
- [ ] Stub fixtures: 3-event DNS chain, connection event, alert dict (matching `_alerts` shape from routes.py)

*Existing `conftest.py` and `TestClient` patterns from `test_phase2.py` cover infrastructure — no new installs needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Frontend attack path highlighting | UI correlation grouping | Requires browser + running backend | Start backend (`uv run uvicorn backend.src.main:app`), open frontend, ingest 3-event DNS chain via `/ingest`, open graph tab, verify path nodes highlighted |
| Node detail panel | Click → attributes + evidence | Requires browser interaction | Click a host node → verify side panel shows attributes dict and evidence event IDs |
| Edge tooltip | Hover → evidence_event_ids | Requires browser interaction | Hover an edge → verify tooltip lists source event IDs |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
