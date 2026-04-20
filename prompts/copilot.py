"""
Prompts for the AI Copilot chat — foundation-sec:8b streaming responses.

The LLM is instructed to answer concisely, surface MITRE ATT&CK techniques,
express uncertainty explicitly, and never fabricate event IDs or hostnames.
"""

from __future__ import annotations

SYSTEM = """You are an expert cybersecurity analyst AI Copilot embedded in a SOC investigation platform.
You are given context about an ongoing security investigation.
Answer the analyst's question concisely. Identify relevant MITRE ATT&CK techniques when applicable.
If you are uncertain, say so. Do not fabricate event IDs or hostnames."""


# ---------------------------------------------------------------------------
# Provenance fingerprinting — must stay at module bottom so the hash
# captures the full template source (SYSTEM, etc.)
# ---------------------------------------------------------------------------

import hashlib as _hashlib
import inspect as _inspect
import pathlib as _pathlib


def _compute_template_sha256() -> str:
    """Compute SHA-256 of this module's source file for provenance tracking."""
    src = _pathlib.Path(_inspect.getfile(_compute_template_sha256)).read_bytes()
    return _hashlib.sha256(src).hexdigest()


TEMPLATE_SHA256: str = _compute_template_sha256()
TEMPLATE_NAME: str = "copilot"
