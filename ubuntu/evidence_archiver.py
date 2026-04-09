"""
EvidenceArchiver — writes raw syslog and EVE JSON bytes to daily gzip archives.

Forensic chain of custody:
- Raw bytes only. Never parsed, never modified.
- SHA256 computed at midnight rotation, not at read time.
- Write-once: gzip opened in append mode.
- Desktop never writes to this path.

Archive layout:
    $EVIDENCE_ARCHIVE_PATH/
        raw/
            syslog/YYYY-MM-DD.log.gz
            eve/YYYY-MM-DD.json.gz
        checksums/
            YYYY-MM-DD.sha256
"""
from __future__ import annotations

import gzip
import hashlib
import os
from datetime import date, datetime, timezone
from pathlib import Path


_DEFAULT_ARCHIVE_ROOT = "/mnt/evidence"


class EvidenceArchiver:
    """Thread-safe (single-writer) daily gzip evidence archiver."""

    def __init__(self, archive_root: str | Path | None = None) -> None:
        root = archive_root or os.environ.get("EVIDENCE_ARCHIVE_PATH", _DEFAULT_ARCHIVE_ROOT)
        self._root = Path(root)
        self._current_date: str = date.today().isoformat()
        self._syslog_dir = self._root / "raw" / "syslog"
        self._eve_dir = self._root / "raw" / "eve"
        self._checksum_dir = self._root / "checksums"
        self._syslog_dir.mkdir(parents=True, exist_ok=True)
        self._eve_dir.mkdir(parents=True, exist_ok=True)
        self._checksum_dir.mkdir(parents=True, exist_ok=True)

    def _today(self) -> str:
        return date.today().isoformat()

    def _syslog_path(self, day: str) -> Path:
        return self._syslog_dir / f"{day}.log.gz"

    def _eve_path(self, day: str) -> Path:
        return self._eve_dir / f"{day}.json.gz"

    def _sha256_file(self, path: Path) -> str:
        """Compute SHA256 of the file at path. File may be gzip-compressed — hash raw bytes."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _rotate(self, closing_date: str) -> None:
        """
        Seal the currently open day's files under closing_date.

        If _current_date differs from closing_date (e.g. in tests or forced rotation),
        the active gzip files are renamed to closing_date before checksumming.
        This ensures forensic archives are labelled with the correct calendar date
        rather than the real-time date at rotation.

        Called either automatically by rotate_if_needed() or forced in tests.
        closing_date — the calendar date being sealed (used as archive filename and checksum label).
        """
        active_date = self._current_date
        checksum_lines: list[str] = []

        # Rename active files to closing_date if needed (test harness or cross-midnight edge)
        for src_path, dst_path in (
            (self._syslog_path(active_date), self._syslog_path(closing_date)),
            (self._eve_path(active_date), self._eve_path(closing_date)),
        ):
            if src_path.exists() and src_path != dst_path:
                src_path.rename(dst_path)

        syslog_p = self._syslog_path(closing_date)
        if syslog_p.exists():
            digest = self._sha256_file(syslog_p)
            rel = f"raw/syslog/{closing_date}.log.gz"
            checksum_lines.append(f"{digest}  {rel}")

        eve_p = self._eve_path(closing_date)
        if eve_p.exists():
            digest = self._sha256_file(eve_p)
            rel = f"raw/eve/{closing_date}.json.gz"
            checksum_lines.append(f"{digest}  {rel}")

        if checksum_lines:
            checksum_file = self._checksum_dir / f"{closing_date}.sha256"
            checksum_file.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

        self._current_date = self._today()

    def rotate_if_needed(self) -> None:
        """Check if the day has rolled over; if so, finalize yesterday and rotate."""
        today = self._today()
        if today != self._current_date:
            self._rotate(self._current_date)

    def write_syslog_line(self, raw_line: bytes) -> None:
        """Append a raw syslog line (bytes) to today's syslog gzip archive."""
        self.rotate_if_needed()
        path = self._syslog_path(self._current_date)
        with gzip.open(path, "ab") as gz:
            gz.write(raw_line)

    def write_eve_line(self, raw_json: bytes) -> None:
        """Append a raw EVE JSON line (bytes) to today's EVE gzip archive."""
        self.rotate_if_needed()
        path = self._eve_path(self._current_date)
        with gzip.open(path, "ab") as gz:
            gz.write(raw_json)
