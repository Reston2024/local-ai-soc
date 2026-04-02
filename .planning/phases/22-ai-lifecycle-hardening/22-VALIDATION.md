---
phase: 22
slug: ai-lifecycle-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-02
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio (auto mode) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/eval/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command above
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 22-00-01 | 00 | 0 | P22-T01–T05 | unit stubs | `uv run pytest tests/eval/ -x -q` | ❌ W0 | ⬜ pending |
| 22-01-01 | 01 | 1 | P22-T01 | unit | `uv run pytest tests/eval/test_grounding.py -x` | ❌ W0 | ⬜ pending |
| 22-01-02 | 01 | 1 | P22-T01 | regression | `uv run pytest tests/ -x -q` | ✅ | ⬜ pending |
| 22-02-01 | 02 | 1 | P22-T02 | unit | `uv run pytest tests/eval/test_confidence.py -x` | ❌ W0 | ⬜ pending |
| 22-02-02 | 02 | 1 | P22-T02 | regression | `uv run pytest tests/ -x -q` | ✅ | ⬜ pending |
| 22-03-01 | 03 | 2 | P22-T03 | eval | `uv run pytest tests/eval/test_analyst_qa_eval.py tests/eval/test_triage_eval.py tests/eval/test_threat_hunt_eval.py -x` | ❌ W0 | ⬜ pending |
| 22-04-01 | 04 | 2 | P22-T04 | unit | `uv run pytest tests/eval/test_model_drift.py -x` | ❌ W0 | ⬜ pending |
| 22-04-02 | 04 | 2 | P22-T04 | regression | `uv run pytest tests/ -x -q` | ✅ | ⬜ pending |
| 22-05-01 | 05 | 3 | P22-T05 | unit | `uv run pytest tests/eval/test_advisory.py -x` | ❌ W0 | ⬜ pending |
| 22-05-02 | 05 | 3 | P22-T05 | regression | `uv run pytest tests/ -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/eval/__init__.py` — marks package
- [ ] `tests/eval/conftest.py` — shared `mock_ollama` fixture + event fixture loader
- [ ] `tests/eval/fixtures/` — 5 NDJSON fixture files (analyst_qa, triage x2, threat_hunt x2)
- [ ] `tests/eval/test_grounding.py` — stubs for P22-T01 (grounding_event_ids in response, is_grounded flag)
- [ ] `tests/eval/test_confidence.py` — stubs for P22-T02 (confidence_score column, heuristic scoring)
- [ ] `tests/eval/test_analyst_qa_eval.py` — stubs for P22-T03 analyst_qa
- [ ] `tests/eval/test_triage_eval.py` — stubs for P22-T03 triage
- [ ] `tests/eval/test_threat_hunt_eval.py` — stubs for P22-T03 threat_hunt
- [ ] `tests/eval/test_model_drift.py` — stubs for P22-T04 (table exists, drift recorded, status endpoint)
- [ ] `tests/eval/test_advisory.py` — stubs for P22-T05 (advisory prefix in SYSTEM prompt)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| AI Advisory banner non-dismissable in InvestigationView | P22-T05 | Requires running Svelte dev server | Navigate to Investigation, send a query, verify banner persists after scroll/click |
| Confidence badge renders correctly for low/high scores | P22-T02 | Browser visual | Send grounded query (badge ≥0.7) vs empty context query (badge <0.3), verify colors |
| SettingsView system tab shows model-status alert | P22-T04 | Requires running backend | Navigate Settings → System tab, verify model name and drift alert shown |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
