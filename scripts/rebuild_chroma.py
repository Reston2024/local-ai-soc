"""
Rebuild ChromaDB collections from source data using bge-m3 embeddings.

Run after `ollama pull bge-m3` to re-embed all soc_evidence and
feedback_verdicts collections with the new bge-m3 embedding model.

WARNING: This script deletes and re-embeds ChromaDB collections.
Back up data before running. In --dry-run mode, only collection
counts are logged; no data is modified.

MANUAL PREREQUISITE before full run:
    ollama pull bge-m3
    # Verify: ollama list | grep bge-m3
    # Smoke-test: curl http://127.0.0.1:11434/api/embeddings \
    #   -d '{"model":"bge-m3","prompt":"test"}' | python -m json.tool

ChromaDB target: configured via CHROMA_URL in .env (default http://192.168.1.22:8200)

Usage:
    uv run python scripts/rebuild_chroma.py --dry-run   # inspect counts only
    uv run python scripts/rebuild_chroma.py             # delete + re-embed
"""
from __future__ import annotations

import argparse
import asyncio
import sqlite3
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so backend/ is importable.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.core.config import settings  # noqa: E402
from backend.core.logging import get_logger  # noqa: E402
from backend.services.ollama_client import OllamaClient  # noqa: E402
from backend.stores.chroma_store import ChromaStore  # noqa: E402
from backend.stores.duckdb_store import DuckDBStore  # noqa: E402

log = get_logger(__name__)

BATCH_SIZE = 100
COLLECTIONS = ["soc_evidence", "feedback_verdicts"]


def _get_chroma_store() -> ChromaStore:
    return ChromaStore(
        data_dir=settings.DATA_DIR,
        chroma_url=settings.CHROMA_URL,
        chroma_token=settings.CHROMA_TOKEN,
    )


async def _rebuild_soc_evidence(
    chroma: ChromaStore,
    duckdb: DuckDBStore,
    ollama: OllamaClient,
    dry_run: bool,
) -> int:
    """Rebuild the soc_evidence collection from normalized_events."""
    count = await asyncio.to_thread(chroma.count, "soc_evidence")
    log.info("soc_evidence current count", count=count)

    if dry_run:
        log.info("Dry run — skipping deletion and re-embedding", collection="soc_evidence")
        return count

    # Delete existing collection
    try:
        await asyncio.to_thread(chroma.delete_collection, "soc_evidence", _admin_override=True)
        log.info("Deleted collection", collection="soc_evidence")
    except Exception as exc:
        log.warning("Collection did not exist — creating fresh", collection="soc_evidence", error=str(exc))

    # Fetch events from DuckDB
    sql = "SELECT event_id, raw_event FROM normalized_events LIMIT 10000"
    try:
        rows = await duckdb.fetch_all(sql)
    except Exception as exc:
        log.warning("DuckDB fetch failed — no events to embed", error=str(exc))
        rows = []

    if not rows:
        log.info("No events found in DuckDB — soc_evidence will be empty", collection="soc_evidence")
        return 0

    log.info("Embedding events", total=len(rows))

    total_added = 0
    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_start:batch_start + BATCH_SIZE]
        ids = [str(row[0]) for row in batch]
        texts = [str(row[1]) if row[1] else "" for row in batch]

        try:
            embeddings = await ollama.embed_batch(texts)
            chroma.add_documents(
                collection_name="soc_evidence",
                ids=ids,
                documents=texts,
                embeddings=embeddings,
            )
            total_added += len(ids)
            log.info(
                "Progress",
                collection="soc_evidence",
                added=total_added,
                total=len(rows),
            )
        except Exception as exc:
            log.error("Batch embed failed", batch_start=batch_start, error=str(exc))

    return total_added


