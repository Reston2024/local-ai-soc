# Phase 9: Intelligence & Analyst Augmentation — Research

**Researched:** 2026-03-25
**Domain:** SOC intelligence layer — risk scoring, anomaly detection, LLM grounding, Cytoscape visualization, FastAPI extension
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Do NOT refactor working Phase 8 systems unless strictly required
- Do NOT remove any existing capability
- All new features integrate with existing pipeline (DuckDB/SQLite/Chroma, investigation API)
- All AI outputs must be evidence-backed — grounded in stored events/detections
- No hallucinated context passed to Ollama — only structured evidence from DuckDB/SQLite
- Phase 8 tests must remain passing (66 unit tests, 4 xpassed)
- Risk scoring: numeric 0.0–1.0 or 0–100, factors include MITRE technique severity, process lineage depth, external network behavior, anomaly indicators, detection count per entity
- Risk scores stored in SQLite (not DuckDB) alongside detection records
- Anomaly rules: deterministic/auditable, configurable ruleset (not ML)
- Known-bad parent-child pairs: Office apps spawning shells, system processes with non-system parents, masquerading process names
- OllamaClient is the existing client (backend/services/ollama_client.py) — use it, don't replace it
- Model: qwen3:14b only
- Three Ollama output types: attack chain explanation, investigation summary, entity Q&A
- Investigation explanation must produce three structured sections: "What Happened", "Why It Matters", "Recommended Next Steps"
- API endpoints: POST /api/score, POST /api/explain, GET /api/top-threats
- All endpoints return HTTP 200 with structured JSON (never 404/500 for missing data)
- Dashboard: risk score color badge on graph nodes, highlighted attack path edges, "Top Suspicious Entities" panel, AI explanation panel (collapsible, regenerate button)
- Dashboard integrates into existing InvestigationPanel.svelte — NOT a new tab
- Case management: saved_investigations table in existing graph.sqlite3, save graph snapshot (JSON) + detection metadata + timestamp, simple GET retrieval

### Claude's Discretion
- Exact scoring formula weights (MITRE weight vs. process lineage weight vs. network weight)
- Whether anomaly rules are in code or YAML config
- Specific Ollama prompt templates (subject to evidence grounding requirement)
- Whether attack path highlighting uses a new Cytoscape style or extends existing severity-border style
- Implementation of risk score persistence: computed on-the-fly vs. cached in SQLite
- Streaming vs. single-response for Ollama explain endpoint

### Deferred Ideas (OUT OF SCOPE)
- ML-based anomaly detection (clustering/baseline learning)
- Full streaming Ollama via SSE to dashboard (acceptable but not required)
- Multi-model support (qwen3:14b only)
- Graph-based path scoring algorithms (PageRank, centrality)
- Integration with external threat intel feeds (VirusTotal, MISP)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P9-T01 | Risk scoring engine: assign 0–100 scores to events, entities, attack paths using MITRE severity, process lineage depth, external network behavior, anomaly indicators, detection count | Extends backend/causality/scoring.py additive pattern; new backend/intelligence/risk_scorer.py |
| P9-T02 | MITRE technique severity mapping: critical (0.9+), high (0.7–0.9), medium (0.4–0.7), low (0.1–0.4) with defined technique IDs | Static lookup table pattern from backend/src/detection/attack_mapper.py; MITRE technique list in CONTEXT.md |
| P9-T03 | Anomaly detection rules: deterministic parent-child process flagging, unusual external connections, process masquerading detection | New backend/intelligence/anomaly_rules.py; rules defined as dataclass list or YAML |
| P9-T04 | POST /api/score endpoint: accepts event_ids or detection_id, returns risk-scored entities | New FastAPI router mounted via deferred try/except pattern in main.py |
| P9-T05 | POST /api/explain endpoint: accepts detection_id or investigation context, calls Ollama with structured evidence, returns explanation | Uses existing OllamaClient.generate(); new backend/intelligence/explain_engine.py |
| P9-T06 | GET /api/top-threats endpoint: returns top N ranked detections + entities by risk score | Queries SQLite detections table sorted by risk_score column (new column added) |
| P9-T07 | Investigation explanation engine: three sections "What Happened", "Why It Matters", "Recommended Next Steps" derived from graph + timeline data | Prompt template in prompts/ module; grounding serialization function |
| P9-T08 | Dashboard: risk score color badge on graph nodes, highlighted attack path edges | Extends InvestigationPanel.svelte Cytoscape style; risk_score in node data |
| P9-T09 | Dashboard: "Top Suspicious Entities" panel + AI explanation panel with regenerate button | New Svelte reactive state blocks in InvestigationPanel.svelte; calls api.score() and api.explain() |
| P9-T10 | Case management: saved_investigations table in SQLite, save/retrieve graph snapshot | New DDL in sqlite_store.py; new API endpoints GET/POST /api/investigations/saved |
</phase_requirements>

