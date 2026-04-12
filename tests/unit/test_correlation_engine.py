"""
Wave 0 TDD stubs for Phase 43 Correlation Engine.
P43-T01: CorrelationEngine module contract.
P43-T02: port scan detection (_detect_port_scans).
P43-T03: brute force detection (_detect_brute_force).
P43-T04: beaconing detection (_detect_beaconing).
P43-T05: chain detection (_detect_chains) + YAML loading.

test_correlation_engine_module_exists runs RED (module does not exist yet).
All other stubs SKIP until Plans 43-02 / 43-03 implement the engine.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

_skip = pytest.mark.skip(reason="stub — implement in Plan 43-02/43-03")


# ---------------------------------------------------------------------------
# RED test — must run and FAIL until Plan 43-02 creates the module
# ---------------------------------------------------------------------------
def test_correlation_engine_module_exists():
    """RED until Plan 43-02 creates detections/correlation_engine.py."""
    from detections.correlation_engine import CorrelationEngine  # noqa: F401


# ---------------------------------------------------------------------------
# Stub 1 — port scan detection
# ---------------------------------------------------------------------------
@_skip
def test_port_scan_detection():
    """
    CorrelationEngine._detect_port_scans() returns a list of DetectionRecord
    when 15+ distinct dst_ports are seen from the same src_ip within a 60-second
    window.
    """
    pass


# ---------------------------------------------------------------------------
# Stub 2 — brute force detection
# ---------------------------------------------------------------------------
@_skip
def test_brute_force_detection():
    """
    CorrelationEngine._detect_brute_force() returns a DetectionRecord with
    severity='high' when 10+ failed authentication events occur from the same
    src_ip within a 60-second window.
    """
    pass


# ---------------------------------------------------------------------------
# Stub 3 — beaconing CV detection
# ---------------------------------------------------------------------------
@_skip
def test_beaconing_cv_detection():
    """
    CorrelationEngine._detect_beaconing() returns a DetectionRecord with
    rule_id='corr-beacon' when the coefficient of variation (stddev/mean) of
    inter-arrival times is below 0.3 across 20+ connections to the same dst_ip.
    """
    pass


# ---------------------------------------------------------------------------
# Stub 4 — DetectionRecord structure
# ---------------------------------------------------------------------------
@_skip
def test_detection_record_created():
    """
    CorrelationEngine.run() result items have:
      - rule_id starting with 'corr-'
      - matched_event_ids as a non-empty list
    """
    pass


# ---------------------------------------------------------------------------
# Stub 5 — dedup suppresses repeat fires
# ---------------------------------------------------------------------------
@_skip
def test_dedup_suppresses_repeat():
    """
    save_detections() skips the DB insert when the same (rule_id, entity_key)
    combination has already fired within the configured dedup window.
    """
    pass


# ---------------------------------------------------------------------------
# Stub 6 — chain detection
# ---------------------------------------------------------------------------
@_skip
def test_chain_detection():
    """
    CorrelationEngine._detect_chains() returns a DetectionRecord with
    rule_id='corr-chain-scan-bruteforce' when both corr-portscan and
    corr-bruteforce have fired for the same src_ip within the last 15 minutes.
    """
    pass


# ---------------------------------------------------------------------------
# Stub 7 — chain YAML loading
# ---------------------------------------------------------------------------
@_skip
def test_chain_yaml_loading():
    """
    load_chains(path) reads a YAML file and returns the count of chain
    definitions loaded.
    """
    pass


# ---------------------------------------------------------------------------
# Stub 8 — ingest hook calls correlation
# ---------------------------------------------------------------------------
@_skip
def test_ingest_hook_calls_correlation():
    """
    When CorrelationEngine is wired into IngestionLoader, loader calls
    correlation_engine.run() after each batch of events is ingested.
    """
    pass
