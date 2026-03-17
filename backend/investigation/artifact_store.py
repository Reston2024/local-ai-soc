"""Forensic artifact storage — filesystem under data/artifacts/ + SQLite metadata."""
from __future__ import annotations
import asyncio
from pathlib import Path
from uuid import uuid4

from backend.core.logging import get_logger
log = get_logger(__name__)


async def save_artifact(
    data_dir: str,
    case_id: str,
    artifact_id: str | None,
    filename: str,
    content: bytes,
    sqlite_store,
    description: str = "",
    mime_type: str | None = None,
) -> dict:
    """Save artifact bytes to filesystem and metadata to SQLite.

    Returns dict: {artifact_id, filename, file_size, file_path}

    sqlite_store may be None (metadata write is skipped in that case).
    """
    art_id = artifact_id or str(uuid4())
    artifact_dir = Path(data_dir) / "artifacts" / case_id
    # Sanitize filename to avoid path traversal
    safe_filename = Path(filename).name or "artifact"
    file_path = artifact_dir / f"{art_id}_{safe_filename}"

    def _write():
        artifact_dir.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)

    await asyncio.to_thread(_write)

    # Store path as posix (forward slashes) — avoid Windows backslash issues
    posix_path = file_path.as_posix()

    if sqlite_store is not None:
        await asyncio.to_thread(
            sqlite_store.insert_artifact,
            art_id,
            case_id,
            safe_filename,
            posix_path,
            len(content),
            mime_type,
            description,
        )

    log.info("Artifact saved: %s (%d bytes) for case %s", art_id, len(content), case_id)
    return {
        "artifact_id": art_id,
        "filename": safe_filename,
        "file_size": len(content),
        "file_path": posix_path,
    }


async def get_artifact(artifact_id: str, sqlite_store) -> dict | None:
    """Retrieve artifact metadata from SQLite by artifact_id."""
    def _lookup():
        cursor = sqlite_store._conn.execute(
            "SELECT * FROM case_artifacts WHERE artifact_id = ?",
            (artifact_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))
    return await asyncio.to_thread(_lookup)
