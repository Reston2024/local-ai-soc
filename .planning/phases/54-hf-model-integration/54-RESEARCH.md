# Phase 54 Research: HF Model Integration — GPU + Embeddings + Reranker

**Researched:** 2026-04-16
**Domain:** Ollama GPU acceleration (Windows/CUDA), bge-m3 embeddings, bge-reranker-v2-m3 cross-encoder, FastAPI microservice, RAG pipeline integration
**Confidence:** HIGH (existing codebase patterns are clear; CUDA + HF on Windows has known gotchas documented below)

---

## Summary

Phase 54 upgrades three layers of the RAG pipeline: move Ollama inference from CPU to the RTX 5080 GPU (CUDA 13.1), replace `mxbai-embed-large` with `BAAI/bge-m3` for higher-quality embeddings, and add a `bge-reranker-v2-m3` cross-encoder microservice between ChromaDB retrieval and LLM inference. All three are independent deliverables that must be executed in dependency order: GPU first (so bge-m3 embeds quickly), embeddings second (ChromaDB collection must be rebuilt due to semantic space change), reranker third (inserts into the existing RAG flow). The reranker cannot be served via Ollama and requires a dedicated FastAPI microservice using HuggingFace `transformers` with CUDA, running on the same Windows desktop GPU.

---

## 1. Ollama GPU Migration

### Current State

Ollama 0.18.2 is installed as a Windows service via winget. The RTX 5080 (16GB VRAM, CUDA 13.1) is present but `ollama ps` shows 0 GPU layers — meaning all inference runs on CPU. The primary cause on Windows is that Ollama requires `CUDA_VISIBLE_DEVICES` to be set as a **system-level environment variable** (not session-level), and the Ollama Windows service does not inherit user-session environment variables.

### Steps to Force GPU

**Step 1.** Set system environment variables (not user-level) via PowerShell (run as Administrator):
```powershell
[System.Environment]::SetEnvironmentVariable("CUDA_VISIBLE_DEVICES", "0", "Machine")
[System.Environment]::SetEnvironmentVariable("OLLAMA_GPU_OVERHEAD", "0", "Machine")
```
Do NOT set `OLLAMA_HOST=0.0.0.0` at system scope — this conflicts with `backend/core/config.py`'s `normalize_ollama_host` validator which already handles the conversion correctly for the Python client.

**Step 2.** Restart the Ollama Windows service after setting env vars:
```powershell
Stop-Service -Name "Ollama"
Start-Service -Name "Ollama"
```

**Step 3.** Verify GPU layers:
```powershell
ollama ps
```
Look for `GPU Layers` > 0 in the output. A value of 0 means CPU-only.

**Step 4 (alternative).** If service restart does not pick up env vars, reinstall via winget:
```powershell
winget uninstall Ollama.Ollama
# Set system env vars first (step 1 above)
winget install Ollama.Ollama
```
The installer registers a new service that inherits the current system env vars at install time.

**Step 5.** Validate GPU utilization during inference:
```powershell
# Terminal 1:
ollama run qwen3:14b "Explain T1059 in one sentence"
# Terminal 2 simultaneously:
nvidia-smi dmon -s u -d 1
```
GPU utilization should spike to 30–80%+ during token generation. If it stays at 0%, the GPU is not being used.

### CUDA Version Note

CUDA 13.1 is the **maximum supported CUDA version** reported by the RTX 5080 driver, not the CUDA Toolkit version installed. As of April 2026, the latest public CUDA SDK is 12.x. Ollama uses its own bundled CUDA runtime (not the system toolkit), so this is not a problem — Ollama 0.18.2 bundles a CUDA 12.x runtime internally. `CUDA_VISIBLE_DEVICES=0` is all that is needed for driver-level visibility.

### Verification Command Set

```powershell
ollama ps                          # confirm GPU layers > 0
nvidia-smi                         # confirm GPU is recognized
nvidia-smi dmon -s u -d 1         # monitor utilization live
curl http://127.0.0.1:11434/api/tags  # confirm Ollama API up
```

---

## 2. bge-m3 Embedding Upgrade

### Model Details

- **Ollama model name:** `bge-m3` (maps to `BAAI/bge-m3` on HuggingFace Hub)
- **Pull command:** `ollama pull bge-m3`
- **Embedding dimension:** **1024** (same as `mxbai-embed-large` which is also 1024)
- **Key capability over mxbai-embed-large:** bge-m3 supports dense retrieval, sparse retrieval (BM25-style), and multi-vector (ColBERT-style) retrieval in one model. For the current ChromaDB dense-vector setup, the dense output (1024-dim) is used — this is the default via Ollama's `/api/embeddings` endpoint.

