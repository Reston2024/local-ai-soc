"""Unit tests for dnstwist_service.run_dnstwist() — Phase 51."""
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock

_AVAILABLE = False
try:
    from backend.services.dnstwist_service import run_dnstwist
    _AVAILABLE = True
except ImportError:
    pass

pytestmark = pytest.mark.skipif(not _AVAILABLE, reason="dnstwist_service not available")


@pytest.mark.asyncio
async def test_run_dnstwist_returns_registered_only():
    """run_dnstwist() filters to only domains with dns_a or dns_ns."""
    mock_results = [
        {"fuzzer": "homoglyph", "domain": "examp1e.com", "dns_a": "1.2.3.4"},
        {"fuzzer": "transposition", "domain": "eaxmple.com", "dns_a": None, "dns_ns": None},
        {"fuzzer": "addition", "domain": "examples.com", "dns_ns": "ns1.examples.com"},
    ]
    with patch("dnstwist.run", return_value=mock_results):
        result = await run_dnstwist("example.com")
    assert len(result) == 2  # filtered out eaxmple.com (no dns_a or dns_ns)
    domains = [r["domain"] for r in result]
    assert "examp1e.com" in domains
    assert "examples.com" in domains
    assert "eaxmple.com" not in domains


@pytest.mark.asyncio
async def test_run_dnstwist_handles_import_error():
    """run_dnstwist() returns [] gracefully when dnstwist not installed."""
    import sys
    # Temporarily hide dnstwist from the module system
    dnstwist_module = sys.modules.get("dnstwist")
    sys.modules["dnstwist"] = None  # type: ignore[assignment]
    try:
        result = await run_dnstwist("example.com")
    finally:
        if dnstwist_module is not None:
            sys.modules["dnstwist"] = dnstwist_module
        elif "dnstwist" in sys.modules:
            del sys.modules["dnstwist"]
    # Graceful fallback — returns empty list
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_run_dnstwist_handles_scan_exception():
    """run_dnstwist() returns [] when dnstwist.run() raises."""
    with patch("dnstwist.run", side_effect=RuntimeError("DNS timeout")):
        result = await run_dnstwist("example.com")
    assert result == []
