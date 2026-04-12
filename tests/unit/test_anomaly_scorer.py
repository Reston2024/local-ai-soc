"""
Wave 0 TDD stubs for Phase 42 AnomalyScorer.
P42-T01: score_one, learn_one, entity_key, model persistence.
P42-T02: HalfSpaceTrees streaming scoring, peer group key extraction.

All stubs SKIP until Plan 42-02 implements AnomalyScorer.
Stubs with real assertion bodies go RED when module exists but behavior is wrong.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Try importing AnomalyScorer — skip all stubs if not yet implemented
# ---------------------------------------------------------------------------
try:
    from backend.services.anomaly.scorer import AnomalyScorer, entity_key
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

pytestmark = pytest.mark.skipif(not _AVAILABLE, reason="AnomalyScorer not yet implemented (Plan 42-02)")


# ---------------------------------------------------------------------------
# Stub 1 — score_event returns float in [0.0, 1.0]
# ---------------------------------------------------------------------------
def test_score_event_returns_float():
    scorer = AnomalyScorer()
    result = scorer.score_one({"hostname": "ws1", "process_name": "svchost.exe"})
    assert isinstance(result, float)
    assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# Stub 2 — learn_one updates model so subsequent score differs
# ---------------------------------------------------------------------------
def test_learn_updates_model():
    """Score after learn_one differs from fresh model — model adapts."""
    scorer_fresh = AnomalyScorer()
    event = {"hostname": "ws1", "process_name": "svchost.exe", "bytes_out": 500}

    # Score without any learning
    score_before = scorer_fresh.score_one(event)

    # Learn many similar events then score
    scorer_learned = AnomalyScorer()
    for _ in range(20):
        scorer_learned.learn_one({"hostname": "ws1", "process_name": "svchost.exe", "bytes_out": 500})
    score_after = scorer_learned.score_one(event)

    # After learning the pattern, model state has changed — scores must differ
    assert score_before != score_after


# ---------------------------------------------------------------------------
# Stub 3 — entity_key extracts peer group key with /24 subnet
# ---------------------------------------------------------------------------
def test_peer_group_key_extraction():
    """entity_key("192.168.1.42", "svchost.exe") returns ("192.168.1.subnet", "svchost.exe")."""
    key = entity_key("192.168.1.42", "svchost.exe")
    assert isinstance(key, tuple)
    assert len(key) == 2
    assert key[0] == "192.168.1.subnet"
    assert key[1] == "svchost.exe"


# ---------------------------------------------------------------------------
# Stub 4 — model persist and load roundtrip
# ---------------------------------------------------------------------------
def test_model_persist_and_load(tmp_path):
    """save_model(key) followed by load_model(key) returns AnomalyScorer with same state."""
    scorer = AnomalyScorer(model_dir=tmp_path)
    for i in range(5):
        scorer.learn_one({"bytes_out": i * 100, "process_name": "cmd.exe"})

    key = ("192.168.1.subnet", "cmd.exe")
    scorer.save_model(key)

    scorer2 = AnomalyScorer(model_dir=tmp_path)
    scorer2.load_model(key)

    # Both scorers should produce the same score on an identical event
    event = {"bytes_out": 999, "process_name": "cmd.exe"}
    assert scorer.score_one(event) == scorer2.score_one(event)


# ---------------------------------------------------------------------------
# Stub 5 — AnomalyScorer instantiation creates data/anomaly_models/ directory
# ---------------------------------------------------------------------------
def test_model_dir_created(tmp_path):
    """AnomalyScorer(model_dir=...) creates the model directory on instantiation."""
    model_dir = tmp_path / "anomaly_models"
    assert not model_dir.exists()
    AnomalyScorer(model_dir=model_dir)
    assert model_dir.exists()


# ---------------------------------------------------------------------------
# Stub 6 — clearly anomalous event scores above 0.7 after learning normal pattern
# ---------------------------------------------------------------------------
def test_score_high_anomaly_exceeds_threshold():
    """After learning a normal low-variance pattern, an outlier event scores > 0.7."""
    scorer = AnomalyScorer()
    # Learn a stable normal pattern: low bytes, same process
    for _ in range(50):
        scorer.learn_one({"bytes_out": 100, "process_name": "svchost.exe"})

    # Score a dramatically different event (high bytes, different process)
    anomaly_event = {"bytes_out": 999999, "process_name": "mimikatz.exe"}
    score = scorer.score_one(anomaly_event)
    assert score > 0.7, f"Expected anomaly score > 0.7, got {score}"


# ---------------------------------------------------------------------------
# Stub 7 — entity_key with None IP uses "unknown_subnet"
# ---------------------------------------------------------------------------
def test_peer_group_key_no_ip():
    """entity_key(None, "powershell.exe") uses "unknown_subnet" as subnet component."""
    key = entity_key(None, "powershell.exe")
    assert isinstance(key, tuple)
    assert len(key) == 2
    assert key[0] == "unknown_subnet"
    assert key[1] == "powershell.exe"


# ---------------------------------------------------------------------------
# Stub 8 — fresh model returns score near 0.5
# ---------------------------------------------------------------------------
def test_fresh_model_mid_score():
    """First event on a fresh model returns score near 0.5 (HalfSpaceTrees default)."""
    scorer = AnomalyScorer()
    score = scorer.score_one({"hostname": "ws1", "process_name": "svchost.exe"})
    # HalfSpaceTrees scores near 0.5 before learning — within a reasonable range
    assert 0.1 <= score <= 0.9, f"Expected mid-range score near 0.5, got {score}"
