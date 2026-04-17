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
    "event_id, timestamp, source_type, hostname, severity, event_type, src_ip, dst_ip, "
    "dst_port, process_name, username, command_line, attack_technique, detection_source"
)

# ---------------------------------------------------------------------------
# Preset hunt definitions
# ---------------------------------------------------------------------------

PRESET_HUNTS = [
    # -----------------------------------------------------------------------
    # Original 6
    # -----------------------------------------------------------------------
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
    # -----------------------------------------------------------------------
    # 14 new hunts — added 2026-04-17
    # -----------------------------------------------------------------------
    {
        "id": "dns-tunnel",
        "name": "DNS tunneling / long subdomains",
        "mitre": "T1071.004",
        "desc": "DNS queries with abnormally long subdomains or high query rate may indicate C2 tunneling",
        "query": "Show DNS events where the dns_query length exceeds 50 characters or where the same source IP made more than 20 DNS queries",
    },
    {
        "id": "tls-ja3",
        "name": "Suspicious TLS JA3 fingerprints",
        "mitre": "T1573",
        "desc": "TLS client fingerprints (JA3) associated with known malware or C2 frameworks",
        "query": "Show TLS or network events where tls_ja3 is not null, ordered by most recent, to review unusual client fingerprints",
    },
    {
        "id": "http-ua",
        "name": "Suspicious HTTP user agents",
        "mitre": "T1071.001",
        "desc": "HTTP requests using tool-like or malformed user agent strings (curl, python-requests, Go-http, empty)",
        "query": "Show HTTP events where http_user_agent contains curl, python-requests, Go-http-client, wget, or powershell, or where http_user_agent is null",
    },
    {
        "id": "exfil-upload",
        "name": "Large outbound HTTP uploads",
        "mitre": "T1048",
        "desc": "HTTP POST requests with bodies over 1 MB may indicate staged data exfiltration",
        "query": "Show HTTP events where http_request_body_len is greater than 1000000 and event_type is http, ordered by http_request_body_len descending",
    },
    {
        "id": "ssh-brute",
        "name": "SSH brute force attempts",
        "mitre": "T1110.004",
        "desc": "Multiple failed SSH authentication attempts from the same source IP",
        "query": "Show SSH events where ssh_auth_success is false or dst_port is 22, grouped to find source IPs with more than 5 failed attempts",
    },
    {
        "id": "rdp-lateral",
        "name": "Internal RDP lateral movement",
        "mitre": "T1021.001",
        "desc": "RDP connections between internal hosts may indicate attacker pivoting",
        "query": "Show network events where dst_port is 3389 and src_ip starts with 10. or 192.168. or 172., ordered by timestamp descending",
    },
    {
        "id": "smb-enum",
        "name": "SMB share enumeration",
        "mitre": "T1135",
        "desc": "SMB tree connect and directory listing activity indicating network share discovery",
        "query": "Show SMB events where smb_action contains tree_connect or list or where smb_path is not null, ordered by timestamp descending",
    },
    {
        "id": "ioc-hits",
        "name": "Known-bad IOC matches",
        "mitre": "T1566",
        "desc": "Events where the source or destination matched a known malicious IOC from threat feeds",
        "query": "Show events where ioc_matched is true, ordered by ioc_confidence descending and timestamp descending",
    },
    {
        "id": "zeek-notice",
        "name": "Zeek notices and anomalies",
        "mitre": "T1040",
        "desc": "Network anomalies flagged by Zeek's notice framework including scan detection and protocol violations",
        "query": "Show events where zeek_notice_note is not null or zeek_weird_name is not null, ordered by timestamp descending",
    },
    {
        "id": "encoded-cmd",
        "name": "Encoded / obfuscated commands",
        "mitre": "T1027",
        "desc": "Base64, XOR, or caret-obfuscated command lines used to evade detection",
        "query": "Show process events where command_line contains base64 or -enc or -encodedcommand or ^, ordered by timestamp descending",
    },
    {
        "id": "schtask-persist",
        "name": "Scheduled task persistence",
        "mitre": "T1053.005",
        "desc": "Scheduled task creation or modification via schtasks.exe, at.exe, or WMI",
        "query": "Show process events where process_name contains schtasks or at.exe or where command_line contains schtasks and create or /sc",
    },
    {
        "id": "port-scan",
        "name": "Internal port scanning",
        "mitre": "T1046",
        "desc": "Single source IP connecting to many distinct destination ports, indicating reconnaissance",
        "query": "Show network events from the last 24 hours grouped by src_ip where the count of distinct dst_port values exceeds 20, ordered by port count descending",
    },
    {
        "id": "ntlm-relay",
        "name": "NTLM relay / pass-the-hash",
        "mitre": "T1557.001",
        "desc": "NTLM authentication from unexpected source IPs or to unusual destinations may indicate relay attacks",
        "query": "Show events where ntlm_username is not null or event_type contains ntlm, ordered by timestamp descending",
    },
    {
        "id": "av-kill",
        "name": "Security tool tampering",
        "mitre": "T1562.001",
        "desc": "Process or command activity targeting AV, EDR, or Windows Defender to disable endpoint protection",
        "query": "Show process events where command_line contains defender or MpCmdRun or sc stop or net stop or taskkill and process_name is not null",
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

    # Check first keyword is SELECT or WITH (CTEs allowed)
    first_token_match = re.match(r"(\w+)", stripped)
    first_kw = first_token_match.group(1).upper() if first_token_match else ""
    if first_kw not in ("SELECT", "WITH"):
        raise ValueError("only SELECT allowed")

    # Check for system table access (sqlite_master, information_schema, pg_catalog)
    if re.search(r"\b(sqlite_master|information_schema|pg_catalog)\b", upper):
        raise ValueError("system table access not allowed")

    # Build allowed tables: normalized_events + any CTE aliases declared in WITH clause
    # Pattern: WITH cte_name AS ( or WITH RECURSIVE cte_name AS (
    cte_names = {name.upper() for name in re.findall(r"\bWITH\s+(?:RECURSIVE\s+)?(\w+)\s+AS\s*\(", upper)}
    # Also catch additional CTEs separated by comma: ), cte2 AS (
    cte_names.update(name.upper() for name in re.findall(r"\),\s*(\w+)\s+AS\s*\(", upper))
    allowed_tables = {"NORMALIZED_EVENTS"} | cte_names

    # Extract all table names referenced in FROM / JOIN clauses.
    # We must exclude FROM that appears inside function calls like:
    #   EXTRACT(HOUR FROM timestamp)  — "FROM" here is part of the function, not a table ref
    #   TRIM(LEADING '0' FROM col)    — same
    # Strategy: strip all balanced parentheses contents before scanning for FROM/JOIN,
    # since table refs in FROM/JOIN are never inside parens at the top level of the clause.
    # Simpler approach: strip known function patterns that contain FROM keyword.
    scrubbed = re.sub(r"\bEXTRACT\s*\([^)]+\)", "EXTRACT_PLACEHOLDER", upper)
    scrubbed = re.sub(r"\bTRIM\s*\([^)]+\)", "TRIM_PLACEHOLDER", scrubbed)
    table_refs = re.findall(r"(?:FROM|JOIN)\s+(\w+)", scrubbed)
    for table_name in table_refs:
        if table_name not in allowed_tables:
            raise ValueError(f"only normalized_events table allowed (got: {table_name.lower()})")

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
            "CRITICAL: Use DuckDB syntax only. "
            "For time arithmetic use: timestamp - INTERVAL '5 minutes' (NOT DATE_SUB). "
            "For hour extraction use: EXTRACT(HOUR FROM timestamp). "
            "For string matching use: LIKE or ILIKE or SIMILAR TO. "
            "Return ONLY the SQL query, no explanation, no markdown, no code fences. "
            f"Available columns: {_SCHEMA_COLUMNS}. "
            f"Analyst query: {query}"
        )

        # 2. Call Ollama — prefer cybersec model; fall back to default if not pulled
        try:
            available = await self._ollama.list_models()
        except Exception:
            available = []
        preferred = settings.OLLAMA_CYBERSEC_MODEL
        # Match by base name (strip :tag) so "foundation-sec:8b" matches "foundation-sec:8b"
        available_bases = {m.split(":")[0].lower() for m in available}
        model_to_use = (
            preferred
            if preferred.split(":")[0].lower() in available_bases or preferred in available
            else settings.OLLAMA_MODEL
        )
        if model_to_use != preferred:
            log.info(
                "Hunt: cybersec model not available, falling back",
                requested=preferred,
                using=model_to_use,
            )
        raw_response = await self._ollama.generate(prompt, model=model_to_use)

        # Strip markdown code fences if present (```sql ... ``` or ``` ... ```)
        sql = raw_response.strip()
        sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*```$", "", sql)
        sql = sql.strip()

        # Normalize common LLM column name mistakes
        sql = re.sub(r'\bts\b', 'timestamp', sql)             # ts → timestamp
        sql = re.sub(r'\bsrc_host\b', 'hostname', sql)
        sql = re.sub(r'\bdst_host\b', 'hostname', sql)
        sql = re.sub(r'\buser_name\b', 'username', sql)       # user_name → username
        sql = re.sub(r'\buser\b(?=\s*[,\)\s])', 'username', sql)
        sql = re.sub(r'\bproc\b', 'process_name', sql)
        sql = re.sub(r'\bevent_dataset\b', 'event_type', sql) # event_dataset → event_type (Malcolm field)
        sql = re.sub(r'\bsrc_port_number\b', 'src_port', sql)
        sql = re.sub(r'\bdst_port_number\b', 'dst_port', sql)

        # ---------------------------------------------------------------------------
        # Fix MySQL/PostgreSQL date functions → DuckDB equivalents
        # LLMs commonly generate MySQL syntax even when asked for DuckDB.
        # ---------------------------------------------------------------------------

        # DATE_SUB(expr, INTERVAL n unit) → (expr) - INTERVAL 'n unit'
        # e.g. DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 5 MINUTE) → CURRENT_TIMESTAMP - INTERVAL '5 minutes'
        def _fix_date_sub(m: re.Match) -> str:
            expr, n, unit = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
            # DuckDB interval units: use plural lowercase
            unit_map = {
                "SECOND": "seconds", "SECONDS": "seconds",
                "MINUTE": "minutes", "MINUTES": "minutes",
                "HOUR": "hours",   "HOURS": "hours",
                "DAY": "days",     "DAYS": "days",
                "WEEK": "weeks",   "WEEKS": "weeks",
                "MONTH": "months", "MONTHS": "months",
                "YEAR": "years",   "YEARS": "years",
            }
            duckdb_unit = unit_map.get(unit.upper(), unit.lower() + "s")
            return f"({expr}) - INTERVAL '{n} {duckdb_unit}'"

        sql = re.sub(
            r"\bDATE_SUB\s*\(\s*(.+?)\s*,\s*INTERVAL\s+(\d+)\s+(\w+)\s*\)",
            _fix_date_sub,
            sql,
            flags=re.IGNORECASE,
        )

        # DATE_ADD(expr, INTERVAL n unit) → (expr) + INTERVAL 'n unit'
        def _fix_date_add(m: re.Match) -> str:
            expr, n, unit = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
            unit_map = {
                "SECOND": "seconds", "SECONDS": "seconds",
                "MINUTE": "minutes", "MINUTES": "minutes",
                "HOUR": "hours",   "HOURS": "hours",
                "DAY": "days",     "DAYS": "days",
                "WEEK": "weeks",   "WEEKS": "weeks",
                "MONTH": "months", "MONTHS": "months",
                "YEAR": "years",   "YEARS": "years",
            }
            duckdb_unit = unit_map.get(unit.upper(), unit.lower() + "s")
            return f"({expr}) + INTERVAL '{n} {duckdb_unit}'"

        sql = re.sub(
            r"\bDATE_ADD\s*\(\s*(.+?)\s*,\s*INTERVAL\s+(\d+)\s+(\w+)\s*\)",
            _fix_date_add,
            sql,
            flags=re.IGNORECASE,
        )

        # INTERVAL n unit (bare form) → INTERVAL 'n unit'  (DuckDB string form)
        # e.g. INTERVAL 5 MINUTE → INTERVAL '5 minutes'
        def _fix_bare_interval(m: re.Match) -> str:
            n, unit = m.group(1).strip(), m.group(2).strip()
            unit_map = {
                "SECOND": "seconds", "SECONDS": "seconds",
                "MINUTE": "minutes", "MINUTES": "minutes",
                "HOUR": "hours",   "HOURS": "hours",
                "DAY": "days",     "DAYS": "days",
                "WEEK": "weeks",   "WEEKS": "weeks",
                "MONTH": "months", "MONTHS": "months",
                "YEAR": "years",   "YEARS": "years",
            }
            duckdb_unit = unit_map.get(unit.upper(), unit.lower() + "s")
            return f"INTERVAL '{n} {duckdb_unit}'"

        sql = re.sub(
            r"\bINTERVAL\s+(\d+)\s+(\w+)\b(?!\s*')",
            _fix_bare_interval,
            sql,
            flags=re.IGNORECASE,
        )

        # NOW() → CURRENT_TIMESTAMP (DuckDB prefers CURRENT_TIMESTAMP)
        sql = re.sub(r'\bNOW\(\)', 'CURRENT_TIMESTAMP', sql, flags=re.IGNORECASE)

        # TIMESTAMPDIFF(unit, t1, t2) — no direct equiv; approximate with epoch diff
        # Most commonly used as TIMESTAMPDIFF(SECOND, t1, t2) — convert to epoch seconds diff
        sql = re.sub(
            r"\bTIMESTAMPDIFF\s*\(\s*SECOND\s*,\s*(.+?)\s*,\s*(.+?)\s*\)",
            r"DATEDIFF('second', \1, \2)",
            sql,
            flags=re.IGNORECASE,
        )
        sql = re.sub(
            r"\bTIMESTAMPDIFF\s*\(\s*MINUTE\s*,\s*(.+?)\s*,\s*(.+?)\s*\)",
            r"DATEDIFF('minute', \1, \2)",
            sql,
            flags=re.IGNORECASE,
        )

        # Fix invalid window-function-in-WHERE pattern that llama3 commonly generates:
        # WHERE ROW_NUMBER() OVER (ORDER BY col [DESC|ASC]) <= N
        # → ORDER BY col [DESC|ASC] LIMIT N
        sql = re.sub(
            r"\s*WHERE\s+ROW_NUMBER\(\)\s+OVER\s*\(\s*ORDER\s+BY\s+(\w+)(\s+(?:DESC|ASC))?\s*\)\s*<=\s*(\d+)",
            r" ORDER BY \1\2 LIMIT \3",
            sql,
            flags=re.IGNORECASE,
        )

        # Ensure every query has a LIMIT to prevent unbounded scans (cap at 500)
        if not re.search(r'\bLIMIT\b', sql, flags=re.IGNORECASE):
            sql = sql.rstrip().rstrip(";") + " LIMIT 500"

        # 3. Validate SQL — raises ValueError on failure
        validate_hunt_sql(sql)

        # 4. Execute against DuckDB — fetch_df returns list[dict] (fetch_all returns tuples)
        # If DuckDB rejects the SQL (bad function, unknown column, etc.) we fall back to a
        # safe broadening query so the hunt always returns something rather than 500-ing.
        try:
            rows: list[dict] = await self._duckdb.fetch_df(sql)
        except Exception as db_exc:
            log.warning(
                "DuckDB rejected generated SQL — using fallback broad query",
                original_sql=sql,
                error=str(db_exc),
            )
            # Extract keywords from the original query and run a broad ILIKE search
            keywords = [w for w in re.split(r'\W+', query) if len(w) > 3]
            keyword = keywords[0].lower() if keywords else "powershell"
            fallback_sql = (
                f"SELECT * FROM normalized_events "
                f"WHERE LOWER(COALESCE(command_line,'') || ' ' || COALESCE(process_name,'') "
                f"|| ' ' || COALESCE(event_type,'')) LIKE '%{keyword}%' "
                f"ORDER BY timestamp DESC LIMIT 500"
            )
            try:
                rows = await self._duckdb.fetch_df(fallback_sql)
                sql = fallback_sql  # report the actual SQL that ran
            except Exception:
                rows = []

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
