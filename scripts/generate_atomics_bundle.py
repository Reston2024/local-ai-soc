"""
Generate Atomic Red Team (ART) atomics bundle for Phase 40.

Fetches all technique YAML files from the redcanaryco/atomic-red-team GitHub
repository, parses them, and writes a flat JSON bundle to
backend/data/atomics.json.

Each entry in the output corresponds to one atomic test within a technique file.

Usage:
    uv run python scripts/generate_atomics_bundle.py
    uv run python scripts/generate_atomics_bundle.py --force  # Regenerate even if file exists

Fields per entry:
    technique_id        ATT&CK technique ID (e.g., "T1059.001")
    display_name        Human-readable technique name
    test_number         1-based index within technique (int)
    test_name           Name of the atomic test
    auto_generated_guid UUID string for this test
    description         Plain-text description
    supported_platforms JSON array string (e.g., '["windows", "linux"]')
    executor_name       Executor type (powershell|command_prompt|bash|sh|manual)
    elevation_required  0 or 1 int
    command             Command string with #{variable} markers preserved
    cleanup_command     Cleanup command string (may be empty)
    prereq_command      Joined prereq get_prereq_command strings (may be empty)
    input_arguments     JSON object string of input argument definitions
"""
from __future__ import annotations

import argparse
import json
import logging
import re
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
logger = logging.getLogger("generate_atomics_bundle")

GITHUB_API_URL = "https://api.github.com/repos/redcanaryco/atomic-red-team/contents/atomics"
RAW_BASE_URL = "https://raw.githubusercontent.com/redcanaryco/atomic-red-team/master/atomics"
OUTPUT_PATH = Path(__file__).parent.parent / "backend" / "data" / "atomics.json"

# Regex pattern to identify valid ATT&CK technique directory names
TECHNIQUE_PATTERN = re.compile(r'^T\d{4}(\.\d{3})?$')


def _fetch_url(url: str, retries: int = 3) -> bytes:
    """Fetch URL contents with retry logic."""
    headers = {
        "User-Agent": "AI-SOC-Brain/1.0 (ART bundle generator)",
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
                logger.warning(
                    "Fetch failed (attempt %d/%d): %s — retrying in %ds",
                    attempt + 1, retries, exc, wait,
                )
                time.sleep(wait)
            else:
                raise


def _get_technique_dirs() -> list[str]:
    """Fetch list of technique directory names from GitHub API."""
    try:
        logger.info("Fetching atomics index from GitHub API: %s", GITHUB_API_URL)
        data = _fetch_url(GITHUB_API_URL)
        entries = json.loads(data)
        dirs = [
            e["name"]
            for e in entries
            if e.get("type") == "dir" and TECHNIQUE_PATTERN.match(e["name"])
        ]
        logger.info("Found %d technique directories via API", len(dirs))
        return sorted(dirs)
    except Exception as exc:
        logger.warning("GitHub API failed (%s) — network may be unavailable", exc)
        return []


def _parse_art_yaml(technique_dir_name: str, content: bytes) -> list[dict]:
    """
    Parse an ART YAML file and return one dict per atomic test.

    Preserves #{variable} markers in command strings — never substitutes them.
    """
    try:
        raw = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        logger.warning("YAML parse error in %s: %s — skipping", technique_dir_name, exc)
        return []

    if not isinstance(raw, dict):
        logger.warning("Unexpected YAML structure in %s — skipping", technique_dir_name)
        return []

    attack_technique = raw.get("attack_technique", technique_dir_name)
    display_name = raw.get("display_name", "")

    entries: list[dict] = []
    for test_number, test in enumerate(raw.get("atomic_tests", []) or [], start=1):
        if not isinstance(test, dict):
            continue

        # executor — handle None executor (Pitfall 3)
        executor = test.get("executor", {}) or {}
        executor_name = executor.get("name", "manual")

        # command — manual tests use "steps" field
        command = executor.get("command", "") or executor.get("steps", "") or ""

        cleanup_command = executor.get("cleanup_command", "") or ""

        # elevation_required — store as 0/1 int
        elevation_required = int(bool(executor.get("elevation_required", False)))

        # dependencies — handle None (Pitfall 7)
        deps = test.get("dependencies") or []
        prereq_command = ""
        if deps:
            dep_executor = test.get("dependency_executor_name", "powershell")  # noqa: F841 — available for future use
            prereq_parts = [
                d.get("get_prereq_command", "")
                for d in deps
                if isinstance(d, dict)
            ]
            prereq_command = "\n---\n".join(p for p in prereq_parts if p)

        # supported_platforms — store as JSON string
        supported_platforms = json.dumps(test.get("supported_platforms", []) or [])

        # input_arguments — store as JSON string; handle None
        input_arguments = json.dumps(test.get("input_arguments", {}) or {})

        entries.append({
            "technique_id": str(attack_technique),
            "display_name": str(display_name),
            "test_number": test_number,
            "test_name": test.get("name", ""),
            "auto_generated_guid": test.get("auto_generated_guid", ""),
            "description": test.get("description", "") or "",
            "supported_platforms": supported_platforms,
            "executor_name": executor_name,
            "elevation_required": elevation_required,
            "command": command,
            "cleanup_command": cleanup_command,
            "prereq_command": prereq_command,
            "input_arguments": input_arguments,
        })

    return entries


def generate_bundle(force: bool = False) -> list[dict]:
    """Main bundle generation logic."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if OUTPUT_PATH.exists() and not force:
        logger.info("Bundle already exists at %s — use --force to regenerate", OUTPUT_PATH)
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        logger.info("Existing bundle has %d entries", len(existing))
        return existing

    tech_dirs = _get_technique_dirs()
    if not tech_dirs:
        logger.warning("No technique directories found — network unavailable? Returning empty bundle.")
        return []

    all_entries: list[dict] = []
    errors = 0

    for i, dir_name in enumerate(tech_dirs, 1):
        yaml_url = f"{RAW_BASE_URL}/{dir_name}/{dir_name}.yaml"
        logger.info("[%d/%d] Fetching %s", i, len(tech_dirs), dir_name)
        try:
            content = _fetch_url(yaml_url)
            entries = _parse_art_yaml(dir_name, content)
            all_entries.extend(entries)
            logger.info("  -> %d atomic tests", len(entries))
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s — skipping", dir_name, exc)
            errors += 1

        # Throttle every 20 files to avoid rate limiting (Pitfall 6)
        if i % 20 == 0:
            time.sleep(0.5)

    # Sort by (technique_id, test_number)
    all_entries.sort(key=lambda e: (e["technique_id"], e["test_number"]))

    logger.info(
        "Bundle complete: %d entries (%d technique dirs, %d errors)",
        len(all_entries),
        len(tech_dirs),
        errors,
    )

    OUTPUT_PATH.write_text(json.dumps(all_entries, indent=2), encoding="utf-8")
    logger.info("Written to %s", OUTPUT_PATH)
    return all_entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Atomic Red Team JSON bundle")
    parser.add_argument("--force", action="store_true", help="Regenerate even if bundle exists")
    args = parser.parse_args()

    bundle = generate_bundle(force=args.force)

    if not bundle:
        logger.warning("Empty bundle — network may be unavailable. Exiting 0 (offline mode).")
        print("WARNING: Empty bundle generated (network unavailable)")
        sys.exit(0)

    if len(bundle) < 800:
        logger.error(
            "Bundle only has %d entries (expected >= 800). Check network or YAML parsing.",
            len(bundle),
        )
        sys.exit(1)

    print(f"SUCCESS: {len(bundle)} entries written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