### Dimension Compatibility

Both `mxbai-embed-large` and `bge-m3` produce **1024-dimensional** vectors. This means the ChromaDB collection schema does **not** need to change. However, the **semantic space is different** — existing vectors embedded with `mxbai-embed-large` are incompatible with new bge-m3 query vectors (cosine similarity across different model spaces is meaningless). The collection must be **re-embedded from scratch**.

### ChromaDB Collection Rebuild Strategy

The `soc_evidence` collection (and `feedback_verdicts` collection from Phase 44) must be rebuilt:

1. Delete the existing collections via `ChromaStore.delete_collection(name, _admin_override=True)`.
2. Re-create with new model metadata: `get_or_create_collection(DEFAULT_COLLECTION, metadata={"embed_model": "bge-m3", "hnsw:space": "cosine"})`.
3. Re-embed all stored events by re-running the ingestion pipeline — `ingestion/loader.py` calls `ollama_client.embed()` which uses `self.embed_model` from settings. Updating `.env` is sufficient to switch the model.
4. The `feedback_verdicts` Chroma collection (Phase 44) must also be rebuilt. It uses the same Ollama embeddings client — updating the env var handles it on the next write.

**Migration risk:** If the GMKtec ChromaDB instance has large collections, deletion + re-ingestion may take time. Plan for a maintenance window or run re-ingestion as a background job while keeping the old collection alive under a temporary name.

### .env Change

```ini
OLLAMA_EMBED_MODEL=bge-m3
```

The existing `backend/core/config.py` `OLLAMA_EMBED_MODEL` setting and `OllamaClient.embed_model` field handle this change with no code modification — it is purely a config change.

### Verify New Embeddings

```powershell
# Quick sanity check via curl:
curl http://127.0.0.1:11434/api/embeddings `
  -d '{"model": "bge-m3", "prompt": "test"}' | python -m json.tool
# Count elements in .embedding array — should be 1024
```

Or in Python:
```python
import httpx, json
r = httpx.post("http://127.0.0.1:11434/api/embeddings",
               json={"model": "bge-m3", "prompt": "test"})
vec = r.json()["embedding"]
assert len(vec) == 1024, f"Expected 1024, got {len(vec)}"
```

---

## 3. bge-reranker-v2-m3 Reranker Service

### Why Not Ollama

Ollama is a **generative model server** — it serves decoder-only or encoder-decoder models for text generation and embedding. Cross-encoder rerankers like `BAAI/bge-reranker-v2-m3` require running a **classification head** (a single linear layer on top of a BERT-style encoder) over a (query, passage) pair. Ollama has no support for this inference pattern. The model must be served via HuggingFace `transformers` directly.

### Python Packages Required

Add to `pyproject.toml` `[project.dependencies]`:
```
transformers>=4.40.0
torch>=2.3.0
sentence-transformers>=3.0.0
```

**Critical on Windows:** `torch` from PyPI defaults to CPU-only. The CUDA-enabled wheel must be requested from the PyTorch index:
```powershell
uv add torch --extra-index-url "https://download.pytorch.org/whl/cu121"
uv add transformers sentence-transformers
```

With uv, `--extra-index-url` can also be set in `pyproject.toml`:
```toml
[tool.uv]
extra-index-url = ["https://download.pytorch.org/whl/cu121"]
```

Verify CUDA is available after install:
```python
import torch; print(torch.cuda.is_available())  # must print True
```

### FastAPI Microservice Design

Create `backend/services/reranker/` as a self-contained mini-service:

**`backend/services/reranker/service.py`** — FastAPI app:

```python
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

MODEL_NAME = "BAAI/bge-reranker-v2-m3"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
model.eval()
device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)

app = FastAPI()

class RerankRequest(BaseModel):
    query: str
    passages: list[str]
    top_n: int = 10

class RerankResponse(BaseModel):
    scores: list[float]        # raw logit scores, parallel to passages
    ranked_indices: list[int]  # indices sorted descending by score

@app.post("/rerank", response_model=RerankResponse)
def rerank(req: RerankRequest):
    pairs = [[req.query, p] for p in req.passages]
    with torch.no_grad():
        inputs = tokenizer(
            pairs, padding=True, truncation=True,
            max_length=512, return_tensors="pt"
        ).to(device)
        scores = model(**inputs, return_dict=True).logits.view(-1).float()
    score_list = scores.cpu().tolist()
    ranked = sorted(range(len(score_list)), key=lambda i: score_list[i], reverse=True)
    return RerankResponse(scores=score_list, ranked_indices=ranked[:req.top_n])
