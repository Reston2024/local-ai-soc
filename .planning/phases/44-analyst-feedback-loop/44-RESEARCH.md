# Phase 44: Analyst Feedback Loop - Research

**Researched:** 2026-04-12
**Domain:** Online ML (River LogisticRegression), Chroma k-NN, SQLite schema migration, Svelte 5 verdict UI
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Verdict buttons live in the expanded row panel (below event details) — not on the collapsed row
- Button style: ghost-style side-by-side pair — `[ ✓ True Positive ] [ ✗ False Positive ]` — neutral until clicked
- After a verdict is set: active button highlights (green for TP, red for FP), AND the collapsed row shows a small TP/FP verdict badge
- Analysts can change their verdict — clicking the other button updates it. No time limit
- Unreviewed filter chip added to DetectionsView alongside CORR/ANOMALY/SIGMA chips
- No confirmation dialog — instant save on click
- Visual feedback: brief toast notification ("Marked as True Positive") + button highlights. Toast disappears after 3 seconds
- ML updates (Chroma embed + SGDClassifier partial_fit) happen async and silently — SQLite verdict persists regardless. Analysts never see backend ML errors
- Similar incidents: new section below the investigation summary (scroll down to see it). No layout change
- Section only appears when there is at least 1 match — no empty state shown
- Shows top 3 matches, both TP and FP clearly labeled
- Each match card shows: rule_name, TP/FP verdict badge, similarity % (e.g. "87% similar"), and 1-2 line event summary
- Chroma collection for feedback: `feedback_verdicts` (separate from `soc_evidence`)
- Extend the OverviewView KPI section — no new tab
- Five new KPI data points: Verdicts Given, TP Rate, FP Rate, Classifier Accuracy (hidden until >= 10 verdicts), Training Samples
- Stats update on the next OverviewView KPI poll cycle (already 60s interval)

### Claude's Discretion
- Exact SGDClassifier feature vector construction (event fields used as features)
- Model persistence format (joblib serialization to data/models/ directory)
- Chroma collection metadata schema for `feedback_verdicts`
- Toast notification positioning and animation
- Exact KPI card layout in OverviewView

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P44-T01 | Add TP/FP verdict buttons to DetectionsView per detection row | Expand panel structure confirmed; corr- branch already at line 491 of DetectionsView.svelte; verdict state tracked as `$state` Map in component |
| P44-T02 | POST /api/feedback endpoint — stores verdict in SQLite feedback table, embeds event sequence in Chroma labeled collection | SQLite ALTER TABLE pattern confirmed; chroma_store.add_documents_async confirmed; Ollama embed client already wired on app.state |
| P44-T03 | SGDClassifier.partial_fit() called on each verdict — persisted to disk between sessions | sklearn NOT in pyproject.toml — River LogisticRegression is already installed and recommended; River uses same online-learning pattern as existing AnomalyScorer |
| P44-T04 | Similar incident surfacing in InvestigationView | chroma_store.query_async confirmed; InvestigationView has inv-section pattern for appended sections; GET /api/feedback/similar endpoint needed |
| P44-T05 | Feedback stats in MetricsView | KpiSnapshot is a typed Pydantic BaseModel — new optional fields with defaults required; KpiSnapshot interface in api.ts must also extend; OverviewView uses scorecard-tile pattern |
</phase_requirements>

---

## Summary

Phase 44 closes the analyst feedback loop by wiring verdict decisions into three persistent layers: SQLite (durable truth), Chroma `feedback_verdicts` (similarity search), and an online classifier (accuracy trending). All infrastructure is already in place — the SQLite and Chroma stores are proven, the lifespan pattern for new service registration is established by Phase 42/43, and the Svelte expand-panel branching for CORR detections (Phase 43, line 491 of DetectionsView.svelte) provides the exact hook for verdict buttons.

The one noteworthy finding is that `scikit-learn` is NOT in `pyproject.toml`. The existing codebase already uses `river>=0.21.0` for the AnomalyScorer (HalfSpaceTrees). River's `LogisticRegression` supports the same `learn_one(x_dict, label)` / `predict_proba_one(x_dict)` API and requires zero new dependencies. Using River is the recommended path. If `SGDClassifier` by name is required, `uv add scikit-learn` must be added to Wave 0.

The KPI extension pattern is clear but requires changes in two places: `KpiSnapshot` in `metrics_service.py` (Pydantic model, add optional fields with defaults) and the `KpiSnapshot` interface in `api.ts` (TypeScript, matching optional fields).

