"""
Architecture fitness tests — module boundary enforcement.

Uses ast.parse + ast.walk to inspect import statements without importing the
modules themselves (so no running services are required).

Rules enforced:
1. backend/api/   must NOT import from ingestion.*
2. backend/api/   must NOT import from detections.* directly
3. ingestion/     must NOT import from backend.api.*
4. backend/stores/ must NOT import from backend.api.*
5. backend/services/ must NOT import from backend.api.*
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Locate the project root (two levels above this file: tests/architecture/ -> tests/ -> root)
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent.parent


def _get_imports(filepath: Path) -> list[str]:
    """Return all top-level module names imported by the given Python file.

    Handles both ``import foo.bar`` and ``from foo.bar import baz`` forms.
    Returns an empty list if the file cannot be parsed (e.g. syntax errors in
    generated files).
    """
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
    return imports


def _python_files(directory: Path) -> list[Path]:
    """Return all *.py files under directory, skipping __pycache__."""
    return [
        p for p in directory.rglob("*.py")
        if "__pycache__" not in str(p)
    ]


# ---------------------------------------------------------------------------
# Rule 1 — backend/api/ must NOT import from ingestion.* (with allowed exceptions)
# ---------------------------------------------------------------------------
def test_api_does_not_import_ingestion():
    """API layer files that are NOT natural ingestion entry-points must not
    import directly from ingestion.*.

    Allowed exceptions (legitimate coupling):
    - ingest.py  — owns the ingest endpoint and directly drives the loader
    - health.py  — calls Hayabusa/Chainsaw scanners from ingestion
    - graph.py   — calls entity_extractor for on-demand graph building
    - chat.py    — uses ingestion.normalizer for text pre-processing
    """
    api_dir = _REPO_ROOT / "backend" / "api"
    if not api_dir.exists():
        pytest.skip("backend/api directory not found")

    # These files are permitted to import from ingestion because they are
    # natural architectural boundary crossings already present in the codebase.
    allowed_exceptions = {"ingest.py", "health.py", "graph.py", "chat.py"}

    violations: list[str] = []
    for filepath in _python_files(api_dir):
        if filepath.name in allowed_exceptions:
            continue
        for imp in _get_imports(filepath):
            if imp.startswith("ingestion.") or imp == "ingestion":
                violations.append(f"{filepath.name}: imports '{imp}'")

    assert not violations, (
        "Non-entry-point backend/api/ modules must NOT import directly from ingestion.\n"
        "If a new api module needs ingestion, add it to allowed_exceptions with justification.\n"
        + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# Rule 2 — backend/api/ must NOT import from detections.* directly
# ---------------------------------------------------------------------------
def test_api_does_not_import_detections_directly():
    """API layer must use stores for detections, not import detections.* directly.

    Exception: detect.py legitimately imports detections.matcher for run_detection.
    The rule is enforced for all OTHER api files.
    """
    api_dir = _REPO_ROOT / "backend" / "api"
    if not api_dir.exists():
        pytest.skip("backend/api directory not found")

    # detect.py is explicitly allowed to import SigmaMatcher (it runs the engine)
    allowed_exceptions = {"detect.py"}

    violations: list[str] = []
    for filepath in _python_files(api_dir):
        if filepath.name in allowed_exceptions:
            continue
        for imp in _get_imports(filepath):
            if imp.startswith("detections.") or imp == "detections":
                violations.append(f"{filepath.name}: imports '{imp}'")

    assert not violations, (
        "backend/api/ modules (except detect.py) must NOT import from detections.\n"
        + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# Rule 3 — ingestion/ must NOT import from backend.api.*
# ---------------------------------------------------------------------------
def test_ingestion_does_not_import_api():
    """Ingestion pipeline must not depend on the API layer."""
    ingestion_dir = _REPO_ROOT / "ingestion"
    if not ingestion_dir.exists():
        pytest.skip("ingestion/ directory not found")

    violations: list[str] = []
    for filepath in _python_files(ingestion_dir):
        for imp in _get_imports(filepath):
            if imp.startswith("backend.api.") or imp == "backend.api":
                violations.append(f"{filepath.name}: imports '{imp}'")

    assert not violations, (
        "ingestion/ modules must NOT import from backend.api.\n"
        + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# Rule 4 — backend/stores/ must NOT import from backend.api.*
# ---------------------------------------------------------------------------
def test_stores_do_not_import_api():
    """Store layer must remain independent of the API layer."""
    stores_dir = _REPO_ROOT / "backend" / "stores"
    if not stores_dir.exists():
        pytest.skip("backend/stores directory not found")

    violations: list[str] = []
    for filepath in _python_files(stores_dir):
        for imp in _get_imports(filepath):
            if imp.startswith("backend.api.") or imp == "backend.api":
                violations.append(f"{filepath.name}: imports '{imp}'")

    assert not violations, (
        "backend/stores/ modules must NOT import from backend.api.\n"
        + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# Rule 5 — backend/services/ must NOT import from backend.api.*
# ---------------------------------------------------------------------------
def test_services_do_not_import_api():
    """Service layer must remain independent of the API layer."""
    services_dir = _REPO_ROOT / "backend" / "services"
    if not services_dir.exists():
        pytest.skip("backend/services directory not found")

    violations: list[str] = []
    for filepath in _python_files(services_dir):
        for imp in _get_imports(filepath):
            if imp.startswith("backend.api.") or imp == "backend.api":
                violations.append(f"{filepath.name}: imports '{imp}'")

    assert not violations, (
        "backend/services/ modules must NOT import from backend.api.\n"
        + "\n".join(violations)
    )