---

## Summary

Phase 9 adds an intelligence layer on top of the fully operational Phase 8 SOC platform. The existing system has all the data foundations: DuckDB normalized events, SQLite detections/entities/edges, Cytoscape investigation graph, OllamaClient, and a `/api/investigate` endpoint that already assembles graph + timeline + attack chain data. Phase 9 transforms raw investigation data into prioritized, explained, analyst-ready output.

The three main workstreams are: (1) a risk scoring engine that assigns numeric scores to entities/detections, (2) an anomaly detection rules layer that flags suspicious process relationships deterministically, and (3) an LLM explanation engine that grounds Ollama calls in structured evidence from the investigation result set. Each workstream extends existing code without replacing it — the scoring engine extends `backend/causality/scoring.py` patterns, the anomaly rules extend the detection pipeline, and the explanation engine wraps the existing `OllamaClient`.

The dashboard work is additive: `InvestigationPanel.svelte` already renders the Cytoscape graph with severity-based border colors. Phase 9 adds risk score badges to node data, attack path edge highlighting, and two new collapsible panels (top entities and AI explanation) — all within the same component using Svelte 5 rune patterns already established.

**Primary recommendation:** Build `backend/intelligence/` as a new package containing `risk_scorer.py`, `anomaly_rules.py`, and `explain_engine.py`. Mount three new API routers via the deferred try/except pattern in `main.py`. Extend `InvestigationPanel.svelte` in-place with Svelte 5 `$state()` / `$derived()` reactive blocks.

---

## Existing Code Audit

### What Already Exists (do not rebuild)

| Module | Path | What It Does | Phase 9 Uses |
|--------|------|-------------|--------------|
| OllamaClient | `backend/services/ollama_client.py` | Async httpx wrapper: `generate()`, `stream_generate()`, `stream_generate_iter()`, `embed()` | Call `generate()` for explain endpoint; low temperature (0.1) for factual output |
| SQLiteStore | `backend/stores/sqlite_store.py` | `detections` table with `id, rule_id, rule_name, severity, matched_event_ids, attack_technique, attack_tactic, explanation, case_id` | Add `risk_score INTEGER DEFAULT 0` column; add `saved_investigations` table via DDL migration |
| investigate.py | `backend/api/investigate.py` | Assembles detection + events + graph (Cytoscape format) + timeline + attack_chain + techniques + entity_clusters + summary | The investigate response is the primary evidence bundle for scoring and explanation |
| causality/scoring.py | `backend/causality/scoring.py` | Additive 0-100 chain scorer: severity points + technique count + chain length + recurrence | Pattern to copy for entity-level risk scoring |
| InvestigationPanel.svelte | `dashboard/src/components/InvestigationPanel.svelte` | Cytoscape graph with type colors + severity border, timeline list, attack chain, selected node detail | Extend node data with `risk_score`; add new panels within same component |
| api.ts | `dashboard/src/lib/api.ts` | Typed fetch client with interfaces for Detection, GraphEntity, NormalizedEvent | Add `score()`, `explain()`, `topThreats()`, `saveInvestigation()` methods |

### Key Observations from Code Review

1. **OllamaClient.generate()** accepts `prompt`, `system`, `temperature`, `model` — the grounding pattern is: serialize evidence as a string block in `prompt`, use `system` for the "only use provided context" instruction.

2. **investigate.py response shape** — already returns: `events[]`, `graph.elements.nodes[]` (each with `entity_type`, `severity`, `attack_technique`), `timeline[]`, `attack_chain[]`, `techniques[]`. This is the ready-made evidence bundle for scoring and explanation.

3. **InvestigationPanel.svelte** already uses `(el: any) => el.data('severity') === 'critical' ? 3 : 1` for border-width. Adding risk_score badge means: pass `risk_score` in node data from backend, then add a CSS/style selector for risk tiers in the Cytoscape stylesheet.

4. **SQLite `detections` table** already has an `explanation` TEXT column. Adding `risk_score INTEGER DEFAULT 0` is a safe backward-compatible ALTER TABLE.

