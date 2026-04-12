---
phase: 44
plan: 44-02
subsystem: backend
tags: [feedback, river, sqlite, chroma, api]
dependency_graph:
  requires: [44-01]
  provides: [P44-T02, P44-T03]
  affects: [backend/api/detect.py, backend/main.py, backend/stores/sqlite_store.py]
tech_stack:
  added: []
  patterns:
    - River LogisticRegression online learning (learn_one / predict_proba_one)
    - joblib model serialization with JSON fallback
    - SQLite ON CONFLICT upsert for idempotent verdicts
    - Chroma feedback_verdicts collection with Ollama embeddings
    - asyncio.ensure_future fire-and-forget for ML updates (analyst never sees ML errors)
key_files:
  created:
    - backend/services/feedback/__init__.py
    - backend/services/feedback/classifier.py
    - backend/api/feedback.py
  modified:
    - backend/stores/sqlite_store.py
    - backend/main.py
    - backend/api/detect.py
    - tests/unit/test_feedback_classifier.py
    - tests/unit/test_feedback_store.py
decisions:
  - River LogisticRegression used (not sklearn SGDClassifier) — already installed, no new deps
  - FeedbackClassifier auto-loads on init; explicit load() call in lifespan for clarity
  - tmp_path isolation added to test_feedback_classifier.py tests 1-6 to prevent inter-test model pollution via shared data/models dir
  - SQLiteStore.__init__ extended with path= keyword alias so unit tests can point directly to .db file
  - Chroma add_documents_async/query_async requires pre-computed embeddings — Ollama.embed() called before storing/querying; graceful degradation when Ollama offline
  - LEFT JOIN feedback in list_detections() uses table alias d. prefix for all WHERE conditions
metrics:
  duration_minutes: 25
  tasks_completed: 3
  files_created: 3
  files_modified: 5
  completed_date: "2026-04-12T20:29:17Z"
---

# Phase 44 Plan 02: Wave 1 — Backend data layer: classifier, SQLite, API, wiring — Summary

**One-liner:** River LogisticRegression FeedbackClassifier with joblib persistence, SQLite feedback table with upsert/stats, POST/GET /api/feedback endpoints with async Chroma k-NN and River learn_one, detections list LEFT JOINs verdict field.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 44-02-01 | FeedbackClassifier (River LogisticRegression) | d1ac1c3 | backend/services/feedback/classifier.py, tests/unit/test_feedback_classifier.py |
| 44-02-02 | SQLite feedback table + upsert/query methods | f4b4f8c | backend/stores/sqlite_store.py, tests/unit/test_feedback_store.py |
| 44-02-03 | feedback API endpoints + main.py wiring + verdict in detections list | 6642799 | backend/api/feedback.py, backend/main.py, backend/api/detect.py |

## Verification Results

- `uv run pytest tests/unit/test_feedback_classifier.py -v` — 7/7 GREEN
- `uv run pytest tests/unit/test_feedback_store.py -v` — 7/7 GREEN
- `uv run pytest tests/unit/ -q` — 1081 passed, 0 failed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Chroma add_documents_async requires embeddings, not query_texts**
- **Found during:** Task 44-02-03
- **Issue:** Plan spec described `add_documents_async` with `documents=[text]` and `query_async` with `query_texts=[text]`, but the actual ChromaStore API requires pre-computed `embeddings=[vector]` for both operations
- **Fix:** Added `await ollama.embed(doc)` before Chroma upsert in `_async_ml_update`; added `await ollama.embed(query_text)` before `query_async` in `get_similar_cases`; embedding failures are non-fatal (return empty cases list)
- **Files modified:** backend/api/feedback.py
- **Commit:** 6642799

**2. [Rule 1 - Bug] Test isolation — shared data/models dir causes inter-test state pollution**
- **Found during:** Task 44-02-01 GREEN phase
- **Issue:** `FeedbackClassifier()` with default `model_dir="data/models"` auto-loads saved model from previous test; test_learn_one_fp loaded state from test_learn_one_tp giving n_samples=2 instead of 1
- **Fix:** Added `tmp_path` parameter to tests 1-6 in test_feedback_classifier.py; each test uses an isolated temp directory
- **Files modified:** tests/unit/test_feedback_classifier.py
- **Commit:** d1ac1c3

**3. [Rule 2 - Missing functionality] SQLiteStore lacked path= parameter for unit test isolation**
- **Found during:** Task 44-02-02 (test stubs used `SQLiteStore(path=...)`)
- **Issue:** Stub tests used `path=tmp_path / "test.db"` but constructor only accepted `data_dir: str` (directory, not file path)
- **Fix:** Added `path: Optional[Any] = None` keyword-only parameter to `SQLiteStore.__init__`; when provided, uses it directly as `_db_path` bypassing directory creation
- **Files modified:** backend/stores/sqlite_store.py
- **Commit:** f4b4f8c

**4. [Rule 1 - Bug] detect.py WHERE clause broken after adding table alias d. prefix**
- **Found during:** Task 44-02-03 implementation review
- **Issue:** Original code built `conditions` as `["case_id = ?", ...]` then used `WHERE ` + join; after adding LEFT JOIN with alias `d.`, the WHERE needed `d.case_id` etc.
- **Fix:** Rebuilt aliased_conditions list with explicit `d.` prefixes in the JOIN query path
- **Files modified:** backend/api/detect.py
- **Commit:** 6642799

## Self-Check: PASSED

Files exist:
- `backend/services/feedback/__init__.py` — FOUND
- `backend/services/feedback/classifier.py` — FOUND
- `backend/api/feedback.py` — FOUND

Commits exist:
- d1ac1c3 — FOUND (feat(44-02): FeedbackClassifier)
- f4b4f8c — FOUND (feat(44-02): SQLite feedback table)
- 6642799 — FOUND (feat(44-02): feedback API endpoints)
