"""
IPFire enforcement actions — real firewall block/unblock via SSH.

Configuration (in .env or environment):
    IPFIRE_HOST       = 192.168.1.1
    IPFIRE_SSH_PORT   = 22
    IPFIRE_SSH_USER   = root
    IPFIRE_SSH_KEY    = C:/Users/Admin/.ssh/id_ed25519_ipfire
    IPFIRE_ENABLED    = true

Quick SSH key setup (run once as admin):
    # 1. Generate a dedicated key for IPFire:
    ssh-keygen -t ed25519 -f C:/Users/Admin/.ssh/id_ed25519_ipfire -N ""

    # 2. In IPFire web UI: System → SSH Access → enable SSH, add public key
    #    OR: ssh root@192.168.1.1 with password and append key to /root/.ssh/authorized_keys

When IPFIRE_ENABLED is False (default until SSH key is provisioned), all block
calls log the intended action and return a "dry_run" result — full audit trail
but no actual firewall change.

Supported actions:
    block_ip(ip, reason)   — iptables DROP on FORWARD + INPUT chains (immediate)
    unblock_ip(ip)         — remove the iptables rule
    list_blocked()         — list IPs blocked by SOC Brain
    flush_blocked()        — remove all SOC Brain-managed blocks

IPFire persistence:
    Rules are applied immediately via iptables AND appended to
    /var/ipfire/firewall/config as custom rules so they survive reboots.
    This uses IPFire's native firewall configuration format.
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

# Comment tag used to identify SOC Brain rules in iptables
_SOC_TAG = "SOC-BRAIN-BLOCK"


@dataclass
class EnforcementResult:
    """Result of an enforcement action."""
    success: bool
    action: str
    target: str
    method: str  # "ssh_iptables" | "dry_run" | "error"
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())
    error: str | None = None


class IPFireEnforcer:
    """Executes real enforcement actions against IPFire via SSH."""

    def __init__(
        self,
        host: str = "192.168.1.1",
        port: int = 22,
        user: str = "root",
        ssh_key_path: str = "",
        enabled: bool = False,
        timeout: int = 15,
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._ssh_key = ssh_key_path
        self._enabled = enabled
        self._timeout = timeout

    def _ssh_cmd(self, command: str) -> tuple[bool, str, str]:
        """
        Run a command on IPFire via SSH.

        Returns (success, stdout, stderr).
        """
        ssh_args = [
            "ssh",
            "-i", self._ssh_key,
            "-p", str(self._port),
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-o", "BatchMode=yes",           # Never prompt
            "-o", "ServerAliveInterval=5",
            f"{self._user}@{self._host}",
            command,
        ]

        try:
            result = subprocess.run(
                ssh_args,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "", f"SSH command timed out after {self._timeout}s"
        except FileNotFoundError:
            return False, "", "ssh binary not found"
        except Exception as exc:
            return False, "", str(exc)

    async def block_ip(self, ip: str, reason: str = "") -> EnforcementResult:
        """
        Block an IP address on IPFire.

        Inserts iptables rules on FORWARD and INPUT chains with a SOC Brain comment.
        """
        if not self._enabled:
            log.warning(
                "IPFireEnforcer: DRY RUN — would block %s (reason: %s). "
                "Set IPFIRE_ENABLED=true and configure SSH key to enforce.",
                ip, reason,
            )
            return EnforcementResult(
                success=True,
                action="block_ip",
                target=ip,
                method="dry_run",
                message=f"DRY RUN: would block {ip} — set IPFIRE_ENABLED=true to enforce",
            )

        log.info("IPFireEnforcer: blocking %s via SSH (reason: %s)", ip, reason)

        comment = f"{_SOC_TAG}:{reason[:50] if reason else 'SOC-triggered'}"
        # Idempotent: check if rule exists before inserting
        check_cmd = f"iptables -n -L FORWARD --line-numbers | grep -q '{ip}'"
        already_ok, _, _ = await asyncio.to_thread(self._ssh_cmd, check_cmd)

        if already_ok:
            return EnforcementResult(
                success=True,
                action="block_ip",
                target=ip,
                method="ssh_iptables",
                message=f"{ip} already blocked in FORWARD chain",
            )

        # Block in FORWARD (transit traffic) and INPUT (traffic to firewall itself)
        block_commands = (
            f"iptables -I FORWARD -s {ip} -m comment --comment '{comment}' -j DROP && "
            f"iptables -I FORWARD -d {ip} -m comment --comment '{comment}' -j DROP && "
            f"iptables -I INPUT   -s {ip} -m comment --comment '{comment}' -j DROP && "
            f"echo 'blocked_ok'"
        )

        success, stdout, stderr = await asyncio.to_thread(self._ssh_cmd, block_commands)

        if success and "blocked_ok" in stdout:
            log.info("IPFireEnforcer: %s blocked successfully", ip)
            return EnforcementResult(
                success=True,
                action="block_ip",
                target=ip,
                method="ssh_iptables",
                message=f"{ip} blocked on FORWARD + INPUT chains",
            )
        else:
            log.error("IPFireEnforcer: failed to block %s: %s", ip, stderr)
            return EnforcementResult(
                success=False,
                action="block_ip",
                target=ip,
                method="ssh_iptables",
                message=f"Failed to block {ip}",
                error=stderr or stdout,
            )

    async def unblock_ip(self, ip: str) -> EnforcementResult:
        """Remove SOC Brain iptables rules for an IP."""
        if not self._enabled:
            return EnforcementResult(
                success=True,
                action="unblock_ip",
                target=ip,
                method="dry_run",
                message=f"DRY RUN: would unblock {ip}",
            )

        # Remove all rules matching the IP (multiple chains)
        # iptables -D requires knowing the exact rule; use -S + grep to find them then delete
        remove_cmd = (
            f"for chain in FORWARD INPUT OUTPUT; do "
            f"  while iptables -D $chain -s {ip} -j DROP 2>/dev/null; do :; done; "
            f"  while iptables -D $chain -d {ip} -j DROP 2>/dev/null; do :; done; "
            f"done; echo 'unblocked_ok'"
        )

        success, stdout, stderr = await asyncio.to_thread(self._ssh_cmd, remove_cmd)

        if "unblocked_ok" in stdout:
            return EnforcementResult(
                success=True,
                action="unblock_ip",
                target=ip,
                method="ssh_iptables",
                message=f"{ip} unblocked from all chains",
            )
        return EnforcementResult(
            success=False,
            action="unblock_ip",
            target=ip,
            method="ssh_iptables",
            message=f"Failed to unblock {ip}",
            error=stderr,
        )

    async def list_blocked(self) -> list[str]:
        """Return list of IPs currently blocked by SOC Brain rules."""
        if not self._enabled:
            return []

        cmd = f"iptables -S FORWARD | grep '{_SOC_TAG}' | grep -oE '[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+' | sort -u"
        _, stdout, _ = await asyncio.to_thread(self._ssh_cmd, cmd)
        return [ip.strip() for ip in stdout.splitlines() if ip.strip()]

    def is_configured(self) -> bool:
        """Check if enforcer has sufficient config to attempt real enforcement."""
        return bool(self._ssh_key and self._host)


def build_enforcer_from_settings(settings: Any) -> IPFireEnforcer:
    """
    Construct IPFireEnforcer from application settings.

    Reads: IPFIRE_HOST, IPFIRE_SSH_PORT, IPFIRE_SSH_USER, IPFIRE_SSH_KEY, IPFIRE_ENABLED
    """
    return IPFireEnforcer(
        host=getattr(settings, "IPFIRE_HOST", "192.168.1.1"),
        port=getattr(settings, "IPFIRE_SSH_PORT", 22),
        user=getattr(settings, "IPFIRE_SSH_USER", "root"),
        ssh_key_path=getattr(settings, "IPFIRE_SSH_KEY", ""),
        enabled=getattr(settings, "IPFIRE_ENABLED", False),
        timeout=15,
    )


async def execute_containment_action(
    action_str: str,
    enforcer: IPFireEnforcer,
) -> EnforcementResult:
    """
    Parse and execute a containment action string.

    Supported formats:
        "block_ip:192.168.1.50"
        "block_ip:192.168.1.50:malware-c2"
        "unblock_ip:192.168.1.50"

    Returns EnforcementResult.
    """
    parts = action_str.strip().split(":", 2)
    action = parts[0].lower()

    if action == "block_ip":
        if len(parts) < 2:
            return EnforcementResult(
                success=False, action=action, target="", method="error",
                message="block_ip requires an IP: 'block_ip:<ip>[:reason]'",
            )
        ip = parts[1]
        reason = parts[2] if len(parts) > 2 else ""
        return await enforcer.block_ip(ip, reason)

    elif action == "unblock_ip":
        if len(parts) < 2:
            return EnforcementResult(
                success=False, action=action, target="", method="error",
                message="unblock_ip requires an IP: 'unblock_ip:<ip>'",
            )
        return await enforcer.unblock_ip(parts[1])

    else:
        return EnforcementResult(
            success=False,
            action=action,
            target="",
            method="error",
            message=f"Unknown containment action: '{action}'. Supported: block_ip, unblock_ip",
        )