```

**Run command:**
```powershell
uv run uvicorn backend.services.reranker.service:app --host 127.0.0.1 --port 8100
```

**Settings additions** to `backend/core/config.py`:
```python
RERANKER_URL: str = ""           # empty = reranker disabled (graceful degradation)
RERANKER_TOP_N: int = 5          # return top N after reranking
RERANKER_CHROMA_K: int = 20      # ChromaDB fetch size when reranker enabled
```

### Async Integration Pattern

The reranker service runs blocking GPU inference. The FastAPI backend calls it via `httpx.AsyncClient`:

```python
async def rerank_passages(
    query: str,
    passages: list[str],
    reranker_url: str,
    top_n: int = 5,
) -> list[int]:
    """Return indices of top-N passages sorted by reranker score.
    Returns [0..n-1] as passthrough if reranker unavailable."""
    if not reranker_url or not passages:
        return list(range(min(top_n, len(passages))))
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{reranker_url}/rerank",
                json={"query": query, "passages": passages, "top_n": top_n},
            )
            resp.raise_for_status()
            return resp.json()["ranked_indices"]
    except Exception:
        log.warning("Reranker unavailable — using original ChromaDB order")
        return list(range(min(top_n, len(passages))))
```

This follows the project's async pattern: `httpx.AsyncClient` for external HTTP calls, graceful degradation on failure, no blocking calls in the async event loop.

---

## 4. RAG Pipeline Integration

### Existing Pipeline Flow

The current RAG flow in this codebase:

1. User query arrives at an API endpoint (`POST /api/query/ask`, `POST /api/investigate`)
2. `ollama_client.embed(query)` → query vector
3. `chroma_store.query(collection, [query_vector], n_results=K)` → top-K passages (documents + metadatas)
4. Passages concatenated into prompt context
5. `ollama_client.generate(prompt)` or `stream_generate_iter(prompt)` → LLM response

### Insertion Point

The reranker inserts between steps 3 and 4:

```
3.   ChromaDB returns top-K candidates (K = RERANKER_CHROMA_K = 20)
3.5  [NEW] POST /rerank with (query, passages) → ranked_indices
3.6  [NEW] Filter and reorder passages to ranked_indices, take top RERANKER_TOP_N
4.   Build prompt from reranked top-N passages
5.   LLM generate
```

**Key parameter change:** ChromaDB initial retrieval `n_results` should increase from the current value (likely 5–10) to `RERANKER_CHROMA_K=20` when the reranker is enabled, to give the reranker a meaningful candidate pool. The reranker then reduces to `RERANKER_TOP_N=5`.

### Config Flags for Graceful Degradation

When `RERANKER_URL=""` (default), the reranking step is skipped entirely — `rerank_passages()` returns the first `top_n` indices unchanged. The RAG pipeline behaves identically to today. This is the graceful degradation path.

### Files to Modify

| File | Change |
|------|--------|
| `backend/core/config.py` | Add `RERANKER_URL`, `RERANKER_TOP_N`, `RERANKER_CHROMA_K` settings |
| `backend/api/query.py` | Add reranking step between ChromaDB query and prompt build |
| `backend/api/investigate.py` | Same insertion if it has a RAG retrieval path |
| `backend/services/reranker/service.py` | New file — reranker microservice |
| `backend/services/reranker/__init__.py` | New empty file |

The `ChromaStore` class (`backend/stores/chroma_store.py`) does not need modification — it already accepts `n_results` as a parameter on `query()`.

---

## 5. Evaluation & Measurement

### Phase 14 Harness Context

The harness is `scripts/eval_models.py`, writing to `data/eval_results.jsonl`. Each record contains `latency_ms` and `keyword_recall` (substring match of ground-truth tokens in LLM response). This is the established baseline format.

### Measurement Plan for Phase 54

**Deliverable 1 — GPU migration:**
- Before: run `scripts/eval_models.py` on CPU (baseline `latency_ms` per prompt)
- After: re-run same script on GPU — measure TTFT (time-to-first-token) improvement
- Target: TTFT should drop from ~30–60s (CPU qwen3:14b) to ~3–8s (GPU)
- Tool: `ollama ps` shows GPU layers; `nvidia-smi dmon` shows live GPU utilization during evaluation

**Deliverable 2 — bge-m3 embeddings:**
- Retrieval quality: run the same set of RAG queries before and after. Compare top-3 ChromaDB results for relevance (manual spot-check of 10 queries targeting known security events)
- Embed latency: time a single `ollama_client.embed()` call before/after GPU migration (bge-m3 on GPU should be <100ms for a 512-token input vs ~500ms on CPU)
- Dimension sanity: assert `len(embedding) == 1024`
- Collection integrity: `chroma_store.count("soc_evidence")` > 0 after re-ingestion

**Deliverable 3 — Reranker:**
- Reranking accuracy test: issue a query that currently returns a borderline-relevant document at position 1. Verify reranker promotes the more relevant document to position 1.
- Passthrough test: confirm that with `RERANKER_URL=""`, the pipeline returns original ChromaDB order unchanged.
- Latency budget: measure added latency from reranker HTTP call. Target: <200ms for 20 passages on GPU.

**Extended eval_results.jsonl fields** to add for Phase 54 (additive, not replacing existing fields):
```json
{
  "model": "qwen3:14b",
  "embed_model": "bge-m3",
  "reranker_enabled": true,
  "prompt_id": "row-42",
  "latency_ms": 1240,
  "embed_latency_ms": 85,
  "rerank_latency_ms": 142,
  "keyword_recall": 0.82,
  "timestamp": "2026-04-16T14:00:00Z"
}
```

---

## 6. Windows / CUDA Gotchas

### 1. PyTorch CUDA Wheel Selection

`pip install torch` or `uv add torch` on Windows installs CPU-only by default. Must specify:
```powershell
uv add torch --extra-index-url "https://download.pytorch.org/whl/cu121"
```
Verify: `import torch; print(torch.cuda.is_available())` must return `True`.

### 2. HuggingFace Model Cache Location

By default, HuggingFace downloads models to `C:\Users\Admin\.cache\huggingface\hub\`. For `bge-reranker-v2-m3` (~568MB), this is fine. On first startup the reranker service will download the model — this takes 1–2 minutes. Subsequent starts load from cache and are fast.

To use a different cache location: set `HF_HOME` environment variable.

### 3. Windows Long Path Support

HuggingFace model cache paths can exceed Windows' default 260-character path limit. Enable long paths (run as Administrator):
```powershell
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name "LongPathsEnabled" -Value 1
```

### 4. CUDA 12.x vs 13.x Driver Compatibility

The RTX 5080 driver reports CUDA 13.1 as the **maximum supported CUDA version**, not the SDK version. PyTorch CUDA 12.1 wheels work with this driver because CUDA is backward compatible (driver 13.x supports runtime 12.x). Do not attempt to use CUDA 13.x PyTorch wheels — they do not exist as of April 2026.

### 5. Ollama Service vs. Interactive Process

Verify which Ollama process is running:
```powershell
Get-Service -Name "Ollama"  # if Running, it's the Windows service
```
If Ollama was originally started via `ollama serve` in a terminal (not the service), system env vars may not have been set. The Windows service is the correct production path — system env vars (set via `SetEnvironmentVariable` with "Machine" scope) are inherited by services.

### 6. Ollama GPU Fallback via Logs

If Ollama still falls back to CPU after setting env vars, check logs:
```powershell
# Ollama log location on Windows:
$env:LOCALAPPDATA\Ollama\ollama.log
```
Look for NUMA warnings or CUDA initialization errors.

### 7. Reranker Service Startup Time

`AutoModelForSequenceClassification.from_pretrained()` + `.to("cuda")` takes 5–15 seconds on first load from disk. Start the reranker service before the main FastAPI backend, or configure the backend health check to retry the reranker with exponential backoff during startup.

### 8. Process Isolation

The reranker microservice runs as a **separate process** on port 8100. It does not access DuckDB or SQLite — no file locking conflicts with the main backend.

---

## Validation Architecture

### GPU Validation (Deliverable 1)

| Check | Command | Pass Criteria |
|-------|---------|---------------|
| Ollama recognizes GPU | `ollama ps` | `GPU Layers` > 0 for loaded model |
| GPU utilization during inference | `nvidia-smi dmon -s u -d 1` while model runs | GPU utilization column non-zero |
| TTFT improvement | `scripts/eval_models.py` before/after | Mean latency_ms drops >= 50% |
| No regressions | `uv run pytest tests/unit/ -x -q` | All 1181+ tests pass |

### Embedding Validation (Deliverable 2)

| Check | Command | Pass Criteria |
|-------|---------|---------------|
| bge-m3 model pulled | `ollama list` | `bge-m3` present |
| Dimension correct | `curl /api/embeddings -d '{"model":"bge-m3","prompt":"test"}'` | `len(embedding) == 1024` |
| Config updated | `grep OLLAMA_EMBED_MODEL .env` | `OLLAMA_EMBED_MODEL=bge-m3` |
| Collection rebuilt | Python: `chroma_store.count("soc_evidence")` | Count > 0 after re-ingestion |
| Embed model in metadata | ChromaDB collection metadata inspection | `embed_model == "bge-m3"` |
| No 500 errors on RAG queries | `POST /api/query/ask` with auth | 200 response with context text |

### Reranker Validation (Deliverable 3)

| Check | Command | Pass Criteria |
|-------|---------|---------------|
| Service starts | `curl http://127.0.0.1:8100/docs` | 200 (FastAPI docs page rendered) |
| CUDA active in reranker | Check service startup log | `device = cuda` logged |
| Rerank endpoint accepts requests | `curl -X POST http://127.0.0.1:8100/rerank -H 'Content-Type: application/json' -d '{"query":"T1059","passages":["cmd.exe","notepad.exe"]}'` | `ranked_indices` returned |
| Reranker actually reorders | Craft query where more relevant passage is at ChromaDB position 2; call /rerank | More relevant passage promoted to index 0 |
| Graceful degradation | Set `RERANKER_URL=""` in .env, restart backend | RAG queries return results; no errors |
| Latency within budget | Measure reranker HTTP roundtrip with 20 passages | < 500ms |

