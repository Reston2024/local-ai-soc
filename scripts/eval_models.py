"""
LLM evaluation harness — benchmarks qwen3:14b vs foundation-sec:8b on seeded SIEM data.

Runs two prompt types per row:
  - triage:    "Briefly triage this security event. Identify the attack technique if present."
  - summarise: "Summarise this security event in one sentence: {event_description}"

Usage:
    uv run python scripts/eval_models.py [--limit 100] [--dry-run]

Output:
    data/eval_results.jsonl  — one JSON object per model call
    stdout                   — markdown summary table grouped by model + prompt_type
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so backend/ is importable when the
# script is invoked as `uv run python scripts/eval_models.py` from the root.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import httpx  # noqa: E402 (must come after sys.path fix if httpx lives in venv)

from backend.core.config import settings  # noqa: E402
from backend.stores.duckdb_store import DuckDBStore  # noqa: E402


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class EvalResult:
    """One evaluation result — one model × one row × one prompt type."""

    model: str
    prompt_id: str        # encodes row + prompt type, e.g. "row-0-triage"
    prompt_type: str      # "triage" | "summarise"
    latency_ms: int
    eval_count: int       # token count from Ollama response JSON eval_count field
    keyword_recall: float # 0.0–1.0
    timestamp: str        # ISO-8601 UTC


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_response(response_text: str, ground_truth_keywords: list[str]) -> float:
    """
    Compute keyword recall: fraction of ground_truth_keywords found in response_text.

    Matching is case-insensitive.  Returns 1.0 when ground_truth_keywords is empty.

    Args:
        response_text:          The model's generated text.
        ground_truth_keywords:  List of keywords that should appear in a good response.

    Returns:
        Float in [0.0, 1.0].  1.0 = all keywords found, 0.0 = none found.
    """
    if not ground_truth_keywords:
        return 1.0
    lower = response_text.lower()
    hits = sum(1 for kw in ground_truth_keywords if kw.lower() in lower)
    return hits / len(ground_truth_keywords)


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATES = {
    "triage": (
        "Event type: {event_type}\n"
        "Host: {hostname}\n"
        "Process: {process_name}\n"
        "Command: {command_line}\n"
        "Severity: {severity}\n\n"
        "Briefly triage this security event. Identify the attack technique if present."
    ),
    "summarise": (
        "Summarise this security event in one sentence: "
        "{event_type} on {hostname} (process: {process_name}, severity: {severity})"
    ),
}

# Column positions in the SELECT result
_COL_EVENT_ID = 0
_COL_EVENT_TYPE = 1
_COL_HOSTNAME = 2
_COL_PROCESS_NAME = 3
_COL_COMMAND_LINE = 4
_COL_SEVERITY = 5
_COL_ATTACK_TECHNIQUE = 6


# ---------------------------------------------------------------------------
# Core evaluation function
# ---------------------------------------------------------------------------


async def _eval_one_row(
    row: tuple,
    model: str,
    prompt_type: str,
    row_idx: int,
    ollama_base_url: str,
    dry_run: bool,
) -> EvalResult:
    """
    Evaluate a single (row, model, prompt_type) combination.

    Makes a direct httpx POST to /api/generate (not via OllamaClient.generate())
    so we can read the eval_count field from the raw Ollama JSON response.

    In dry-run mode: returns a zero-latency placeholder EvalResult without
    making any HTTP calls.
    """
    event_type = row[_COL_EVENT_TYPE] or "unknown"
    hostname = row[_COL_HOSTNAME] or "unknown"
    process_name = row[_COL_PROCESS_NAME] or "unknown"
    command_line = row[_COL_COMMAND_LINE] or ""
    severity = row[_COL_SEVERITY] or "low"
    attack_technique = row[_COL_ATTACK_TECHNIQUE] or ""

    prompt_id = f"row-{row_idx}-{prompt_type}"
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build ground truth keywords per prompt type
    if prompt_type == "triage":
        ground_truth_keywords = [kw for kw in [event_type, attack_technique] if kw and kw != "unknown"]
    else:  # summarise
        ground_truth_keywords = [kw for kw in [event_type, severity] if kw and kw != "unknown"]

    if dry_run:
        return EvalResult(
            model=model,
            prompt_id=prompt_id,
            prompt_type=prompt_type,
            latency_ms=0,
            eval_count=0,
            keyword_recall=1.0,
            timestamp=ts,
        )

    # Build the prompt using the appropriate template
    template = _PROMPT_TEMPLATES[prompt_type]
    prompt = template.format(
        event_type=event_type,
        hostname=hostname,
        process_name=process_name,
        command_line=command_line,
        severity=severity,
    )

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }

    base_url = ollama_base_url.rstrip("/")
    t0 = time.monotonic_ns()

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=120.0, write=30.0, pool=5.0)
    ) as client:
        resp = await client.post(f"{base_url}/api/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()

    latency_ms = int((time.monotonic_ns() - t0) / 1_000_000)

    response_text = data.get("response", "")
    eval_count = data.get("eval_count", 0)
    keyword_recall = score_response(response_text, ground_truth_keywords)

    return EvalResult(
        model=model,
        prompt_id=prompt_id,
        prompt_type=prompt_type,
        latency_ms=latency_ms,
        eval_count=eval_count,
        keyword_recall=keyword_recall,
        timestamp=ts,
    )


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------


def _print_summary_table(results: list[EvalResult]) -> None:
    """Print a markdown summary table grouped by (model, prompt_type)."""
    from collections import defaultdict

    groups: dict[tuple[str, str], list[EvalResult]] = defaultdict(list)
    for r in results:
        groups[(r.model, r.prompt_type)].append(r)

    # Sort by model name then prompt type for consistent output
    sorted_keys = sorted(groups.keys(), key=lambda k: (k[0], k[1]))

    header = (
        "| Model | Prompt Type | Rows | Avg Latency (ms) | Avg Keyword Recall | Total Tokens |"
    )
    separator = (
        "|-------|-------------|------|-----------------|-------------------|--------------|"
    )

    print("\n" + header)
    print(separator)

    for (model, prompt_type) in sorted_keys:
        group = groups[(model, prompt_type)]
        rows = len(group)
        avg_latency = int(sum(r.latency_ms for r in group) / rows) if rows else 0
        avg_recall = round(sum(r.keyword_recall for r in group) / rows, 2) if rows else 0.0
        total_tokens = sum(r.eval_count for r in group)
        print(f"| {model} | {prompt_type} | {rows} | {avg_latency} | {avg_recall} | {total_tokens} |")

    print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "LLM eval harness: benchmarks qwen3:14b vs foundation-sec:8b "
            "on seeded SIEM data using triage and summarise prompts."
        )
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        metavar="N",
        help="Maximum number of normalized_events rows to evaluate (default: 100).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip actual Ollama calls; write placeholder results to eval_results.jsonl.",
    )
    args = parser.parse_args()

    # Resolve output path
    output_path = Path(_PROJECT_ROOT) / "data" / "eval_results.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Initialize DuckDB store
    duckdb_store = DuckDBStore(settings.DATA_DIR)
    # Start write worker (needed for initialise_schema)
    worker_task = duckdb_store.start_write_worker()
    await duckdb_store.initialise_schema()

    try:
        # Fetch rows
        sql = (
            "SELECT event_id, event_type, hostname, process_name, command_line, "
            "severity, attack_technique "
            "FROM normalized_events LIMIT ?"
        )
        rows = await duckdb_store.fetch_all(sql, [args.limit])
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    if not rows:
        print("[!] No rows found in normalized_events. Run seed_siem_data.py first.")
        return

    print(
        f"[*] Evaluating {len(rows)} rows x 2 models x 2 prompt types "
        f"= {len(rows) * 2 * 2} calls"
        + (" (DRY RUN)" if args.dry_run else "")
    )

    models = [settings.OLLAMA_MODEL, settings.OLLAMA_CYBERSEC_MODEL]
    prompt_types = ["triage", "summarise"]
    ollama_base_url = settings.OLLAMA_HOST

    results: list[EvalResult] = []

    with open(output_path, "a", encoding="utf-8") as jsonl_file:
        for row_idx, row in enumerate(rows):
            for model in models:
                for prompt_type in prompt_types:
                    try:
                        result = await _eval_one_row(
                            row=row,
                            model=model,
                            prompt_type=prompt_type,
                            row_idx=row_idx,
                            ollama_base_url=ollama_base_url,
                            dry_run=args.dry_run,
                        )
                    except Exception as exc:
                        print(
                            f"[!] row={row_idx} model={model} prompt_type={prompt_type} error: {exc}",
                            file=sys.stderr,
                        )
                        # Write a failed result placeholder so we don't lose the row
                        result = EvalResult(
                            model=model,
                            prompt_id=f"row-{row_idx}-{prompt_type}",
                            prompt_type=prompt_type,
                            latency_ms=0,
                            eval_count=0,
                            keyword_recall=0.0,
                            timestamp=datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        )

                    results.append(result)
                    jsonl_file.write(json.dumps(dataclasses.asdict(result)) + "\n")

                    if not args.dry_run:
                        print(
                            f"  [{row_idx + 1}/{len(rows)}] model={model} "
                            f"prompt_type={prompt_type} "
                            f"latency={result.latency_ms}ms "
                            f"recall={result.keyword_recall:.2f} "
                            f"tokens={result.eval_count}"
                        )

    print(f"\n[+] Results written to {output_path} ({len(results)} entries)")
    _print_summary_table(results)


if __name__ == "__main__":
    asyncio.run(main())
