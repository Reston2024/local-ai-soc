---
phase: 14-llmops-evaluation-investigation-ai-copilot
plan: "02"
subsystem: llmops
tags: [eval-harness, ollama, duckdb, httpx, asyncio, dataclass, keyword-recall, jsonl]

# Dependency graph
requires:
  - phase: 14-01
    provides: "Foundation-Sec-8B OLLAMA_CYBERSEC_MODEL wired into settings and OllamaClient"
provides:
  - "scripts/eval_models.py — standalone CLI eval harness for qwen3:14b vs foundation-sec:8b"
  - "EvalResult dataclass with prompt_type field for structured per-call result storage"
  - "score_response() keyword recall function (case-insensitive, 0.0-1.0)"
  - "data/eval_results.jsonl output schema with model, prompt_type, latency_ms, eval_count, keyword_recall"
  - "scripts/__init__.py enabling test imports from scripts package"
affects:
  - "14-03: Analysis of eval_results.jsonl to produce LLMOps decision data"
  - "14-04: Any prompt engineering work building on triage/summarise templates"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Direct httpx.AsyncClient POST to /api/generate to capture eval_count field (bypassing OllamaClient.generate() which discards token count)"
    - "sys.path.insert(0, project_root) pattern in scripts/ for importable backend/ modules"
    - "Dual-loop evaluation: rows × models × prompt_types produces rows*2*2 total calls"
    - "Ground truth keywords derived from event metadata: [event_type, attack_technique] for triage, [event_type, severity] for summarise"

key-files:
  created:
    - scripts/eval_models.py
    - scripts/__init__.py
  modified: []

key-decisions:
  - "14-02: Direct httpx POST to /api/generate (not OllamaClient.generate()) — necessary to read eval_count token field that generate() discards"
  - "14-02: Ground truth keywords for triage = [event_type, attack_technique]; for summarise = [event_type, severity]"
  - "14-02: Summary table sorted by (model, prompt_type) alphabetically for consistent output"
  - "14-02: Dry-run mode returns keyword_recall=1.0 and eval_count=0 placeholders — no HTTP calls"

patterns-established:
  - "Pattern: scripts/__init__.py + sys.path.insert(0, project_root) enables clean test imports of eval scripts"
  - "Pattern: EvalResult.prompt_id encodes row index and prompt type: 'row-{idx}-{prompt_type}'"

requirements-completed:
  - P14-T01

# Metrics
duration: 2min
completed: 2026-03-28
---

# Phase 14 Plan 02: LLM Eval Harness Summary

**Standalone eval CLI (eval_models.py) benchmarks qwen3:14b vs foundation-sec:8b on seeded SIEM events using triage and summarise prompts, writing per-call results to data/eval_results.jsonl with keyword recall scoring**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-28T11:49:10Z
- **Completed:** 2026-03-28T11:51:30Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2 created

## Accomplishments

- Implemented `EvalResult` dataclass with `prompt_type` field covering all 7 required fields
- Implemented `score_response()` with case-insensitive keyword recall (0.0-1.0, empty list returns 1.0)
- Built dual-prompt evaluation loop: rows × [qwen3:14b, foundation-sec:8b] × [triage, summarise]
- Direct httpx POST to `/api/generate` captures `eval_count` token field (OllamaClient.generate() discards it)
- `--dry-run --limit N` mode works without a running Ollama instance, writes 20 placeholder JSONL entries per 5 rows
- Markdown summary table groups results by `(model, prompt_type)` — 4 rows for 2 models × 2 prompt types
- `scripts/__init__.py` created to enable test imports from the `scripts` package
- All 8 tests in `tests/unit/test_eval_models.py` pass green

## Task Commits

Each task was committed atomically:

1. **Task 1: EvalResult, score_response, dual-prompt main harness** - `6591321` (feat)

**Plan metadata:** (docs commit follows)

_Note: Wave-0 RED test file already existed as a stub from plan 14-01; implementation turned it GREEN._

## Files Created/Modified

- `scripts/eval_models.py` — LLM eval harness CLI (357 lines): EvalResult dataclass, score_response(), _eval_one_row(), main()
- `scripts/__init__.py` — Empty package init enabling test imports

## Decisions Made

- **Direct httpx over OllamaClient.generate():** The plan specifies capturing `eval_count` (token count) from the raw Ollama JSON response. `OllamaClient.generate()` only returns the response text string, discarding the full JSON body. Direct httpx POST is necessary to read `eval_count`.
- **Ground truth keywords:** triage prompt uses `[event_type, attack_technique]`; summarise uses `[event_type, severity]`. Both filter out `None` and `"unknown"` values.
- **Table sort order:** `(model, prompt_type)` sorted alphabetically gives deterministic output — `foundation-sec:8b` before `qwen3:14b`, `summarise` before `triage`.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — the Wave-0 test stub from plan 14-01 already existed at `tests/unit/test_eval_models.py` with 8 tests. They were RED before implementation and turned GREEN after. A pre-existing failure in `test_investigation_chat.py::test_chat_messages_ddl_create_table` (event loop closed error) is unrelated to this plan and confirmed present on the baseline branch.

## User Setup Required

None — no external service configuration required. Dry-run mode works without Ollama running. Live mode requires Ollama with `qwen3:14b` and `foundation-sec:8b` loaded, and `seed_siem_data.py` run first to populate `normalized_events`.

## Next Phase Readiness

- `scripts/eval_models.py` is fully functional — run `uv run python scripts/eval_models.py --limit 10` with Ollama running to generate real benchmark data
- `data/eval_results.jsonl` schema: `{model, prompt_id, prompt_type, latency_ms, eval_count, keyword_recall, timestamp}`
- Plan 14-03 can consume the JSONL output for LLMOps decision analysis

---
*Phase: 14-llmops-evaluation-investigation-ai-copilot*
*Completed: 2026-03-28*
