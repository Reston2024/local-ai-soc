"""Phase 40: Enforcement Policy Gate tests."""
import time
import pytest

from backend.enforcement.policy import EnforcementPolicy, _DEFAULT_MIN_CONFIDENCE


@pytest.fixture()
def policy():
    """Live policy (learning_mode=False) for gate behaviour tests."""
    return EnforcementPolicy(
        min_confidence=0.70,
        rate_limit=3,
        rate_window_sec=60,
        safelist_cidrs=["10.0.0.0/8", "192.168.1.0/24"],
        learning_mode=False,
    )


@pytest.fixture()
def learning_policy():
    """Learning-mode policy — observe only, no execution."""
    return EnforcementPolicy(
        min_confidence=0.70,
        rate_limit=3,
        rate_window_sec=60,
        safelist_cidrs=["10.0.0.0/8", "192.168.1.0/24"],
        learning_mode=True,
    )


class TestConfidenceGate:
    def test_allows_above_threshold(self, policy):
        d = policy.allow("block_ip:1.2.3.4", confidence=0.90, human_confirmed=True)
        assert d.allowed

    def test_denies_below_threshold(self, policy):
        d = policy.allow("block_ip:1.2.3.4", confidence=0.50, human_confirmed=True)
        assert not d.allowed
        assert d.gate_applied == "confidence"
        assert "50%" in d.reason or "0.5" in d.reason.lower() or "threshold" in d.reason

    def test_allows_when_confidence_none(self, policy):
        d = policy.allow("block_ip:1.2.3.4", confidence=None, human_confirmed=True)
        assert d.allowed

    def test_exactly_at_threshold(self, policy):
        d = policy.allow("block_ip:1.2.3.4", confidence=0.70, human_confirmed=True)
        assert d.allowed  # >= threshold passes


class TestSafelistGate:
    def test_denies_safelisted_ip(self, policy):
        d = policy.allow("block_ip:192.168.1.50", confidence=0.99, human_confirmed=True)
        assert not d.allowed
        assert d.gate_applied == "safelist"
        assert "192.168.1.50" in d.reason or "protected" in d.reason.lower()

    def test_denies_safelisted_private_class_a(self, policy):
        d = policy.allow("block_ip:10.20.30.40", confidence=0.99, human_confirmed=True)
        assert not d.allowed
        assert d.gate_applied == "safelist"

    def test_allows_external_ip(self, policy):
        d = policy.allow("block_ip:203.0.113.5", confidence=0.99, human_confirmed=True)
        assert d.allowed

    def test_safelist_ignored_for_non_block_actions(self, policy):
        # disable_account on an internal IP — safelist only applies to block_ip
        d = policy.allow("disable_account:192.168.1.50", confidence=0.99, human_confirmed=True)
        assert d.allowed  # no safelist block for non-IP actions


class TestRateLimitGate:
    def test_allows_under_limit(self, policy):
        for _ in range(3):
            d = policy.allow("block_ip:1.2.3.4", confidence=0.90, human_confirmed=True)
            assert d.allowed

    def test_denies_at_limit(self, policy):
        for _ in range(3):
            policy.allow("block_ip:1.2.3.4", confidence=0.90, human_confirmed=True)
        d = policy.allow("block_ip:5.6.7.8", confidence=0.99, human_confirmed=True)
        assert not d.allowed
        assert d.gate_applied == "rate_limit"
        assert "rate limit" in d.reason.lower()

    def test_rate_resets_after_window(self, policy):
        policy._rate_window_sec = 1  # 1-second window for testing
        policy.rate_window_sec = 1
        for _ in range(3):
            policy.allow("block_ip:1.2.3.4", confidence=0.90, human_confirmed=True)
        time.sleep(1.1)
        d = policy.allow("block_ip:1.2.3.4", confidence=0.90, human_confirmed=True)
        assert d.allowed

    def test_current_rate_tracks_actions(self, policy):
        assert policy.current_rate() == 0
        policy.allow("block_ip:1.2.3.4", confidence=0.90, human_confirmed=True)
        assert policy.current_rate() == 1


class TestApprovalGate:
    def test_high_risk_requires_human_confirmation(self, policy):
        d = policy.allow("block_ip:1.2.3.4", confidence=0.99, human_confirmed=False)
        assert not d.allowed
        assert d.gate_applied == "approval"

    def test_human_confirmed_passes_gate(self, policy):
        d = policy.allow("block_ip:1.2.3.4", confidence=0.99, human_confirmed=True)
        assert d.allowed

    def test_disable_account_requires_confirmation(self, policy):
        d = policy.allow("disable_account:jdoe", confidence=0.99, human_confirmed=False)
        assert not d.allowed

    def test_revoke_access_requires_confirmation(self, policy):
        d = policy.allow("revoke_access:jdoe", confidence=0.99, human_confirmed=False)
        assert not d.allowed


