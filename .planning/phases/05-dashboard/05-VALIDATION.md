---
phase: 5
slug: dashboard
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-16
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (auto mode, set in pyproject.toml) |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest backend/src/tests/test_phase5.py -x` |
| **Full suite command** | `uv run pytest backend/src/tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest backend/src/tests/test_phase5.py -x`
- **After every plan wave:** Run `uv run pytest backend/src/tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| P5-T1 | 01 | 1 | parse alert | unit | `pytest test_phase5.py::TestSuricataParser::test_parse_alert_event -x` | ❌ W0 | ⬜ pending |
| P5-T2 | 01 | 1 | dest_ip→dst_ip | unit | `pytest test_phase5.py::TestSuricataParser::test_parse_dns_event -x` | ❌ W0 | ⬜ pending |
| P5-T3 | 01 | 1 | parse flow | unit | `pytest test_phase5.py::TestSuricataParser::test_parse_flow_event -x` | ❌ W0 | ⬜ pending |
| P5-T4 | 01 | 1 | parse http | unit | `pytest test_phase5.py::TestSuricataParser::test_parse_http_event -x` | ❌ W0 | ⬜ pending |
| P5-T5 | 01 | 1 | parse tls | unit | `pytest test_phase5.py::TestSuricataParser::test_parse_tls_event -x` | ❌ W0 | ⬜ pending |
| P5-T6 | 01 | 1 | unknown type no crash | unit | `pytest test_phase5.py::TestSuricataParser::test_parse_unknown_event_no_crash -x` | ❌ W0 | ⬜ pending |
| P5-T7 | 01 | 1 | severity inversion | unit | `pytest test_phase5.py::TestSuricataParser::test_severity_mapping -x` | ❌ W0 | ⬜ pending |
| P5-T8 | 01 | 1 | IngestSource.suricata | unit | `pytest test_phase5.py::TestModels::test_ingest_source_suricata -x` | ❌ W0 | ⬜ pending |
| P5-T9 | 01 | 1 | Alert new fields defaults | unit | `pytest test_phase5.py::TestModels::test_alert_new_fields_defaults -x` | ❌ W0 | ⬜ pending |
| P5-T10 | 01 | 1 | regression | regression | `uv run pytest backend/src/tests/ -v` | ✅ | ⬜ pending |
| P5-T11 | 02 | 1 | score critical | unit | `pytest test_phase5.py::TestThreatScorer::test_score_critical_suricata -x` | ❌ W0 | ⬜ pending |
| P5-T12 | 02 | 1 | score sigma hit | unit | `pytest test_phase5.py::TestThreatScorer::test_score_sigma_hit -x` | ❌ W0 | ⬜ pending |
| P5-T13 | 02 | 1 | score cap 100 | unit | `pytest test_phase5.py::TestThreatScorer::test_score_capped_at_100 -x` | ❌ W0 | ⬜ pending |
| P5-T14 | 02 | 1 | ATT&CK dns→C2 | unit | `pytest test_phase5.py::TestAttackMapper::test_dns_query_maps_to_c2 -x` | ❌ W0 | ⬜ pending |
| P5-T15 | 02 | 1 | ATT&CK unmapped=[] | unit | `pytest test_phase5.py::TestAttackMapper::test_unmapped_returns_empty_list -x` | ❌ W0 | ⬜ pending |
| P5-T16 | 03 | 2 | ingest suricata source | integration | `pytest test_phase5.py::TestSuricataRoute::test_ingest_suricata_source -x` | ❌ W0 | ⬜ pending |
| P5-T17 | 03 | 2 | alerts have new fields | integration | `pytest test_phase5.py::TestSuricataRoute::test_alerts_have_new_fields -x` | ❌ W0 | ⬜ pending |
| P5-T18 | 03 | 2 | high score for critical | integration | `pytest test_phase5.py::TestSuricataRoute::test_high_score_for_critical_alert -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/src/tests/test_phase5.py` — test stubs for P5-T1 through P5-T18
- [ ] `backend/src/parsers/suricata_parser.py` — stub with `parse_eve_line()` signature
- [ ] `backend/src/detection/threat_scorer.py` — stub with `score_alert()` signature
- [ ] `backend/src/detection/attack_mapper.py` — stub with `map_attack_tags()` signature
- [ ] `fixtures/suricata_eve_sample.ndjson` — one line per event type (alert/flow/dns/http/tls)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Suricata Docker service scaffolded with blocker comment | infra | Windows host cannot run suricata container | Inspect `infra/docker-compose.yml` for suricata service with blocker comment |
| EvidencePanel shows threat_score badge | UI | No frontend test harness | Load dashboard, ingest suricata fixture, open alert detail — verify score badge appears |
| ATT&CK tags display as pills in EvidencePanel | UI | No frontend test harness | Verify `tactic · technique` pills render for tagged alerts |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