5. **No `backend/causality/` directory in the main project** — `backend/causality/scoring.py` and `engine.py` exist and follow a clean pure-function pattern. Phase 9 should mirror this pattern in `backend/intelligence/`.

6. **Deferred router pattern in main.py** — all new routers use `try/except ImportError` wrapping. Phase 9 routers must follow this pattern to preserve graceful degradation.

---

## Standard Stack

### Core (all already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | existing | API framework | Already used for all 10 existing routes |
| sqlalchemy/sqlite3 | stdlib | SQLite persistence | SQLiteStore uses stdlib sqlite3 directly |
| httpx | existing | Async HTTP | OllamaClient is built on it |
| pydantic | existing | Request/response models | Already used throughout backend |
| cytoscape | existing (npm) | Graph visualization | InvestigationPanel already renders with it |

### No New Dependencies Required

Phase 9 does not require any new Python packages. All scoring, anomaly detection, and LLM calling uses existing dependencies. The dashboard also requires no new npm packages — Cytoscape and Svelte 5 are already present.

If anomaly rules are stored in YAML, use `pyyaml` which is available in the environment. Recommendation: implement anomaly rules as Python dataclasses in code (not YAML) to avoid an additional file format and keep rules testable with pytest.

---

## Architecture Patterns

### Recommended Project Structure

```
backend/
└── intelligence/          # NEW — Phase 9 intelligence layer
    ├── __init__.py
    ├── risk_scorer.py     # score_entities(), score_detection(), score_attack_path()
    ├── anomaly_rules.py   # ANOMALY_RULES list, check_event_anomalies()
    └── explain_engine.py  # build_evidence_context(), generate_explanation()

backend/api/
├── score.py               # NEW — POST /api/score router
├── explain.py             # NEW — POST /api/explain router
├── top_threats.py         # NEW — GET /api/top-threats router
└── investigations.py      # NEW — GET/POST /api/investigations/saved router
```

### Pattern 1: Risk Scoring — Additive Components

Extend the established pattern from `backend/causality/scoring.py`. The existing scorer uses integer points (0-100). Phase 9 can output float (0.0-1.0) or integer — recommendation is 0-100 integer to match existing stored values.

```python
# backend/intelligence/risk_scorer.py
# Source: extends pattern from backend/causality/scoring.py

_MITRE_WEIGHTS: dict[str, int] = {
    # critical techniques (T1003.001 LSASS, T1071.001 C2) → 40 pts
    "T1003.001": 40, "T1071.001": 40,
    # high techniques → 30 pts
    "T1547.001": 30, "T1059.001": 30,
    # medium techniques → 20 pts
    "T1033": 20, "T1087.002": 20,
}
_SEVERITY_BASE: dict[str, int] = {
    "critical": 40, "high": 30, "medium": 20, "low": 10
}

def score_entity(
    entity_id: str,
    events: list[dict],
    detections: list[dict],
    anomaly_flags: list[str],
) -> int:
    """Additive 0-100 entity risk score."""
    score = 0
    # Component 1: Max MITRE technique weight (0-40 pts)
    # Component 2: Process lineage depth bonus (0-20 pts)
    # Component 3: External network connection bonus (0-20 pts)
    # Component 4: Anomaly flag count (0-10 pts per flag, max 20)
    # Component 5: Detection count for entity (0-10 pts, max 2 detections)
    return min(score, 100)
```

### Pattern 2: Anomaly Rules — Deterministic Ruleset

```python
# backend/intelligence/anomaly_rules.py
# Pattern: dataclass list, no external config required

from dataclasses import dataclass
from typing import Callable

@dataclass
class AnomalyRule:
    rule_id: str
    name: str
    description: str
    check: Callable[[dict], bool]  # takes normalized event dict, returns True if anomalous

ANOMALY_RULES: list[AnomalyRule] = [
    AnomalyRule(
        rule_id="ANO-001",
        name="office_spawns_shell",
        description="Office application spawning a shell or scripting process",
        check=lambda evt: (
            evt.get("parent_process_name", "").lower() in
            {"winword.exe", "excel.exe", "powerpnt.exe", "outlook.exe", "mspub.exe"}
            and evt.get("process_name", "").lower() in
            {"cmd.exe", "powershell.exe", "wscript.exe", "cscript.exe", "mshta.exe"}
        ),
    ),
    # ANO-002: system_process_unusual_parent
    # ANO-003: process_masquerading (svchost/lsass/csrss in AppData/Temp)
    # ANO-004: unusual_external_port (non-80/443/8080 to non-RFC1918)
]

def check_event_anomalies(event: dict) -> list[str]:
    """Return list of rule_ids that fire for this event."""
    return [r.rule_id for r in ANOMALY_RULES if r.check(event)]
```

