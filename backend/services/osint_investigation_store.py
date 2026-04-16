"""
OsintInvestigationStore — SQLite CRUD for Phase 51 OSINT investigation jobs.

Wraps sqlite3.Connection directly (same pattern as IocStore, AttackStore, CARStore).
All methods are synchronous; callers wrap in asyncio.to_thread().
"""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class OsintInvestigationStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        # Ensure tables exist (idempotent — for unit tests using :memory: connections)
        self._conn.executescript(_OSINT_DDL)
        self._conn.commit()

    def create_investigation(self, target: str, usecase: str) -> str:
        """Insert new investigation row, return the job ID (SpiderFoot will assign its own,
        but we generate a placeholder until start_scan returns)."""
        job_id = str(uuid4())
        self._conn.execute(
            """INSERT INTO osint_investigations
               (id, target, target_type, usecase, status, started_at)
               VALUES (?, ?, ?, ?, 'RUNNING', ?)""",
            (job_id, target, _detect_target_type(target), usecase, _now()),
        )
        self._conn.commit()
        return job_id

    def update_job_id(self, old_id: str, new_id: str) -> None:
        """Replace placeholder UUID with actual SpiderFoot scan ID."""
        self._conn.execute(
            "UPDATE osint_investigations SET id=? WHERE id=?", (new_id, old_id)
        )
        self._conn.commit()

    def get_investigation(self, job_id: str) -> Optional[dict]:
        self._conn.row_factory = sqlite3.Row
        cur = self._conn.execute(
            "SELECT * FROM osint_investigations WHERE id=?", (job_id,)
        )
        row = cur.fetchone()
        self._conn.row_factory = None
        return dict(row) if row else None

    def update_investigation_status(
        self, job_id: str, status: str, completed_at: Optional[str] = None,
        error: Optional[str] = None, result_summary: Optional[dict] = None,
    ) -> None:
        self._conn.execute(
            """UPDATE osint_investigations
               SET status=?, completed_at=?, error=?, result_summary=?
               WHERE id=?""",
            (status, completed_at, error,
             json.dumps(result_summary) if result_summary else None,
             job_id),
        )
        self._conn.commit()

    def list_investigations(self, limit: int = 50) -> list[dict]:
        self._conn.row_factory = sqlite3.Row
        cur = self._conn.execute(
            "SELECT * FROM osint_investigations ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        self._conn.row_factory = None
        return rows

    def bulk_insert_osint_findings(self, findings: list[dict]) -> None:
        now = _now()
        rows = [
            (
                f["investigation_id"],
                f["event_type"],
                f["data"],
                f.get("source_module"),
                f.get("confidence", 1.0),
                now,
                f.get("misp_hit", 0),
                json.dumps(f.get("misp_event_ids", [])),
            )
            for f in findings
        ]
        self._conn.executemany(
            """INSERT INTO osint_findings
               (investigation_id, event_type, data, source_module, confidence,
                created_at, misp_hit, misp_event_ids)
               VALUES (?,?,?,?,?,?,?,?)""",
            rows,
        )
        self._conn.commit()

    def get_findings(self, job_id: str, event_type: Optional[str] = None) -> list[dict]:
        self._conn.row_factory = sqlite3.Row
        if event_type:
            cur = self._conn.execute(
                "SELECT * FROM osint_findings WHERE investigation_id=? AND event_type=? ORDER BY id",
                (job_id, event_type),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM osint_findings WHERE investigation_id=? ORDER BY event_type, id",
                (job_id,),
            )
        rows = [dict(r) for r in cur.fetchall()]
        self._conn.row_factory = None
        return rows

    def bulk_query_ioc_cache(self, ioc_values: list[str]) -> list[dict]:
        """Bulk lookup against ioc_store table. Returns rows for matching values."""
        if not ioc_values:
            return []
        placeholders = ",".join("?" * len(ioc_values))
        self._conn.row_factory = sqlite3.Row
        cur = self._conn.execute(
            f"""SELECT ioc_value AS value, ioc_type, confidence, feed_source,
                       actor_tag, malware_family
                FROM ioc_store
                WHERE ioc_value IN ({placeholders}) AND ioc_status='active'""",
            ioc_values,
        )
        rows = [dict(r) for r in cur.fetchall()]
        self._conn.row_factory = None
        return rows

    def bulk_insert_dnstwist_findings(self, lookalikes: list[dict]) -> None:
        now = _now()
        rows = [
            (
                l["investigation_id"],
                l["seed_domain"],
                l.get("fuzzer"),
                l["lookalike_domain"],
                l.get("dns_a"),
                l.get("dns_mx"),
                l.get("whois_registrar"),
                l.get("whois_created"),
                now,
            )
            for l in lookalikes
        ]
        self._conn.executemany(
            """INSERT INTO dnstwist_findings
               (investigation_id, seed_domain, fuzzer, lookalike_domain,
                dns_a, dns_mx, whois_registrar, whois_created, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            rows,
        )
        self._conn.commit()

    def get_dnstwist_findings(self, job_id: str, seed_domain: str) -> list[dict]:
        self._conn.row_factory = sqlite3.Row
        cur = self._conn.execute(
            """SELECT * FROM dnstwist_findings
               WHERE investigation_id=? AND seed_domain=?
               ORDER BY lookalike_domain""",
            (job_id, seed_domain),
        )
        rows = [dict(r) for r in cur.fetchall()]
        self._conn.row_factory = None
        return rows

    def get_findings_since(self, job_id: str, last_seen_id: int) -> list[dict]:
        """Return findings with id > last_seen_id for SSE streaming cursor."""
        self._conn.row_factory = sqlite3.Row
        cur = self._conn.execute(
            "SELECT * FROM osint_findings WHERE investigation_id=? AND id>? ORDER BY id",
            (job_id, last_seen_id),
        )
        rows = [dict(r) for r in cur.fetchall()]
        self._conn.row_factory = None
        return rows


def _detect_target_type(target: str) -> str:
    """Heuristic: classify seed target as ip, domain, email, or asn."""
    import re
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", target):
        return "ip"
    if target.startswith("AS") and target[2:].isdigit():
        return "asn"
    if "@" in target:
        return "email"
    return "domain"


# Minimal DDL for standalone use (e.g. unit tests with :memory: connections
# that bypass SQLiteStore.__init__).  CREATE IF NOT EXISTS is idempotent.
_OSINT_DDL = """
CREATE TABLE IF NOT EXISTS osint_investigations (
    id              TEXT PRIMARY KEY,
    target          TEXT NOT NULL,
    target_type     TEXT,
    usecase         TEXT DEFAULT 'investigate',
    status          TEXT DEFAULT 'RUNNING',
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    result_summary  TEXT,
    error           TEXT
);

CREATE TABLE IF NOT EXISTS osint_findings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id    TEXT NOT NULL REFERENCES osint_investigations(id),
    event_type          TEXT NOT NULL,
    data                TEXT NOT NULL,
    source_module       TEXT,
    confidence          REAL DEFAULT 1.0,
    created_at          TEXT NOT NULL,
    misp_hit            INTEGER DEFAULT 0,
    misp_event_ids      TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS dnstwist_findings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id    TEXT NOT NULL REFERENCES osint_investigations(id),
    seed_domain         TEXT NOT NULL,
    fuzzer              TEXT,
    lookalike_domain    TEXT NOT NULL,
    dns_a               TEXT,
    dns_mx              TEXT,
    whois_registrar     TEXT,
    whois_created       TEXT,
    created_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_osint_findings_inv ON osint_findings(investigation_id);
CREATE INDEX IF NOT EXISTS idx_dnstwist_findings_inv ON dnstwist_findings(investigation_id);
CREATE INDEX IF NOT EXISTS idx_osint_inv_started ON osint_investigations(started_at DESC);
"""
