"""
Generate MITRE CAR analytics bundle for Phase 39.

Fetches all CAR-*.yaml files from the MITRE CAR GitHub repository,
parses them, and writes a flat JSON bundle to backend/data/car_analytics.json.

Each entry in the output corresponds to one (analytic_id, technique_id) pair
from the coverage[] list in the YAML file.

Usage:
    uv run python scripts/generate_car_bundle.py
    uv run python scripts/generate_car_bundle.py --force  # Regenerate even if file exists

Fields per entry:
    analytic_id     CAR identifier (e.g., "CAR-2020-09-001")
    technique_id    ATT&CK technique ID (e.g., "T1053")
    title           Human-readable title
    description     Plain-text description (stripped)
    log_sources     Comma-joined data_model_references
    analyst_notes   First non-Pseudocode implementation description, or ""
    pseudocode      First Pseudocode implementation code, or ""
    coverage_level  Coverage level ("Low", "Moderate", "High", etc.)
    platforms       JSON array string of platform names
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.request
from pathlib import Path

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("generate_car_bundle")

GITHUB_API_URL = "https://api.github.com/repos/mitre-attack/car/contents/analytics"
RAW_BASE_URL = "https://raw.githubusercontent.com/mitre-attack/car/master/analytics"
OUTPUT_PATH = Path(__file__).parent.parent / "backend" / "data" / "car_analytics.json"


def _fetch_url(url: str, retries: int = 3) -> bytes:
    """Fetch URL contents with retry logic."""
    headers = {
        "User-Agent": "AI-SOC-Brain/1.0 (CAR bundle generator)",
        "Accept": "application/vnd.github.v3+json",
    }
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except Exception as exc:
            if attempt < retries - 1:
                wait = 2 ** attempt
                logger.warning("Fetch failed (attempt %d/%d): %s — retrying in %ds", attempt + 1, retries, exc, wait)
                time.sleep(wait)
            else:
                raise


def _get_yaml_filenames() -> list[str]:
    """Fetch list of CAR YAML filenames from GitHub API or fall back to raw URL pattern."""
    try:
        logger.info("Fetching analytics index from GitHub API: %s", GITHUB_API_URL)
        data = _fetch_url(GITHUB_API_URL)
        entries = json.loads(data)
        filenames = [
            e["name"]
            for e in entries
            if e["name"].startswith("CAR-") and e["name"].endswith(".yaml")
        ]
        logger.info("Found %d CAR YAML files via API", len(filenames))
        return sorted(filenames)
    except Exception as exc:
        logger.warning("GitHub API failed (%s) — using known filename list fallback", exc)
        return _get_fallback_filenames()


def _get_fallback_filenames() -> list[str]:
    """Generate CAR filenames by trying to fetch them directly from raw GitHub."""
    # Known CAR analytics filename range: CAR-2013 through CAR-2022
    # We'll try fetching the README index page to get the list
    try:
        readme_url = "https://raw.githubusercontent.com/mitre-attack/car/master/docs/analytics.md"
        content = _fetch_url(readme_url).decode("utf-8", errors="replace")
        import re
        filenames = re.findall(r"CAR-\d{4}-\d{2}-\d{3}\.yaml", content)
        if filenames:
            unique = sorted(set(filenames))
            logger.info("Found %d CAR files from README index", len(unique))
            return unique
    except Exception as exc:
        logger.warning("README fallback failed: %s", exc)

    # Last resort: hardcoded list of known CAR analytics (as of 2024)
    logger.info("Using hardcoded fallback filename list")
    return KNOWN_CAR_FILES


def _parse_car_yaml(filename: str, content: bytes) -> list[dict]:
    """Parse a CAR YAML file and return list of (analytic_id, technique_id) entries."""
    try:
        raw = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        logger.warning("YAML parse error in %s: %s — skipping", filename, exc)
        return []

    if not isinstance(raw, dict):
        logger.warning("Unexpected YAML structure in %s — skipping", filename)
        return []

    analytic_id = raw.get("id", "").strip()
    if not analytic_id:
        # Try deriving from filename: CAR-2020-09-001.yaml -> CAR-2020-09-001
        analytic_id = filename.replace(".yaml", "")

    title = raw.get("title", "").strip()
    description = raw.get("description", "").strip()
    platforms = json.dumps(raw.get("platforms", []))

    # log_sources from data_model_references
    data_model_refs = raw.get("data_model_references", []) or []
    log_sources = ", ".join(str(r) for r in data_model_refs if r)

    # Extract implementations
    implementations = raw.get("implementations", []) or []
    pseudocode = ""
    analyst_notes = ""
    for impl in implementations:
        if not isinstance(impl, dict):
            continue
        if impl.get("type") == "Pseudocode" and not pseudocode:
            pseudocode = str(impl.get("code", "")).strip()
        elif impl.get("type") != "Pseudocode" and not analyst_notes:
            analyst_notes = str(impl.get("description", "")).strip()

    # Build one entry per technique in coverage[]
    coverage = raw.get("coverage", []) or []
    entries = []
    for cov in coverage:
        if not isinstance(cov, dict):
            continue
        technique_id = str(cov.get("technique", "")).upper().strip()
        if not technique_id:
            continue
        coverage_level = str(cov.get("coverage", "")).strip()
        entries.append({
            "analytic_id": analytic_id,
            "technique_id": technique_id,
            "title": title,
            "description": description,
            "log_sources": log_sources,
            "analyst_notes": analyst_notes,
            "pseudocode": pseudocode,
            "coverage_level": coverage_level,
            "platforms": platforms,
        })

    # If no coverage entries but analytic exists, emit one entry with empty technique_id omitted
    # (skip analytics with no technique coverage — they're not actionable)
    return entries


def generate_bundle(force: bool = False) -> list[dict]:
    """Main bundle generation logic."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if OUTPUT_PATH.exists() and not force:
        logger.info("Bundle already exists at %s — use --force to regenerate", OUTPUT_PATH)
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        logger.info("Existing bundle has %d entries", len(existing))
        return existing

    filenames = _get_yaml_filenames()
    all_entries: list[dict] = []
    errors = 0

    for i, filename in enumerate(filenames, 1):
        url = f"{RAW_BASE_URL}/{filename}"
        logger.info("[%d/%d] Fetching %s", i, len(filenames), filename)
        try:
            content = _fetch_url(url)
            entries = _parse_car_yaml(filename, content)
            all_entries.extend(entries)
            if entries:
                logger.info("  -> %d technique entries", len(entries))
            else:
                logger.info("  -> no coverage entries (skipped)")
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s — skipping", filename, exc)
            errors += 1

        # Brief throttle to avoid rate limiting
        if i % 20 == 0:
            time.sleep(0.5)

    # Sort by analytic_id then technique_id
    all_entries.sort(key=lambda e: (e["analytic_id"], e["technique_id"]))

    # Remove duplicates (same analytic_id + technique_id)
    seen: set[tuple[str, str]] = set()
    deduped: list[dict] = []
    for entry in all_entries:
        key = (entry["analytic_id"], entry["technique_id"])
        if key not in seen:
            seen.add(key)
            deduped.append(entry)

    logger.info(
        "Bundle complete: %d entries (%d files, %d errors, %d duplicates removed)",
        len(deduped),
        len(filenames),
        errors,
        len(all_entries) - len(deduped),
    )

    OUTPUT_PATH.write_text(json.dumps(deduped, indent=2), encoding="utf-8")
    logger.info("Written to %s", OUTPUT_PATH)
    return deduped


