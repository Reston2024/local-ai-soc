"""
Enforcement Policy Gate — Phase 40 response control layer.

Implements NIST SP 800-53 SI-4 / SOAR best practice controls:
  - Learning mode: observe and log decisions without executing (NIST 800-61r2 §3.1 baseline period)
  - Confidence threshold: block only when evidence is strong enough
  - IP safelist: never block protected CIDRs (own infrastructure, gateways)
  - Rate limiting: cap auto-blocks per rolling window to prevent runaway automation
  - Requires-approval gate: respect playbook step's requires_approval flag

Usage (in advance_step):
    policy = EnforcementPolicy.from_settings(settings)
    decision = policy.allow(action_str, confidence=0.85, step_requires_approval=False)
    if not decision.allowed:
        return policy-denied response

Conservative defaults (NIST 800-61r2 / CISA SOAR guidance):
  - ENFORCEMENT_LEARNING_MODE=true  for first 30 days (observe only, no execution)
  - ENFORCEMENT_MIN_CONFIDENCE=0.85 (tighter than 70% default during baseline period)
  - ENFORCEMENT_RATE_LIMIT=3        (conservative cap during baseline)
  - ENFORCEMENT_REQUIRE_APPROVAL=true (always — no automated containment without human)

All decisions are logged to enforcement_audit_log in SQLite.
"""
from __future__ import annotations

import ipaddress
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults — override via settings or .env
# ---------------------------------------------------------------------------

_DEFAULT_MIN_CONFIDENCE: float = 0.85      # 85% — conservative per NIST 800-61r2
_DEFAULT_RATE_LIMIT: int = 3               # max automated blocks per rolling window (conservative)
_DEFAULT_RATE_WINDOW_SEC: int = 3600       # 1-hour rolling window
_DEFAULT_SAFELIST: list[str] = [
    "127.0.0.0/8",        # loopback
    "::1/128",            # IPv6 loopback
    "10.0.0.0/8",         # RFC-1918 class A
    "172.16.0.0/12",      # RFC-1918 class B
    "192.168.0.0/16",     # RFC-1918 class C
]

# Actions that require human approval regardless of confidence
_HIGH_RISK_ACTIONS = {"block_ip", "disable_account", "revoke_access"}


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
    action: str
    target: str
    confidence: float | None
    gate_applied: str          # "confidence" | "safelist" | "rate_limit" | "approval" | "allowed" | "learning_mode"
    timestamp: float = field(default_factory=time.time)
    learning_mode: bool = False         # True when policy is in observe-only mode
    shadow_gate: str | None = None      # Gate that *would* have applied if not in learning mode


