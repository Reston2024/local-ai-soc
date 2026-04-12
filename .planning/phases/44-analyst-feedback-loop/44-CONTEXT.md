# Phase 44: Analyst Feedback Loop - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Analysts mark detections True Positive or False Positive from DetectionsView. Each verdict: (1) persists to SQLite feedback table, (2) embeds the event sequence in a Chroma labeled collection, (3) updates an SGDClassifier via partial_fit(). In InvestigationView, the top 3 similar confirmed incidents surface via Chroma k-NN. Feedback stats (TP rate, FP rate, classifier accuracy, sample count) appear in OverviewView KPIs. The system measurably improves with each analyst decision.

</domain>

<decisions>
## Implementation Decisions

### TP/FP Button Placement
- Verdict buttons live **in the expanded row panel** (below event details) — not on the collapsed row. Consistent with Phase 43's expand-to-events pattern. Collapsed rows stay clean.
- Button style: ghost-style side-by-side pair — `[ ✓ True Positive ] [ ✗ False Positive ]` — neutral until clicked.
- After a verdict is set: the active button highlights (green for TP, red for FP), AND the **collapsed row shows a small TP/FP verdict badge**.
- Analysts can **change their verdict** — clicking the other button updates it. No time limit.
- **Unreviewed filter chip** added to DetectionsView alongside CORR/ANOMALY/SIGMA chips — when active, hides rows that already have a verdict, keeping the triage queue focused.

### Feedback Confirmation Flow
- **No confirmation dialog** — instant save on click.
- Visual feedback: brief **toast notification** ("Marked as True Positive") + button highlights. Toast disappears after 3 seconds.
- ML updates (Chroma embed + SGDClassifier partial_fit) happen **async and silently** — SQLite verdict persists regardless. Analysts never see backend ML errors.

### Similar Incidents in InvestigationView
- Renders as a **new section below the investigation summary** (scroll down to see it). No layout change.
- Section **only appears when there is at least 1 match** — no empty state shown.
- Shows **top 3 matches, both TP and FP** clearly labeled.
- Each match card shows: `rule_name`, TP/FP verdict badge, similarity % (e.g. "87% similar"), and 1-2 line event summary.
- Chroma collection for feedback: `feedback_verdicts` (separate from `soc_evidence`).

### Feedback Stats in OverviewView
- Extend the **OverviewView KPI section** — no new tab.
- Five new KPI data points:
  1. **Verdicts Given** — total TP + FP count
  2. **TP Rate** — % of verdicted detections that are TP
  3. **FP Rate** — % of verdicted detections that are FP
  4. **Classifier Accuracy** — single % from SGDClassifier running score (hidden until >= 10 verdicts)
  5. **Training Samples** — count of samples used to train the classifier
- Stats update on the **next OverviewView KPI poll cycle** (already 60s interval) — no live-push wiring needed.

### Claude's Discretion
- Exact SGDClassifier feature vector construction (event fields used as features)
- Model persistence format (joblib serialization to data/models/ directory)
- Chroma collection metadata schema for `feedback_verdicts`
- Toast notification positioning and animation
- Exact KPI card layout in OverviewView

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/stores/chroma_store.py` — `get_or_create_collection()` pattern; reuse for `feedback_verdicts` collection. No new Chroma infrastructure needed.
- `backend/services/metrics_service.py` — `compute_all_kpis()` returns `KpiSnapshot`; extend with feedback-derived fields.
- `dashboard/src/views/DetectionsView.svelte` — already has `typeFilter` rune and filter chips (CORR/ANOMALY/SIGMA) from Phase 43; add `Unreviewed` chip following the same pattern. Expand panel already branches on rule_id prefix — add TP/FP buttons in the same panel.
- `dashboard/src/views/InvestigationView.svelte` — existing summary + event list layout; append `Similar Confirmed Cases` section below.
- `dashboard/src/views/OverviewView.svelte` — existing KPI cards with 60s poll; add feedback KPI cards to the existing grid.

### Established Patterns
- Svelte 5 runes: `$state`, `$derived`, `$effect` — no stores
- Relative imports in Svelte (not `$lib` alias)
- `asyncio.to_thread()` for all SQLite writes
- Idempotent `ALTER TABLE ... try/except` for schema migration (used in sqlite_store.py 8+ times)
- Async background tasks that don't surface errors to analyst (Phase 42 anomaly scoring pattern)
- `api.ts` typed client pattern — all API calls go through typed functions

### Integration Points
- `backend/stores/sqlite_store.py` — add `feedback` table (detection_id, verdict, created_at, features_json) + `insert_feedback()`, `get_feedback_stats()`, `get_verdict_for_detection()` methods
- `backend/api/feedback.py` (new) — `POST /api/feedback` endpoint + `GET /api/feedback/similar` endpoint; wired into `main.py`
- `backend/services/feedback/classifier.py` (new) — `FeedbackClassifier` with `partial_fit()`, `score()`, `save_model()`, `load_model()`
- `dashboard/src/lib/api.ts` — add `FeedbackRequest`, `FeedbackResponse`, `SimilarCase`, `FeedbackStats` interfaces + `api.feedback.submit()` and `api.feedback.similar()` methods

</code_context>

<specifics>
## Specific Ideas

- The Unreviewed filter chip is the key workflow enabler — analysts working a queue of 50 detections need to see "how many left to triage" at a glance.
- Verdict badge on the collapsed row (TP green / FP red) makes it immediately clear which detections have been reviewed without expanding each one.
- Show classifier accuracy only after >= 10 verdicts — avoids misleading "100% accuracy from 1 sample" syndrome.

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope.

</deferred>

---

*Phase: 44-analyst-feedback-loop*
*Context gathered: 2026-04-12*
