"""
Ubuntu ECS normalization server.

Reads incoming syslog and EVE JSON from files on disk (written by EvidenceArchiver),
maps to ECS-normalized NDJSON, and exposes HTTP endpoints for desktop polling.

NO AI. Pure field transformation: rename, type coerce, severity map.

Endpoints:
    GET /normalized/{date}   — streams full day's gzip NDJSON (Content-Encoding: gzip)
    GET /normalized/latest   — today's partial file (live)
    GET /normalized/index    — list of available dates with doc counts

Runs on 0.0.0.0:8080. No auth (LAN-only service).

Usage:
    uvicorn ubuntu.normalization_server:app --host 0.0.0.0 --port 8080
"""
from __future__ import annotations

import asyncio
import gzip
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NORMALIZED_DIR = Path(
    os.environ.get("SOC_NORMALIZED_DIR", "/var/lib/soc-pipeline/normalized")
)
_EVIDENCE_ROOT = Path(
    os.environ.get("EVIDENCE_ARCHIVE_PATH", "/mnt/evidence")
)

# ---------------------------------------------------------------------------
# ECS field mapping
# ---------------------------------------------------------------------------

_SEVERITY_MAP = {
    "1": "critical", "2": "high", "3": "medium", "4": "low",
    "critical": "critical", "high": "high", "medium": "medium",
    "low": "low", "info": "info", "informational": "info",
}


def _map_eve_doc(doc: dict) -> dict:
    """Map a Suricata EVE JSON doc to ECS-normalized output dict."""
    src = doc.get("source") or {}
    dst = doc.get("destination") or {}
    sev_raw = str(
        (doc.get("event") or {}).get("severity", "")
        or (doc.get("alert") or {}).get("severity", "")
    ).lower()
    return {
        "timestamp": doc.get("@timestamp"),
        "source_type": "suricata_eve",
        "event_type": (doc.get("event") or {}).get("type") or doc.get("event.type"),
        "hostname": (doc.get("observer") or {}).get("hostname") or (doc.get("agent") or {}).get("hostname"),
        "src_ip": src.get("ip") or doc.get("src_ip"),
        "dst_ip": dst.get("ip") or doc.get("dst_ip"),
        "src_port": src.get("port") or doc.get("src_port"),
        "dst_port": dst.get("port") or doc.get("dst_port"),
        "severity": _SEVERITY_MAP.get(sev_raw, "info"),
        # Protocol sub-fields pass through intact for downstream normalization
        "dns": doc.get("dns"),
        "tls": doc.get("tls"),
        "file": doc.get("file"),
        "http": doc.get("http"),
        "alert": doc.get("alert"),
        "raw_event": json.dumps(doc)[:8192],
    }