**Primary recommendation:** Use River `LogisticRegression` (already installed). Persist with joblib or the same approach used by AnomalyScorer. Add `scikit-learn` only if the requirement explicitly mandates `SGDClassifier`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| river | >=0.21.0 (installed) | Online learning — LogisticRegression.learn_one() / predict_proba_one() | Already in pyproject.toml; same idiom as AnomalyScorer; no new dep |
| scikit-learn | latest (NOT installed) | SGDClassifier.partial_fit() | Add only if SGDClassifier is locked; ~50MB dependency |
| chromadb | 1.5.5 (installed) | feedback_verdicts collection for k-NN similarity | Already used; add_documents_async + query_async verified |
| sqlite3 | stdlib | feedback table — durable verdict storage | Existing store; ALTER TABLE migration pattern established |
| joblib | bundled with scikit-learn OR standalone | Model serialization | Use for scikit-learn models; AnomalyScorer uses Python's built-in serialization for River |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio.to_thread | stdlib | Wrap all blocking ML/SQLite calls | Required for all sync operations in async FastAPI handlers |
| river.metrics.Accuracy | bundled with river | Rolling accuracy tracking alongside classifier | Required — River classifiers have no built-in score method |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| River LogisticRegression | SGDClassifier (sklearn) | sklearn adds ~50MB dep; SGDClassifier needs feature matrix not dict; River handles dict features natively and is already installed |
| Separate /api/feedback/similar call | Inline similar cases in detection list | Separate call is cleaner; similar cases only needed in InvestigationView, not DetectionsView list |

**Installation (only if SGDClassifier chosen):**
```bash
uv add scikit-learn
```

**No installation needed if River is used.**

---

## Architecture Patterns

### Recommended Project Structure
```
backend/
├── api/
│   └── feedback.py          # POST /api/feedback, GET /api/feedback/similar
├── services/
│   └── feedback/
│       ├── __init__.py
│       └── classifier.py    # FeedbackClassifier wrapping River LogisticRegression
└── stores/
    └── sqlite_store.py      # feedback table DDL + upsert_feedback(), get_feedback_stats(), get_verdict_for_detection()

dashboard/src/
├── lib/
│   └── api.ts               # FeedbackRequest, FeedbackResponse, SimilarCase, FeedbackStats interfaces + api.feedback.*
└── views/
    ├── DetectionsView.svelte # verdict buttons in expand panel, Unreviewed chip, verdict badge on collapsed row
    ├── InvestigationView.svelte  # Similar Confirmed Cases section below CAR analytics
    └── OverviewView.svelte  # 5 new KPI scorecard tiles in scorecard-row
```

### Pattern 1: SQLite Feedback Table (CREATE TABLE IF NOT EXISTS)
**What:** Add `feedback` table in `_DDL` string in sqlite_store.py with a UNIQUE constraint on `detection_id` for upsert semantics.
**When to use:** Schema initialization in `__init__` via the existing `_DDL` string mechanism.

```python
# Append to _DDL string in sqlite_store.py
"""
CREATE TABLE IF NOT EXISTS feedback (
    id            TEXT PRIMARY KEY,
    detection_id  TEXT NOT NULL UNIQUE,
    verdict       TEXT NOT NULL CHECK(verdict IN ('TP', 'FP')),
    features_json TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_detection ON feedback (detection_id);
"""
```

For existing databases where schema already ran, add idempotent migration:
```python
def _run_feedback_migrations(self) -> None:
    try:
        self._conn.execute("ALTER TABLE feedback ADD COLUMN features_json TEXT")
        self._conn.commit()
    except Exception:
        pass  # Column already exists — idempotent
```

Upsert method:
```python
def upsert_feedback(self, detection_id: str, verdict: str) -> None:
    now = datetime.now(tz=timezone.utc).isoformat()
    self._conn.execute(
        """INSERT INTO feedback (id, detection_id, verdict, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(detection_id) DO UPDATE SET verdict=excluded.verdict, updated_at=excluded.updated_at""",
        (str(uuid4()), detection_id, verdict, now, now)
    )
    self._conn.commit()
```

### Pattern 2: Chroma feedback_verdicts Collection
**What:** Separate Chroma collection from `soc_evidence`. Each add uses detection_id as the document ID.
**Key finding:** `chroma_store.add_documents()` uses `collection.upsert()` internally (confirmed line 146 of chroma_store.py) — safe to call repeatedly with the same ID. Chroma 1.5+ rejects empty metadata dicts — always pass non-empty metadata.

Metadata schema for `feedback_verdicts`:
```python
metadata = {
    "detection_id": detection_id,
    "verdict": verdict,          # "TP" | "FP"
    "rule_id": rule_id,
    "rule_name": rule_name,
    "severity": severity,
    "created_at": iso_timestamp,
}
```