### Pattern 3: LLM Grounding — Evidence Serialization

The key principle: the `system` prompt contains the "only use provided context" constraint; the `prompt` contains serialized evidence. This is the existing pattern for the query endpoint — extend it for the explain endpoint.

```python
# backend/intelligence/explain_engine.py

_SYSTEM_PROMPT = """You are a cybersecurity analyst assistant.
CRITICAL: You MUST only use the evidence provided below.
Do NOT invent, assume, or hallucinate any facts not present in the evidence.
If the evidence does not support a statement, say "insufficient evidence"."""

def build_evidence_context(investigation: dict, max_events: int = 10) -> str:
    """Serialize investigation result into a grounded evidence block."""
    lines = []
    # 1. Detection info (rule name, severity, technique)
    if detection := investigation.get("detection"):
        lines.append(f"DETECTION: {detection.get('rule_name')} | severity={detection.get('severity')} | technique={detection.get('attack_technique')}")
    # 2. Top N events (chronological, most severe first)
    events = sorted(
        investigation.get("events", []),
        key=lambda e: (e.get("severity") or "info"),
        reverse=True
    )[:max_events]
    for evt in events:
        lines.append(f"EVENT: {evt.get('timestamp','?')} | {evt.get('event_type')} | {evt.get('process_name')} on {evt.get('hostname')} | technique={evt.get('attack_technique')}")
    # 3. Unique MITRE techniques observed
    techniques = [t.get("technique_id") for t in investigation.get("techniques", []) if t.get("technique_id")]
    if techniques:
        lines.append(f"MITRE TECHNIQUES: {', '.join(techniques)}")
    # 4. Entity count summary
    nodes = investigation.get("graph", {}).get("elements", {}).get("nodes", [])
    lines.append(f"GRAPH: {len(nodes)} entities, {len(investigation.get('timeline', []))} timeline events")
    return "\n".join(lines)

async def generate_explanation(
    investigation: dict,
    ollama_client,  # OllamaClient instance
) -> dict:
    """Generate three-section explanation grounded in evidence."""
    context = build_evidence_context(investigation)
    prompt = f"""Based ONLY on the following evidence, provide a structured analysis:

{context}

Respond with exactly three sections:
## What Happened
[Describe the attack chain step by step, citing specific processes and timestamps]

## Why It Matters
[Explain the MITRE technique impact and business risk, citing specific technique IDs]

## Recommended Next Steps
[List 3-5 concrete containment and investigation actions based on the evidence]"""

    response = await ollama_client.generate(
        prompt=prompt,
        system=_SYSTEM_PROMPT,
        temperature=0.1,  # low temperature for factual/grounded output
    )
    return _parse_explanation_sections(response)
```

### Pattern 4: FastAPI Router — Deferred Mount Pattern

All new routers must follow the existing deferred try/except pattern from `main.py`:

```python
# backend/main.py — add after existing deferred router blocks
try:
    from backend.api.score import router as score_router
    app.include_router(score_router, prefix="/api")
    log.info("Score router mounted at /api/score")
except ImportError as exc:
    log.warning("Score router not available: %s", exc)

try:
    from backend.api.explain import router as explain_router
    app.include_router(explain_router, prefix="/api")
    log.info("Explain router mounted at /api/explain")
except ImportError as exc:
    log.warning("Explain router not available: %s", exc)
```

### Pattern 5: Cytoscape Risk Score Visualization

The existing `InvestigationPanel.svelte` uses `el.data('severity')` for border styling. Risk score is passed as `risk_score` in node data from the backend. Color tiers: 0-30 green, 31-60 yellow, 61-80 orange, 81-100 red.

```typescript
// Extend the Cytoscape stylesheet in InvestigationPanel.svelte
// Source: existing Cytoscape style pattern in the file

// In node style, add background overlay or badge:
// Recommendation: Use a separate selector for risk-score tiers

{
  selector: 'node[risk_score > 80]',
  style: { 'border-color': '#ef4444', 'border-width': 4 }
},
{
  selector: 'node[risk_score > 60][risk_score <= 80]',
  style: { 'border-color': '#f97316', 'border-width': 3 }
},
{
  selector: 'node[risk_score > 30][risk_score <= 60]',
  style: { 'border-color': '#eab308', 'border-width': 2 }
},
// Attack path highlighting:
{
  selector: 'edge.attack-path',
  style: { 'line-color': '#ef4444', 'width': 3, 'line-style': 'solid' }
}
```