def _map_syslog_line(line: str) -> dict:
    """Map a raw syslog line to ECS-normalized output dict."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_type": "ipfire_syslog",
        "event_type": "syslog",
        "severity": "info",
        "raw_event": line.strip()[:8192],
    }

# ---------------------------------------------------------------------------
# Normalized NDJSON output helpers
# ---------------------------------------------------------------------------


def _ndjson_path(day: str) -> Path:
    return _NORMALIZED_DIR / f"{day}.ndjson.gz"


def _stream_gzip_file(path: Path) -> Iterator[bytes]:
    """Stream gzip file in chunks."""
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            yield chunk


def _count_lines_in_gz(path: Path) -> int:
    """Count NDJSON lines in a gzip file (doc count)."""
    count = 0
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            for _ in f:
                count += 1
    except Exception:
        pass
    return count

# ---------------------------------------------------------------------------
# NormalizationWriter — background task that reads raw EVE/syslog lines from
# EvidenceArchiver output and writes ECS-normalized NDJSON to $SOC_NORMALIZED_DIR
# ---------------------------------------------------------------------------

log = logging.getLogger("normalization_writer")


class NormalizationWriter:
    """
    Reads raw EVE JSON lines from $EVIDENCE_ARCHIVE_PATH/raw/eve/YYYY-MM-DD.json.gz
    and raw syslog lines from $EVIDENCE_ARCHIVE_PATH/raw/syslog/YYYY-MM-DD.log.gz,
    applies ECS field mapping, and appends normalized NDJSON to
    $SOC_NORMALIZED_DIR/YYYY-MM-DD.ndjson.gz.

    Runs as an asyncio background task inside the FastAPI lifespan.
    Tracks its position via in-memory line offset (resets on restart — files are append-only
    and idempotent re-ingestion is acceptable for this forensic-only pipeline).
    """

    POLL_INTERVAL = 5  # seconds between scans

    def __init__(self) -> None:
        self._eve_offset: int = 0      # lines already processed from today's EVE gz
        self._syslog_offset: int = 0   # lines already processed from today's syslog gz
        self._current_date: str = date.today().isoformat()
        _NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)

    def _reset_if_new_day(self) -> None:
        today = date.today().isoformat()
        if today != self._current_date:
            self._current_date = today
            self._eve_offset = 0
            self._syslog_offset = 0

    def _read_new_lines_gz(self, gz_path: Path, offset: int) -> tuple[list[str], int]:
        """Read lines from a gzip file starting at `offset`, return (new_lines, new_offset)."""
        if not gz_path.exists():
            return [], offset
        lines = []
        try:
            with gzip.open(gz_path, "rt", encoding="utf-8", errors="replace") as f:
                for idx, line in enumerate(f):
                    if idx >= offset:
                        lines.append(line)
        except Exception as exc:
            log.warning("NormalizationWriter: read error %s: %s", gz_path, exc)
        return lines, offset + len(lines)

    def _append_normalized(self, doc: dict) -> None:
        """Append one normalized NDJSON line to today's output file."""
        out_path = _NORMALIZED_DIR / f"{self._current_date}.ndjson.gz"
        line = json.dumps(doc, ensure_ascii=False) + "\n"
        with gzip.open(out_path, "at", encoding="utf-8") as gz:
            gz.write(line)

    def process_once(self) -> None:
        """One scan cycle: read new EVE and syslog lines, normalize, append output."""
        self._reset_if_new_day()
        day = self._current_date

        # --- EVE JSON ---
        eve_path = _EVIDENCE_ROOT / "raw" / "eve" / f"{day}.json.gz"
        new_eve_lines, new_eve_offset = self._read_new_lines_gz(eve_path, self._eve_offset)
        for raw_line in new_eve_lines:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                doc = json.loads(raw_line)
                normalized = _map_eve_doc(doc)
                self._append_normalized(normalized)
            except Exception as exc:
                log.warning("NormalizationWriter: EVE parse error: %s | line: %.120s", exc, raw_line)
        self._eve_offset = new_eve_offset

        # --- Syslog ---
        syslog_path = _EVIDENCE_ROOT / "raw" / "syslog" / f"{day}.log.gz"
        new_syslog_lines, new_syslog_offset = self._read_new_lines_gz(syslog_path, self._syslog_offset)
        for raw_line in new_syslog_lines:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                normalized = _map_syslog_line(raw_line)
                self._append_normalized(normalized)
            except Exception as exc:
                log.warning("NormalizationWriter: syslog parse error: %s | line: %.120s", exc, raw_line)
        self._syslog_offset = new_syslog_offset


async def _run_writer(writer: NormalizationWriter) -> None:
    """Background coroutine: call process_once() every POLL_INTERVAL seconds."""
    while True:
        try:
            await asyncio.to_thread(writer.process_once)
        except Exception as exc:
            log.error("NormalizationWriter: unexpected error: %s", exc)
        await asyncio.sleep(NormalizationWriter.POLL_INTERVAL)


@asynccontextmanager
async def lifespan(app_: FastAPI):
    """FastAPI lifespan: start NormalizationWriter background task on startup."""
    writer = NormalizationWriter()
    task = asyncio.create_task(_run_writer(writer))
    log.info("NormalizationWriter started (poll_interval=%ds)", NormalizationWriter.POLL_INTERVAL)
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        log.info("NormalizationWriter stopped")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="SOC Ubuntu Normalization Server", version="1.0.0", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/normalized/index")
async def normalized_index():
    """Return list of available normalized dates with doc counts."""
    _NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    for gz_path in sorted(_NORMALIZED_DIR.glob("*.ndjson.gz")):
        day = gz_path.stem.replace(".ndjson", "")
        doc_count = _count_lines_in_gz(gz_path)
        entries.append({
            "date": day,
            "doc_count": doc_count,
            "size_bytes": gz_path.stat().st_size,
            "path": str(gz_path),
        })
    return {"dates": entries, "total_dates": len(entries)}


@app.get("/normalized/latest")
async def normalized_latest():
    """Stream today's partial normalized NDJSON file."""
    today = date.today().isoformat()
    path = _ndjson_path(today)
    if not path.exists():
        # Return empty gzip stream — desktop handles empty gracefully
        raise HTTPException(status_code=404, detail=f"No normalized data for {today} yet")
    return StreamingResponse(
        _stream_gzip_file(path),
        media_type="application/x-ndjson",
        headers={
            "Content-Encoding": "gzip",
            "X-Soc-Date": today,
        },
    )


@app.get("/normalized/{day}")
async def normalized_by_date(day: str):
    """Stream a specific day's normalized NDJSON file."""
    # Validate date format
    try:
        date.fromisoformat(day)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {day} (use YYYY-MM-DD)")
    path = _ndjson_path(day)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No normalized data for {day}")
    return StreamingResponse(
        _stream_gzip_file(path),
        media_type="application/x-ndjson",
        headers={
            "Content-Encoding": "gzip",
            "X-Soc-Date": day,
        },
    )