async def _rebuild_feedback_verdicts(
    chroma: ChromaStore,
    ollama: OllamaClient,
    dry_run: bool,
) -> int:
    """Rebuild the feedback_verdicts collection from SQLite feedback table."""
    count = await asyncio.to_thread(chroma.count, "feedback_verdicts")
    log.info("feedback_verdicts current count", count=count)

    if dry_run:
        log.info("Dry run — skipping deletion and re-embedding", collection="feedback_verdicts")
        return count

    # Delete existing collection
    try:
        await asyncio.to_thread(chroma.delete_collection, "feedback_verdicts", _admin_override=True)
        log.info("Deleted collection", collection="feedback_verdicts")
    except Exception as exc:
        log.warning("Collection did not exist — creating fresh", collection="feedback_verdicts", error=str(exc))

    # Fetch feedback from SQLite
    sqlite_path = Path(settings.DATA_DIR) / "soc_brain.sqlite3"
    rows: list[tuple[str, str]] = []
    if sqlite_path.exists():
        try:
            conn = sqlite3.connect(str(sqlite_path))
            try:
                cur = conn.execute(
                    "SELECT detection_id, verdict, reason FROM feedback LIMIT 10000"
                )
                fb_rows = cur.fetchall()
                rows = [
                    (str(r[0]), f"verdict:{r[1]} reason:{r[2] or ''}") for r in fb_rows
                ]
            except Exception as exc:
                log.warning("SQLite feedback query failed", error=str(exc))
            finally:
                conn.close()
        except Exception as exc:
            log.warning("SQLite connect failed", path=str(sqlite_path), error=str(exc))

    if not rows:
        log.info("No feedback found in SQLite — feedback_verdicts will be empty")
        return 0

    log.info("Embedding feedback verdicts", total=len(rows))

    total_added = 0
    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_start:batch_start + BATCH_SIZE]
        ids = [row[0] for row in batch]
        texts = [row[1] for row in batch]

        try:
            embeddings = await ollama.embed_batch(texts)
            chroma.add_documents(
                collection_name="feedback_verdicts",
                ids=ids,
                documents=texts,
                embeddings=embeddings,
            )
            total_added += len(ids)
            log.info("Progress", collection="feedback_verdicts", added=total_added, total=len(rows))
        except Exception as exc:
            log.error("Batch embed failed", batch_start=batch_start, error=str(exc))

    return total_added


async def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild ChromaDB collections using bge-m3 embeddings.\n"
            "PREREQUISITE: ollama pull bge-m3 must be run first."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log current collection counts and exit without modifying any data.",
    )
    args = parser.parse_args()

    mode = "DRY RUN" if args.dry_run else "FULL REBUILD"
    log.info("rebuild_chroma starting", mode=mode, embed_model=settings.OLLAMA_EMBED_MODEL)

    chroma = _get_chroma_store()
    ollama = OllamaClient(base_url=settings.OLLAMA_HOST, model=settings.OLLAMA_EMBED_MODEL)

    # Initialize DuckDB for event fetching (full run only)
    duckdb: Any = None
    worker_task: Any = None
    if not args.dry_run:
        duckdb = DuckDBStore(settings.DATA_DIR)
        worker_task = duckdb.start_write_worker()
        await duckdb.initialise_schema()

    try:
        evidence_count = await _rebuild_soc_evidence(chroma, duckdb, ollama, args.dry_run)
        feedback_count = await _rebuild_feedback_verdicts(chroma, ollama, args.dry_run)
    finally:
        if worker_task is not None:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

    # Final counts
    if not args.dry_run:
        final_evidence = await asyncio.to_thread(chroma.count, "soc_evidence")
        final_feedback = await asyncio.to_thread(chroma.count, "feedback_verdicts")
    else:
        final_evidence = evidence_count
        final_feedback = feedback_count

    print(f"\nRebuild complete: soc_evidence={final_evidence} records, feedback_verdicts={final_feedback} records")
    log.info(
        "rebuild_chroma complete",
        soc_evidence=final_evidence,
        feedback_verdicts=final_feedback,
        mode=mode,
    )


if __name__ == "__main__":
    asyncio.run(main())
