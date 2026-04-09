"""
Hunt engine: NL → validated DuckDB SQL → ranked results.

SQL safety rules (validate_hunt_sql raises ValueError on violation):
- Only SELECT statements allowed (first non-whitespace token must be SELECT)
- Only normalized_events table may appear in FROM/JOIN clauses
- ATTACH, COPY, PRAGMA (except read-only), DROP, DELETE, UPDATE, INSERT are forbidden
- Multiple statements separated by semicolons are forbidden
- Subqueries on system tables (sqlite_master, information_schema) are forbidden
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.core.config import settings
from backend.core.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Schema columns available in normalized_events
# ---------------------------------------------------------------------------

_SCHEMA_COLUMNS = (
    "event_id, ts, source_type, hostname, severity, event_type, src_ip, dst_ip, "
    "dst_port, process_name, user_name, event_dataset, detection_source"
)

# ---------------------------------------------------------------------------
# Preset hunt definitions
# ---------------------------------------------------------------------------

PRESET_HUNTS = [
    {
        "id": "ps-child",
        "name": "PowerShell child processes",
        "mitre": "T1059.001",
        "desc": "Identify unusual processes spawned by powershell.exe or pwsh.exe",
        "query": "Show processes where parent process is powershell.exe or pwsh.exe that are not common child processes",
    },
    {
        "id": "beaconing",
        "name": "Suspicious network beaconing",
        "mitre": "T1071",
        "desc": "Detect regular outbound connections with jitter < 5s to external IPs",
        "query": "Show network events with repeated connections to the same external IP within short intervals",
    },
    {
        "id": "auth-hours",
        "name": "Unusual auth hour patterns",
        "mitre": "T1078",
        "desc": "Logins outside business hours or from new geolocation",
        "query": "Show authentication events that occurred outside business hours (before 07:00 or after 19:00)",
    },
    {
        "id": "lolbin",
        "name": "LOLBin abuse (certutil/mshta)",
        "mitre": "T1218",
        "desc": "Living-off-the-land binaries used for payload delivery or evasion",
        "query": "Show process events where process_name contains certutil, mshta, regsvr32, rundll32, or wscript",
    },
    {
        "id": "lateral",
        "name": "Lateral movement via WMI/PsExec",
        "mitre": "T1021",
        "desc": "Remote execution patterns indicating lateral movement",
        "query": "Show network or process events indicating WMI remote execution or PsExec usage",
    },
    {
        "id": "cred-dump",
        "name": "Credential dumping indicators",
        "mitre": "T1003",
        "desc": "Access to LSASS memory or SAM database from unexpected processes",
        "query": "Show process events where a process accessed lsass.exe memory or the SAM database",
    },
]

# ---------------------------------------------------------------------------
# Severity rank map for result ranking
# ---------------------------------------------------------------------------

_SEVERITY_ORDER: dict[str | None, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
    "informational": 4,
}


# ---------------------------------------------------------------------------
# SQL validator
# ---------------------------------------------------------------------------

def validate_hunt_sql(sql: str) -> bool:
    """
    Validate a SQL string for safe execution against normalized_events.

    Raises ValueError with a descriptive message on any violation.
    Returns True if the query passes all checks.
    """
    # Strip surrounding whitespace
    stripped = sql.strip()
    upper = stripped.upper()

    # Check for multiple statements FIRST (semicolons not at trailing position)
    # Strip trailing semicolon, then check for any remaining semicolons
    no_trailing_semi = stripped.rstrip(";").strip()
    if ";" in no_trailing_semi:
        raise ValueError("multiple statements not allowed")

    # Check for ATTACH keyword
    if re.search(r"\bATTACH\b", upper):
        raise ValueError("ATTACH not allowed")

    # Check for COPY keyword
    if re.search(r"\bCOPY\b", upper):
        raise ValueError("COPY not allowed")

    # Check for DDL keywords: CREATE, DROP, ALTER, TRUNCATE
    if re.search(r"\b(CREATE|DROP|ALTER|TRUNCATE)\b", upper):
        raise ValueError("DDL not allowed")

    # Check for DML keywords that are not SELECT: DELETE, UPDATE, INSERT
    if re.search(r"\b(DELETE|UPDATE|INSERT)\b", upper):
        raise ValueError("only SELECT allowed")

    # Check first keyword is SELECT
    first_token_match = re.match(r"(\w+)", stripped)
    if not first_token_match or first_token_match.group(1).upper() != "SELECT":
        raise ValueError("only SELECT allowed")

    # Check for system table access (sqlite_master, information_schema, pg_catalog)
    if re.search(r"\b(sqlite_master|information_schema|pg_catalog)\b", upper):
        raise ValueError("system table access not allowed")

    # Extract all table names referenced in FROM / JOIN clauses
    # Pattern: FROM <table> or JOIN <table> (with optional AS alias)
    table_refs = re.findall(r"(?:FROM|JOIN)\s+(\w+)", upper)
    allowed_tables = {"NORMALIZED_EVENTS"}
    for table_name in table_refs:
        if table_name not in allowed_tables:
            raise ValueError("only normalized_events table allowed")

    return True


# ---------------------------------------------------------------------------
# Result ranking
# ---------------------------------------------------------------------------

def _rank_results(rows: list[dict]) -> list[dict]:
    """
    Sort result rows by severity priority (critical first) then by ts descending.

    Severity order: critical=0, high=1, medium=2, low=3, info/informational=4, None=5
    """

    def sort_key(row: dict) -> tuple:
        severity = (row.get("severity") or "").lower() or None
        sev_rank = _SEVERITY_ORDER.get(severity, 5)
        ts = row.get("ts") or ""
        # Negate ts string for descending order (ISO-8601 strings sort lexicographically)
        return (sev_rank, tuple([-ord(c) for c in ts]))

    return sorted(rows, key=sort_key)


# ---------------------------------------------------------------------------
# HuntResult dataclass
# ---------------------------------------------------------------------------

@dataclass
class HuntResult:
    """Container for completed hunt results."""

    hunt_id: str
    query: str
    sql: str
    rows: list[dict]
    row_count: int
    ranked: bool = True
    created_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# HuntEngine
# ---------------------------------------------------------------------------

class HuntEngine:
    """
    Orchestrates NL → SQL → DuckDB execution → SQLite persistence.

    Instantiate per-request (lightweight — stores are shared).
    """

    def __init__(self, duckdb_store: Any, sqlite_store: Any, ollama_client: Any) -> None:
        self._duckdb = duckdb_store
        self._sqlite = sqlite_store
        self._ollama = ollama_client

    async def run(self, query: str, analyst_id: str = "unknown") -> HuntResult:
        """
        Execute a natural-language threat hunt.

        1. Generate DuckDB SQL via Ollama
        2. Validate SQL (raises ValueError on rejection)
        3. Execute against DuckDB
        4. Rank results by severity/recency
        5. Persist to SQLite hunts table
        6. Return HuntResult
        """
        # 1. Build prompt
        prompt = (
            "You are a DuckDB SQL generator for a SOC analyst. "
            "The analyst wants to hunt for threats. "
            "Write a single DuckDB SELECT statement against the normalized_events table only. "
            "Return ONLY the SQL, no explanation, no markdown. "
            f"Schema columns available: {_SCHEMA_COLUMNS}. "
            f"Analyst query: {query}"
        )

        # 2. Call Ollama — use cybersec model for hunting
        model = settings.OLLAMA_CYBERSEC_MODEL
        raw_response = await self._ollama.generate(prompt, model=model)

        # Strip markdown code fences if present (```sql ... ``` or ``` ... ```)
        sql = raw_response.strip()
        sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*```$", "", sql)
        sql = sql.strip()

        # Normalize common LLM column name mistakes (llama3 uses 'ts' instead of 'timestamp')
        sql = re.sub(r'\bts\b', 'timestamp', sql)
        sql = re.sub(r'\bsrc_host\b', 'hostname', sql)
        sql = re.sub(r'\bdst_host\b', 'hostname', sql)
        sql = re.sub(r'\buser\b(?=\s*[,\)\s])', 'username', sql)
        sql = re.sub(r'\bproc\b', 'process_name', sql)

        # 3. Validate SQL — raises ValueError on failure
        validate_hunt_sql(sql)

        # 4. Execute against DuckDB — fetch_df returns list[dict] (fetch_all returns tuples)
        rows: list[dict] = await self._duckdb.fetch_df(sql)

        # 5. Rank results
        ranked_rows = _rank_results(rows)

        # 6. Build HuntResult
        hunt_id = str(uuid4())
        result = HuntResult(
            hunt_id=hunt_id,
            query=query,
            sql=sql,
            rows=ranked_rows,
            row_count=len(ranked_rows),
        )

        # 7. Persist to SQLite
        await asyncio.to_thread(
            self._sqlite.save_hunt,
            hunt_id,
            query,
            sql,
            json.dumps(ranked_rows, default=str),
            len(ranked_rows),
            analyst_id,
        )

        log.info(
            "Hunt complete",
            hunt_id=hunt_id,
            row_count=result.row_count,
            analyst_id=analyst_id,
        )
        return result
