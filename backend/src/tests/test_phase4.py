"""Phase 4 smoke tests — Graph builder, correlation, attack paths, alert edges.

Wave 1 stubs: All tests are marked xfail until Phase 4 implementation plans
(02 and 03) are complete. Module-level imports are minimal (pytest, TestClient,
app only) to ensure this file imports cleanly against the current codebase.
"""
import pytest
from fastapi.testclient import TestClient
from backend.src.api.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# TestGraphModels
# Tests for extended GraphNode model with first_seen, last_seen, evidence fields.
# P4: Plan 02 extends GraphNode with new temporal + evidence fields.
# ---------------------------------------------------------------------------

class TestGraphModels:
    @pytest.mark.xfail(strict=False, reason="Phase 4 Plan 02/03 not yet implemented")
    def test_graphnode_has_new_fields(self):
        """GraphNode must have first_seen, last_seen, and evidence fields after Plan 02."""
        from backend.src.api.models import GraphNode
        node = GraphNode(id="host:testhost", type="host", label="testhost")
        assert hasattr(node, "first_seen"), "GraphNode must have first_seen field"
        assert hasattr(node, "last_seen"), "GraphNode must have last_seen field"
        assert hasattr(node, "evidence"), "GraphNode must have evidence field"


# ---------------------------------------------------------------------------
# TestNodeExtraction
# Tests for build_graph node emission.
# P4: build_graph([events], [alerts]) → GraphResponse; should emit host node.
# ---------------------------------------------------------------------------

