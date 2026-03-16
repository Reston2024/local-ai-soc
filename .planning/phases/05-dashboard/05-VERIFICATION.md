---
phase: 05-dashboard
verified: 2026-03-16T19:30:00Z
status: passed
score: 9/9 must-haves verified
re_verification: false
---

# Phase 5: Dashboard Verification Report

**Phase Goal:** Suricata EVE JSON ingestion, ATT&CK-aware threat scoring, and score/tag display in the existing dashboard.
**Verified:** 2026-03-16T19:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Suricata EVE parser handles all 5 event types without crashing | VERIFIED | `suricata_parser.py` L69–165 handles alert/dns/flow/http/tls; unknown types return `suricata_{type}` prefix |
| 2 | EVE `dest_ip` correctly mapped to `dst_ip` (not left as None) | VERIFIED | L49: `dst_ip = data.get("dest_ip")` — trap documented in docstring |
| 3 | Suricata severity 1=critical, 4=low (inverted scale) | VERIFIED | `_SEVERITY_MAP = {1: "critical", 2: "high", 3: "medium", 4: "low"}` — P5-T7 XPASS |
| 4 | Threat scoring additive 0–100 with 4 components, capped | VERIFIED | `threat_scorer.py` L17–95; P5-T11 (score=40), P5-T12 (score=20), P5-T13 (<=100) all XPASS |
| 5 | ATT&CK mapper returns C2/T1071.004 for dns_query events | VERIFIED | `_EVENT_TYPE_MAP` dict L30–32; P5-T14 XPASS |
| 6 | POST /events accepts source=suricata; GET /alerts returns threat_score + attack_tags | VERIFIED | `routes.py` L107–117 honours source field; scoring block L68–76 wired; P5-T16/T17/T18 XPASS |
| 7 | Critical suricata alert gets threat_score >= 40 | VERIFIED | `rule_suricata_alert` in `rules.py` fires for critical/high suricata events; P5-T18 XPASS |
| 8 | Frontend shows score badge (green/yellow/red) and ATT&CK pill tags | VERIFIED | `EvidencePanel.svelte` L23–42 render score-badge and attack-pill; CSS L57–61 |
| 9 | Full regression — 41 pre-existing tests still pass | VERIFIED | `uv run pytest backend/src/tests/ -q` → 41 passed, 27 xpassed, 0 failures |

