---
phase: 24
slug: recommendation-artifact-store
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-06
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (auto mode) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/unit/test_recommendation_model.py tests/unit/test_recommendation_api.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~30 seconds (unit only), ~60 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_recommendation_model.py tests/unit/test_recommendation_api.py -x`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| DB schema: recommendations table | 01 | 1 | P24-T01 | unit | `uv run pytest tests/unit/test_recommendation_model.py -x` | Wave 0 | ⬜ pending |
| DB schema: dispatch_log table | 01 | 1 | P24-T01 | unit | same | Wave 0 | ⬜ pending |
| DB schema: migration idempotent | 01 | 1 | P24-T01 | unit | same | Wave 0 | ⬜ pending |
| RecommendationArtifact model validation | 02 | 1 | P24-T02 | unit | `uv run pytest tests/unit/test_recommendation_model.py -x` | Wave 0 | ⬜ pending |
| JSON Schema validation on instantiation | 02 | 1 | P24-T02 | unit | same | Wave 0 | ⬜ pending |
| PromptInspection nested model | 02 | 1 | P24-T02 | unit | same | Wave 0 | ⬜ pending |
| POST /api/recommendations creates draft | 03 | 2 | P24-T03 | integration | `uv run pytest tests/unit/test_recommendation_api.py -x` | Wave 0 | ⬜ pending |
| GET /api/recommendations/{id} returns artifact | 03 | 2 | P24-T03 | integration | same | Wave 0 | ⬜ pending |
| GET /api/recommendations list with filters | 03 | 2 | P24-T03 | integration | same | Wave 0 | ⬜ pending |
| PATCH approve sets analyst_approved=true | 04 | 2 | P24-T04 | integration | same | Wave 0 | ⬜ pending |
| Gate: approved_by required | 04 | 2 | P24-T04 | unit | same | Wave 0 | ⬜ pending |
| Gate: override_log required on low confidence | 04 | 2 | P24-T04 | unit | same | Wave 0 | ⬜ pending |
| Gate: expires_at must be future | 04 | 2 | P24-T04 | unit | same | Wave 0 | ⬜ pending |
| Gate: double-approval returns 409 | 04 | 2 | P24-T04 | unit | same | Wave 0 | ⬜ pending |
| Gate failures return 422 structured | 04 | 2 | P24-T04 | unit | same | Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_recommendation_model.py` — stubs for P24-T01, P24-T02 (new file)
- [ ] `tests/unit/test_recommendation_api.py` — stubs for P24-T03, P24-T04 (new file)

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
