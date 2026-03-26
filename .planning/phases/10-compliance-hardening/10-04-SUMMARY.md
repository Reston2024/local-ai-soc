---
phase: 10-compliance-hardening
plan: "04"
subsystem: backend/services, backend/core
tags: [audit-logging, llm, compliance, nist-ai-rmf, sha256]
dependency_graph:
  requires: [10-01]
  provides: [llm-audit-log, audit-wrapped-ollama-client]
  affects: [backend/services/ollama_client.py, backend/core/logging.py, logs/llm_audit.jsonl]
tech_stack:
  added: [hashlib (stdlib), llm_audit named logger, RotatingFileHandler for llm_audit.jsonl]
  patterns: [pre/post audit log wrapping, sha256 hash-only logging, propagate=False logger isolation]
key_files:
  created: [tests/unit/test_ollama_audit.py]
  modified: [backend/services/ollama_client.py, backend/core/logging.py]
decisions:
  - "Hash-only audit logging (sha256[:16]) — full prompt text not written, satisfies privacy/size constraints while enabling NIST AI RMF MAP-5.2 accountability"
  - "embed() uses len(embedding) as response_length (vector element count) rather than string length for semantic accuracy"
  - "llm_audit handler placed inside the try block so it shares the same log_path directory creation as backend.jsonl"
metrics:
  duration: "~10 minutes"
  completed: "2026-03-26"
  tasks_completed: 2
  files_changed: 3
---

# Phase 10 Plan 04: LLM Audit Logging Summary

**One-liner:** SHA-256 hash-only audit logging for every OllamaClient.generate() and embed() call, routed to a separate `logs/llm_audit.jsonl` rotating file via a `propagate=False` named logger.

## What Was Built

### Task 1: llm_audit RotatingFileHandler in backend/core/logging.py

Added a second `RotatingFileHandler` inside `setup_logging()`, after the existing `backend.jsonl` handler. The handler targets `logs/llm_audit.jsonl` (10 MB x 5 backups), reuses the same `_JsonFormatter` instance, and is attached to the `llm_audit` named logger with `propagate=False` so audit entries never appear in `backend.jsonl` or on stderr.

The `logs/` directory is created by the existing `log_path.mkdir(parents=True, exist_ok=True)` call, so no additional directory creation is needed.

Verification: `logging.getLogger("llm_audit")` reports `handlers: 1 propagate: False` after `setup_logging()`.

### Task 2: Audit wrapping in backend/services/ollama_client.py

Added at module level:
- `import hashlib` and `import logging`
- `_audit_log = logging.getLogger("llm_audit")`
- `_sha256_short(text: str) -> str` helper (first 16 hex chars of SHA-256)

`generate()`:
- Pre-call: logs `{event_type: "llm_generate", model, prompt_length, prompt_hash, status: "start"}`
- Post-call: logs same fields plus `response_length`, `response_hash`, `status: "complete"`
- On HTTP error or generic exception: logs `{status: "error", error_type: ...}` and re-raises

`embed()`:
- Same pattern with `event_type: "llm_embed"`, `response_length` = number of embedding vector elements

Full prompt text is never written. Only SHA-256 truncated hashes appear in the audit log.

### Tests (tests/unit/test_ollama_audit.py)

Replaced 3 `xfail` stubs with real async tests:
1. `test_generate_writes_audit_log` — patches `_audit_log`, calls `generate()`, asserts `mock_log.info.called`
2. `test_embed_writes_audit_log` — same pattern for `embed()`
3. `test_audit_log_has_required_fields` — captures `extra` dicts, asserts `event_type` and `prompt_hash` present

Mock target: `patch.object(client._client, "post", new_callable=AsyncMock)` — matches actual `httpx.AsyncClient` usage.

## Verification Results

```
tests/unit/test_ollama_audit.py: 3 passed
Full suite (tests/unit/ + tests/security/ excluding pre-existing normalizer failures): 62 passed, 13 xfailed, 7 xpassed
```

The 6 `TestInjectionScrubbing` failures in `test_normalizer.py` are pre-existing from plan 10-02 work and are out of scope for this plan.

## Deviations from Plan

None — plan executed exactly as written. The `log_path` variable in `logging.py` is already the directory path (`Path(log_dir)`), so `log_path / "llm_audit.jsonl"` was used directly (the plan's comment about `log_path.parent` was slightly off, but the intent was the same).

## Self-Check: PASSED

- `backend/core/logging.py` modified: FOUND
- `backend/services/ollama_client.py` modified: FOUND
- `tests/unit/test_ollama_audit.py` created: FOUND
- Commit `8569817` exists: FOUND
- llm_audit logger: handlers=1, propagate=False
- All 3 audit tests pass