Initialize collection at startup (add to `initialise_default_collections` or a new call in lifespan):
```python
await chroma_store.get_or_create_collection_async(
    "feedback_verdicts",
    metadata={"embed_model": settings.OLLAMA_EMBED_MODEL, "hnsw:space": "cosine"}
)
```

### Pattern 3: FeedbackClassifier (River online learning)
**What:** River `LogisticRegression` with `learn_one(features_dict, label)` where label is `1` for TP, `0` for FP. River's `metrics.Accuracy()` tracks rolling accuracy alongside the classifier.

**Note on model persistence:** AnomalyScorer uses Python's built-in serialization for River models. The same approach is appropriate here since the data is local and trusted (written and read by this process only — never from external or untrusted sources). Alternatively, joblib serialization can be used if scikit-learn is added to the project.

```python
# backend/services/feedback/classifier.py
from __future__ import annotations
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_DEFAULT_MODEL_DIR = "data/models"


class FeedbackClassifier:
    def __init__(self, model_dir: str = _DEFAULT_MODEL_DIR) -> None:
        self._model_dir = Path(model_dir)
        self._model_dir.mkdir(parents=True, exist_ok=True)
        self._model_path = self._model_dir / "feedback_classifier.bin"
        self._model, self._metric, self._n_samples = self._load_or_create()

    def _load_or_create(self):
        from river.linear_model import LogisticRegression
        from river.metrics import Accuracy
        if self._model_path.exists():
            try:
                import joblib  # preferred if available; falls back to River's own save/load
                state = joblib.load(self._model_path)
                return state["model"], state["metric"], state.get("n_samples", 0)
            except Exception as exc:
                log.warning("FeedbackClassifier load failed, starting fresh: %s", exc)
        return LogisticRegression(), Accuracy(), 0

    def learn_one(self, features: dict, verdict: str) -> None:
        label = 1 if verdict == "TP" else 0
        pred = self._model.predict_one(features)
        if pred is not None:
            self._metric.update(label, pred)
        self._model.learn_one(features, label)
        self._n_samples += 1
        self._save()

    def predict_proba_tp(self, features: dict) -> float:
        return self._model.predict_proba_one(features).get(1, 0.5)

    def accuracy(self) -> float | None:
        if self._n_samples < 10:
            return None
        return round(self._metric.get(), 4)

    def _save(self) -> None:
        try:
            import joblib
            joblib.dump(
                {"model": self._model, "metric": self._metric, "n_samples": self._n_samples},
                self._model_path,
            )
        except Exception as exc:
            log.warning("FeedbackClassifier save failed: %s", exc)

    @property
    def n_samples(self) -> int:
        return self._n_samples
```

**Dependency note:** `joblib` is available as a standalone package (`uv add joblib`) or is bundled when scikit-learn is installed. If neither is available, use River's own `model.clone()` + manual state dict approach.

### Pattern 4: KpiSnapshot Extension
**What:** Add optional fields to the typed `KpiSnapshot` Pydantic model. Fields must have defaults to avoid breaking existing serialization.
**Key finding:** `KpiSnapshot` is a Pydantic `BaseModel` with explicit named fields — NOT a dict (lines 37–51 of `metrics_service.py`). Both the backend model AND the frontend TypeScript interface need updating.

```python
# Append to KpiSnapshot in metrics_service.py (after log_sources field)
verdicts_given: int = 0
tp_rate: float = 0.0
fp_rate: float = 0.0
classifier_accuracy: float | None = None   # None = hidden in frontend until >= 10 samples
training_samples: int = 0
```

```typescript
// Extend KpiSnapshot interface in api.ts
export interface KpiSnapshot {
  computed_at: string
  mttd: KpiValue
  mttr: KpiValue
  mttc: KpiValue
  false_positive_rate: KpiValue
  alert_volume_24h: KpiValue
  active_rules: KpiValue
  open_cases: KpiValue
  assets_monitored: KpiValue
  log_sources: KpiValue
  // Phase 44 feedback fields
  verdicts_given?: number
  tp_rate?: number
  fp_rate?: number
  classifier_accuracy?: number | null
  training_samples?: number
}
```

In `compute_all_kpis()`, add feedback KPI computation and merge results into the `KpiSnapshot` constructor call.

### Pattern 5: Expand Panel Verdict Buttons (Svelte 5)
**What:** Verdict buttons go inside the expand panel `<tr class="car-panel-row">`, at the bottom of BOTH the corr-expand-panel and the existing CAR panel — after their existing content. The verdict `$state` Map lives in the component.