### Full Regression Suite

- `uv run pytest tests/unit/ -x -q` — must remain >= 1181 tests passing
- Agentic investigation smoke test: `POST /api/investigate/agentic` with auth → verify agent returns a verdict within 300s (Phase 45 behavior preserved)
- RAG smoke test: `POST /api/query/ask` with a known security question → verify response references real events (not empty context)
- Feedback similarity smoke test: `GET /api/feedback/similar?investigation_id=X` → verify still returns results (Phase 44 `feedback_verdicts` collection intact after rebuild)

---

## Implementation Notes

### Recommended Wave Structure

**Wave 1 — GPU Migration** (operational, no code changes):
1. Set `CUDA_VISIBLE_DEVICES=0` as system env var (Administrator PowerShell)
2. Restart Ollama Windows service
3. Verify `ollama ps` shows GPU layers > 0
4. Run `scripts/eval_models.py` to capture GPU baseline latency

**Wave 2 — bge-m3 Embedding Upgrade** (config change + data migration):
1. `ollama pull bge-m3`
2. Update `.env`: `OLLAMA_EMBED_MODEL=bge-m3`
3. Delete + recreate ChromaDB `soc_evidence` and `feedback_verdicts` collections
4. Re-run ingestion pipeline to re-embed all events
5. Verify retrieval quality with 10 spot-check queries