class TestNodeExtraction:
    @pytest.mark.xfail(strict=False, reason="Phase 4 Plan 02/03 not yet implemented")
    def test_extract_nodes_emits_host_node(self):
        """build_graph must emit a node with id='host:testhost' for a dns event."""
        builder = pytest.importorskip(
            "backend.src.graph.builder",
            reason="graph.builder not yet implemented — Phase 4 Plan 02",
        )
        response = builder.build_graph(
            [
                {
                    "host": "testhost",
                    "event_type": "dns",
                    "id": "e1",
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            ],
            [],
        )
        assert any(n.id == "host:testhost" for n in response.nodes), (
            "Expected node with id='host:testhost' in graph nodes"
        )


# ---------------------------------------------------------------------------
# TestEdgeExtraction
# Tests for build_graph edge emission on connection events.
# P4: connection event with src_ip + dst_ip must produce at least one edge.
# ---------------------------------------------------------------------------

class TestEdgeExtraction:
    @pytest.mark.xfail(strict=False, reason="Phase 4 Plan 02/03 not yet implemented")
    def test_extract_edges_emits_connection_edge(self):
        """build_graph must emit at least one edge for a connection event with src/dst IPs."""
        builder = pytest.importorskip(
            "backend.src.graph.builder",
            reason="graph.builder not yet implemented — Phase 4 Plan 02",
        )
        response = builder.build_graph(
            [
                {
                    "host": "testhost",
                    "event_type": "connection",
                    "id": "e2",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "src_ip": "10.0.0.1",
                    "dst_ip": "8.8.8.8",
                }
            ],
            [],
        )
        assert len(response.edges) >= 1, "Expected at least one edge for a connection event"
        assert response.edges[0].src is not None, "Edge must have a non-None src field"


# ---------------------------------------------------------------------------
# TestCorrelation
# Tests for temporal correlation between dns_query and connection events.
# P4: same host + domain->IP within 30s window should produce a related_event edge.
# ---------------------------------------------------------------------------

class TestCorrelation:
    @pytest.mark.xfail(strict=False, reason="Phase 4 Plan 02/03 not yet implemented")
    def test_correlate_dns_chain(self):
        """build_graph must emit a 'related_event' edge when dns + connection events are within 30s."""
        builder = pytest.importorskip(
            "backend.src.graph.builder",
            reason="graph.builder not yet implemented — Phase 4 Plan 02",
        )
        response = builder.build_graph(
            [
                {
                    "host": "testhost",
                    "event_type": "dns",
                    "id": "e3",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "query": "evil.example.com",
                    "dst_ip": "1.2.3.4",
                },
                {
                    "host": "testhost",
                    "event_type": "connection",
                    "id": "e4",
                    "timestamp": "2026-01-01T00:00:30Z",
                    "dst_ip": "1.2.3.4",
                },
            ],
            [],
        )
        related_edges = [e for e in response.edges if e.type == "related_event"]
        assert len(related_edges) >= 1, (
            "Expected at least one 'related_event' edge for dns→connection chain within 30s"
        )


# ---------------------------------------------------------------------------
# TestAttackPaths
# Tests for attack path grouping in GraphResponse.
# P4: build_graph must return response with attack_paths as a list.
# ---------------------------------------------------------------------------

class TestAttackPaths:
    @pytest.mark.xfail(strict=False, reason="Phase 4 Plan 02/03 not yet implemented")
    def test_group_attack_paths_returns_list(self):
        """GraphResponse.attack_paths must be a list when returned by build_graph."""
        builder = pytest.importorskip(
            "backend.src.graph.builder",
            reason="graph.builder not yet implemented — Phase 4 Plan 02",
        )
        response = builder.build_graph(
            [
                {
                    "host": "testhost",
                    "event_type": "connection",
                    "id": "e5",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "src_ip": "10.0.0.1",
                    "dst_ip": "8.8.8.8",
                },
                {
                    "host": "testhost",
                    "event_type": "dns",
                    "id": "e6",
                    "timestamp": "2026-01-01T00:00:10Z",
                    "query": "evil.example.com",
                },
            ],
            [],
        )
        assert isinstance(response.attack_paths, list), (
            "GraphResponse must have an 'attack_paths' attribute that is a list"
        )


# ---------------------------------------------------------------------------
# TestGraphAPI
# Tests for GET /graph returning attack_paths and stats fields.
# P4: /graph endpoint must include attack_paths and stats keys after Plan 02.
# ---------------------------------------------------------------------------

class TestGraphAPI:
    @pytest.mark.xfail(strict=False, reason="Phase 4 Plan 02/03 not yet implemented")
    def test_get_graph_has_attack_paths_and_stats(self):
        """GET /graph must return 200 with both 'attack_paths' and 'stats' keys in response."""
        r = client.get("/graph")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert "attack_paths" in data, "GET /graph response must include 'attack_paths' key"
        assert "stats" in data, "GET /graph response must include 'stats' key"


# ---------------------------------------------------------------------------
# TestAlertGraph
# Tests for alert_trigger edges when a critical alert is triggered.
# P4: POST event that fires alert → GET /graph has edge with type='alert_trigger'.
# ---------------------------------------------------------------------------

class TestAlertGraph:
    @pytest.mark.xfail(strict=False, reason="Phase 4 Plan 02/03 not yet implemented")
    def test_alert_trigger_edge_created(self):
        """POST critical event → GET /graph must contain an edge with type='alert_trigger'."""
        payload = {
            "timestamp": "2026-01-01T00:00:00Z",
            "host": "alert-graph-host",
            "event": "dns",
            "severity": "critical",
            "query": "suspicious-domain.test",
        }
        client.post("/events", json=payload)
        r = client.get("/graph")
        assert r.status_code == 200, f"Expected 200 from GET /graph, got {r.status_code}"
        data = r.json()
        edges = data.get("edges", [])
        alert_trigger_edges = [e for e in edges if e.get("type") == "alert_trigger"]
        assert len(alert_trigger_edges) >= 1, (
            "Expected at least one edge with type='alert_trigger' after posting critical event"
        )


# ---------------------------------------------------------------------------
# TestCorrelateRoute
# Tests for GET /graph/correlate?event_id= endpoint.
# P4: New /graph/correlate route added in Plan 02; 200 for known, 404 for unknown.
# ---------------------------------------------------------------------------

class TestCorrelateRoute:
    @pytest.mark.xfail(strict=False, reason="Phase 4 Plan 02/03 not yet implemented")
    def test_get_graph_correlate_returns_200(self):
        """POST an event then GET /graph/correlate?event_id={id} must return 200."""
        ingest_payload = {
            "timestamp": "2026-01-01T00:00:00Z",
            "host": "correlate-host",
            "event": "dns",
            "query": "example.com",
        }
        post_r = client.post("/events", json=ingest_payload)
        event_id = post_r.json().get("id", "unknown-id")
        r = client.get("/graph/correlate", params={"event_id": event_id})
        assert r.status_code == 200, (
            f"GET /graph/correlate with known event_id must return 200, got {r.status_code}"
        )

    @pytest.mark.xfail(strict=False, reason="Phase 4 Plan 02/03 not yet implemented")
    def test_get_graph_correlate_unknown_returns_404(self):
        """GET /graph/correlate with unknown event_id must return 404."""
        r = client.get("/graph/correlate", params={"event_id": "nonexistent-id"})
        assert r.status_code == 404, (
            f"GET /graph/correlate with unknown event_id must return 404, got {r.status_code}"
        )
