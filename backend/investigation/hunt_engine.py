"""Threat hunting query engine — 4 DuckDB SQL templates for analyst hypothesis testing."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HuntTemplate:
    name: str
    description: str
    sql: str
    param_keys: list[str] = field(default_factory=list)


HUNT_TEMPLATES: dict[str, HuntTemplate] = {
    "suspicious_ip_comms": HuntTemplate(
        name="suspicious_ip_comms",
        description="Find hosts communicating with a suspicious IP",
        sql="""
            SELECT DISTINCT hostname, src_ip, dst_ip, timestamp, event_type
            FROM normalized_events
            WHERE dst_ip = ?
            ORDER BY timestamp DESC
            LIMIT 200
        """,
        param_keys=["dst_ip"],
    ),
    "powershell_children": HuntTemplate(
        name="powershell_children",
        description="Identify processes spawned by PowerShell",
        sql="""
            SELECT hostname, process_name, process_id, parent_process_name,
                   command_line, timestamp
            FROM normalized_events
            WHERE parent_process_name ILIKE '%powershell%'
            ORDER BY timestamp DESC
            LIMIT 200
        """,
        param_keys=[],
    ),
    "unusual_auth": HuntTemplate(
        name="unusual_auth",
        description="Detect unusual authentication patterns (high frequency per host/user)",
        sql="""
            SELECT hostname, username, COUNT(*) AS cnt,
                   MIN(timestamp) AS first_seen, MAX(timestamp) AS last_seen
            FROM normalized_events
            WHERE event_type = 'authentication'
            GROUP BY hostname, username
            HAVING cnt > ?
            ORDER BY cnt DESC
            LIMIT 100
        """,
        param_keys=["threshold"],
    ),
    "ioc_search": HuntTemplate(
        name="ioc_search",
        description="Search for a specific IOC value across all telemetry fields",
        sql="""
            SELECT event_id, timestamp, hostname, username, process_name,
                   src_ip, dst_ip, domain, file_hash_sha256, event_type, severity
            FROM normalized_events
            WHERE hostname ILIKE ?
               OR username ILIKE ?
               OR dst_ip = ?
               OR src_ip = ?
               OR domain ILIKE ?
               OR file_hash_sha256 = ?
            ORDER BY timestamp DESC
            LIMIT 500
        """,
        param_keys=["ioc_value"],
    ),
}


async def execute_hunt(duckdb_store, template_name: str, params: dict) -> list[dict]:
    """Execute a named hunt template against normalized_events. Returns list[dict]."""
    tmpl = HUNT_TEMPLATES.get(template_name)
    if tmpl is None:
        raise ValueError(
            f"Unknown hunt template: {template_name!r}. "
            f"Available: {list(HUNT_TEMPLATES)}"
        )

    # Build positional param list from params dict
    if template_name == "ioc_search":
        ioc = params.get("ioc_value", "")
        # 6 bindings: hostname ILIKE, username ILIKE, dst_ip =, src_ip =, domain ILIKE, file_hash =
        param_list: list | None = [f"%{ioc}%", f"%{ioc}%", ioc, ioc, f"%{ioc}%", ioc]
    elif template_name == "unusual_auth":
        param_list = [int(params.get("threshold", 10))]
    elif template_name == "suspicious_ip_comms":
        param_list = [params.get("dst_ip", "")]
    else:
        # powershell_children has no params
        param_list = None

    return await duckdb_store.fetch_df(tmpl.sql, param_list)
