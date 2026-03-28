---
phase: 14
slug: llmops-evaluation-investigation-ai-copilot
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-27
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (Python) + uv run pytest |
| **Config file** | pyproject.toml (pytest-asyncio mode: auto) |
| **Quick run command** | `uv run pytest tests/unit/ -x -q` |
| **Full suite command** | `uv run pytest -x -q` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/ -x -q`
- **After every plan wave:** Run `uv run pytest -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 1 | P14-T01 | unit | `uv run pytest tests/unit/test_eval_models.py -x -q` | ❌ W0 | ⬜ pending |
| 14-02-01 | 02 | 2 | P14-T02 | unit | `uv run pytest tests/unit/test_ollama_client.py -x -q` | ✅ | ⬜ pending |
| 14-02-02 | 02 | 2 | P14-T02 | unit | `uv run pytest tests/unit/test_metrics_service.py -x -q` | ✅ | ⬜ pending |
| 14-03-01 | 03 | 3 | P14-T03 | unit | `uv run pytest tests/unit/test_investigation_timeline.py -x -q` | ❌ W0 | ⬜ pending |
| 14-03-02 | 03 | 3 | P14-T03 | manual | Open browser → InvestigationView timeline renders | — | ✅ green |
| 14-04-01 | 04 | 4 | P14-T04 | unit | `uv run pytest tests/unit/test_investigation_chat.py -x -q` | ❌ W0 | ⬜ pending |
| 14-04-02 | 04 | 4 | P14-T04 | manual | Open browser → AI Copilot streams tokens in real time | — | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_eval_models.py` — stubs for P14-T01 (eval harness output schema)
- [ ] `tests/unit/test_investigation_timeline.py` — stubs for P14-T03 (timeline endpoint response shape)
- [ ] `tests/unit/test_investigation_chat.py` — stubs for P14-T04 (chat endpoint SSE response)

*Existing test files (test_ollama_client.py, test_metrics_service.py) cover P14-T02 extensions — no Wave 0 stubs needed for those.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Investigation timeline renders with colour-coded severity rows | P14-T03 | Svelte visual rendering requires browser | Open http://localhost:5173, navigate to any investigation, verify vertical timeline appears |
| AI Copilot streams tokens in real time | P14-T04 | SSE streaming in browser requires visual confirmation | Click "Ask Copilot" in InvestigationView, type question, verify tokens appear progressively |
| Stop button halts generation | P14-T04 | Requires interaction | Click stop mid-stream, verify stream terminates |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