To add risk_score badges: use a Cytoscape `label` function that appends the score, OR render HTML overlay badges positioned over the canvas using `cy.on('render')`. The simplest approach that works with existing code: append score to the node label string when risk_score > 0, e.g., `"powershell.exe [85]"`.

### Pattern 6: SQLite Schema Extension — Safe Migration

The `saved_investigations` table and `risk_score` column must be added without breaking existing code. Use `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (SQLite supports this since 3.37):

```python
# In SQLiteStore.__init__() — add to _DDL string

"""
CREATE TABLE IF NOT EXISTS saved_investigations (
    id           TEXT PRIMARY KEY,
    detection_id TEXT,
    title        TEXT NOT NULL,
    graph_snapshot TEXT NOT NULL,  -- JSON blob of Cytoscape elements
    detection_metadata TEXT,       -- JSON blob
    risk_scores  TEXT,             -- JSON blob: {entity_id: score}
    created_at   TEXT NOT NULL,
    case_id      TEXT
);

CREATE INDEX IF NOT EXISTS idx_saved_inv_case ON saved_investigations (case_id);
"""

# Add risk_score to detections table — safe ALTER (SQLite 3.37+)
# In SQLiteStore.__init__() after executescript:
try:
    self._conn.execute(
        "ALTER TABLE detections ADD COLUMN risk_score INTEGER DEFAULT 0"
    )
    self._conn.commit()
except sqlite3.OperationalError:
    pass  # Column already exists — idempotent
```

### Anti-Patterns to Avoid

- **Free-form LLM generation without evidence:** Never call `ollama_client.generate()` with just a question string — always serialize structured evidence first into the prompt context.
- **Blocking the event loop:** All SQLite calls from async routes must be wrapped in `asyncio.to_thread()`. The OllamaClient is already async.
- **New DuckDB write patterns:** Phase 9 stores risk scores in SQLite, not DuckDB. Never bypass the DuckDB write queue.
- **Replacing InvestigationPanel.svelte:** Phase 9 extends in-place. Do not create a new tab or route.
- **Using `writable()` or `svelte:store`:** Svelte 5 runes only (`$state()`, `$derived()`, `$effect()`).
- **Hard-coded technique IDs as the only scoring factor:** The scoring must combine MITRE weight + lineage depth + network behavior — not just technique lookup.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async HTTP to Ollama | Custom httpx wrapper | `OllamaClient.generate()` | Already handles timeouts, error handling, logging |
| Graph traversal for attack path | Custom BFS | Cytoscape `cy.elements().dijkstra()` or `cy.elements().aStar()` on client side | Cytoscape has built-in pathfinding; server already returns full graph |
| Evidence serialization from scratch | Custom format | Use the `investigate.py` response shape directly — it already has events, timeline, techniques | The investigation endpoint already assembles exactly what is needed |
| SQLite schema creation | Custom ORM | Extend existing `_DDL` string in `sqlite_store.py` | Consistent with all other tables in the project |
| Risk score color thresholds in JS | Custom color logic | CSS classes via Cytoscape selectors (node[risk_score > 80]) | Declarative, matches existing severity-border pattern |

**Key insight:** The `POST /api/investigate` response is the pre-assembled evidence bundle. The explain endpoint should accept a `detection_id`, call investigate internally, then pass the result to `build_evidence_context()` → `generate_explanation()`. Do not re-query DuckDB/SQLite separately.

---

## Common Pitfalls

### Pitfall 1: LLM Hallucination via Thin Grounding
**What goes wrong:** Ollama generates plausible-sounding but fabricated attack narrative not present in the evidence (process names, IPs, techniques that don't appear in the actual events).
**Why it happens:** The prompt context is too sparse (e.g., only passes detection name without event details) or uses general security knowledge rather than the specific evidence.
**How to avoid:** The `system` prompt MUST include "ONLY based on provided context" constraint (already established in existing prompt templates in `prompts/`). The `prompt` MUST contain the serialized evidence block from `build_evidence_context()`. Cap events at 10-15 to keep context window manageable for qwen3:14b (14B parameter model — context window ~8k tokens).
**Warning signs:** Response mentions entities not in the events list. Response describes techniques not in the techniques list.

### Pitfall 2: SQLite ALTER TABLE on Existing Column
**What goes wrong:** `ALTER TABLE detections ADD COLUMN risk_score INTEGER DEFAULT 0` fails with "duplicate column name" on subsequent startups.
**Why it happens:** The schema migration runs in `__init__()` on every startup.
**How to avoid:** Wrap in try/except `sqlite3.OperationalError` — see Pattern 6 above. This is the standard SQLite migration pattern when not using a migration framework.

### Pitfall 3: Cytoscape Style Selectors with Numeric Comparisons
**What goes wrong:** `node[risk_score > 80]` doesn't apply because the data value is a string `"85"` not a number `85`.
**Why it happens:** JSON serialization of node data in the investigate response may coerce integers to strings depending on Pydantic/Python serialization.
**How to avoid:** Ensure the backend scores are serialized as integers (not strings) in the graph node data. In `investigate.py`, when adding `risk_score` to node data, pass it as `int(score)` not `str(score)`.

### Pitfall 4: Cytoscape Attack Path Highlighting Without Path Data
**What goes wrong:** The frontend tries to highlight attack path edges but doesn't know which edges form the path.
**Why it happens:** The investigate endpoint returns edges but doesn't tag them as "attack path" vs "background" edges.
**How to avoid:** Backend should return an `attack_path_edges` list of edge IDs in the investigate/score response. Frontend then applies the `attack-path` CSS class to those edges: `cy.getElementById(edgeId).addClass('attack-path')`.

### Pitfall 5: qwen3:14b Response Format Deviation
**What goes wrong:** The explanation response doesn't follow the three-section format despite prompting.
**Why it happens:** LLMs are probabilistic and may format differently at low temperatures.
**How to avoid:** Parse with a resilient `_parse_explanation_sections()` that falls back to returning the full response in "What Happened" if section headers aren't found. Never raise an error on parse failure — return partial results.

### Pitfall 6: Risk Score Not Persisted Causing Stale GET /api/top-threats
**What goes wrong:** The `GET /api/top-threats` endpoint returns empty or zero-score results because scoring only happened in-memory.
**Why it happens:** If risk scores are computed on-the-fly at `POST /api/score` but not written back to SQLite, the top-threats query finds no scored detections.
**How to avoid:** `POST /api/score` must write `risk_score` back to the `detections` row in SQLite. Use `UPDATE detections SET risk_score = ? WHERE id = ?` after scoring.

---

## Code Examples

### Registering a New Router (deferred pattern)
```python
# Source: existing pattern in backend/main.py lines 256-288
try:
    from backend.api.score import router as score_router
    app.include_router(score_router, prefix="/api")
    log.info("Score router mounted at /api/score")
