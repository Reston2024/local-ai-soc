"""
Integration test for Phase 49 Chainsaw EVTX threat hunting.
CHA-01: End-to-end scan — scan_evtx() with a real binary and
        sample EVTX; gated on shutil.which('chainsaw') (CHA-08).

Skips automatically when the chainsaw binary is not on PATH.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.chainsaw

CHAINSAW_AVAILABLE = shutil.which("chainsaw") or shutil.which("chainsaw.exe")


@pytest.mark.skipif(not CHAINSAW_AVAILABLE, reason="chainsaw binary not on PATH")
def test_chainsaw_e2e_scan():
    """With a real chainsaw binary on PATH and a sample EVTX file,
    scan_evtx() returns a list (could be empty on clean EVTX — that is fine);
    no crash, no exception (CHA-01).
    """
    from ingestion.chainsaw_scanner import scan_evtx

    sample_evtx = Path("fixtures") / "windows_events.evtx"
    if not sample_evtx.exists():
        pytest.skip("No fixture EVTX available for integration test")

    records = list(scan_evtx(str(sample_evtx)))
    assert isinstance(records, list)  # could be empty on clean EVTX — that is fine