**Wave 3 — Reranker Microservice** (new code, TDD):
1. Add `transformers`, `torch` (CUDA wheel), `sentence-transformers` to pyproject.toml
2. Create `backend/services/reranker/__init__.py` and `service.py`
3. Add `RERANKER_URL`, `RERANKER_TOP_N`, `RERANKER_CHROMA_K` to config.py
4. Write unit tests: reranker passthrough (empty URL), mock HTTP call, graceful degradation on failure
5. Insert reranking step in `backend/api/query.py` (and `investigate.py` if applicable)
6. Start reranker service; run validation checks

### Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Ollama ignores GPU on Windows service restart | Medium | Uninstall/reinstall Ollama with system env vars set; check Ollama logs |
| PyTorch CUDA wheel not resolving via uv | Medium | Pin `torch==2.3.0+cu121`; set explicit index URL in pyproject.toml |
| ChromaDB re-ingestion takes >1 hour | Low | Keep old collection live under temp name during migration; swap atomically |
| Reranker adds >500ms latency | Low | Reduce `RERANKER_CHROMA_K` to 10; or run model with `torch.compile()` |
| bge-reranker-v2-m3 OOM on RTX 5080 16GB | Very Low | Model is ~568MB; qwen3:14b is ~9GB; total fits in 16GB VRAM with margin |
| Dimension mismatch after partial migration | Low | Always delete + recreate collection before re-embedding; never mix model outputs |

### Rollback Plan

- **GPU:** Revert `CUDA_VISIBLE_DEVICES` system env var; restart Ollama service → CPU inference restored. No data loss.
- **Embeddings:** Revert `.env` to `OLLAMA_EMBED_MODEL=mxbai-embed-large`; delete + re-embed ChromaDB collection → prior retrieval behavior restored. No data loss.
- **Reranker:** Set `RERANKER_URL=""` in `.env`; restart backend → reranker bypassed, original ChromaDB order used. No data loss possible since reranker is stateless.
