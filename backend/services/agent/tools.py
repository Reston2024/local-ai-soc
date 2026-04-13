"""
backend/services/agent/tools.py

6 read-only investigation tools for the smolagents ToolCallingAgent.
Each tool wraps existing DuckDB/SQLite/Chroma stores via synchronous connections.

DESIGN NOTE: Tools are always synchronous (smolagents requirement).
They open fresh read-only DB connections per call — thread-safe, no async needed.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Optional

import duckdb
from smolagents import Tool


@contextmanager
def _sqlite_read(path: str):
    """Context manager for sqlite3 read connections — ensures close on Windows."""
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class QueryEventsTool(Tool):
    name = "query_events"
    description = (
        "Query normalized security events from the database. "
        "Filter by hostname, process name, or event type. "
        "Returns a summary of matching events with counts by type."
    )
    inputs = {
        "hostname": {
            "type": "string",
            "description": "Host to filter by (optional, use null to skip)",
            "nullable": True,
        },
        "process_name": {
            "type": "string",
            "description": "Process name to filter by (optional, use null to skip)",
            "nullable": True,
        },
        "event_type": {
            "type": "string",
            "description": "Event type filter: process_create, network_connection, auth_failure, etc. (optional)",
            "nullable": True,
        },
        "limit": {
            "type": "integer",
            "description": "Max events to return (default 20, max 50)",
            "nullable": True,
        },
    }
    output_type = "string"

    def __init__(self, db_path: str):
        super().__init__()
        self._db_path = db_path

    def forward(
        self,
        hostname: Optional[str] = None,
        process_name: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> str:
        limit = min(int(limit or 20), 50)
        conditions = []
        params = []
        if hostname:
            conditions.append("hostname = ?")
            params.append(hostname)
        if process_name:
            conditions.append("process_name ILIKE ?")
            params.append(f"%{process_name}%")
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"""
            SELECT event_type, COUNT(*) as cnt
            FROM normalized_events
            {where}
            GROUP BY event_type
            ORDER BY cnt DESC
            LIMIT {limit}
        """
        try:
            with duckdb.connect(self._db_path, read_only=True) as conn:
                conn.execute("SET enable_external_access = false")
                rows = conn.execute(sql, params).fetchall()
        except Exception as exc:
            return f"Query failed: {exc}"
        if not rows:
            filters = ", ".join(
                filter(
                    None,
                    [
                        f"hostname={hostname}" if hostname else "",
                        f"process={process_name}" if process_name else "",
                        f"type={event_type}" if event_type else "",
                    ],
                )
            )
            return f"No events found{' for ' + filters if filters else ''}."
        total = sum(r[1] for r in rows)
        breakdown = ", ".join(f"{r[0]}: {r[1]}" for r in rows)
        return f"{total} events found — {breakdown}"


class GetEntityProfileTool(Tool):
    name = "get_entity_profile"
    description = (
        "Get a behavioural profile for a host or user: total event count, "
        "unique destination IPs, anomaly score range, and most common process names."
    )
    inputs = {
        "hostname": {
            "type": "string",
            "description": "Hostname to profile (optional)",
            "nullable": True,
        },
        "username": {
            "type": "string",
            "description": "Username to profile (optional)",
            "nullable": True,
        },
    }
    output_type = "string"

    def __init__(self, db_path: str):
        super().__init__()
        self._db_path = db_path

    def forward(
        self, hostname: Optional[str] = None, username: Optional[str] = None
    ) -> str:
        if not hostname and not username:
            return "Error: provide hostname or username to profile."
        conditions = []
        params = []
        if hostname:
            conditions.append("hostname = ?")
            params.append(hostname)
        if username:
            conditions.append("username = ?")
            params.append(username)
        where = "WHERE " + " AND ".join(conditions)
        try:
            with duckdb.connect(self._db_path, read_only=True) as conn:
                conn.execute("SET enable_external_access = false")
                count_row = conn.execute(
                    f"SELECT COUNT(*) FROM normalized_events {where}", params
                ).fetchone()
                total = count_row[0] if count_row else 0
                ip_row = conn.execute(
                    f"SELECT COUNT(DISTINCT dst_ip) FROM normalized_events {where} AND dst_ip IS NOT NULL",
                    params,
                ).fetchone()
                unique_ips = ip_row[0] if ip_row else 0
                proc_rows = conn.execute(
                    f"""SELECT process_name, COUNT(*) as c FROM normalized_events
                        {where} AND process_name IS NOT NULL
                        GROUP BY process_name ORDER BY c DESC LIMIT 5""",
                    params,
                ).fetchall()
                score_row = conn.execute(
                    f"""SELECT MIN(anomaly_score), MAX(anomaly_score), AVG(anomaly_score)
                        FROM normalized_events {where} AND anomaly_score IS NOT NULL""",
                    params,
                ).fetchone()
        except Exception as exc:
            return f"Profile query failed: {exc}"
        entity = hostname or username
        if total == 0:
            return f"No events found for {entity}."
        procs = ", ".join(r[0] for r in proc_rows) if proc_rows else "none"
        score_str = ""
        if score_row and score_row[0] is not None:
            score_str = (
                f"; anomaly scores min={score_row[0]:.2f} "
                f"max={score_row[1]:.2f} avg={score_row[2]:.2f}"
            )
        return (
            f"Entity profile for {entity}: {total} total events, "
            f"{unique_ips} unique destination IPs, "
            f"top processes: {procs}{score_str}."
        )


class EnrichIpTool(Tool):
    name = "enrich_ip"
    description = (
        "Enrich an IP address with OSINT data: country, organization, "
        "proxy/hosting flags, and ipsum threat tier if available."
    )
    inputs = {
        "ip": {"type": "string", "description": "IPv4 address to enrich"},
    }
    output_type = "string"

    def __init__(self, sqlite_path: str):
        super().__init__()
        self._sqlite_path = sqlite_path

    def forward(self, ip: str) -> str:
        if not ip:
            return "Error: ip is required."
        try:
            with _sqlite_read(self._sqlite_path) as conn:
                row = conn.execute(
                    "SELECT * FROM osint_cache WHERE ip = ? LIMIT 1", (ip,)
                ).fetchone()
        except Exception:
            return f"No OSINT data cached for {ip} — not yet enriched."
        if not row:
            return f"No OSINT data cached for {ip} — not yet enriched."
        # The osint_cache stores data as result_json blob; parse it for display
        try:
            keys = row.keys()
            result_json = row["result_json"] if "result_json" in keys else None
            data: dict = json.loads(result_json) if result_json else {}
        except Exception:
            data = {}
        parts = [f"IP {ip}:"]
        country = data.get("country") or data.get("countryCode")
        if country:
            parts.append(f"country={country}")
        org = data.get("org") or data.get("as") or data.get("isp")
        if org:
            parts.append(f"org={org}")
        # Check classification columns if present (Phase 41 additions)
        row_keys = list(row.keys()) if row else []
        proxy = row["is_proxy"] if "is_proxy" in row_keys else data.get("proxy")
        hosting = (
            row["is_datacenter"] if "is_datacenter" in row_keys else data.get("hosting")
        )
        is_tor = row["is_tor"] if "is_tor" in row_keys else data.get("tor")
        flags = []
        if proxy:
            flags.append("proxy=YES")
        if hosting:
            flags.append("hosting=YES")
        if is_tor:
            flags.append("tor=YES")
        if flags:
            parts.append(", ".join(flags))
        ipsum_tier = row["ipsum_tier"] if "ipsum_tier" in row_keys else None
        if ipsum_tier:
            parts.append(f"ipsum_threat_tier={ipsum_tier}")
        return " | ".join(parts)


class SearchSigmaMatchesTool(Tool):
    name = "search_sigma_matches"
    description = (
        "Search for recent Sigma rule detection matches for a host or entity. "
        "Returns detection rule IDs, severities, and MITRE techniques from the last 24 hours."
    )
    inputs = {
        "hostname": {
            "type": "string",
            "description": "Hostname to search detections for (optional)",
            "nullable": True,
        },
        "limit": {
            "type": "integer",
            "description": "Max detections to return (default 10)",
            "nullable": True,
        },
    }
    output_type = "string"

    def __init__(self, sqlite_path: str):
        super().__init__()
        self._sqlite_path = sqlite_path

    def forward(self, hostname: Optional[str] = None, limit: Optional[int] = None) -> str:
        limit = min(int(limit or 10), 20)
        try:
            with _sqlite_read(self._sqlite_path) as conn:
                rows = conn.execute(
                    """SELECT rule_id, severity, attack_technique, id
                       FROM detections
                       WHERE created_at >= datetime('now', '-24 hours')
                       ORDER BY created_at DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
        except Exception as exc:
            return f"No Sigma detections found — {exc}"
        if not rows:
            target = f" for {hostname}" if hostname else ""
            return f"No Sigma detections found{target} in the last 24 hours."
        lines = []
        for r in rows:
            technique = r["attack_technique"] or "unknown technique"
            lines.append(
                f"  * {r['rule_id']} (severity={r['severity']}, technique={technique})"
            )
        header = f"{len(rows)} Sigma detection(s):\n"
        return header + "\n".join(lines)