except ImportError as exc:
    log.warning("Score router not available — skipping: %s", exc)
```

### OllamaClient.generate() Call Pattern
```python
# Source: backend/services/ollama_client.py
# Non-streaming, low temperature for factual analysis
response = await request.app.state.ollama.generate(
    prompt=prompt,          # contains serialized evidence block
    system=_SYSTEM_PROMPT,  # "ONLY use provided context" constraint
    temperature=0.1,        # deterministic output for grounded analysis
)
```

### SQLite asyncio.to_thread Pattern
```python
# Source: existing pattern in backend/api/investigate.py lines 92-101
import asyncio
result = await asyncio.to_thread(
    stores.sqlite.save_investigation,
    investigation_id, detection_id, graph_snapshot, metadata
)
```

### Svelte 5 Rune Pattern for New Panel State
```typescript
// Source: existing pattern in InvestigationPanel.svelte
let explanation = $state<any>(null)
let explanationLoading = $state(false)
let topEntities = $state<any[]>([])

// Derived from investigation result
let highRiskNodes = $derived(
  (investigation?.graph?.elements?.nodes ?? [])
    .filter((n: any) => (n.data?.risk_score ?? 0) > 60)
    .sort((a: any, b: any) => (b.data?.risk_score ?? 0) - (a.data?.risk_score ?? 0))
    .slice(0, 5)
)
```

### Risk Score Color Badge in Svelte Template
```svelte
<!-- Pattern: conditional class based on score tier -->
{#snippet riskBadge(score: number)}
  <span class="risk-badge risk-{score > 80 ? 'critical' : score > 60 ? 'high' : score > 30 ? 'medium' : 'low'}">
    {score}
  </span>
{/snippet}
```

### api.ts Extension Pattern
```typescript
// Source: existing api.ts pattern — add to export const api = { ... }
score: (payload: { detection_id?: string; event_ids?: string[] }) =>
  request<{ entities: Array<{ entity_id: string; score: number; reasons: string[] }> }>(
    '/api/score', { method: 'POST', body: JSON.stringify(payload) }
  ),

explain: (payload: { detection_id: string }) =>
  request<{ what_happened: string; why_it_matters: string; next_steps: string }>(
    '/api/explain', { method: 'POST', body: JSON.stringify(payload) }
  ),

topThreats: (limit = 10) =>
  request<{ threats: Array<{ detection_id: string; score: number; entities: any[] }> }>(
    `/api/top-threats?limit=${limit}`
  ),
```

---

## MITRE Severity Mapping Reference

From CONTEXT.md (locked decision):

| Tier | Techniques | Score Range | Points (0-100 scale) |
|------|-----------|-------------|----------------------|
| critical | T1003.001 (LSASS), T1071.001 (C2 HTTP) | 0.9+ | 40 pts |
| high | T1547.001 (persistence), T1059.001 (PowerShell) | 0.7–0.9 | 30 pts |
| medium | T1033 (discovery), T1087.002 (enum), T1105 (tool transfer) | 0.4–0.7 | 20 pts |
| low | All others | 0.1–0.4 | 10 pts |

For techniques not in the explicit lookup table, fall back to the severity field on the detection record using the same `_SEVERITY_BASE` dict. This ensures all detections get a score even if their technique ID is not explicitly listed.

---

## Process Anomaly Rules Reference

From CONTEXT.md (locked decision):

| Rule | Parent | Child | Anomaly Type |
|------|--------|-------|--------------|
| ANO-001 | winword.exe, excel.exe, powerpnt.exe, outlook.exe | cmd.exe, powershell.exe, wscript.exe, cscript.exe | Office macro execution |
| ANO-002 | Any non-system process | svchost.exe, lsass.exe, csrss.exe, winlogon.exe | System process injection |
| ANO-003 | Any | svchost.exe, lsass.exe, csrss.exe (but path contains AppData/Temp/Users) | Masquerading |
| ANO-004 | Any | Any | Non-standard external port (not 80/443/8080) to non-RFC1918 IP |

APT scenario verification: `svchosts.exe` (not `svchost.exe`) in AppData path spawned by powershell.exe from winword.exe chain → should trigger ANO-001 + ANO-003 + high network score from 185.220.101.45:4444 → expected combined score 80-100.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Passing full raw event JSON to LLM | Serialize only structured fields (type, timestamp, technique, process) as a text block | Prevents context window overflow; reduces hallucination surface |
| Global risk thresholds | Per-entity additive scoring based on observable evidence fields | More accurate prioritization for APT scenarios with multi-stage chains |
| Single explanation call per investigation | Three structured sections with explicit grounding constraint | Produces actionable analyst output, not just narrative text |

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via uv run pytest) |
| Config file | pyproject.toml (pytest-asyncio mode=auto) |
| Quick run command | `uv run pytest tests/unit/ -x -q` |
| Full suite command | `uv run pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P9-T01 | score_entity() returns 0-100 int; additive components | unit | `uv run pytest tests/unit/test_risk_scorer.py -x` | Wave 0 |
| P9-T02 | MITRE technique weight lookup: T1003.001=40, T1059.001=30, T1033=20 | unit | `uv run pytest tests/unit/test_risk_scorer.py::TestMitreWeights -x` | Wave 0 |
| P9-T03 | ANO-001 fires for winword→powershell; ANO-003 fires for svchost in AppData | unit | `uv run pytest tests/unit/test_anomaly_rules.py -x` | Wave 0 |
| P9-T04 | POST /api/score returns 200 with entity scores list | unit | `uv run pytest tests/unit/test_score_api.py -x` | Wave 0 |
| P9-T05 | POST /api/explain calls OllamaClient.generate() with non-empty evidence block | unit (mocked Ollama) | `uv run pytest tests/unit/test_explain_api.py -x` | Wave 0 |
| P9-T06 | GET /api/top-threats returns detections sorted by risk_score descending | unit | `uv run pytest tests/unit/test_top_threats_api.py -x` | Wave 0 |
| P9-T07 | generate_explanation() returns dict with what_happened, why_it_matters, next_steps keys | unit (mocked Ollama) | `uv run pytest tests/unit/test_explain_engine.py -x` | Wave 0 |
| P9-T08 | Graph node data contains risk_score integer when score endpoint called | unit | `uv run pytest tests/unit/test_risk_scorer.py::TestNodeData -x` | Wave 0 |
| P9-T09 | Dashboard: TypeScript compiles without errors after api.ts extensions | build | `cd dashboard && npm run build` | Existing |
| P9-T10 | save_investigation() inserts row; list_saved_investigations() returns it | unit | `uv run pytest tests/unit/test_sqlite_store.py::TestSavedInvestigations -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/ -x -q`
- **Per wave merge:** `uv run pytest -x -q` (full suite — must not break Phase 8's 66 passing tests)
- **Phase gate:** Full suite green + `cd dashboard && npm run build` exits 0 before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_risk_scorer.py` — covers P9-T01, P9-T02, P9-T08
- [ ] `tests/unit/test_anomaly_rules.py` — covers P9-T03
- [ ] `tests/unit/test_explain_engine.py` — covers P9-T07 (mock OllamaClient)
- [ ] `tests/unit/test_score_api.py` — covers P9-T04 (FastAPI TestClient)
- [ ] `tests/unit/test_explain_api.py` — covers P9-T05 (FastAPI TestClient, mock Ollama)
- [ ] `tests/unit/test_top_threats_api.py` — covers P9-T06
- [ ] `tests/unit/test_sqlite_store.py` extended with `TestSavedInvestigations` class — covers P9-T10

Existing test infrastructure: pytest + pytest-asyncio already configured in pyproject.toml. Pattern from `test_normalizer.py`: use `make_event()` helper, class-based test grouping, no external I/O in unit tests.

---

## Open Questions

1. **Risk score persistence strategy: on-the-fly vs. cached**
   - What we know: `POST /api/score` can compute scores per-request. `GET /api/top-threats` needs pre-scored data to query efficiently.
   - What's unclear: Should scoring be triggered automatically on each `POST /detect/run` invocation, or only when `POST /api/score` is called explicitly?
   - Recommendation: Compute and persist risk scores inside the `/api/score` endpoint (write to SQLite). Add a lightweight `rescore_all()` call inside `POST /api/detect/run` so top-threats is always fresh after a detection run. This avoids a background job while keeping scores current.

2. **Explanation panel: streaming vs. single-response**
   - What we know: OllamaClient supports both `generate()` (single) and `stream_generate_iter()` (async generator for SSE). CONTEXT.md marks streaming as discretionary.
   - Recommendation: Use `generate()` (single-response) for Phase 9. This is simpler, avoids SSE complexity in the Svelte component, and qwen3:14b produces complete responses within the 120-second timeout. A "generating..." loading state in the panel is sufficient UX.

3. **Attack path identification: which edges are "attack path"?**
   - What we know: The investigate endpoint returns all graph edges. The highest-risk path should be highlighted.
   - Recommendation: Define attack path as the edges connecting the highest-risk process nodes in chronological order. The backend's `attack_chain` array (already sorted by timestamp) provides this sequence. Map `attack_chain[i].entity` → `attack_chain[i+1].entity` to identify path edges.

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `backend/services/ollama_client.py` — full API surface confirmed
- Direct code inspection: `backend/stores/sqlite_store.py` — schema DDL and method signatures confirmed
- Direct code inspection: `backend/api/investigate.py` — response shape confirmed
- Direct code inspection: `backend/main.py` — deferred router pattern confirmed
- Direct code inspection: `dashboard/src/components/InvestigationPanel.svelte` — Cytoscape style structure confirmed
- Direct code inspection: `dashboard/src/lib/api.ts` — typed client pattern confirmed
- Direct code inspection: `backend/causality/scoring.py` — additive scoring pattern confirmed
- Direct code inspection: `fixtures/ndjson/apt_scenario.ndjson` — test data shape confirmed

### Secondary (MEDIUM confidence)
- Cytoscape.js selector syntax for numeric comparisons (`node[prop > N]`) — standard documented behavior
- SQLite `ALTER TABLE ADD COLUMN IF NOT EXISTS` — available since SQLite 3.37 (Windows ships 3.40+)
- qwen3:14b context window — approximately 32k tokens; serializing 10-15 events is well within limit

### Tertiary (LOW confidence — flag for validation)
- Exact qwen3:14b response consistency for structured three-section output — should be validated against the actual model during Wave 1 implementation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed present by code inspection
- Architecture: HIGH — all patterns confirmed by reading existing source code
- Pitfalls: HIGH — most derived from actual code inspection (SQLite alter, Cytoscape data typing, investigate response shape)
- LLM grounding patterns: MEDIUM — patterns confirmed by existing prompts/ module structure; exact qwen3:14b behavior is LOW until tested

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (stable libraries; 30-day estimate)
