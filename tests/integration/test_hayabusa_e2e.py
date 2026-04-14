"""
Wave 0 TDD integration stub for Phase 48 Hayabusa EVTX threat hunting.
P48-T02: End-to-end scan — HayabusaScanner.scan() with a real binary and
         sample EVTX; gated on shutil.which('hayabusa') (HAY-08).

The test body is a stub. Plan 48-02 will implement the real assertion:
call HayabusaScanner with a fixture EVTX, verify findings >= 0, verify no exception.
"""
from __future__ import annotations

import shutil

import pytest

pytestmark = pytest.mark.hayabusa

HAYABUSA_AVAILABLE = shutil.which("hayabusa") or shutil.which("hayabusa.exe")


@pytest.mark.skipif(not HAYABUSA_AVAILABLE, reason="hayabusa binary not on PATH")
def test_hayabusa_e2e_scan():
    """With a real hayabusa binary on PATH and a sample EVTX file,
    HayabusaScanner.scan() returns >= 0 findings (no crash); if binary absent,
    test is skipped automatically (HAY-08).
    """
    pytest.skip("Wave 0 stub — implement after Plan 48-02")