```typescript
// Component-level state (add to <script lang="ts">)
let verdicts = $state<Map<string, 'TP' | 'FP'>>(new Map())
let toastMessage = $state<string | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | null = null

// Initialize from backend on load (prevents state loss on refresh)
// In load() function, after fetching detections:
for (const d of detections) {
  if (d.verdict) verdicts.set(getDetectionId(d), d.verdict as 'TP' | 'FP')
}

function showToast(msg: string) {
  toastMessage = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastMessage = null }, 3000)
}

async function submitVerdict(d: Detection, newVerdict: 'TP' | 'FP') {
  const id = getDetectionId(d)
  verdicts = new Map(verdicts).set(id, newVerdict)  // trigger reactivity
  showToast(newVerdict === 'TP' ? 'Marked as True Positive' : 'Marked as False Positive')
  try {
    await api.feedback.submit({
      detection_id: id, verdict: newVerdict,
      rule_id: d.rule_id, rule_name: d.rule_name, severity: d.severity
    })
  } catch { /* ML errors are silent; SQLite errors logged server-side */ }
}
```

**Unreviewed filter chip:** Add `verdictFilter = $state(false)`. Extend `displayDetections` derived:
```typescript
let displayDetections = $derived(
  (() => {
    let base = typeFilter === 'CORR'
      ? detections.filter(d => d.rule_id?.startsWith('corr-'))
      : typeFilter === 'ANOMALY'
      ? detections.filter(d => d.rule_id?.startsWith('anomaly-'))
      : typeFilter === 'SIGMA'
      ? detections.filter(d => !d.rule_id?.startsWith('corr-') && !d.rule_id?.startsWith('anomaly-'))
      : detections
    if (verdictFilter) {
      base = base.filter(d => !verdicts.has(getDetectionId(d)))
    }
    return base
  })()
)
```

**Verdict badge on collapsed row:** Add inside the `<td class="rule-name">` cell after existing badges:
```svelte
{#if verdicts.get(getDetectionId(d)) === 'TP'}
  <span class="verdict-badge verdict-tp">TP</span>
{:else if verdicts.get(getDetectionId(d)) === 'FP'}
  <span class="verdict-badge verdict-fp">FP</span>
{/if}
```

### Pattern 6: Similar Confirmed Cases Section (InvestigationView)
**What:** New `<section class="inv-section similar-cases-section">` appended after the CAR analytics section at line 188. Conditional render only when `similarCases.length > 0`.

```typescript
// Add to InvestigationView <script lang="ts">
let similarCases = $state<SimilarCase[]>([])

$effect(() => {
  if (!investigationId) return
  api.feedback.similar(investigationId).then(r => {
    similarCases = r.cases ?? []
  }).catch(() => { similarCases = [] })
})
```

```svelte
<!-- After CAR analytics section (line 188), inside .panel.timeline-panel -->
{#if similarCases.length > 0}
  <section class="inv-section similar-cases-section">
    <h3 class="inv-section-title">Similar Confirmed Cases</h3>
    <div class="similar-cases-list">
      {#each similarCases as c (c.detection_id)}
        <div class="similar-case-card">
          <span class="verdict-badge verdict-{c.verdict.toLowerCase()}">{c.verdict}</span>
          <span class="similar-rule-name">{c.rule_name}</span>
          <span class="similar-score">{c.similarity_pct}% similar</span>
          <p class="similar-summary">{c.summary}</p>
        </div>
      {/each}
    </div>
  </section>
{/if}
```

