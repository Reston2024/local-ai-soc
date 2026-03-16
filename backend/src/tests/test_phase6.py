"""Phase 6 smoke tests — causality engine, entity resolver, attack chain, MITRE mapper,
scoring, API endpoints, and dashboard build verification.

Wave 0 stubs: All tests are marked xfail until Phase 6 implementation plans
(01 through 04) are complete. Module-level imports are minimal to ensure this
file imports cleanly before implementation stubs are replaced.
"""
import pytest
from fastapi.testclient import TestClient
from backend.src.api.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# TestEntityResolver
# Tests for resolve_canonical_id: entity normalization.
# P6: Plan 01 will implement resolve_canonical_id in causality/entity_resolver.py.
# ---------------------------------------------------------------------------

class TestEntityResolver:
    @pytest.mark.xfail(strict=False, reason="Phase 6 Plan 01 not yet implemented")
    def test_resolve_host_returns_lowercase(self):
        """resolve_canonical_id must return 'host:workstation01' for WORKSTATION01 input."""
        from backend.causality.entity_resolver import resolve_canonical_id
        result = resolve_canonical_id({"host": "WORKSTATION01"}, "host")
        assert result == "host:workstation01", \
            f"Expected 'host:workstation01', got {result!r}"


# ---------------------------------------------------------------------------
# TestEntityResolverCaseFolding
# Tests that canonical IDs are case-insensitive.
# P6: Plan 01 will implement case folding in resolve_canonical_id.
# ---------------------------------------------------------------------------

class TestEntityResolverCaseFolding:
    @pytest.mark.xfail(strict=False, reason="Phase 6 Plan 01 not yet implemented")
    def test_case_folding_consistent(self):
        """resolve_canonical_id must return same ID regardless of input case."""
        from backend.causality.entity_resolver import resolve_canonical_id
        upper = resolve_canonical_id({"host": "WORKSTATION01"}, "host")
        lower = resolve_canonical_id({"host": "workstation01"}, "host")
        assert upper == lower, \
            f"Case folding failed: upper={upper!r} != lower={lower!r}"


# ---------------------------------------------------------------------------
# TestAttackChainBuilder
# Tests for find_causal_chain: BFS causal chain construction.
# P6: Plan 01 will implement find_causal_chain in causality/attack_chain_builder.py.
# ---------------------------------------------------------------------------

class TestAttackChainBuilder:
    @pytest.mark.xfail(strict=False, reason="Phase 6 Plan 01 not yet implemented")
    def test_chain_sorted_by_timestamp_starts_with_start_id(self):
        """find_causal_chain must return list sorted by timestamp where first item has id == start_id."""
        from backend.causality.attack_chain_builder import find_causal_chain
        events = [
            {"id": "e1", "timestamp": "2026-01-15T10:00:00Z", "host": "W01", "src_ip": "192.168.1.50"},
            {"id": "e2", "timestamp": "2026-01-15T10:00:01Z", "host": "W01", "src_ip": "192.168.1.50"},
            {"id": "e3", "timestamp": "2026-01-15T10:00:02Z", "host": "W01", "src_ip": "192.168.1.50"},
        ]
        result = find_causal_chain("e1", events)
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert len(result) >= 1, "Chain must have at least the start event"
        assert result[0]["id"] == "e1", \
            f"First chain event must have id='e1', got {result[0].get('id')!r}"


# ---------------------------------------------------------------------------
# TestAttackChainDepthCap
# Tests that max_depth limits BFS traversal.
# P6: Plan 01 will implement depth capping in find_causal_chain.
# ---------------------------------------------------------------------------

class TestAttackChainDepthCap:
    @pytest.mark.xfail(strict=False, reason="Phase 6 Plan 01 not yet implemented")
    def test_depth_cap_limits_results(self):
        """BFS with max_depth=1 on a 3-hop chain must return only events at depth <= 1."""
        from backend.causality.attack_chain_builder import find_causal_chain
        # 3-hop chain: e1 -> e2 -> e3 -> e4 (each shares a field with the next)
        events = [
            {"id": "e1", "timestamp": "2026-01-15T10:00:00Z", "host": "W01", "src_ip": "192.168.1.50"},
            {"id": "e2", "timestamp": "2026-01-15T10:00:01Z", "host": "W01", "src_ip": "192.168.1.51"},
            {"id": "e3", "timestamp": "2026-01-15T10:00:02Z", "host": "W02", "src_ip": "192.168.1.51"},
            {"id": "e4", "timestamp": "2026-01-15T10:00:03Z", "host": "W02", "src_ip": "192.168.1.52"},
        ]
        result = find_causal_chain("e1", events, max_depth=1)
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        # With max_depth=1 a 3-hop chain should not include e4 (at depth 3)
        result_ids = [e["id"] for e in result]
        assert "e4" not in result_ids, \
            f"max_depth=1 must exclude events beyond depth 1; got {result_ids}"


# ---------------------------------------------------------------------------
# TestAttackChainCycleDetection
# Tests that circular event references do not cause infinite loops.
# P6: Plan 01 will implement cycle detection in find_causal_chain.
# ---------------------------------------------------------------------------