class TestPolicyStatus:
    def test_status_returns_expected_keys(self, policy):
        s = policy.status()
        assert "min_confidence" in s
        assert "rate_limit" in s
        assert "current_rate" in s
        assert "safelist_cidrs" in s
        assert "learning_mode" in s

    def test_status_reflects_config(self, policy):
        s = policy.status()
        assert s["min_confidence"] == 0.70
        assert s["rate_limit"] == 3
        assert s["learning_mode"] is False

    def test_status_reflects_learning_mode(self, learning_policy):
        s = learning_policy.status()
        assert s["learning_mode"] is True


class TestLearningMode:
    """NIST 800-61r2 §3.1 — observe only, no execution during baseline period."""

    def test_learning_mode_blocks_otherwise_allowed_action(self, learning_policy):
        """All gates pass but learning mode suppresses execution."""
        d = learning_policy.allow("block_ip:203.0.113.5", confidence=0.99, human_confirmed=True)
        assert not d.allowed
        assert d.gate_applied == "learning_mode"
        assert d.learning_mode is True

    def test_shadow_gate_records_real_outcome(self, learning_policy):
        """shadow_gate shows what *would* have happened."""
        d = learning_policy.allow("block_ip:203.0.113.5", confidence=0.99, human_confirmed=True)
        assert d.shadow_gate == "allowed"

    def test_learning_mode_blocks_confidence_denied_action(self, learning_policy):
        """Even when confidence gate would deny, learning mode wraps the result."""
        d = learning_policy.allow("block_ip:203.0.113.5", confidence=0.30, human_confirmed=True)
        assert not d.allowed
        assert d.gate_applied == "learning_mode"
        assert d.shadow_gate == "confidence"

    def test_learning_mode_blocks_safelist_denied_action(self, learning_policy):
        """Safelist denial is wrapped with learning_mode context."""
        d = learning_policy.allow("block_ip:10.20.30.40", confidence=0.99, human_confirmed=True)
        assert not d.allowed
        assert d.gate_applied == "learning_mode"
        assert d.shadow_gate == "safelist"

    def test_learning_mode_blocks_approval_denied_action(self, learning_policy):
        """Approval denial is wrapped with learning_mode context."""
        d = learning_policy.allow("block_ip:203.0.113.5", confidence=0.99, human_confirmed=False)
        assert not d.allowed
        assert d.gate_applied == "learning_mode"
        assert d.shadow_gate == "approval"

    def test_reason_mentions_nist(self, learning_policy):
        """Reason string must reference NIST standard for auditability."""
        d = learning_policy.allow("block_ip:203.0.113.5", confidence=0.99, human_confirmed=True)
        assert "NIST" in d.reason or "800-61" in d.reason

    def test_live_mode_still_allows(self, policy):
        """Sanity: live policy (learning_mode=False) allows clean actions."""
        d = policy.allow("block_ip:203.0.113.5", confidence=0.99, human_confirmed=True)
        assert d.allowed
        assert d.gate_applied == "allowed"
        assert d.learning_mode is False


class TestFromSettings:
    def test_loads_from_settings_object(self):
        class FakeSettings:
            ENFORCEMENT_MIN_CONFIDENCE = 0.80
            ENFORCEMENT_RATE_LIMIT = 5
            ENFORCEMENT_RATE_WINDOW_SEC = 1800
            ENFORCEMENT_SAFELIST_CIDRS = "10.0.0.0/8,172.16.0.0/12"
            ENFORCEMENT_REQUIRE_APPROVAL = True
            ENFORCEMENT_LEARNING_MODE = False

        p = EnforcementPolicy.from_settings(FakeSettings())
        assert p.min_confidence == 0.80
        assert p.rate_limit == 5
        assert len(p._safelist) == 2
        assert p.learning_mode is False

    def test_learning_mode_defaults_to_true(self):
        """Conservative default — new deployments start in learning mode."""
        class EmptySettings:
            pass

        p = EnforcementPolicy.from_settings(EmptySettings())
        assert p.learning_mode is True

    def test_uses_defaults_when_settings_absent(self):
        class EmptySettings:
            pass

        p = EnforcementPolicy.from_settings(EmptySettings())
        assert p.min_confidence == _DEFAULT_MIN_CONFIDENCE