### Pattern 7: POST /api/feedback Endpoint (fire-and-forget ML)
**What:** SQLite write is synchronous and always succeeds (from the analyst's perspective). ML updates run via `asyncio.ensure_future` — errors are logged at DEBUG only.

```python
@router.post("")
async def submit_feedback(body: FeedbackRequest, request: Request) -> JSONResponse:
    stores = request.app.state.stores
    classifier = getattr(request.app.state, "feedback_classifier", None)

    # 1. SQLite write (always, synchronous via to_thread)
    await asyncio.to_thread(stores.sqlite.upsert_feedback, body.detection_id, body.verdict)

    # 2. ML updates — fire-and-forget, never surface errors to analyst
    asyncio.ensure_future(_async_ml_update(stores, classifier, body))

    return JSONResponse({"status": "ok", "verdict": body.verdict, "detection_id": body.detection_id})
```

### Anti-Patterns to Avoid
- **Blocking the feedback HTTP response on ML updates:** Chroma embed + model save take 100–500ms. Always use `ensure_future()`.
- **Empty metadata to Chroma:** Chroma 1.5.5 rejects `{}` metadata. Always pass non-empty dict (confirmed in chroma_store.py line 138–145).
- **Required fields on KpiSnapshot:** Adding non-optional fields breaks existing `/api/metrics/kpis` consumers. All Phase 44 KPI fields must default (e.g. `verdicts_given: int = 0`).
- **Svelte writable() stores:** Project convention is Svelte 5 runes only. Use `$state<Map<string, 'TP' | 'FP'>>`.
- **Direct `stores.sqlite._conn.execute()` from async routes:** Must use `asyncio.to_thread(stores.sqlite.upsert_feedback, ...)`.
- **Querying Chroma with n_results > collection.count():** Will raise an error when collection is empty. Guard with `min(n, count)`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| k-NN similarity search | Custom cosine distance loop | `chroma_store.query_async()` | Already returns `distances` list; similarity = `1 - distance` for cosine space |
| Online learning with dict features | Custom gradient descent | River `LogisticRegression.learn_one()` | Handles dict features natively, no encoding matrix needed |
| Rolling accuracy tracking | Custom counter class | `river.metrics.Accuracy()` | One-liner update: `metric.update(true_label, predicted_label)` |
| Model serialization | Custom JSON export | joblib (for sklearn) or River model state (for River) | Established; AnomalyScorer already demonstrates the River approach |
| Feature normalization | Custom scaler | Reuse `_preprocess_features()` from AnomalyScorer | tanh normalization already implemented and tested |
| Toast timer | Third-party notification lib | `setTimeout` + `$state<string | null>` | Minimal, no new deps; fits project pattern |

**Key insight:** Chroma's `distances` in cosine space equal `1 - cosine_similarity`, so similarity % = `(1 - distance) * 100`. A distance of `0.13` means `87%` similar — matches the design spec example exactly.

---

## Common Pitfalls

### Pitfall 1: River accuracy tracking requires manual metric object
**What goes wrong:** `river.linear_model.LogisticRegression` has no `.score()` or `.accuracy` property. Calling either raises `AttributeError`.
**Why it happens:** River models are pure online learners — no internal score buffer.
**How to avoid:** Instantiate `river.metrics.Accuracy()` alongside the classifier. Call `metric.update(true_label, pred)` before `learn_one()`. Serialize both in the same state dict.
**Warning signs:** AttributeError on `model.score()` or `model._accuracy`.

### Pitfall 2: Chroma query on empty collection
**What goes wrong:** `collection.query(n_results=3)` raises `chromadb.errors.InvalidArgumentError` when `collection.count() == 0` (or count < n_results).
**Why it happens:** Chroma validates `n_results <= count`.
**How to avoid:** Always guard: `safe_n = min(3, await stores.chroma.count_async("feedback_verdicts"))`. Return empty list when `safe_n == 0`.
**Warning signs:** 500 error on GET /api/feedback/similar before any verdicts have been submitted.

### Pitfall 3: Verdict state lost on component remount
**What goes wrong:** `$state<Map>` is ephemeral — verdict badges disappear on page reload or navigation away and back.
**Why it happens:** No persistence for Svelte runtime state.
**How to avoid:** Include `verdict: 'TP' | 'FP' | null` field in `Detection` response from `GET /detect`. Achieved by LEFT JOINing the `feedback` table in `list_detections()` SQL. Populate the `verdicts` Map from the loaded detections in `load()`.
**Warning signs:** TP/FP badges disappear on refresh even though SQLite has the verdicts.

### Pitfall 4: KpiSnapshot missing feedback fields on old data
**What goes wrong:** Pydantic raises a validation error if `classifier_accuracy: float | None` is missing from old KPI snapshot data stored in DuckDB.
**Why it happens:** DuckDB `kpi_snapshots` table columns don't match updated model.
**How to avoid:** Use `= None` / `= 0` defaults on ALL new KpiSnapshot fields. The DuckDB daily snapshot table stores separate named columns — verify column list there too before assuming JSON serialization.
**Warning signs:** `ValidationError` on `/api/metrics/kpis` after deploy.

### Pitfall 5: Svelte `Map` mutation does not trigger reactivity
**What goes wrong:** Calling `verdicts.set(id, verdict)` on a `$state` Map does not trigger Svelte 5 re-render because the Map reference hasn't changed.
**Why it happens:** Svelte 5's fine-grained reactivity tracks object identity, not nested mutations.
**How to avoid:** Always replace the Map: `verdicts = new Map(verdicts).set(id, verdict)`. This creates a new reference, triggering `$derived` recomputation for `displayDetections` and badge rendering.
**Warning signs:** Verdict badge doesn't appear after clicking button despite `verdicts.has(id)` being true in console.

### Pitfall 6: joblib not available as standalone
**What goes wrong:** `import joblib` fails if scikit-learn is not installed and joblib standalone was not added.
**Why it happens:** joblib ships bundled with scikit-learn; standalone package requires explicit install.
**How to avoid:** If staying with River only, use Python's built-in `shelve` or River's native model snapshot. Or `uv add joblib` (tiny package, ~1MB).

---

## Code Examples

Verified patterns from official sources:

### Chroma query with empty-collection guard
```python
# Based on chroma_store.py query() signature (lines 175-210, verified)
async def get_similar_cases(chroma_store, embedding: list[float], n: int = 3) -> list[dict]:
    count = await chroma_store.count_async("feedback_verdicts")
    if count == 0:
        return []
    safe_n = min(n, count)
    results = await chroma_store.query_async(
        "feedback_verdicts",
        query_embeddings=[embedding],
        n_results=safe_n,
    )
    # results structure: {"ids": [[...]], "distances": [[...]], "documents": [[...]], "metadatas": [[...]]}
    cases = []
    for i, doc_id in enumerate(results["ids"][0]):
        distance = results["distances"][0][i]
        similarity_pct = round((1.0 - distance) * 100, 1)
        meta = (results.get("metadatas") or [[]])[0][i] or {}
        document = (results.get("documents") or [[]])[0][i] or ""
        cases.append({
            "detection_id": doc_id,
            "rule_name": meta.get("rule_name", "Unknown Rule"),
            "verdict": meta.get("verdict", "TP"),
            "similarity_pct": similarity_pct,
            "summary": document[:200],
        })
    return cases
```

### Feature vector for the feedback classifier
```python
# Reuses the tanh normalization pattern from AnomalyScorer._preprocess_features()
SEV_MAP = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25, "informational": 0.1}

def extract_feedback_features(
    severity: str,
    rule_id: str,
    anomaly_score: float | None,
    event_count: int,
) -> dict:
    return {
        "severity_score": SEV_MAP.get(severity.lower(), 0.5),
        "is_correlation": 1.0 if rule_id.startswith("corr-") else 0.0,
        "is_anomaly": 1.0 if rule_id.startswith("anomaly-") else 0.0,
        "anomaly_score": float(anomaly_score or 0.0),
        "event_count_norm": min(float(event_count) / 50.0, 1.0),
        "rule_id_hash": (hash(rule_id) % 10000) / 10000.0,
    }
```

### Lifespan wiring for FeedbackClassifier (main.py)
```python
# Insert after Phase 43 block (currently ~line 356 in main.py)
# 7h. Phase 44: Feedback classifier (River online learning)
try:
    from backend.services.feedback.classifier import FeedbackClassifier as _FeedbackClassifier
    _feedback_classifier = _FeedbackClassifier(model_dir=str(data_dir / "models"))
    app.state.feedback_classifier = _feedback_classifier
    log.info("FeedbackClassifier initialised (Phase 44)", n_samples=_feedback_classifier.n_samples)
except Exception as exc:
    log.warning("FeedbackClassifier failed to initialise — feedback ML disabled: %s", exc)
    app.state.feedback_classifier = None
```

### MetricsService feedback KPI method
```python
# Add to MetricsService class in metrics_service.py
async def compute_feedback_kpis(self) -> dict:
    """Return verdicts_given, tp_rate, fp_rate, training_samples."""
    try:
        conn = self._stores.sqlite._conn
        rows = await asyncio.to_thread(
            _sqlite_fetchall, conn,
            "SELECT verdict, COUNT(*) FROM feedback GROUP BY verdict"
        )
        counts = {r[0]: int(r[1]) for r in rows}
        tp = counts.get("TP", 0)
        fp = counts.get("FP", 0)
        total = tp + fp
        return {
            "verdicts_given": total,
            "tp_rate": round(tp / total, 4) if total > 0 else 0.0,
            "fp_rate": round(fp / total, 4) if total > 0 else 0.0,
            "training_samples": total,
        }
    except Exception as exc:
        log.warning("compute_feedback_kpis failed: %s", exc)
        return {"verdicts_given": 0, "tp_rate": 0.0, "fp_rate": 0.0, "training_samples": 0}
```

### Detection list query including verdict (detect.py extension)
```sql
-- Replace SELECT * FROM detections in list_detections()
SELECT d.*, f.verdict
FROM detections d
LEFT JOIN feedback f ON f.detection_id = d.id
{where_clause}
ORDER BY d.created_at DESC
LIMIT ? OFFSET ?
```
Add `verdict?: 'TP' | 'FP' | null` to the `Detection` interface in api.ts.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Proxy FP rate (severity=low AND case_id IS NULL heuristic) | Real FP rate from analyst verdicts | Phase 44 | `compute_false_positive_rate()` becomes supplementary; feedback-derived `fp_rate` is authoritative |
| No system learning from analyst actions | River online classifier per verdict | Phase 44 | System measurably improves; classifier_accuracy KPI makes improvement visible |
| `soc_evidence` collection only | Separate `feedback_verdicts` collection | Phase 44 | Clean separation of operational vs. confirmed-case embeddings |

**Deprecated/outdated:**
- The proxy `compute_false_positive_rate()` (severity='low' AND case_id IS NULL) — still useful as a heuristic before 10 verdicts but should be superseded by `fp_rate` from the feedback table once data accumulates.

---

## Open Questions

1. **Verdict field in GET /detect response (state persistence)**
   - What we know: `list_detections()` in detect.py does `SELECT * FROM detections` with no JOIN currently. Svelte `$state` Map is ephemeral.
   - What's unclear: Whether to JOIN feedback in the list query vs. fetch verdicts separately on mount.
   - Recommendation: Add LEFT JOIN in the list query and add `verdict?: 'TP' | 'FP' | null` to the `Detection` interface. One SQL change, avoids a second API call, and populates initial Map state from backend.

2. **River accuracy tracking detail**
   - What we know: `river.linear_model.LogisticRegression` has no `.score()` method.
   - What's unclear: Whether `river.metrics.Accuracy` updates should happen before or after `learn_one`.
   - Recommendation: Update metric BEFORE `learn_one()` (predict first, then train). This gives honest accuracy on unseen data, not trivially-fitted data.

3. **GET /api/feedback/similar — input parameter**
   - What we know: InvestigationView has `investigationId` prop. `saved_investigations.detection_id` FK confirms investigationId = detectionId in the data model.
   - What's unclear: Whether to embed the event sequence at query time or use stored embeddings.
   - Recommendation: At query time, re-embed the detection's event text (or use the stored embedding from `soc_evidence` if available) and run k-NN against `feedback_verdicts`. Simpler than caching query embeddings.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio (auto mode, set in pyproject.toml) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` — asyncio_mode = "auto" |
| Quick run command | `uv run pytest tests/unit/ -k "feedback" -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P44-T01 | Verdict buttons appear in expand panel; `submitVerdict()` sets state | Manual (Svelte UI) | N/A — browser verification | N/A |
| P44-T01 | Unreviewed chip hides verdicted detections | Manual (Svelte UI) | N/A — browser verification | N/A |
| P44-T01 | Verdict badge appears on collapsed row after verdict set | Manual (Svelte UI) | N/A — browser verification | N/A |
| P44-T02 | POST /api/feedback 200 + SQLite row inserted | Integration | `uv run pytest tests/integration/test_feedback_api.py::test_submit_verdict -x` | Wave 0 |
| P44-T02 | Re-submitting opposite verdict updates existing row (upsert) | Unit | `uv run pytest tests/unit/test_sqlite_feedback.py::test_verdict_upsert_idempotent -x` | Wave 0 |
| P44-T02 | Chroma/classifier failure does NOT cause HTTP 500 (ML silent) | Unit | `uv run pytest tests/unit/test_feedback_api.py::test_ml_failure_silent -x` | Wave 0 |
| P44-T03 | `FeedbackClassifier.learn_one()` increments n_samples | Unit | `uv run pytest tests/unit/test_feedback_classifier.py::test_learn_increments -x` | Wave 0 |
| P44-T03 | Model round-trips through save/load with same n_samples | Unit | `uv run pytest tests/unit/test_feedback_classifier.py::test_persistence_roundtrip -x` | Wave 0 |
| P44-T03 | `accuracy()` returns None when n_samples < 10 | Unit | `uv run pytest tests/unit/test_feedback_classifier.py::test_accuracy_hidden_threshold -x` | Wave 0 |
| P44-T04 | GET /api/feedback/similar returns [] when no verdicts exist | Integration | `uv run pytest tests/integration/test_feedback_api.py::test_similar_empty -x` | Wave 0 |
| P44-T04 | GET /api/feedback/similar returns <= 3 results with similarity_pct field | Integration | `uv run pytest tests/integration/test_feedback_api.py::test_similar_results_shape -x` | Wave 0 |
| P44-T05 | KpiSnapshot includes verdicts_given, tp_rate, fp_rate, training_samples | Unit | `uv run pytest tests/unit/test_metrics_service.py::test_feedback_kpi_fields -x` | Wave 0 |
| P44-T05 | classifier_accuracy is None when < 10 verdicts | Unit | `uv run pytest tests/unit/test_metrics_service.py::test_classifier_accuracy_hidden -x` | Wave 0 |

### Mock Data Shapes

**FeedbackRequest (POST /api/feedback body):**
```json
{
  "detection_id": "det-abc123",
  "verdict": "TP",
  "rule_id": "corr-bruteforce-001",
  "rule_name": "Brute Force Detected",
  "severity": "high"
}
```

**FeedbackResponse (POST /api/feedback):**
```json
{
  "status": "ok",
  "verdict": "TP",
  "detection_id": "det-abc123"
}
```

**SimilarCase (element of GET /api/feedback/similar response):**
```json
{
  "detection_id": "det-xyz789",
  "rule_name": "Brute Force Detected",
  "verdict": "TP",
  "similarity_pct": 87.3,
  "summary": "10 failed logins from 192.168.1.45 within 60s window targeting user admin"
}
```

**GET /api/feedback/similar response:**
```json
{
  "cases": [
    {
      "detection_id": "det-xyz789",
      "rule_name": "Brute Force Detected",
      "verdict": "TP",
      "similarity_pct": 87.3,
      "summary": "10 failed logins from 192.168.1.45 within 60s targeting admin"
    }
  ],
  "total": 1
}
```

**KpiSnapshot feedback fields (added to existing response):**
```json
{
  "verdicts_given": 15,
  "tp_rate": 0.6,
  "fp_rate": 0.4,
  "classifier_accuracy": 0.73,
  "training_samples": 15
}
```
When classifier_accuracy is null (< 10 verdicts), the field is omitted or null — frontend hides the card.

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/ -k "feedback" -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_feedback_classifier.py` — covers P44-T03 (learn_one, persistence round-trip, accuracy threshold)
- [ ] `tests/unit/test_sqlite_feedback.py` — covers P44-T02 (table creation, upsert idempotency)
- [ ] `tests/integration/test_feedback_api.py` — covers P44-T02, P44-T04 (POST verdict, GET similar empty + with results)
- [ ] `tests/unit/test_metrics_service.py` — extend existing file with `test_feedback_kpi_fields` and `test_classifier_accuracy_hidden`

---

## Sources

### Primary (HIGH confidence)
- `backend/stores/sqlite_store.py` lines 30–214 — detections table schema (lines 64–76), DDL pattern, `uuid4` and `datetime` import patterns
- `backend/stores/chroma_store.py` lines 1–304 — `add_documents()` uses `collection.upsert()` (line 146), `query()` returns ids/distances/documents/metadatas (lines 175–210), `count()` confirmed (lines 240–243), empty metadata rejection confirmed (lines 138–145)
- `backend/services/metrics_service.py` lines 1–463 — `KpiSnapshot` is typed Pydantic BaseModel (lines 37–51), `compute_all_kpis()` uses `asyncio.gather` (lines 415–462), `_sqlite_fetchall` helper (lines 97–99)
- `dashboard/src/views/DetectionsView.svelte` lines 1–553 — filter chip pattern (lines 333–350), expand panel corr- branch (lines 488–544), `typeFilter` rune (line 22), `displayDetections` derived (lines 36–44)
- `dashboard/src/views/InvestigationView.svelte` lines 1–189 — `inv-section` CSS class pattern (lines 162–188), `investigationId` prop (line 9), `$effect()` pattern for data loading (lines 31–36)
- `dashboard/src/lib/api.ts` lines 1–1200 — `KpiSnapshot` interface (lines 1146–1157), `api.metrics.kpis()` (line 798), `Detection` interface (lines 87–105), `request<T>()` helper (lines 666–676)
- `backend/main.py` lines 325–357 — Phase 42/43 lifespan service registration pattern; `app.state.anomaly_scorer` as template for Phase 44
- `pyproject.toml` lines 8–42 — `river>=0.21.0` confirmed present (line 41), `scikit-learn` confirmed absent
- `backend/services/anomaly/scorer.py` lines 1–80 — River HalfSpaceTrees model, feature dict normalization pattern, established approach for ML model handling
- `dashboard/src/views/OverviewView.svelte` lines 184–204 — `scorecard-row` and `scorecard-tile` pattern for KPI card layout

### Secondary (MEDIUM confidence)
- River documentation pattern: `LogisticRegression.learn_one(x: dict, y: int)` — consistent with River's unified API across all classifiers
- River documentation: `river.metrics.Accuracy().update(y_true, y_pred)` / `.get()` — standard metrics pattern

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all existing dependencies verified by reading pyproject.toml; sklearn absence confirmed; River confirmed present
- Architecture: HIGH — all integration points verified by reading actual source files; no assumptions
- Pitfalls: HIGH for Chroma/SQLite/KpiSnapshot (verified in code); HIGH for River accuracy (River API docs pattern)
- Frontend patterns: HIGH — all Svelte patterns verified in existing DetectionsView.svelte; Map reactivity pitfall is a known Svelte 5 gotcha

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (stable stack; chromadb/River APIs change infrequently)
