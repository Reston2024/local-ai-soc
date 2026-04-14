"""
Integration test for Phase 48 Hayabusa EVTX threat hunting.
P48-T02: End-to-end scan — scan_evtx() with a real binary and
         sample EVTX; gated on shutil.which('hayabusa') (HAY-08).

Skips automatically when the hayabusa binary is not on PATH.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.hayabusa

HAYABUSA_AVAILABLE = shutil.which("hayabusa") or shutil.which("hayabusa.exe")


@pytest.mark.skipif(not HAYABUSA_AVAILABLE, reason="hayabusa binary not on PATH")
def test_hayabusa_e2e_scan():
    """With a real hayabusa binary on PATH and a sample EVTX file,
    scan_evtx() returns a list (could be empty on clean EVTX — that is fine);
    no crash, no exception (HAY-08).
    """
    from ingestion.hayabusa_scanner import scan_evtx

    sample_evtx = Path("fixtures") / "windows_events.evtx"
    if not sample_evtx.exists():
        pytest.skip("No fixture EVTX available for integration test")

    records = list(scan_evtx(str(sample_evtx)))
    assert isinstance(records, list)  # could be empty on clean EVTX — that is fine
