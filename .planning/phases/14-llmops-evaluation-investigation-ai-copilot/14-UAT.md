---
status: resolved
phase: 14-llmops-evaluation-investigation-ai-copilot
source: [14-01-SUMMARY.md, 14-02-SUMMARY.md, 14-03-SUMMARY.md, 14-04-SUMMARY.md, 14-05-SUMMARY.md, 14-06-SUMMARY.md]
started: 2026-03-28T15:05:00Z
updated: 2026-03-28T18:30:00Z
---

## Current Test

complete: true

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running backend. Run `uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000`. Server boots without errors. Logs show "timeline router mounted" and "chat router mounted". GET /health returns 200 with duckdb/chroma/sqlite ok.
result: pass

### 2. Eval Harness Dry-Run
expected: Run `uv run python scripts/eval_models.py --dry-run --limit 5`. Script runs without errors, prints a markdown table with 4 rows (foundation-sec:8b/summarise, foundation-sec:8b/triage, qwen3:14b/summarise, qwen3:14b/triage). Creates data/eval_results.jsonl with 20 placeholder entries (5 rows × 2 models × 2 prompt types).
result: pass
note: Fixed by plan 14-06 (commit b6e8452). DuckDBStore init now guarded behind else-branch; dry-run generates synthetic rows. Verified: 4-row table printed, 20 JSONL entries written, 10 unit tests pass.

### 3. LLMOps KPI Fields in Metrics Endpoint
expected: With the backend running, call GET http://127.0.0.1:8000/api/metrics/kpis. The JSON response includes three new LLMOps fields: `total_llm_calls` (int), `avg_latency_ms_per_model` (object), and `error_rate` (float between 0 and 1).
result: pass

### 4. Investigation Timeline API
expected: Call GET http://127.0.0.1:8000/api/investigations/1a73989a-4263-44dc-a45e-31202e5516da/timeline. Returns 200 with JSON body `{"items": [...], "total": N}`. Even if items is empty, the shape is correct (no 404, no 500).
result: pass

### 5. InvestigationView Two-Panel Layout
expected: Open http://localhost:5173/app/ (frontend running). Click "Investigate →" on any detection. The view switches to show two panels side-by-side: left panel titled "Evidence Timeline" with a Refresh button, right panel titled "AI Copilot" with "foundation-sec:8b" label, a textarea, and a Send button.
result: pass
note: Chrome showed ERR_SSL_PROTOCOL_ERROR (HSTS forcing HTTPS on localhost — not a code bug). DOM verified programmatically via browser automation: both panels confirmed with correct headings, buttons, and labels.

### 6. AI Copilot Send + Stop Flow
expected: In the AI Copilot panel, type any question and click Send. Immediately after clicking Send, the Send button is replaced by a "Stop" button (while streaming is active). After the stream ends (Ollama offline = near-instant), the Send button returns. The chat area shows a "Copilot" response bubble (may be empty if Ollama is offline).
result: pass
note: POST /chat → 200 OK confirmed. 5 "You" bubbles + Copilot label in DOM. Send button restored after stream. Stop button swap confirmed in 14-05 checkpoint (step 9); too fast to catch programmatically when Ollama is offline (near-instant EOF).

### 7. Chat History Persistence + Reload
expected: After sending a message in the AI Copilot, navigate away (click Detections) then click "Investigate →" on the same detection again. The previously sent message reappears as a "You" bubble in the chat history — confirming persistence to SQLite and reload via GET /api/investigations/{id}/chat/history.
result: pass
note: 5 messages confirmed in SQLite via GET /chat/history. Navigated to Detections and back — 5 "You" bubbles reloaded in DOM on mount.

### 8. LLMOps Telemetry Table Exists
expected: The llm_calls DuckDB table is created on startup. Verify via API or direct DB access: the table exists in data/events.duckdb with columns call_id, called_at, model, endpoint, prompt_chars, completion_chars, latency_ms, success, error_type. (Skip if you prefer not to inspect DB directly — the metrics KPI fields in Test 3 confirm it indirectly.)
result: pass
note: All 9 columns confirmed in duckdb_store.py DDL (lines 74-82). KPI endpoint returns total_llm_calls=0 (Ollama offline, no calls logged yet). Direct DB read blocked by backend write lock — schema verified via source.

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0

## Gaps

- truth: "uv run python scripts/eval_models.py --dry-run --limit 5 runs without errors and prints a 4-row markdown table"
  status: resolved
  reason: "DuckDB IOException: File already open — DuckDBStore() instantiated unconditionally on line 274 even in --dry-run mode, conflicts with backend holding file lock"
  severity: major
  test: 2
  fix: "plan 14-06 (commit b6e8452) — DuckDBStore init moved to else-branch; dry-run generates synthetic _DRY_RUN_ROW tuples instead of querying DB"
  resolved_at: "2026-03-28T18:30:00Z"
