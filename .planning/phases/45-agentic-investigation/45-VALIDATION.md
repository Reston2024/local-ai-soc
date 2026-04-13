---
phase: 45
slug: agentic-investigation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-12
---

# Phase 45 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (uv run pytest) |
| **Config file** | pyproject.toml — `pytest-asyncio` mode: auto |
| **Quick run command** | `uv run pytest tests/unit/test_agent_tools.py tests/unit/test_agent_runner.py tests/unit/test_agentic_api.py -x` |
| **Full suite command** | `uv run pytest tests/unit/ -x --tb=short` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_agent_tools.py tests/unit/test_agent_runner.py tests/unit/test_agentic_api.py -x`
- **After every plan wave:** Run `uv run pytest tests/unit/ -x --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 45-01-01 | 01 | 0 | P45-T01 | unit stub | `uv run pytest tests/unit/test_agent_tools.py -x` | ❌ W0 | ⬜ pending |
| 45-01-02 | 01 | 0 | P45-T02 | unit stub | `uv run pytest tests/unit/test_agent_runner.py -x` | ❌ W0 | ⬜ pending |
| 45-01-03 | 01 | 0 | P45-T03 | unit stub | `uv run pytest tests/unit/test_agentic_api.py -x` | ❌ W0 | ⬜ pending |
| 45-02-01 | 02 | 1 | P45-T01 | unit | `uv run pytest tests/unit/test_agent_tools.py::TestQueryEventsTool -x` | ❌ W0 | ⬜ pending |
| 45-02-02 | 02 | 1 | P45-T01 | unit | `uv run pytest tests/unit/test_agent_tools.py::TestGetEntityProfileTool -x` | ❌ W0 | ⬜ pending |
| 45-02-03 | 02 | 1 | P45-T01 | unit | `uv run pytest tests/unit/test_agent_tools.py::TestEnrichIpTool -x` | ❌ W0 | ⬜ pending |
| 45-02-04 | 02 | 1 | P45-T01 | unit | `uv run pytest tests/unit/test_agent_tools.py::TestSearchSigmaMatchesTool -x` | ❌ W0 | ⬜ pending |
| 45-02-05 | 02 | 1 | P45-T01 | unit | `uv run pytest tests/unit/test_agent_tools.py::TestGetGraphNeighborsTool -x` | ❌ W0 | ⬜ pending |
| 45-02-06 | 02 | 1 | P45-T01 | unit | `uv run pytest tests/unit/test_agent_tools.py::TestSearchSimilarIncidentsTool -x` | ❌ W0 | ⬜ pending |
| 45-03-01 | 03 | 2 | P45-T02 | unit | `uv run pytest tests/unit/test_agent_runner.py::test_build_agent -x` | ❌ W0 | ⬜ pending |
| 45-03-02 | 03 | 2 | P45-T05 | unit | `uv run pytest tests/unit/test_agent_runner.py::test_max_steps_limit -x` | ❌ W0 | ⬜ pending |
| 45-03-03 | 03 | 2 | P45-T05 | unit | `uv run pytest tests/unit/test_agent_runner.py::test_timeout_fires -x` | ❌ W0 | ⬜ pending |
| 45-04-01 | 04 | 3 | P45-T03 | unit | `uv run pytest tests/unit/test_agentic_api.py::test_agentic_endpoint_exists -x` | ❌ W0 | ⬜ pending |
| 45-04-02 | 04 | 3 | P45-T03 | unit | `uv run pytest tests/unit/test_agentic_api.py::test_agentic_sse_content_type -x` | ❌ W0 | ⬜ pending |
| 45-05-01 | 05 | 4 | P45-T04 | manual | See Manual-Only below | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_agent_tools.py` — 6 tool class stubs + mock DuckDB/Chroma fixtures (P45-T01)
- [ ] `tests/unit/test_agent_runner.py` — build_agent, max_steps, timeout stubs (P45-T02, P45-T05)
- [ ] `tests/unit/test_agentic_api.py` — endpoint exists, SSE content-type stubs (P45-T03)
- [ ] `uv add "smolagents[litellm]"` — smolagents not yet installed; Wave 0 installs this dependency

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| [Agent] tab appears in InvestigationView alongside [Summary] | P45-T04 | Browser UI — no headless test | Open investigation, verify two tabs render without breaking existing Summary tab |
| Streaming reasoning text appears between tool call cards | P45-T04 | Requires live Ollama + SSE stream | Click Run Agent, watch reasoning tokens appear between step cards |
| Verdict card pinned at bottom with TP/FP confirm buttons | P45-T04 | Browser UI — verdict layout | After run completes, verify verdict section at bottom with working confirm buttons |
| Partial results shown on 10-call limit with yellow banner | P45-T05 | Requires triggering the limit | Run against a complex detection until 10-call limit fires |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
