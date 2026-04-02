---
phase: 21
slug: evidence-provenance
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-01
---

# Phase 21 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio (auto mode) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/unit/test_ingest_provenance.py tests/unit/test_detection_provenance.py tests/unit/test_llm_provenance.py tests/unit/test_playbook_provenance.py -q` |
| **Full suite command** | `uv run pytest tests/ -q --tb=short` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command above
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 21-00-01 | 00 | 0 | P21-T01–T04 | unit stubs | `uv run pytest tests/unit/test_ingest_provenance.py tests/unit/test_detection_provenance.py tests/unit/test_llm_provenance.py tests/unit/test_playbook_provenance.py -q` | ❌ W0 | ⬜ pending |
| 21-01-01 | 01 | 1 | P21-T01 | unit | `uv run pytest tests/unit/test_ingest_provenance.py -v` | ❌ W0 | ⬜ pending |
| 21-01-02 | 01 | 1 | P21-T01 | regression | `uv run pytest tests/ -q --tb=short` | ✅ | ⬜ pending |
| 21-02-01 | 02 | 1 | P21-T02 | unit | `uv run pytest tests/unit/test_detection_provenance.py -v` | ❌ W0 | ⬜ pending |
| 21-03-01 | 03 | 2 | P21-T03 | unit | `uv run pytest tests/unit/test_llm_provenance.py -v` | ❌ W0 | ⬜ pending |
| 21-04-01 | 04 | 2 | P21-T04 | unit | `uv run pytest tests/unit/test_playbook_provenance.py -v` | ❌ W0 | ⬜ pending |
| 21-05-01 | 05 | 3 | P21-T05 | unit | `uv run pytest tests/unit/test_provenance_api.py -v` | ❌ W0 | ⬜ pending |
| 21-05-02 | 05 | 3 | P21-T05 | regression | `uv run pytest tests/ -q --tb=short` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_ingest_provenance.py` — stubs for P21-T01 (SQLite table, SHA-256, parser version)
- [ ] `tests/unit/test_detection_provenance.py` — stubs for P21-T02 (rule SHA-256, pySigma version, field_map version)
- [ ] `tests/unit/test_llm_provenance.py` — stubs for P21-T03 (model_id, template hash, response hash, grounding_event_ids)
- [ ] `tests/unit/test_playbook_provenance.py` — stubs for P21-T04 (playbook SHA-256, trigger_event_ids, approver)
- [ ] `tests/unit/test_provenance_api.py` — stubs for P21-T05 (4 GET endpoints, 200/404 responses)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ProvenanceView tab renders in browser | P21-T05 | Requires running Svelte dev server | Navigate to dashboard, click Provenance nav item, verify 4 panels load |
| Hash copy-to-clipboard works | P21-T05 | Browser clipboard API | Click copy icon on hash value, paste into text field |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
