"""
Wave 0 TDD stubs for Phase 41 threat map API.
P41-T01: flow query structure
P41-T02: window mapping constants
P41-T03: direction detection
P41-T04: stats aggregation
P41-T05: map endpoint response shape
All stubs SKIP RED until Plan 02 implements backend/api/map.py.
"""
from __future__ import annotations
import pytest

pytestmark = pytest.mark.unit

# Guard: skip entire module if map API not yet implemented
try:
    from backend.api.map import WINDOW_TO_SECONDS, detect_direction, build_map_stats, parse_ipsum_line
    _MAP_AVAILABLE = True
except ImportError:
    _MAP_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _MAP_AVAILABLE, reason="map API not yet implemented (Plan 02)")


def test_flow_query_structure():
    """get_network_flows returns list[dict] with src_ip, dst_ip, conn_count keys."""
    # Stub: will be implemented in Plan 02
    # Expected: each row dict has keys src_ip, dst_ip, conn_count (integers/strings)
    pytest.skip("stub — Plan 02 implements get_network_flows()")


def test_window_mapping():
    """WINDOW_TO_SECONDS maps time window strings to integer seconds."""
    assert WINDOW_TO_SECONDS["1h"] == 3600
    assert WINDOW_TO_SECONDS["6h"] == 21600
    assert WINDOW_TO_SECONDS["24h"] == 86400
    assert WINDOW_TO_SECONDS["7d"] == 604800


def test_direction_detection():
    """detect_direction classifies flows based on RFC1918 address ranges."""
    assert detect_direction("192.168.1.5", "1.2.3.4") == "outbound"
    assert detect_direction("1.2.3.4", "192.168.1.5") == "inbound"
    assert detect_direction("10.0.0.1", "8.8.8.8") == "outbound"
    assert detect_direction("8.8.8.8", "1.1.1.1") == "lateral"


def test_stats_aggregation():
    """build_map_stats returns dict with all required stat keys."""
    # Stub: will be implemented in Plan 02
    pytest.skip("stub — Plan 02 implements build_map_stats()")


def test_map_endpoint_response_shape():
    """GET /api/map/data?window=24h returns flows, ips, stats top-level keys."""
    # Stub: will be implemented in Plan 02
    pytest.skip("stub — Plan 02 implements /api/map/data endpoint")