**Score:** 9/9 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/parsers/suricata_parser.py` | Full `parse_eve_line` with all 5 EVE types | VERIFIED | 166 lines; `_SEVERITY_MAP` + all 5 event branches + unknown fallback + JSON error fallback |
| `backend/src/detection/threat_scorer.py` | Additive 0–100 `score_alert` (4 components) | VERIFIED | 95 lines; `_SEVERITY_POINTS`, UUID regex, recurrence, graph_data guard |
| `backend/src/detection/attack_mapper.py` | Static ATT&CK lookup `map_attack_tags` | VERIFIED | 84 lines; 4 lookup dicts + first-match-wins logic |
| `backend/src/api/models.py` | `IngestSource.suricata` + `Alert.threat_score/attack_tags` | VERIFIED | L30: `suricata = "suricata"`; L93–94: `threat_score: int = 0`, `attack_tags: list[dict] = Field(...)` |
| `backend/src/tests/test_phase5.py` | 18 tests (P5-T1 through P5-T18) | VERIFIED | 452 lines; 5 classes, 18 methods; all 18 XPASS |
| `fixtures/suricata_eve_sample.ndjson` | 5 EVE lines (alert/dns/flow/http/tls) | VERIFIED | Exactly 5 lines, each valid JSON with correct event_type values |
| `backend/src/api/routes.py` | Scoring block in `_store_event()` + GET /threats | VERIFIED | L68–76: deferred import try/except block; L195–199: GET /threats endpoint |
| `backend/src/detection/rules.py` | `rule_suricata_alert` wired into `_RULES` | VERIFIED | L59–64: fires for `source=suricata` + severity critical/high; L73: in `_RULES` list |
| `infra/vector/vector.yaml` | Suricata EVE source scaffold (commented) | VERIFIED | `grep -c suricata_eve` = 5 hits |
| `infra/docker-compose.yml` | `jasonish/suricata` scaffold with BLOCKER comment | VERIFIED | `grep -c jasonish/suricata` = 1; `grep -c BLOCKER` = 1 |
| `infra/suricata/suricata.yaml` | Config scaffold | VERIFIED | File exists at `infra/suricata/suricata.yaml` |
| `infra/suricata/rules/local.rules` | Placeholder rules file | VERIFIED | File exists at `infra/suricata/rules/local.rules` |
| `frontend/src/lib/api.ts` | `AlertItem` with `threat_score` + `attack_tags`; `getThreats()` | VERIFIED | L19–28: `AlertItem` interface with both Phase 5 fields; L63–66: `getThreats()` |
| `frontend/src/components/panels/EvidencePanel.svelte` | Score badge + ATT&CK pills | VERIFIED | L23–42: conditional rendering with score-badge and attack-pill; CSS at L57–61 |
| `docs/decision-log.md` | Phase 5 decisions including `dest_ip` trap | VERIFIED | `grep -c dest_ip` = 1 |
| `docs/manifest.md` | Phase 5 file inventory | VERIFIED | `grep -c suricata_parser` = 1 |
| `docs/reproducibility.md` | Phase 5 validation commands | VERIFIED | `grep -c suricata_eve_sample` = 2 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/src/api/routes.py` | `backend/src/detection/threat_scorer.py` | deferred import `score_alert` in `_store_event()` | WIRED | L70: `from backend.src.detection.threat_scorer import score_alert as _score_alert` inside try/except |
| `backend/src/api/routes.py` | `backend/src/detection/attack_mapper.py` | deferred import `map_attack_tags` in `_store_event()` | WIRED | L71: `from backend.src.detection.attack_mapper import map_attack_tags as _map_attack_tags` |
| `backend/src/tests/test_phase5.py` | `backend/src/parsers/suricata_parser.py` | `import parse_eve_line` | WIRED | L24: `from backend.src.parsers.suricata_parser import parse_eve_line` (deferred, inside test) |
| `backend/src/tests/test_phase5.py` | `backend/src/detection/threat_scorer.py` | `import score_alert` | WIRED | L281: `from backend.src.detection.threat_scorer import score_alert` |
| `frontend/src/components/panels/EvidencePanel.svelte` | `frontend/src/lib/api.ts` | `AlertItem.threat_score` consumed via `selected` prop | WIRED | `selected.threat_score` and `selected.attack_tags` rendered in component |
| `backend/src/api/routes.py` | `backend/src/detection/rules.py` | `rule_suricata_alert` in `_RULES` list evaluated by `evaluate()` | WIRED | `rules.py` L73: `rule_suricata_alert` in `_RULES`; `routes.py` L59: `evaluate(event)` |

---

### Requirements Coverage

All requirement IDs declared across Phase 5 plans:

