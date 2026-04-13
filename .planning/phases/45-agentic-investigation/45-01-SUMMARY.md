---
phase: 45-agentic-investigation
plan: "01"
subsystem: agentic-investigation
tags: [smolagents, tdd, wave-0, stubs, litellm]
dependency_graph:
  requires: []
  provides: [agent-tools-test-contracts, agent-runner-test-contracts, agentic-api-test-contracts]
  affects: [45-02, 45-03, 45-04]
tech_stack:
  added: [smolagents==1.24.0, litellm==1.83.0]
  patterns: [importorskip-tdd-stubs]
key_files:
  created:
    - tests/unit/test_agent_tools.py
    - tests/unit/test_agent_runner.py
    - tests/unit/test_agentic_api.py
  modified:
    - pyproject.toml
    - uv.lock
decisions:
  - "importorskip pattern used for all Phase 45 stubs (matches Phase 44/42/43 pattern)"
  - "smolagents[litellm]==1.24.0 installed; litellm routes agent to Ollama via LiteLLMModel"
  - "12 stubs total: 7 tool stubs, 3 runner stubs, 2 API stubs — all SKIP until source modules exist"
metrics:
  duration_minutes: 8
  completed_date: "2026-04-13T03:23:10Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 2
---

# Phase 45 Plan 01: TDD Wave 0 Stubs Summary

**One-liner:** smolagents[litellm]==1.24.0 installed + 12 TDD stubs across 3 test files using importorskip pattern for Phase 45 agentic investigation contracts.

## What Was Done

### Task 1: Install smolagents[litellm]
- Ran `uv add "smolagents[litellm]"` — installed smolagents==1.24.0, litellm==1.83.0, openai==2.31.0 and transitive deps
- Verified: `from smolagents import ToolCallingAgent, LiteLLMModel, Tool` prints OK
- Commit: 4d372db

### Task 2: TDD Wave 0 Stubs
Created 3 test files matching the established importorskip pattern from Phase 44:

**tests/unit/test_agent_tools.py** (7 stubs, 6 tool classes):
- TestQueryEventsTool: test_returns_string, test_hostname_filter
- TestGetEntityProfileTool: test_returns_string
- TestEnrichIpTool: test_returns_string
- TestSearchSigmaMatchesTool: test_returns_string
- TestGetGraphNeighborsTool: test_returns_string
- TestSearchSimilarIncidentsTool: test_returns_string

**tests/unit/test_agent_runner.py** (3 stubs):
- test_build_agent: ToolCallingAgent with 6 tools
- test_max_steps_limit: max_steps == 10
- test_timeout_fires: TimeoutError on short timeout

**tests/unit/test_agentic_api.py** (2 stubs):
- test_agentic_endpoint_exists: /agentic route registered
- test_agentic_sse_content_type: returns text/event-stream

All 12 stubs SKIP cleanly (not ERROR, not FAIL) when source modules absent.
Commit: c804dfe

## Verification

```
1081 passed, 15 skipped, 9 xfailed, 7 xpassed, 8 warnings in 30.41s
```

- 1081 existing tests remain GREEN (zero regressions)
- 12 new stubs all SKIP cleanly
- smolagents + litellm importable

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- tests/unit/test_agent_tools.py: FOUND
- tests/unit/test_agent_runner.py: FOUND
- tests/unit/test_agentic_api.py: FOUND
- Commit 4d372db: FOUND
- Commit c804dfe: FOUND
