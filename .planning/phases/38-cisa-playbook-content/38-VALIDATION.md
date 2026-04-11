---
phase: 38
slug: cisa-playbook-content
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-11
---

# Phase 38 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/unit/test_playbooks*.py -x -q` |
| **Full suite command** | `uv run pytest tests/unit/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_playbooks*.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/unit/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 38-01-01 | 01 | 0 | P38-T04 | unit | `uv run pytest tests/unit/test_playbooks_model.py -x -q` | ❌ W0 | ⬜ pending |
| 38-01-02 | 01 | 0 | P38-T05 | unit | `uv run pytest tests/unit/test_playbooks_seed.py -x -q` | ❌ W0 | ⬜ pending |
| 38-01-03 | 01 | 1 | P38-T01 | unit | `uv run pytest tests/unit/test_playbooks_cisa.py -x -q` | ❌ W0 | ⬜ pending |
| 38-01-04 | 01 | 1 | P38-T02 | unit | `uv run pytest tests/unit/test_playbooks_cisa.py::test_technique_ids -x -q` | ❌ W0 | ⬜ pending |
| 38-01-05 | 01 | 1 | P38-T03 | unit | `uv run pytest tests/unit/test_playbooks_cisa.py::test_escalation_fields -x -q` | ❌ W0 | ⬜ pending |
| 38-02-01 | 02 | 1 | P38-T05 | unit | `uv run pytest tests/unit/test_playbooks_seed.py -x -q` | ❌ W0 | ⬜ pending |
| 38-02-02 | 02 | 2 | P38-T06 | manual | — | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_playbooks_model.py` — stubs for PlaybookStep field extension (P38-T04)
- [ ] `tests/unit/test_playbooks_seed.py` — stubs for CISA seeding and NIST replacement (P38-T05)
- [ ] `tests/unit/test_playbooks_cisa.py` — stubs for CISA content: step count, ATT&CK IDs, escalation fields (P38-T01, T02, T03)

*Existing `tests/unit/` infrastructure covers pytest runner and fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CISA source badge (amber) / Custom badge (blue) visible on playbook cards | P38-T06 | Svelte UI visual | Open PlaybooksView, verify CISA playbooks show amber "CISA" badge, custom playbooks show blue "Custom" badge |
| Escalation warning banner appears at correct severity threshold | P38-T03 | Requires active detection context in UI | Start a playbook run linked to a Critical detection; verify yellow banner appears on steps with escalation_threshold="critical" |
| ATT&CK technique chips clickable → attack.mitre.org | P38-T02, T06 | Browser interaction | Click a technique chip (e.g. T1566); verify new tab opens to correct MITRE URL |
| "Suggested: [Playbook]" appears in detection panel | P38-T02 | Requires detection with matching TTP in dashboard | Navigate to a detection with T1566; verify soft CTA appears in detection panel |
| Step completion containment_action dropdown | P38-T04, T06 | UI interaction at step completion | Complete a step; verify dropdown appears with controlled vocabulary options |
| Run completion PDF prompt | P38-T06 | End-to-end flow | Complete all steps of a CISA playbook run; verify "Generate Playbook Execution Log PDF?" prompt appears |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