| Requirement | Source Plan | Description | Status | Evidence |
|------------|------------|-------------|--------|---------|
| FR-5S-1 | 05-00, 05-01 | Suricata EVE parser (all 5 event types) | SATISFIED | `suricata_parser.py` — full implementation; P5-T1 through P5-T7 pass |
| FR-5S-2 | 05-00, 05-01 | EVE field normalization (dest_ip→dst_ip, inverted severity) | SATISFIED | `_SEVERITY_MAP` + `dst_ip = data.get("dest_ip")` |
| FR-5S-3 | 05-00, 05-02 | Threat scoring model (additive 0–100) | SATISFIED | `score_alert` with all 4 components; P5-T11/T12/T13 pass |
| FR-5S-4 | 05-00, 05-02 | ATT&CK-style static tagging | SATISFIED | `map_attack_tags` with 4 lookup paths; P5-T14/T15 pass |
| FR-5S-5 | 05-03 | Route wiring — POST /events source=suricata accepted | SATISFIED | `routes.py` L110–115 honours source field; P5-T16 pass |
| FR-5S-6 | 05-03 | GET /alerts returns threat_score + attack_tags | SATISFIED | Alert.model_dump includes both fields; P5-T17 pass |
| FR-5S-7 | 05-03 | Frontend score badge + ATT&CK pill display | SATISFIED | `EvidencePanel.svelte` + `api.ts` AlertItem; TypeScript build clean (exit 0) |
| FR-5S-8 | 05-04 | Docs: decision-log, manifest, reproducibility | SATISFIED | All 3 docs updated with Phase 5 content |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/src/detection/threat_scorer.py` | 83–84 | `alert_host`/`alert_src_ip` referenced in graph block but assigned only inside `if alert_event is not None:` | INFO | Python ternary short-circuits correctly (`alert_host if alert_event is not None else None` — when condition is False, `alert_host` is not evaluated). Confirmed safe by runtime test with `graph_data={}` and no matching event. No action required. |
| `frontend/src/lib/api.ts` | 82 | `postIngest` source type is `'api' \| 'vector' \| 'syslog' \| 'fixture'` — does not include `'suricata'` | INFO | `getThreats()` is provided and typed. `postIngest` omission of `suricata` is minor — `POST /ingest` accepts all `IngestSource` enum values at runtime via `ingest_batch`. The typed function could be extended but is not a blocker. |

No blocker anti-patterns found.

---

### Human Verification Required

The following behaviors require human testing (cannot be verified programmatically):

#### 1. Score Badge Visual Rendering

**Test:** Load the dashboard in a browser; ingest a critical-severity Suricata event via POST /events; click the resulting alert node in the graph view to open EvidencePanel.
**Expected:** Score badge appears as a red pill (score=40 >= 30 triggers `score-yellow`; no additional signals so score=40 lands yellow, not red). Verify green/yellow/red thresholds visually at scores 20, 40, 70.
**Why human:** CSS class application (`score-red`/`score-yellow`/`score-green`) cannot be tested without a rendered browser.

#### 2. ATT&CK Pill Rendering

**Test:** Trigger an alert from a `dns_query` event. Open EvidencePanel for that alert.
**Expected:** "Command and Control · T1071.004" appears as a blue pill badge.
**Why human:** The template `{tag.tactic} · {tag.technique}` formatting and visual pill appearance requires browser rendering to verify.

#### 3. GET /threats Endpoint Ordering

**Test:** Ingest events that trigger alerts with different scores; call GET /threats.
**Expected:** Alerts returned sorted by `threat_score` descending; alerts with score=0 are excluded.
**Why human:** Ordering is deterministic but requires multiple alerts with different scores to verify sorting behavior in a live session.

---

### Gaps Summary

No gaps found. All 9 observable truths are verified. All required artifacts exist, are substantive (not stubs), and are correctly wired. The full test suite passes: 41 pre-existing tests pass + 18 Phase 5 tests XPASS. Frontend TypeScript compiles cleanly.

**Notable deviation from original plan (handled correctly):** Plan 03 added `rule_suricata_alert` to `rules.py` (not in the original plan scope). This was a required fix — without a detection rule firing for suricata source events, the scoring block in `_store_event()` would have no alerts to enrich, making P5-T18 unachievable. The fix is minimal, targeted, and correct.

---

## Commit Trail

| Commit | Description |
|--------|-------------|
| `c8f9e10` | feat(05-00): suricata_parser, threat_scorer, attack_mapper stubs + EVE fixture |
| `9b2751c` | test(05-00): 18 xfail stubs in test_phase5.py |
| `90e4fad` | feat(05-01): implement Suricata EVE parser + extend models |
| `ac35477` | feat(05-02): implement threat_scorer and attack_mapper |
| `8734fde` | feat(05-03): wire score_alert + map_attack_tags into _store_event(), add GET /threats |
| `eec5ed1` | feat(05-03): infrastructure scaffolds + frontend threat score/ATT&CK extensions |
| `1fc8d93` | docs(05-04): append Phase 5 content to decision-log, manifest, reproducibility |

---

*Verified: 2026-03-16T19:30:00Z*
*Verifier: Claude (gsd-verifier)*
