"""Unit tests for EvidenceArchiver (P31-T07). Red phase — stubs."""
from __future__ import annotations

import gzip
import hashlib
from datetime import date
from pathlib import Path

import pytest

try:
    from ubuntu.evidence_archiver import EvidenceArchiver
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False

pytestmark = pytest.mark.skipif(
    not _IMPORT_OK,
    reason="EvidenceArchiver not implemented — Wave 1 (plan 31-02)",
)


def test_write_gzip(tmp_path: Path):
    """write_syslog_line() creates a gzip file containing the raw bytes."""
    archiver = EvidenceArchiver(archive_root=tmp_path)
    archiver.write_syslog_line(b"hello\n")

    today = date.today().isoformat()
    gzip_path = tmp_path / "raw" / "syslog" / f"{today}.log.gz"
    assert gzip_path.exists(), f"Expected {gzip_path}"
    with gzip.open(gzip_path, "rb") as f:
        content = f.read()
    assert content == b"hello\n"


def test_sha256_written(tmp_path: Path):
    """rotate() writes a .sha256 file with digests for both closed files."""
    archiver = EvidenceArchiver(archive_root=tmp_path)
    archiver.write_syslog_line(b"line1\n")
    archiver.write_eve_line(b'{"type":"tls"}\n')

    yesterday = "2000-01-01"
    archiver._rotate(yesterday)  # force rotation

    checksum_path = tmp_path / "checksums" / f"{yesterday}.sha256"
    assert checksum_path.exists(), f"Expected {checksum_path}"
    content = checksum_path.read_text()
    assert "raw/syslog/" in content
    assert "raw/eve/" in content
    # Verify SHA256 values match the gzip files
    for line in content.strip().splitlines():
        digest, rel_path = line.split("  ", 1)
        full_path = tmp_path / rel_path.strip()
        if full_path.exists():
            actual = hashlib.sha256(full_path.read_bytes()).hexdigest()
            assert digest == actual, f"Digest mismatch for {rel_path}"


def test_daily_rotation(tmp_path: Path):
    """Writing across a day boundary creates separate per-day gzip files."""
    archiver = EvidenceArchiver(archive_root=tmp_path)
    archiver.write_syslog_line(b"day1\n")

    # Force rotation as if it's now the next day
    archiver._rotate("2000-01-01")
    archiver.write_syslog_line(b"day2\n")

    day1_path = tmp_path / "raw" / "syslog" / "2000-01-01.log.gz"
    assert day1_path.exists()
    with gzip.open(day1_path, "rb") as f:
        assert f.read() == b"day1\n"
