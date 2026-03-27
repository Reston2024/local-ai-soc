#!/usr/bin/env python
"""
Seed the DuckDB/Chroma stores with up to MAX_ROWS rows from the
darkknight25/Advanced_SIEM_Dataset Hugging Face dataset.

Usage:
    uv run python scripts/seed_siem_data.py            # ingest
    uv run python scripts/seed_siem_data.py --dry-run  # validate without writing
    uv run python scripts/seed_siem_data.py --limit 100

This script is idempotent: rows with duplicate event_ids are silently skipped
(DuckDB PRIMARY KEY constraint).
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so backend/ingestion packages resolve
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.core.config import settings  # noqa: E402  (must come after sys.path fix)
from backend.core.deps import Stores  # noqa: E402
from backend.models.event import NormalizedEvent  # noqa: E402
from backend.services.ollama_client import OllamaClient  # noqa: E402
from backend.stores.chroma_store import ChromaStore  # noqa: E402
from backend.stores.duckdb_store import DuckDBStore  # noqa: E402
from backend.stores.sqlite_store import SQLiteStore  # noqa: E402
from ingestion.loader import IngestionLoader  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HF_DATASET = "darkknight25/Advanced_SIEM_Dataset"
_HF_SPLIT = "train"
_INGEST_BATCH_SIZE = 50

# Canonical severity values accepted by NormalizedEvent / normalizer
_VALID_SEVERITIES = {"low", "medium", "high", "critical"}

# Severity aliases that map to "low" (normalizer maps "info" → stored, but
# the plan spec says "informational"/"info" → "low" for seeding purposes)
_SEVERITY_ALIAS: dict[str, str] = {
    "informational": "low",
    "information": "low",
    "info": "low",
    "debug": "low",
    "verbose": "low",
    "unknown": "low",
    "warning": "medium",
    "warn": "medium",
    "moderate": "medium",
    "med": "medium",
    "crit": "critical",
    "hi": "high",
}


# ---------------------------------------------------------------------------
# Field normalisation
# ---------------------------------------------------------------------------


def _parse_timestamp(raw: object) -> datetime:
    """Parse a timestamp field from an HF row, falling back to utcnow()."""
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    if isinstance(raw, str) and raw.strip():
        for fmt in (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S.%f",
        ):
            try:
                return datetime.strptime(raw.strip(), fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        # Try ISO format fallback
        try:
            return datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(tz=timezone.utc)


def _normalise_severity(raw: object) -> str:
    """Normalise HF Severity field to a controlled vocabulary value."""
    if not isinstance(raw, str) or not raw.strip():
        return "low"
    lower = raw.strip().lower()
    if lower in _VALID_SEVERITIES:
        return lower
    return _SEVERITY_ALIAS.get(lower, "low")


def _normalise_row(row: dict) -> NormalizedEvent:
    """Map a single HF SIEM dataset row to a NormalizedEvent."""
    now = datetime.now(tz=timezone.utc)

    # Timestamp
    ts_raw = row.get("Timestamp") or row.get("timestamp")
    timestamp = _parse_timestamp(ts_raw)

    # Optional string fields — map from several possible column names
    hostname = (
        row.get("Source IP")
        or row.get("hostname")
        or row.get("Host")
        or None
    )
    username = row.get("User") or row.get("username") or None
    process_name = row.get("Process") or row.get("process") or None
    event_type = (
        row.get("Event Type")
        or row.get("event_type")
        or "siem_event"
    )
    severity = _normalise_severity(row.get("Severity") or row.get("severity"))

    # Network fields
    src_ip = row.get("Source IP") or row.get("src_ip") or None
    dst_ip = row.get("Destination IP") or row.get("dst_ip") or None

    # Coerce hostname to str if it came from src_ip (keep as IP string)
    if isinstance(hostname, str) and not hostname.strip():
        hostname = None
    if isinstance(username, str) and not username.strip():
        username = None
    if isinstance(process_name, str) and not process_name.strip():
        process_name = None

    return NormalizedEvent(
        event_id=str(uuid.uuid4()),
        timestamp=timestamp,
        ingested_at=now,
        source_type="hf_siem_seed",
        hostname=hostname,
        username=username,
        process_name=process_name,
        event_type=event_type,
        severity=severity,
        src_ip=src_ip,
        dst_ip=dst_ip,
        raw_event=json.dumps(row, default=str),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _load_hf_rows(limit: int) -> list[dict]:
    """
    Stream up to *limit* rows from the HF dataset and return them as dicts.

    Raises SystemExit on network or dataset errors.
    """
    try:
        import datasets  # noqa: PLC0415  (lazy import — only needed at runtime)
    except ImportError:
        print(
            "[!] The 'datasets' library is not installed. "
            "Run: uv add 'datasets>=2.21.0'",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        ds = datasets.load_dataset(
            path=_HF_DATASET,
            split=_HF_SPLIT,
            streaming=True,
            trust_remote_code=False,
        )
    except Exception as exc:
        print(
            f"[!] Failed to load HF dataset '{_HF_DATASET}': {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    rows: list[dict] = []
    try:
        for row in itertools.islice(ds, limit):
            rows.append(dict(row))
    except Exception as exc:
        print(
            f"[!] Error while streaming rows from '{_HF_DATASET}': {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    return rows


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed DuckDB/Chroma stores with HF SIEM dataset rows."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate normalisation without writing to any store.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        metavar="N",
        help="Maximum number of HF rows to fetch (default: 500).",
    )
    args = parser.parse_args()

    print(f"[*] Fetching up to {args.limit} rows from {_HF_DATASET} ...")
    rows = _load_hf_rows(args.limit)

    if not rows:
        print("[!] No rows returned from HF dataset. Exiting.")
        sys.exit(1)

    print(f"[*] Fetched {len(rows)} rows. Normalising ...")
    events = [_normalise_row(row) for row in rows]

    if args.dry_run:
        # Print first 3 normalised events as a sample, then exit
        print(f"\n[DRY-RUN] Would ingest {len(events)} events. Sample (first 3):\n")
        for i, ev in enumerate(events[:3]):
            print(
                f"  [{i + 1}] event_id={ev.event_id!r}\n"
                f"       timestamp={ev.timestamp}\n"
                f"       source_type={ev.source_type!r}\n"
                f"       hostname={ev.hostname!r}\n"
                f"       username={ev.username!r}\n"
                f"       event_type={ev.event_type!r}\n"
                f"       severity={ev.severity!r}\n"
            )
        print(f"[DRY-RUN] Normalisation OK — {len(events)} events validated. No writes performed.")
        return

    # ------------------------------------------------------------------
    # Normal (non-dry-run) ingestion path
    # ------------------------------------------------------------------
    data_dir = settings.DATA_DIR
    print(f"[*] Initialising stores at '{data_dir}' ...")

    duckdb_store = DuckDBStore(data_dir)
    chroma_store = ChromaStore(data_dir)
    sqlite_store = SQLiteStore(data_dir)
    stores = Stores(duckdb=duckdb_store, chroma=chroma_store, sqlite=sqlite_store)

    ollama_client = OllamaClient(
        base_url=settings.OLLAMA_HOST,
        model=settings.OLLAMA_MODEL,
        embed_model=settings.OLLAMA_EMBED_MODEL,
    )

    # Start DuckDB write worker
    worker_task = duckdb_store.start_write_worker()

    # Bootstrap schemas
    await duckdb_store.initialise_schema()

    try:
        loader = IngestionLoader(stores, ollama_client)

        total_loaded = 0
        total_embedded = 0
        total_edges = 0
        total_errors: list[str] = []

        # Ingest in batches of _INGEST_BATCH_SIZE
        for batch_start in range(0, len(events), _INGEST_BATCH_SIZE):
            batch = events[batch_start : batch_start + _INGEST_BATCH_SIZE]
            result = await loader.ingest_events(batch)
            total_loaded += result.loaded
            total_embedded += result.embedded
            total_edges += result.edges_created
            total_errors.extend(result.errors)
            print(
                f"  Batch {batch_start // _INGEST_BATCH_SIZE + 1}: "
                f"loaded={result.loaded}, embedded={result.embedded}, "
                f"edges={result.edges_created}"
            )

        print(
            f"\n[+] Seeded {total_loaded} events from HF SIEM dataset "
            f"(embedded={total_embedded}, edges={total_edges}, "
            f"errors={len(total_errors)})"
        )
        if total_errors:
            print("[!] Errors encountered (non-fatal):")
            for err in total_errors[:10]:
                print(f"    - {err}")

    finally:
        # Graceful shutdown
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        # Close Ollama HTTP client
        try:
            await ollama_client._client.aclose()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
