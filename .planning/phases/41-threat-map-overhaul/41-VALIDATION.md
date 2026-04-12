---
phase: 41
slug: threat-map-overhaul
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-12
---

# Phase 41 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (uv managed) |
| **Config file** | pyproject.toml (pytest-asyncio mode: auto) |
| **Quick run command** | `uv run pytest tests/unit/test_map_api.py tests/unit/test_osint_classification.py -x` |
| **Full suite command** | `uv run pytest tests/unit/ -x` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_map_api.py tests/unit/test_osint_classification.py -x`
- **After every plan wave:** Run `uv run pytest tests/unit/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 41-01-01 | 01 | 0 | MAP-01..04,11 | unit | `uv run pytest tests/unit/test_map_api.py -x` | ❌ Wave 0 | ⬜ pending |
| 41-01-02 | 01 | 0 | MAP-05..10 | unit | `uv run pytest tests/unit/test_osint_classification.py -x` | ❌ Wave 0 | ⬜ pending |
| 41-02-01 | 02 | 1 | MAP-01,03 | unit | `uv run pytest tests/unit/test_map_api.py::test_flow_query_structure tests/unit/test_map_api.py::test_direction_detection -x` | ✅ (from W0) | ⬜ pending |
| 41-02-02 | 02 | 1 | MAP-02,04 | unit | `uv run pytest tests/unit/test_map_api.py::test_window_mapping tests/unit/test_map_api.py::test_stats_aggregation -x` | ✅ (from W0) | ⬜ pending |
| 41-02-03 | 02 | 1 | MAP-11 | unit | `uv run pytest tests/unit/test_map_api.py::test_map_endpoint_response_shape -x` | ✅ (from W0) | ⬜ pending |
| 41-03-01 | 03 | 2 | MAP-05,06 | unit | `uv run pytest tests/unit/test_osint_classification.py::test_geo_ipapi_extended_fields tests/unit/test_osint_classification.py::test_ipapi_is_parse -x` | ✅ (from W0) | ⬜ pending |
| 41-03-02 | 03 | 2 | MAP-07,08,10 | unit | `uv run pytest tests/unit/test_osint_classification.py::test_ipsum_tier_lookup tests/unit/test_osint_classification.py::test_tor_exit_check tests/unit/test_osint_classification.py::test_ipsum_parser -x` | ✅ (from W0) | ⬜ pending |
| 41-03-03 | 03 | 2 | MAP-09 | unit | `uv run pytest tests/unit/test_osint_classification.py::test_osint_cache_schema_migration -x` | ✅ (from W0) | ⬜ pending |
| 41-04-01 | 04 | 3 | MAP-12 | manual | Browser: navigate to Threat Map, verify MarkerCluster renders, arc lines appear, LAN node at center | N/A | ⬜ pending |
| 41-04-02 | 04 | 3 | MAP-13 | manual | Browser: click [1h][6h][24h][7d] buttons, verify markers and arcs update | N/A | ⬜ pending |
| 41-04-03 | 04 | 3 | MAP-14 | manual | Browser: click a marker, verify side panel shows CLASSIFICATION section at top | N/A | ⬜ pending |
| 41-04-04 | 04 | 3 | MAP-15 | manual | Browser: verify 60s auto-refresh fires; hover a marker and confirm refresh pauses | N/A | ⬜ pending |
| 41-04-05 | 04 | 3 | MAP-16 | manual | Browser: verify ipsum-flagged IPs show thicker ring vs clean IPs | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_map_api.py` — 5 stubs: flow_query_structure, window_mapping, direction_detection, stats_aggregation, map_endpoint_response_shape
- [ ] `tests/unit/test_osint_classification.py` — 6 stubs: geo_ipapi_extended_fields, ipapi_is_parse, ipsum_tier_lookup, tor_exit_check, osint_cache_schema_migration, ipsum_parser

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| MarkerCluster renders, arc lines appear, LAN node at center | MAP-12 | Leaflet rendering requires browser | Navigate to Threat Map, zoom in/out, verify cluster expansion and LAN→external arcs |
| Time window buttons update map content | MAP-13 | DOM interaction + data reload requires browser | Click each time window button, verify marker set changes |
| Side panel CLASSIFICATION section | MAP-14 | Svelte reactive DOM requires browser | Click any external IP marker, verify CLASSIFICATION is first section with Tor/VPN/Datacenter badge |
| 60s auto-refresh + pause on hover | MAP-15 | Timer behavior requires browser | Watch map for 60s, hover a marker, verify no redraw during hover |
| ipsum tier ring thickness variation | MAP-16 | CSS visual difference requires browser | Compare ring thickness of a tier-5+ IP vs a clean IP |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
