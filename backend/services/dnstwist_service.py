"""
DNSTwist async service — Phase 51.

dnstwist.run() is synchronous/blocking; always wrap in asyncio.to_thread().
Only returns confirmed-registered domains (dns_a or dns_ns present).
"""
from __future__ import annotations
import asyncio
from backend.core.logging import get_logger

log = get_logger(__name__)


async def run_dnstwist(domain: str, threads: int = 8) -> list[dict]:
    """
    Run dnstwist permutation scan in thread pool.
    Returns only registered lookalike domains (has dns_a or dns_ns).
    """
    def _scan() -> list[dict]:
        try:
            import dnstwist  # lazy import — not installed in all envs
            results = dnstwist.run(
                domain=domain,
                registered=True,
                threads=threads,
                mxcheck=True,
                format="null",
            )
            return [
                r for r in results
                if r.get("dns_a") or r.get("dns_ns")
            ]
        except ImportError:
            log.warning("dnstwist not installed — skipping permutation scan", domain=domain)
            return []
        except Exception as exc:
            log.warning("dnstwist scan failed", domain=domain, error=str(exc))
            return []

    return await asyncio.to_thread(_scan)