class GetGraphNeighborsTool(Tool):
    name = "get_graph_neighbors"
    description = (
        "Get graph neighbors (connected entities) for a host, IP, or user. "
        "Shows lateral movement paths and relationship types (network_connection, process_spawn, etc)."
    )
    inputs = {
        "entity_id": {
            "type": "string",
            "description": "Entity value to look up (hostname, IP address, or username)",
        },
        "limit": {
            "type": "integer",
            "description": "Max neighbors to return (default 10)",
            "nullable": True,
        },
    }
    output_type = "string"

    def __init__(self, sqlite_path: str):
        super().__init__()
        self._sqlite_path = sqlite_path

    def forward(self, entity_id: str, limit: Optional[int] = None) -> str:
        if not entity_id:
            return "Error: entity_id is required."
        limit = min(int(limit or 10), 20)
        try:
            with _sqlite_read(self._sqlite_path) as conn:
                entity_row = conn.execute(
                    "SELECT id, type FROM entities WHERE name = ? LIMIT 1",
                    (entity_id,),
                ).fetchone()
                if not entity_row:
                    return f"Entity '{entity_id}' not found in graph."
                eid = entity_row["id"]
                entity_type = entity_row["type"]
                neighbors = conn.execute(
                    """SELECT e.type, e.name, ed.edge_type
                       FROM edges ed
                       JOIN entities e ON e.id = ed.target_id
                       WHERE ed.source_id = ?
                       ORDER BY ed.id DESC LIMIT ?""",
                    (eid, limit),
                ).fetchall()
        except Exception as exc:
            return f"Graph neighbor query failed: {exc}"
        if not neighbors:
            return f"No graph neighbors found for '{entity_id}'."
        lines = [f"Graph neighbors for {entity_id} ({entity_type}):"]
        for n in neighbors:
            lines.append(
                f"  -> {n['name']} ({n['type']}) via {n['edge_type']}"
            )
        return "\n".join(lines)


