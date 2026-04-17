---
phase: 54
slug: hf-model-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-16
---

# Phase 54 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` (pytest-asyncio mode: auto) |
| **Quick run command** | `uv run pytest tests/unit/test_reranker.py tests/unit/test_chroma_store.py -x -q` |
| **Full suite command** | `uv run pytest tests/unit/ tests/security/ -q --tb=short` |
| **Estimated runtime** | ~30 seconds (unit); ~90 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_reranker.py -x -q`
- **After Wave 1 (GPU):** Run `ollama ps` and verify GPU Layers > 0
- **After Wave 2 (bge-m3):** Run embed smoke test, verify 1024-dim output
- **After Wave 3 (reranker):** Run reranker integration test against live service
- **End of phase:** Full suite + eval harness comparison

---

## Per-Task Verifications

### Wave 1 — Ollama GPU Migration

| # | Test | Method | Pass Condition |
|---|------|--------|----------------|
| W1-1 | GPU env var set system-wide | `[System.Environment]::GetEnvironmentVariable("CUDA_VISIBLE_DEVICES","Machine")` | Returns `"0"` |
| W1-2 | Ollama service using GPU | `ollama ps` during active inference | `GPU Layers > 0` shown |
| W1-3 | nvidia-smi shows utilization | `nvidia-smi dmon -s u -d 1 -c 5` during `ollama run qwen3:14b "test"` | GPU util > 0% |
| W1-4 | TTFT improved | Time `curl` to `/api/generate` before/after | TTFT < 30s (was ~300s) |
| W1-5 | Existing LLM calls unaffected | `uv run pytest tests/unit/ -q` | All pass, no regressions |

### Wave 2 — bge-m3 Embedding Upgrade

| # | Test | Method | Pass Condition |
|---|------|--------|----------------|
| W2-1 | bge-m3 pulled to Ollama | `ollama list` | `bge-m3` present |
| W2-2 | OLLAMA_EMBED_MODEL updated | `cat .env \| grep EMBED` | `OLLAMA_EMBED_MODEL=bge-m3` |
| W2-3 | Embedding dimension correct | Embed test string, check len | 1024 dimensions |
| W2-4 | ChromaDB collections rebuilt | `uv run python scripts/rebuild_chroma.py` | No errors, record count > 0 |
| W2-5 | RAG query returns results | POST `/api/query` with test query | Non-empty results, no 500 |
| W2-6 | Unit tests pass | `uv run pytest tests/unit/test_chroma_store.py -q` | All pass |

### Wave 3 — bge-reranker-v2-m3 Microservice

| # | Test | Method | Pass Condition |
|---|------|--------|----------------|
| W3-1 | Reranker service starts | `curl http://127.0.0.1:8100/health` | `{"status": "ok"}` |
| W3-2 | Reranker scores are plausible | POST `/rerank` with query + 5 passages | Scores in [-10, 10], sorted desc |
| W3-3 | Top result is semantically best | Known query + shuffled passages | Best passage ranked #1 |
| W3-4 | RERANKER_URL config works | Set `RERANKER_URL=` (empty), run RAG | Graceful passthrough, no error |
| W3-5 | Reranker unit tests | `uv run pytest tests/unit/test_reranker.py -q` | All pass |
| W3-6 | Backend integration test | POST `/api/query` with reranker enabled | Results returned, latency < 10s |

### Wave 4 — Eval Harness Integration

| # | Test | Method | Pass Condition |
|---|------|--------|----------------|
| W4-1 | Eval harness runs | `uv run python scripts/eval_models.py` | Completes without error |
| W4-2 | Additive fields present | Check `data/eval_results.jsonl` entries | `embed_model`, `reranker_enabled` fields present |
| W4-3 | bge-m3 recall ≥ mxbai baseline | Compare eval scores | Top-5 recall ≥ baseline or within 5% |
| W4-4 | Reranker improves MRR | MRR with/without reranker | MRR with reranker ≥ MRR without |

---

## Manual-Only Verifications (require live hardware)

| # | Verification | How to Check |
|---|-------------|--------------|
| M1 | nvidia-smi shows RTX 5080 during inference | `nvidia-smi dmon` in separate terminal during `ollama run` |
| M2 | VRAM usage visible | `nvidia-smi` shows memory used > 0 MB during inference |
| M3 | Reranker GPU utilization | `nvidia-smi` during reranker scoring shows GPU util |
| M4 | Dashboard RAG responses visibly better | Analyst subjective: investigation summaries more relevant |

---

## Regression Gate

Before marking Phase 54 complete, the full test suite must pass:

```powershell
uv run pytest tests/unit/ tests/security/ -q --tb=short --cov=backend --cov-fail-under=70
```

No regressions in:
- `tests/unit/test_chroma_store.py`
- `tests/security/` (all auth + injection tests)
- `tests/sigma_smoke/` (Sigma parse tests)
