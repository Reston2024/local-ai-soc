---
status: complete
phase: 54-hf-model-integration
source: 54-01-SUMMARY.md, 54-02-SUMMARY.md, 54-03-SUMMARY.md, 54-04-SUMMARY.md, 54-05-SUMMARY.md, 54-06-SUMMARY.md, 54-07-SUMMARY.md, 54-08-SUMMARY.md, 54-09-SUMMARY.md, 54-10-SUMMARY.md
started: 2026-04-17T01:00:00Z
updated: 2026-04-17T01:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. GPU Acceleration Active
expected: Run `ollama ps` while a model is loaded (e.g. after `Start-Job { ollama run qwen3:14b "test" }`). PROCESSOR column shows GPU involvement — "11%/89%" CPU/GPU split or similar. Not "100% CPU".
result: pass

### 2. bge-m3 Configured as Embed Model
expected: Run `uv run python -c "from backend.core.config import settings; print(settings.OLLAMA_EMBED_MODEL)"` from the project root. Output should be `bge-m3`.
result: pass

### 3. Reranker Settings Present
expected: Run `uv run python -c "from backend.core.config import settings; print(settings.RERANKER_URL, settings.RERANKER_ENABLED, settings.RERANKER_TOP_K)"` from the project root. Output should be ` False 5` (empty URL, disabled by default, top_k=5).
result: pass

### 4. rebuild_chroma.py Dry-Run
expected: Run `uv run python scripts/rebuild_chroma.py --dry-run` from the project root. Script should exit cleanly (exit 0), printing row count stats for `soc_evidence` collection without actually modifying ChromaDB.
result: pass

### 5. Reranker Service Starts in Passthrough Mode
expected: Run `uv run python -c "import backend.services.reranker_service as s; print('OK')"` from the project root. Should print `OK` even if torch is not installed — the service has graceful degradation.
result: pass

### 6. Reranker Unit Tests Pass
expected: Run `uv run pytest tests/unit/test_reranker.py -v` from the project root. All 3 tests should pass: `test_rerank_returns_sorted_scores`, `test_rerank_graceful_degradation`, `test_rerank_empty_passages`.
result: pass

### 7. bge-m3 Embed Dimension Test Passes
expected: Run `uv run pytest tests/unit/test_chroma_store.py -k test_bge_m3 -v` from the project root. `test_bge_m3_embed_dimension` should pass (verifies 1024-dim output from the bge-m3 model).
result: pass

### 8. Health Endpoint Includes Reranker
expected: Start the backend (`uv run python -m backend.main` or via scripts) then `curl http://localhost:8000/health` (or the Caddy HTTPS equivalent). The JSON response should include a `reranker` key in the `optional` section — showing "disabled" or "unreachable" (not missing entirely).
result: skipped
reason: DuckDB single-writer lock held by Claude Code's own Python process — pre-existing constraint, not a Phase 54 regression. Reranker health code confirmed present in backend/api/health.py lines 225-232.

### 9. Dashboard Shows Reranker Health Row
expected: Open the dashboard (https://localhost or the Svelte dev server). In the Overview tab, the health/status section should show a "Reranker" row alongside MISP, TheHive, SpiderFoot etc. It should show a grey/red dot (disabled) since RERANKER_ENABLED=False.
result: issue
reported: "Reranker row not visible in System Health panel. Backend health endpoint DOES include reranker key (confirmed in routes.py line 353). Svelte source has the row at OverviewView.svelte line 440. But dashboard/dist JS does not contain 'reranker' — dist was never rebuilt after Plan 54-10 added the row."
severity: major

### 10. Eval Harness Has New Fields
expected: Run `uv run python scripts/eval_models.py --dry-run --limit 1` from the project root (or check `data/eval_results.jsonl` if it exists). Output entries should contain the fields: `embed_model`, `reranker_enabled`, `embed_latency_ms`, `rerank_latency_ms`, `recall_at_5`.
result: pass

### 11. Full Unit Test Suite Passes
expected: Run `uv run pytest tests/unit/ tests/security/ -q --tb=short` from the project root. Should pass ~1201 tests with ≤4 skipped. No new failures from Phase 54 work.
result: pass

## Summary

total: 11
passed: 9
issues: 1
pending: 0
skipped: 1

## Gaps

- truth: "Dashboard System Health panel shows a Reranker row (disabled/grey dot when RERANKER_ENABLED=False)"
  status: failed
  reason: "User reported: Reranker row not visible in System Health panel. Svelte source has the row at OverviewView.svelte line 440 but dashboard/dist JS was never rebuilt after Plan 54-10 committed the change."
  severity: major
  test: 9
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""