class SearchSimilarIncidentsTool(Tool):
    name = "search_similar_incidents"
    description = (
        "Search for previously confirmed TP or FP incidents similar to this detection. "
        "Returns top matches with verdict labels and similarity scores."
    )
    inputs = {
        "detection_id": {
            "type": "string",
            "description": "Current detection ID (for context)",
        },
        "narrative": {
            "type": "string",
            "description": "Text description of the detection to search against",
        },
    }
    output_type = "string"

    def __init__(self, chroma_path: str):
        super().__init__()
        self._chroma_path = chroma_path

    def forward(self, detection_id: str, narrative: str) -> str:
        if not narrative:
            return "Error: narrative text is required for similarity search."
        try:
            import chromadb

            client = chromadb.PersistentClient(path=self._chroma_path)
            try:
                collection = client.get_collection("feedback_verdicts")
                results = collection.query(
                    query_texts=[narrative],
                    n_results=3,
                    include=["documents", "metadatas", "distances"],
                )
                docs = results.get("documents", [[]])[0]
                metas = results.get("metadatas", [[]])[0]
                distances = results.get("distances", [[]])[0]
            except Exception:
                return (
                    "No confirmed incidents in the feedback database yet"
                    " — this is the first investigation."
                )
            finally:
                # Release chromadb file handles (important on Windows)
                try:
                    client._system.stop()
                except Exception:
                    pass
        except Exception as exc:
            return f"Similar incident search failed: {exc}"
        if not docs:
            return "No similar confirmed incidents found."
        lines = [f"Top {len(docs)} similar confirmed incident(s):"]
        for i, (doc, meta, dist) in enumerate(zip(docs, metas, distances), 1):
            verdict = meta.get("verdict", "unknown") if meta else "unknown"
            similarity = round((1 - dist) * 100, 1) if dist is not None else "?"
            lines.append(
                f"  {i}. [{verdict}] similarity={similarity}% — {str(doc)[:120]}"
            )
        return "\n".join(lines)
