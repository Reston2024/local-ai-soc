---
phase: 7
slug: threat-hunting-case-management
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (asyncio_mode = "auto" in pyproject.toml) |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest backend/src/tests/test_phase7.py -x` |
| **Full suite command** | `uv run pytest backend/src/tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest backend/src/tests/test_phase7.py -x`
- **After every plan wave:** Run `uv run pytest backend/src/tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| P7-T01 | 07-01 | 0 | case_manager | unit | `uv run pytest backend/src/tests/test_phase7.py::TestCaseManager::test_create_case_returns_id -x` | ❌ Wave 0 | ⬜ pending |
| P7-T02 | 07-01 | 0 | case_manager | unit | `uv run pytest backend/src/tests/test_phase7.py::TestCaseManager::test_list_cases_empty -x` | ❌ Wave 0 | ⬜ pending |
| P7-T03 | 07-01 | 0 | case_manager | unit | `uv run pytest backend/src/tests/test_phase7.py::TestCaseManager::test_update_case_status -x` | ❌ Wave 0 | ⬜ pending |
| P7-T04 | 07-02 | 1 | cases API | integration | `uv run pytest backend/src/tests/test_phase7.py::TestCaseAPI::test_create_case_endpoint -x` | ❌ Wave 0 | ⬜ pending |
| P7-T05 | 07-02 | 1 | cases API | integration | `uv run pytest backend/src/tests/test_phase7.py::TestCaseAPI::test_list_cases_endpoint -x` | ❌ Wave 0 | ⬜ pending |
| P7-T06 | 07-02 | 1 | cases API | integration | `uv run pytest backend/src/tests/test_phase7.py::TestCaseAPI::test_get_case_detail -x` | ❌ Wave 0 | ⬜ pending |
| P7-T07 | 07-02 | 1 | cases API | integration | `uv run pytest backend/src/tests/test_phase7.py::TestCaseAPI::test_patch_case_status -x` | ❌ Wave 0 | ⬜ pending |
| P7-T08 | 07-03 | 1 | hunt_engine | unit | `uv run pytest backend/src/tests/test_phase7.py::TestHuntEngine::test_suspicious_ip_template -x` | ❌ Wave 0 | ⬜ pending |
| P7-T09 | 07-03 | 1 | hunt_engine | unit | `uv run pytest backend/src/tests/test_phase7.py::TestHuntEngine::test_powershell_children_template -x` | ❌ Wave 0 | ⬜ pending |
| P7-T10 | 07-03 | 1 | hunt API | integration | `uv run pytest backend/src/tests/test_phase7.py::TestHuntAPI::test_list_hunt_templates -x` | ❌ Wave 0 | ⬜ pending |
| P7-T11 | 07-03 | 1 | hunt API | integration | `uv run pytest backend/src/tests/test_phase7.py::TestHuntAPI::test_execute_hunt -x` | ❌ Wave 0 | ⬜ pending |
| P7-T12 | 07-04 | 2 | timeline_builder | unit | `uv run pytest backend/src/tests/test_phase7.py::TestTimelineBuilder::test_timeline_entry_shape -x` | ❌ Wave 0 | ⬜ pending |
| P7-T13 | 07-04 | 2 | timeline API | integration | `uv run pytest backend/src/tests/test_phase7.py::TestTimelineAPI::test_get_timeline -x` | ❌ Wave 0 | ⬜ pending |
| P7-T14 | 07-04 | 2 | artifact_store | unit | `uv run pytest backend/src/tests/test_phase7.py::TestArtifactStore::test_save_artifact -x` | ❌ Wave 0 | ⬜ pending |
| P7-T15 | 07-04 | 2 | artifact API | integration | `uv run pytest backend/src/tests/test_phase7.py::TestArtifactAPI::test_upload_artifact -x` | ❌ Wave 0 | ⬜ pending |
| P7-T16 | 07-05 | 3 | dashboard build | build | `cd frontend && npm run build` | ❌ Wave 3 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/src/tests/test_phase7.py` — 16 xfail stubs P7-T01 through P7-T16
- [ ] `backend/src/tests/conftest.py` — confirm shared fixtures exist (tmp_path, TestClient)
- [ ] Stub files: `backend/investigation/__init__.py`, `case_manager.py`, `timeline_builder.py`, `hunt_engine.py`, `artifact_store.py`, `tagging.py`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dashboard investigation panel renders correctly | P7-T16 | Visual layout | Open https://localhost/app/ → navigate to Investigation tab, confirm case list renders |
| Hunt panel pivot-to-case action works | PRD | User interaction | Run a hunt query → click "Open as Case" → confirm case created |
| AI summary generates in read-only mode | PRD | LLM dependency | Open case detail → click "Generate Summary" → confirm text appears, no edit controls |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
