"""
Backfill graph entities and edges from existing DuckDB normalized_events.

Usage:
    uv run python scripts/backfill_graph.py [--limit N] [--source-type TYPE]

Reads normalized events from DuckDB, runs them through entity_extractor,
and upserts entities/edges into SQLite graph.db.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import duckdb
from backend.core.config import settings
from backend.stores.sqlite_store import SQLiteStore
from backend.models.event import NormalizedEvent
from ingestion.entity_extractor import extract_entities_and_edges, extract_perimeter_entities


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill graph from DuckDB events")
    parser.add_argument("--limit", type=int, default=50_000, help="Max events to process")
    parser.add_argument("--source-type", default=None, help="Filter by source_type (e.g. suricata_eve)")
    args = parser.parse_args()

    db_path = str(Path(settings.DATA_DIR) / "events.duckdb")
    sqlite_path = str(Path(settings.DATA_DIR) / "graph.db")

    print(f"DuckDB: {db_path}")
    print(f"SQLite: {sqlite_path}")

    # Connect to DuckDB (read-only secondary connection)
    conn = duckdb.connect(db_path, read_only=True)
    conn.execute("SET enable_external_access = false")

    sql = """
        SELECT event_id, timestamp, source_type, event_type,
               hostname, username, user_domain,
               process_name, process_id, process_executable,
               parent_process_id, parent_process_name,
               command_line, file_path, file_hash_sha256,
               src_ip, src_port, dst_ip, dst_port,
               network_protocol, network_direction,
               domain, severity, attack_technique, attack_tactic,
               case_id, tags, event_outcome
        FROM normalized_events
    """
    params: list = []
    if args.source_type:
        sql += " WHERE source_type = ?"
        params.append(args.source_type)
    sql += f" ORDER BY timestamp DESC LIMIT {args.limit}"

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    print(f"Loaded {len(rows)} events from DuckDB")

    sqlite = SQLiteStore(sqlite_path)

    cols = [
        "event_id", "timestamp", "source_type", "event_type",
        "hostname", "username", "user_domain",
        "process_name", "process_id", "process_executable",
        "parent_process_id", "parent_process_name",
        "command_line", "file_path", "file_hash_sha256",
        "src_ip", "src_port", "dst_ip", "dst_port",
        "network_protocol", "network_direction",
        "domain", "severity", "attack_technique", "attack_tactic",
        "case_id", "tags", "event_outcome",
    ]

    entity_count = 0
    edge_count = 0

    for i, row in enumerate(rows):
        d = dict(zip(cols, row))

        try:
            ev = NormalizedEvent(**d)
        except Exception:
            continue

        entities, edges = extract_entities_and_edges(ev)
        perimeter_entities, perimeter_edges = extract_perimeter_entities(ev)
        all_entities = entities + perimeter_entities
        all_edges = edges + perimeter_edges

        for ent in all_entities:
            sqlite.upsert_entity(
                ent["id"], ent["type"], ent["name"],
                ent.get("attributes", {}), ent.get("case_id"),
            )
            entity_count += 1

        for edge in all_edges:
            sqlite.insert_edge(
                edge["source_type"], edge["source_id"],
                edge["edge_type"],
                edge["target_type"], edge["target_id"],
                edge.get("properties", {}),
            )
            edge_count += 1

        if (i + 1) % 1000 == 0:
            print(f"  Processed {i+1}/{len(rows)} events "
                  f"({entity_count} entity upserts, {edge_count} edge inserts)…")

    print(f"\nDone. {entity_count} entity upserts, {edge_count} edge inserts.")

    # Final counts
    import sqlite3
    sc = sqlite3.connect(sqlite_path)
    ent_total = sc.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    edge_total = sc.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    print(f"Graph totals — entities: {ent_total}, edges: {edge_total}")
    sc.close()


if __name__ == "__main__":
    main()