# Hardcoded fallback list of known CAR analytics filenames
KNOWN_CAR_FILES = [
    "CAR-2013-01-002.yaml", "CAR-2013-01-003.yaml", "CAR-2013-02-003.yaml",
    "CAR-2013-02-008.yaml", "CAR-2013-02-012.yaml", "CAR-2013-03-001.yaml",
    "CAR-2013-04-002.yaml", "CAR-2013-05-002.yaml", "CAR-2013-05-003.yaml",
    "CAR-2013-05-004.yaml", "CAR-2013-05-005.yaml", "CAR-2013-05-006.yaml",
    "CAR-2013-05-007.yaml", "CAR-2013-05-009.yaml", "CAR-2013-06-002.yaml",
    "CAR-2013-07-001.yaml", "CAR-2013-07-002.yaml", "CAR-2013-08-001.yaml",
    "CAR-2013-09-005.yaml", "CAR-2013-10-001.yaml", "CAR-2013-10-002.yaml",
    "CAR-2014-02-001.yaml", "CAR-2014-03-001.yaml", "CAR-2014-03-005.yaml",
    "CAR-2014-03-006.yaml", "CAR-2014-04-003.yaml", "CAR-2014-05-001.yaml",
    "CAR-2014-05-002.yaml", "CAR-2014-06-001.yaml", "CAR-2014-07-001.yaml",
    "CAR-2014-11-002.yaml", "CAR-2014-11-003.yaml", "CAR-2014-11-004.yaml",
    "CAR-2014-11-005.yaml", "CAR-2014-11-006.yaml", "CAR-2014-11-007.yaml",
    "CAR-2014-11-008.yaml", "CAR-2019-04-001.yaml", "CAR-2019-04-002.yaml",
    "CAR-2019-04-003.yaml", "CAR-2019-04-004.yaml", "CAR-2019-07-001.yaml",
    "CAR-2019-07-002.yaml", "CAR-2019-08-001.yaml", "CAR-2019-08-002.yaml",
    "CAR-2020-04-001.yaml", "CAR-2020-05-001.yaml", "CAR-2020-05-002.yaml",
    "CAR-2020-05-003.yaml", "CAR-2020-05-004.yaml", "CAR-2020-08-001.yaml",
    "CAR-2020-09-001.yaml", "CAR-2020-09-002.yaml", "CAR-2020-09-003.yaml",
    "CAR-2020-09-004.yaml", "CAR-2020-11-001.yaml", "CAR-2020-11-002.yaml",
    "CAR-2020-11-003.yaml", "CAR-2020-11-004.yaml", "CAR-2020-11-005.yaml",
    "CAR-2020-11-006.yaml", "CAR-2020-11-007.yaml", "CAR-2020-11-008.yaml",
    "CAR-2020-11-009.yaml", "CAR-2020-11-010.yaml", "CAR-2020-11-011.yaml",
    "CAR-2021-01-001.yaml", "CAR-2021-01-002.yaml", "CAR-2021-01-003.yaml",
    "CAR-2021-01-004.yaml", "CAR-2021-01-005.yaml", "CAR-2021-01-006.yaml",
    "CAR-2021-01-007.yaml", "CAR-2021-01-008.yaml", "CAR-2021-01-009.yaml",
    "CAR-2021-02-001.yaml", "CAR-2021-02-002.yaml", "CAR-2021-04-001.yaml",
    "CAR-2021-05-001.yaml", "CAR-2021-05-002.yaml", "CAR-2021-05-003.yaml",
    "CAR-2021-05-004.yaml", "CAR-2021-05-005.yaml", "CAR-2021-05-006.yaml",
    "CAR-2021-05-007.yaml", "CAR-2021-05-008.yaml", "CAR-2021-05-009.yaml",
    "CAR-2021-05-010.yaml", "CAR-2021-05-011.yaml", "CAR-2021-05-012.yaml",
    "CAR-2021-12-001.yaml", "CAR-2021-12-002.yaml", "CAR-2022-03-001.yaml",
    "CAR-2022-06-001.yaml", "CAR-2022-06-002.yaml", "CAR-2022-06-003.yaml",
    "CAR-2023-03-001.yaml", "CAR-2024-06-001.yaml",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MITRE CAR analytics JSON bundle")
    parser.add_argument("--force", action="store_true", help="Regenerate even if bundle exists")
    args = parser.parse_args()

    bundle = generate_bundle(force=args.force)

    if len(bundle) < 90:
        logger.error(
            "Bundle only has %d entries (expected >= 90). Check network or YAML parsing.",
            len(bundle),
        )
        sys.exit(1)

    print(f"SUCCESS: {len(bundle)} entries written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