class TestAttackChainCycleDetection:
    @pytest.mark.xfail(strict=False, reason="Phase 6 Plan 01 not yet implemented")
    def test_circular_events_no_infinite_loop(self):
        """Events referencing each other circularly must not cause infinite loop (completes < 1s)."""
        import time
        from backend.causality.attack_chain_builder import find_causal_chain
        # Two events that share all entity fields — circular reference
        events = [
            {"id": "e1", "timestamp": "2026-01-15T10:00:00Z", "host": "W01", "src_ip": "10.0.0.1"},
            {"id": "e2", "timestamp": "2026-01-15T10:00:01Z", "host": "W01", "src_ip": "10.0.0.1"},
        ]
        start = time.monotonic()
        result = find_causal_chain("e1", events)
        elapsed = time.monotonic() - start
        assert elapsed < 1.0, f"Cycle detection failed: took {elapsed:.2f}s (expected < 1s)"
        assert isinstance(result, list), f"Expected list, got {type(result)}"


# ---------------------------------------------------------------------------
# TestMitreMapper
# Tests for map_techniques: MITRE ATT&CK technique/tactic mapping.
# P6: Plan 02 will implement map_techniques in causality/mitre_mapper.py.
# ---------------------------------------------------------------------------

class TestMitreMapper:
    @pytest.mark.xfail(strict=False, reason="Phase 6 Plan 02 not yet implemented")
    def test_known_tag_maps_to_technique(self):
        """map_techniques(['attack.t1059.001'], '', '') must return PowerShell/Execution entry."""
        from backend.causality.mitre_mapper import map_techniques
        result = map_techniques(["attack.t1059.001"], "", "")
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert len(result) >= 1, "Expected at least one technique mapping"
        entry = result[0]
        assert entry.get("technique") == "T1059.001", \
            f"Expected technique='T1059.001', got {entry.get('technique')!r}"
        assert entry.get("tactic") == "Execution", \
            f"Expected tactic='Execution', got {entry.get('tactic')!r}"
        assert entry.get("name") == "PowerShell", \
            f"Expected name='PowerShell', got {entry.get('name')!r}"


# ---------------------------------------------------------------------------
# TestMitreMapperGraceful
# Tests that unknown tags return empty list without exception.
# P6: Plan 02 will implement graceful fallback in map_techniques.
# ---------------------------------------------------------------------------

class TestMitreMapperGraceful:
    @pytest.mark.xfail(strict=False, reason="Phase 6 Plan 02 not yet implemented")
    def test_unknown_tag_returns_empty(self):
        """map_techniques(['attack.tunknown999'], '', '') must return [] without raising."""
        from backend.causality.mitre_mapper import map_techniques
        result = map_techniques(["attack.tunknown999"], "", "")
        assert result == [], \
            f"Unknown tag must return [], got {result!r}"


# ---------------------------------------------------------------------------
# TestScoring
# Tests for score_chain: attack chain severity scoring (0-100).
# P6: Plan 02 will implement score_chain in causality/scoring.py.
# ---------------------------------------------------------------------------

class TestScoring:
    @pytest.mark.xfail(strict=False, reason="Phase 6 Plan 02 not yet implemented")
    def test_empty_inputs_return_zero(self):
        """score_chain([], [], []) must return 0."""
        from backend.causality.scoring import score_chain
        result = score_chain([], [], [])
        assert result == 0, f"Empty inputs must score 0, got {result}"

    @pytest.mark.xfail(strict=False, reason="Phase 6 Plan 02 not yet implemented")
    def test_critical_alert_scores_above_zero(self):
        """score_chain with a critical alert must return value > 0."""
        from backend.causality.scoring import score_chain
        alerts = [{"severity": "critical", "rule": "some-rule", "threat_score": 40}]
        result = score_chain([], alerts, [])
        assert result > 0, f"Critical alert must produce score > 0, got {result}"

    @pytest.mark.xfail(strict=False, reason="Phase 6 Plan 02 not yet implemented")
    def test_score_capped_at_100(self):
        """score_chain must never exceed 100 regardless of stacked signals."""
        from backend.causality.scoring import score_chain
        # Lots of critical alerts and techniques to stress-test cap
        alerts = [{"severity": "critical", "rule": "r", "threat_score": 90}] * 10
        techniques = [{"technique": "T1059.001", "tactic": "Execution"}] * 10
        events = [{"id": f"e{i}", "timestamp": "2026-01-15T10:00:00Z"} for i in range(20)]
        result = score_chain(events, alerts, techniques)
        assert result <= 100, f"Score must be capped at 100, got {result}"


# ---------------------------------------------------------------------------
# TestCausalityEngine
# Tests for build_causality_sync: full orchestrator returning graph dict.
# P6: Plan 03 will implement build_causality_sync in causality/engine.py.
# ---------------------------------------------------------------------------

