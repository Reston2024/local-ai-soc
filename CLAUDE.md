# AI-SOC-Brain — Project Conventions for Claude

## Environment
- Python: **3.12** via `.venv/` (uv managed) — NOT system Python 3.14
- Activate: `.venv\Scripts\activate` (PowerShell) or `.venv\Scripts\activate.bat` (CMD)
- Run Python: `.venv\Scripts\python.exe` or `uv run python`
- Run tests: `uv run pytest` or `.venv\Scripts\pytest`

## Project Layout
```
backend/           FastAPI application (Python 3.12)
  main.py          App factory: create_app()
  core/            Config (pydantic-settings), logging, deps
  stores/          DuckDB, Chroma, SQLite store wrappers
  models/          Pydantic models (NormalizedEvent, etc.)
  services/        Ollama HTTP client
  api/             Route handlers (health, events, ingest, query, detect, graph, export)
ingestion/         Event parsing and normalization pipeline
  parsers/         EVTX, JSON/NDJSON, CSV, osquery parsers
  normalizer.py    Field normalization, severity mapping
  entity_extractor.py  Entity/edge extraction for graph
  loader.py        Batch ingest + Chroma embed coordinator
detections/        Sigma rule matching
  field_map.py     Sigma field → DuckDB column mapping
  matcher.py       Custom DuckDB SQL backend for Sigma
correlation/       Event clustering (Union-Find + temporal window)
graph/             Graph schema constants and BFS traversal
prompts/           LLM prompt templates (analyst_qa, triage, etc.)
dashboard/         Svelte 5 SPA (npm project)
  src/lib/api.ts   Typed API client — DO NOT import langchain wrappers here
config/caddy/      Caddyfile for Caddy HTTPS proxy
scripts/           PowerShell management scripts
fixtures/          Test fixture data (NDJSON, EVTX samples)
tests/             pytest test suite
  unit/            Unit tests (no I/O)
  integration/     Integration tests (requires running services)
  sigma_smoke/     Sigma rule parsing smoke tests
data/              Runtime data (gitignored)
logs/              Runtime logs (gitignored)
```

## Key Conventions

### Python
- Imports: `from sigma.collection import SigmaCollection` (NOT `from pySigma`)
- DuckDB: ALL writes via `store.execute_write(sql, params)` (write queue pattern)
- DuckDB reads: `await store.fetch_all(sql)` (asyncio.to_thread wrapper)
- Chroma: use `chroma_store` directly — NEVER via LangChain wrapper
- Async: use `asyncio.to_thread()` for all blocking I/O
- Settings: import `from backend.core.config import settings` (module-level singleton)

### TypeScript/Svelte
- Svelte 5 runes: `$state()`, `$derived()`, `$effect()` — NOT stores
- API calls: use `src/lib/api.ts` typed client only
- No `svelte:store` or writable() — use runes

### Testing
- pytest-asyncio mode: auto (set in pyproject.toml)
- Test files: `tests/unit/test_*.py`, `tests/integration/test_*.py`

### Git
- Commit granularity: one logical change per commit
- Format: `type(scope): message` (feat, fix, test, chore, docs, refactor)