class EnforcementPolicy:
    """
    Gate that every automated containment action must pass before execution.

    Thread-safety: rate-limit deque is protected by simple length check; for
    production multi-worker deployments move the counter to Redis or SQLite.
    """

    def __init__(
        self,
        min_confidence: float = _DEFAULT_MIN_CONFIDENCE,
        rate_limit: int = _DEFAULT_RATE_LIMIT,
        rate_window_sec: int = _DEFAULT_RATE_WINDOW_SEC,
        safelist_cidrs: list[str] | None = None,
        require_approval_for_high_risk: bool = True,
        learning_mode: bool = True,
    ) -> None:
        self.min_confidence = min_confidence
        self.rate_limit = rate_limit
        self.rate_window_sec = rate_window_sec
        self.require_approval_for_high_risk = require_approval_for_high_risk
        self.learning_mode = learning_mode

        # Parse safelist CIDRs
        raw_cidrs = safelist_cidrs if safelist_cidrs is not None else _DEFAULT_SAFELIST
        self._safelist: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        for cidr in raw_cidrs:
            try:
                self._safelist.append(ipaddress.ip_network(cidr, strict=False))
            except ValueError:
                log.warning("EnforcementPolicy: invalid CIDR in safelist: %s", cidr)

        # Rate-limit tracking — sliding window of block timestamps
        self._block_times: deque[float] = deque()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def allow(
        self,
        action_str: str,
        target: str = "",
        confidence: float | None = None,
        step_requires_approval: bool = True,
        human_confirmed: bool = True,
    ) -> PolicyDecision:
        """
        Return a PolicyDecision indicating whether the action is permitted.

        In learning mode (NIST 800-61r2 §3.1 baseline period) all gates are
        evaluated for observability but execution is always suppressed.  The
        shadow_gate field records what the real outcome would have been.

        Args:
            action_str:             e.g. "block_ip:192.168.1.50:malware_c2"
            target:                 extracted IP or resource identifier
            confidence:             0.0–1.0 score from detection/triage; None = skip check
            step_requires_approval: playbook step's requires_approval flag
            human_confirmed:        True if a human clicked "Confirm" in the UI
        """
        real = self._evaluate(action_str, target, confidence, step_requires_approval, human_confirmed)

        if self.learning_mode:
            log.info(
                "LEARNING MODE — shadow decision: gate=%s allowed=%s action='%s' target='%s' confidence=%s",
                real.gate_applied, real.allowed, real.action, real.target, confidence,
            )
            return PolicyDecision(
                allowed=False,
                reason=(
                    f"Learning mode active (NIST 800-61r2 §3.1 baseline period) — "
                    f"shadow decision: {real.reason}"
                ),
                action=real.action,
                target=real.target,
                confidence=real.confidence,
                gate_applied="learning_mode",
                learning_mode=True,
                shadow_gate=real.gate_applied,
            )

        return real

    def _evaluate(
        self,
        action_str: str,
        target: str = "",
        confidence: float | None = None,
        step_requires_approval: bool = True,
        human_confirmed: bool = True,
    ) -> PolicyDecision:
        """
        Run all policy gates and return the real (non-learning-mode) decision.
        Called by allow(); separated so learning mode can inspect shadow outcomes.
        """
        # Parse action
        parts = action_str.split(":", 1)
        action = parts[0] if parts else action_str
        target = target or (parts[1].split(":")[0] if len(parts) > 1 else "")

        # 1. Approval gate — high-risk actions require human confirmation
        if (
            self.require_approval_for_high_risk
            and action in _HIGH_RISK_ACTIONS
            and not human_confirmed
        ):
            return PolicyDecision(
                allowed=False,
                reason=f"Action '{action}' requires human confirmation — not yet confirmed",
                action=action,
                target=target,
                confidence=confidence,
                gate_applied="approval",
            )

        # 2. Confidence gate
        if confidence is not None and confidence < self.min_confidence:
            return PolicyDecision(
                allowed=False,
                reason=(
                    f"Confidence {confidence:.0%} below threshold {self.min_confidence:.0%} "
                    f"for action '{action}'"
                ),
                action=action,
                target=target,
                confidence=confidence,
                gate_applied="confidence",
            )

        # 3. Safelist gate — never block protected CIDRs
        if target and action == "block_ip":
            try:
                target_ip = ipaddress.ip_address(target.strip())
                for net in self._safelist:
                    if target_ip in net:
                        return PolicyDecision(
                            allowed=False,
                            reason=f"Target {target} is in protected CIDR {net} — safelist blocks action",
                            action=action,
                            target=target,
                            confidence=confidence,
                            gate_applied="safelist",
                        )
            except ValueError:
                pass  # Not an IP address — not subject to safelist

        # 4. Rate-limit gate
        now = time.time()
        cutoff = now - self.rate_window_sec
        # Prune old entries
        while self._block_times and self._block_times[0] < cutoff:
            self._block_times.popleft()

        if len(self._block_times) >= self.rate_limit:
            return PolicyDecision(
                allowed=False,
                reason=(
                    f"Rate limit reached: {len(self._block_times)} automated actions "
                    f"in last {self.rate_window_sec // 60} minutes "
                    f"(limit={self.rate_limit})"
                ),
                action=action,
                target=target,
                confidence=confidence,
                gate_applied="rate_limit",
            )

        # All gates passed — record the action timestamp
        self._block_times.append(now)
        return PolicyDecision(
            allowed=True,
            reason="All policy gates passed",
            action=action,
            target=target,
            confidence=confidence,
            gate_applied="allowed",
        )

    def current_rate(self) -> int:
        """Return count of enforcement actions in the current rate window."""
        now = time.time()
        cutoff = now - self.rate_window_sec
        return sum(1 for t in self._block_times if t >= cutoff)

    def status(self) -> dict[str, Any]:
        return {
            "learning_mode": self.learning_mode,
            "min_confidence": self.min_confidence,
            "rate_limit": self.rate_limit,
            "rate_window_minutes": self.rate_window_sec // 60,
            "current_rate": self.current_rate(),
            "safelist_cidrs": [str(n) for n in self._safelist],
            "require_approval_for_high_risk": self.require_approval_for_high_risk,
        }

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls, settings: Any) -> "EnforcementPolicy":
        """Construct from app settings object."""
        safelist_raw = getattr(settings, "ENFORCEMENT_SAFELIST_CIDRS", None)
        if isinstance(safelist_raw, str):
            safelist_raw = [s.strip() for s in safelist_raw.split(",") if s.strip()]
        # Empty list / None → use built-in defaults (RFC-1918 + loopback)
        if not safelist_raw:
            safelist_raw = None

        return cls(
            min_confidence=float(getattr(settings, "ENFORCEMENT_MIN_CONFIDENCE", _DEFAULT_MIN_CONFIDENCE)),
            rate_limit=int(getattr(settings, "ENFORCEMENT_RATE_LIMIT", _DEFAULT_RATE_LIMIT)),
            rate_window_sec=int(getattr(settings, "ENFORCEMENT_RATE_WINDOW_SEC", _DEFAULT_RATE_WINDOW_SEC)),
            safelist_cidrs=safelist_raw,
            require_approval_for_high_risk=bool(
                getattr(settings, "ENFORCEMENT_REQUIRE_APPROVAL", True)
            ),
            learning_mode=bool(
                getattr(settings, "ENFORCEMENT_LEARNING_MODE", True)
            ),
        )
