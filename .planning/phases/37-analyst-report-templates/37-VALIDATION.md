---
phase: 37
slug: analyst-report-templates
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-11
---

# Phase 37 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (asyncio mode: auto) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/unit/ -q` |
| **Full suite command** | `uv run pytest tests/unit/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/ -q`
- **After every plan wave:** Run `uv run pytest tests/unit/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 37-01-01 | 01 | 1 | P37-T08 | unit | `uv run pytest tests/unit/test_report_templates.py -q` | ❌ W0 | ⬜ pending |
| 37-01-02 | 01 | 1 | P37-T01 | unit | `uv run pytest tests/unit/test_report_templates.py::test_session_log -q` | ❌ W0 | ⬜ pending |
| 37-01-03 | 01 | 1 | P37-T02 | unit | `uv run pytest tests/unit/test_report_templates.py::test_incident_report -q` | ❌ W0 | ⬜ pending |
| 37-01-04 | 01 | 1 | P37-T03 | unit | `uv run pytest tests/unit/test_report_templates.py::test_playbook_log -q` | ❌ W0 | ⬜ pending |
| 37-02-01 | 02 | 1 | P37-T04 | unit | `uv run pytest tests/unit/test_report_templates.py::test_pir -q` | ❌ W0 | ⬜ pending |
| 37-02-02 | 02 | 1 | P37-T05 | unit | `uv run pytest tests/unit/test_report_templates.py::test_ti_bulletin -q` | ❌ W0 | ⬜ pending |
| 37-02-03 | 02 | 1 | P37-T06 | unit | `uv run pytest tests/unit/test_report_templates.py::test_severity_reference -q` | ❌ W0 | ⬜ pending |
| 37-03-01 | 03 | 2 | P37-T07 | manual | See Manual-Only below | N/A | ⬜ pending |
| 37-03-02 | 03 | 2 | P37-T07,T08 | unit | `uv run pytest tests/unit/ -q` | ✅ | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `tests/unit/test_report_templates.py` — stubs for all 6 template endpoint tests + Report.type widening test

*Existing infrastructure (conftest, pytest-asyncio auto mode) covers all other needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Templates tab renders in dashboard with 2×3 card grid | P37-T07 | Requires running frontend | Open dashboard → Reports → Templates tab, verify 6 cards visible with data badges |
| Generate button swaps to Download after generate | P37-T07 | Requires running frontend + backend | Click Generate on Session Log card, confirm button changes to Download PDF |
| Shortcut button in InvestigationsView routes to Templates tab | P37-T07 | Requires running frontend | Open any investigation, click Generate Report, confirm routes to Reports > Templates with case pre-selected |
| PDF renders with SOC Brain dark header + signature lines | P37-T01 through T06 | Requires WeasyPrint + running backend | Download any generated template PDF, verify dark header with AI-SOC-Brain branding and signature line at bottom |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
