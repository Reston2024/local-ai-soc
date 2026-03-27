"""Shared slowapi Limiter singleton.

Import this in main.py (for middleware wiring) and in router files (for
@limiter.limit() decorators).  The limiter is disabled when the TESTING
environment variable equals "1" so the test suite never hits rate limits.
"""
from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],
    enabled=os.getenv("TESTING") != "1",
)