class TestCausalityEngine:
    @pytest.mark.xfail(strict=False, reason="Phase 6 Plan 03 not yet implemented")
    def test_engine_returns_required_keys(self):
        """build_causality_sync must return dict with 'nodes', 'edges', 'chain' keys."""
        from backend.causality.engine import build_causality_sync
        events = [
            {"id": "e1", "timestamp": "2026-01-15T10:00:00Z", "host": "W01", "severity": "high"},
        ]
        alerts = [
            {
                "id": "alert1",
                "event_id": "e1",
                "timestamp": "2026-01-15T10:00:01Z",
                "rule": "some-rule",
                "severity": "high",
                "description": "Test alert",
                "threat_score": 40,
            }
        ]
        result = build_causality_sync("alert1", events, alerts)
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "nodes" in result, f"Result must have 'nodes' key; got keys: {list(result.keys())}"
        assert "edges" in result, f"Result must have 'edges' key; got keys: {list(result.keys())}"
        assert "chain" in result, f"Result must have 'chain' key; got keys: {list(result.keys())}"


# ---------------------------------------------------------------------------
# TestGraphEndpoint
# Tests for GET /api/graph/{alert_id}: causality graph endpoint.
# P6: Plan 04 will implement the endpoint in causality_routes.py.
# ---------------------------------------------------------------------------

class TestGraphEndpoint:
    @pytest.mark.xfail(strict=False, reason="Phase 6 Plan 04 not yet implemented")
    def test_graph_endpoint_returns_nodes(self):
        """GET /api/graph/alert1 with seeded alert must return 200 with 'nodes' key."""
        # Seed an event first
        client.post("/events", json={
            "timestamp": "2026-01-15T10:00:00Z",
            "host": "W01",
            "event_type": "process_creation",
            "severity": "high",
            "src_ip": "192.168.1.50",
        })
        r = client.get("/api/graph/alert1")
        assert r.status_code == 200, \
            f"GET /api/graph/alert1 must return 200, got {r.status_code}"
        data = r.json()
        assert "nodes" in data, \
            f"Response must contain 'nodes' key; got: {list(data.keys())}"


# ---------------------------------------------------------------------------
# TestEntityEndpoint
# Tests for GET /api/entity/{entity_id}: entity lookup endpoint.
# P6: Plan 04 will implement the endpoint in causality_routes.py.
# ---------------------------------------------------------------------------

class TestEntityEndpoint:
    @pytest.mark.xfail(strict=False, reason="Phase 6 Plan 04 not yet implemented")
    def test_entity_endpoint_returns_data(self):
        """GET /api/entity/host:workstation01 must return 200 with entity data dict."""
        r = client.get("/api/entity/host:workstation01")
        assert r.status_code == 200, \
            f"GET /api/entity/host:workstation01 must return 200, got {r.status_code}"
        data = r.json()
        assert isinstance(data, dict), \
            f"Response must be a dict; got {type(data)}"


# ---------------------------------------------------------------------------
# TestAttackChainEndpoint
# Tests for GET /api/attack_chain/{alert_id}: attack chain endpoint.
# P6: Plan 04 will implement the endpoint in causality_routes.py.
# ---------------------------------------------------------------------------

class TestAttackChainEndpoint:
    @pytest.mark.xfail(strict=False, reason="Phase 6 Plan 04 not yet implemented")
    def test_attack_chain_endpoint_returns_edges(self):
        """GET /api/attack_chain/alert1 must return 200 with 'edges' key."""
        # Seed an event first
        client.post("/events", json={
            "timestamp": "2026-01-15T10:00:00Z",
            "host": "W01",
            "event_type": "process_creation",
            "severity": "high",
            "src_ip": "192.168.1.50",
        })
        r = client.get("/api/attack_chain/alert1")
        assert r.status_code == 200, \
            f"GET /api/attack_chain/alert1 must return 200, got {r.status_code}"
        data = r.json()
        assert "edges" in data, \
            f"Response must contain 'edges' key; got: {list(data.keys())}"


# ---------------------------------------------------------------------------
# TestQueryEndpoint
# Tests for POST /api/query: causality query endpoint.
# P6: Plan 04 will implement the endpoint in causality_routes.py.
# ---------------------------------------------------------------------------

class TestQueryEndpoint:
    @pytest.mark.xfail(strict=False, reason="Phase 6 Plan 04 not yet implemented")
    def test_query_endpoint_returns_200(self):
        """POST /api/query with minimal payload must return 200."""
        r = client.post("/api/query", json={"q": "test", "entity_id": None})
        assert r.status_code == 200, \
            f"POST /api/query must return 200, got {r.status_code}"


# ---------------------------------------------------------------------------
# TestDashboardBuild
# Tests that the frontend npm build succeeds.
# P6: Plan 04 will ensure dashboard build is green with new components.
# ---------------------------------------------------------------------------

class TestDashboardBuild:
    @pytest.mark.xfail(strict=False, reason="dashboard build test — passes when npm build is green")
    def test_npm_build_exits_zero(self):
        """npm run build in frontend/ must exit 0."""
        import subprocess
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd="frontend",
            capture_output=True,
            timeout=120,
        )
        assert result.returncode == 0, \
            f"npm run build failed with exit code {result.returncode}.\n" \
            f"stdout: {result.stdout.decode()[-1000:]}\n" \
            f"stderr: {result.stderr.decode()[-1000:]}"
