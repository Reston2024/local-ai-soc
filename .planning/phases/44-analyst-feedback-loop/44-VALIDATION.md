---
phase: 44
slug: analyst-feedback-loop
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-12
---

# Phase 44 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x (existing, pyproject.toml configured) |
| **Config file** | `pyproject.toml` — `asyncio_mode = "auto"` |
| **Quick run command** | `uv run pytest tests/unit/test_feedback*.py -v` |
| **Full suite command** | `uv run pytest tests/unit/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_feedback*.py -v`
- **After every plan wave:** Run `uv run pytest tests/unit/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 44-01-01 | 01 | 0 | P44-T01,T02 | unit stub | `uv run pytest tests/unit/test_feedback_store.py -v` | ❌ W0 | ⬜ pending |
| 44-01-02 | 01 | 0 | P44-T02,T03 | unit stub | `uv run pytest tests/unit/test_feedback_classifier.py -v` | ❌ W0 | ⬜ pending |
| 44-02-01 | 02 | 1 | P44-T02 | unit | `uv run pytest tests/unit/test_feedback_store.py -v` | ❌ W0 | ⬜ pending |
| 44-02-02 | 02 | 1 | P44-T03 | unit | `uv run pytest tests/unit/test_feedback_classifier.py -v` | ❌ W0 | ⬜ pending |
| 44-02-03 | 02 | 1 | P44-T02,T03 | unit | `uv run pytest tests/unit/ -q 2>&1 \| tail -5` | ❌ W0 | ⬜ pending |
| 44-03-01 | 03 | 2 | P44-T04,T05 | unit | `uv run pytest tests/unit/test_feedback_store.py -v` | ❌ W0 | ⬜ pending |
| 44-03-02 | 03 | 2 | P44-T05 | unit | `uv run pytest tests/unit/ -q 2>&1 \| tail -5` | ❌ W0 | ⬜ pending |
| 44-04-01 | 04 | 3 | P44-T01,T04 | TypeScript | `cd dashboard && npx tsc --noEmit 2>&1 \| tail -10` | ❌ W0 | ⬜ pending |
| 44-04-02 | 04 | 3 | P44-T05 | TypeScript | `cd dashboard && npx tsc --noEmit 2>&1 \| tail -10` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_feedback_store.py` — stubs for SQLite feedback table and insert/query methods
- [ ] `tests/unit/test_feedback_classifier.py` — stubs for River-based FeedbackClassifier (learn_one, predict_proba_one, save/load, accuracy)
- [ ] One RED import test: `from backend.services.feedback.classifier import FeedbackClassifier` — fails until Plan 44-02 creates the module
- [ ] All other stubs use `pytestmark = pytest.mark.skip(reason="stub")` pattern (same as Phase 42/43)

*Existing pytest infrastructure covers all other phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| TP/FP ghost buttons appear in expanded row | P44-T01 | DOM rendering | Open DetectionsView, expand a row, confirm [ ✓ True Positive ] [ ✗ False Positive ] appear |
| Verdict badge appears on collapsed row after submit | P44-T01 | DOM interaction | Submit TP, collapse row, confirm green TP badge is visible |
| Toast notification fires on verdict submit | P44-T01 | DOM/visual | Submit FP, confirm brief toast "Marked as False Positive" appears and fades |
| Unreviewed chip hides verdicted rows | P44-T01 | DOM filter | Submit some verdicts, click Unreviewed chip, confirm those rows disappear |
| Similar cases section appears in InvestigationView | P44-T04 | Requires live Chroma data | Submit 2+ verdicts, open an investigation, scroll to confirm Similar Confirmed Cases section |
| Feedback KPI cards appear in OverviewView | P44-T05 | Requires live feedback data | Submit verdicts, check Overview KPIs update within 60s |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
