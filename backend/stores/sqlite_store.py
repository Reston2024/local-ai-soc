"""
SQLite store for graph entities, edges, detections, and cases.

Uses WAL journal mode for better concurrent read performance.
All operations are synchronous (sqlite3 module) and should be wrapped in
asyncio.to_thread() when called from async route handlers.

Schema design:
- entities: nodes in the investigation graph (host, user, process, file, …)
- edges:    directed relationships between entities
- detections: correlated alert records produced by the detection engine
- cases:    investigation case containers grouping entities and detections
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from backend.core.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS cases (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entities (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    name        TEXT NOT NULL,
    attributes  TEXT,          -- JSON blob
    case_id     TEXT,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases (id)
);

CREATE TABLE IF NOT EXISTS edges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    edge_type   TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    properties  TEXT,          -- JSON blob
    created_at  TEXT NOT NULL,
    UNIQUE (source_id, edge_type, target_id)
);

CREATE TABLE IF NOT EXISTS detections (
    id                  TEXT PRIMARY KEY,
    rule_id             TEXT,
    rule_name           TEXT,
    severity            TEXT,
    matched_event_ids   TEXT,  -- JSON array of event_id strings
    attack_technique    TEXT,
    attack_tactic       TEXT,
    explanation         TEXT,
    case_id             TEXT,
    created_at          TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases (id)
);

CREATE INDEX IF NOT EXISTS idx_entities_type    ON entities (type);
CREATE INDEX IF NOT EXISTS idx_entities_case_id ON entities (case_id);
CREATE INDEX IF NOT EXISTS idx_edges_source     ON edges (source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target     ON edges (target_id);
CREATE INDEX IF NOT EXISTS idx_detections_case  ON detections (case_id);
CREATE INDEX IF NOT EXISTS idx_detections_rule  ON detections (rule_id);

CREATE TABLE IF NOT EXISTS investigation_cases (
    case_id         TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    description     TEXT DEFAULT '',
    case_status     TEXT NOT NULL DEFAULT 'open',
    related_alerts  TEXT DEFAULT '[]',
    related_entities TEXT DEFAULT '[]',
    timeline_events TEXT DEFAULT '[]',
    analyst_notes   TEXT DEFAULT '',
    tags            TEXT DEFAULT '[]',
    artifacts       TEXT DEFAULT '[]',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS case_artifacts (
    artifact_id     TEXT PRIMARY KEY,
    case_id         TEXT NOT NULL,
    filename        TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    file_size       INTEGER,
    mime_type       TEXT,
    description     TEXT DEFAULT '',
    created_at      TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES investigation_cases (case_id)
);

CREATE TABLE IF NOT EXISTS case_tags (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id         TEXT NOT NULL,
    tag             TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    UNIQUE(case_id, tag),
    FOREIGN KEY (case_id) REFERENCES investigation_cases (case_id)
);

CREATE INDEX IF NOT EXISTS idx_inv_cases_status ON investigation_cases (case_status);
CREATE INDEX IF NOT EXISTS idx_artifacts_case   ON case_artifacts (case_id);
CREATE INDEX IF NOT EXISTS idx_tags_case        ON case_tags (case_id);

CREATE TABLE IF NOT EXISTS saved_investigations (
    id              TEXT PRIMARY KEY,
    detection_id    TEXT,
    graph_snapshot  TEXT NOT NULL,
    metadata        TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_saved_inv_detection ON saved_investigations (detection_id);
"""


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class SQLiteStore:
    """
    Manages an SQLite database for the investigation graph.

    Provides synchronous helper methods that are safe to call from
    asyncio.to_thread().
    """

    def __init__(self, data_dir: str) -> None:
        db_dir = Path(data_dir)
        db_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = str(db_dir / "graph.db")

        # check_same_thread=False is required when sharing the connection
        # across threads (asyncio.to_thread creates a thread-pool thread).
        # We serialize writes ourselves via asyncio.to_thread wrapping.
        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self._conn.row_factory = sqlite3.Row

        # Apply schema
        self._conn.executescript(_DDL)
        self._conn.commit()

        # Backward-compatible migration: add risk_score to detections if absent
        try:
            self._conn.execute(
                "ALTER TABLE detections ADD COLUMN risk_score INTEGER DEFAULT 0"
            )
            self._conn.commit()
        except Exception:
            pass  # column already exists — idempotent

        log.info("SQLite store initialised", db_path=self._db_path)

    # ------------------------------------------------------------------
    # Case management
    # ------------------------------------------------------------------

    def create_case(
        self,
        name: str,
        description: str = "",
        case_id: Optional[str] = None,
    ) -> str:
        """Create a new investigation case and return its ID."""
        cid = case_id or str(uuid4())
        self._conn.execute(
            """
            INSERT OR IGNORE INTO cases (id, name, description, status, created_at)
            VALUES (?, ?, ?, 'active', ?)
            """,
            (cid, name, description, _now_iso()),
        )
        self._conn.commit()
        log.debug("Case created", case_id=cid, name=name)
        return cid

    def get_case(self, case_id: str) -> Optional[dict[str, Any]]:
        """Return a case record as a dict, or None if not found."""
        row = self._conn.execute(
            "SELECT * FROM cases WHERE id = ?", (case_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_cases(self, status: Optional[str] = None) -> list[dict[str, Any]]:
        """List cases, optionally filtered by status."""
        if status:
            rows = self._conn.execute(
                "SELECT * FROM cases WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM cases ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Entity management
    # ------------------------------------------------------------------

    def upsert_entity(
        self,
        entity_id: str,
        entity_type: str,
        name: str,
        attributes: Optional[dict[str, Any]] = None,
        case_id: Optional[str] = None,
    ) -> None:
        """
        Insert or replace an entity node.

        Args:
            entity_id:   Unique identifier (e.g. SHA256 of type+name).
            entity_type: One of: host, user, process, file, network, domain,
                         ip, detection, evidence, case, technique.
            name:        Human-readable label.
            attributes:  Arbitrary metadata stored as JSON.
            case_id:     Associated investigation case.
        """
        attrs_json = json.dumps(attributes) if attributes else None
        self._conn.execute(
            """
            INSERT OR REPLACE INTO entities
                (id, type, name, attributes, case_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (entity_id, entity_type, name, attrs_json, case_id, _now_iso()),
        )
        self._conn.commit()

    def get_entity(self, entity_id: str) -> Optional[dict[str, Any]]:
        """Return a single entity by ID, with attributes deserialized."""
        row = self._conn.execute(
            "SELECT * FROM entities WHERE id = ?", (entity_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("attributes"):
            try:
                d["attributes"] = json.loads(d["attributes"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d

    def get_entities_by_case(self, case_id: str) -> list[dict[str, Any]]:
        """Return all entities for a given case."""
        rows = self._conn.execute(
            "SELECT * FROM entities WHERE case_id = ? ORDER BY type, name",
            (case_id,),
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if d.get("attributes"):
                try:
                    d["attributes"] = json.loads(d["attributes"])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(d)
        return result

    # ------------------------------------------------------------------
    # Edge management
    # ------------------------------------------------------------------

    def insert_edge(
        self,
        source_type: str,
        source_id: str,
        edge_type: str,
        target_type: str,
        target_id: str,
        properties: Optional[dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        Insert a directed edge between two entities.

        Silently ignores duplicate edges (same source_id, edge_type, target_id).

        Returns:
            The row ID of the inserted edge, or None if it already existed.
        """
        props_json = json.dumps(properties) if properties else None
        cursor = self._conn.execute(
            """
            INSERT OR IGNORE INTO edges
                (source_type, source_id, edge_type, target_type, target_id,
                 properties, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (source_type, source_id, edge_type, target_type, target_id,
             props_json, _now_iso()),
        )
        self._conn.commit()
        return cursor.lastrowid if cursor.rowcount else None

    def get_edges_from(
        self, entity_id: str, depth: int = 2
    ) -> list[dict[str, Any]]:
        """
        Retrieve all edges reachable from entity_id up to given depth.

        Uses a recursive CTE for multi-hop traversal.

        Args:
            entity_id: Starting node ID.
            depth:     Maximum hop count (1 = direct neighbours only).

        Returns:
            List of edge dicts, each containing source_id, edge_type,
            target_id, source_type, target_type, properties.
        """
        sql = """
        WITH RECURSIVE traverse(source_id, edge_type, target_id,
                                 source_type, target_type, properties,
                                 created_at, hops) AS (
            -- Anchor: direct edges from the start node
            SELECT source_id, edge_type, target_id,
                   source_type, target_type, properties, created_at, 1
            FROM edges
            WHERE source_id = ?

            UNION ALL

            -- Recursive: follow edges from newly discovered nodes
            SELECT e.source_id, e.edge_type, e.target_id,
                   e.source_type, e.target_type, e.properties, e.created_at,
                   t.hops + 1
            FROM edges e
            JOIN traverse t ON e.source_id = t.target_id
            WHERE t.hops < ?
        )
        SELECT DISTINCT source_id, edge_type, target_id,
                        source_type, target_type, properties, created_at
        FROM traverse
        ORDER BY created_at
        """
        rows = self._conn.execute(sql, (entity_id, depth)).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if d.get("properties"):
                try:
                    d["properties"] = json.loads(d["properties"])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(d)
        return result

    def get_edges_to(self, entity_id: str) -> list[dict[str, Any]]:
        """
        Return all edges that point TO entity_id (reverse lookup).

        Args:
            entity_id: Target node ID.

        Returns:
            List of edge dicts.
        """
        rows = self._conn.execute(
            """
            SELECT source_id, edge_type, target_id,
                   source_type, target_type, properties, created_at
            FROM edges
            WHERE target_id = ?
            ORDER BY created_at
            """,
            (entity_id,),
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if d.get("properties"):
                try:
                    d["properties"] = json.loads(d["properties"])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(d)
        return result

    def get_neighbours(
        self, entity_id: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Return (outbound_edges, inbound_edges) for entity_id."""
        outbound = self._conn.execute(
            "SELECT * FROM edges WHERE source_id = ?", (entity_id,)
        ).fetchall()
        inbound = self._conn.execute(
            "SELECT * FROM edges WHERE target_id = ?", (entity_id,)
        ).fetchall()
        return [dict(r) for r in outbound], [dict(r) for r in inbound]

    # ------------------------------------------------------------------
    # Detection management
    # ------------------------------------------------------------------

    def insert_detection(
        self,
        detection_id: str,
        rule_id: str,
        rule_name: str,
        severity: str,
        matched_event_ids: list[str],
        attack_technique: Optional[str] = None,
        attack_tactic: Optional[str] = None,
        explanation: Optional[str] = None,
        case_id: Optional[str] = None,
    ) -> None:
        """
        Insert a detection record.

        Args:
            detection_id:       Unique detection ID (UUID recommended).
            rule_id:            Sigma rule ID or custom rule identifier.
            rule_name:          Human-readable rule name.
            severity:           critical / high / medium / low / informational.
            matched_event_ids:  event_id values from normalized_events.
            attack_technique:   MITRE ATT&CK technique (e.g. T1059.001).
            attack_tactic:      MITRE ATT&CK tactic name.
            explanation:        LLM-generated or rule-derived explanation text.
            case_id:            Associated case.
        """
        self._conn.execute(
            """
            INSERT OR REPLACE INTO detections
                (id, rule_id, rule_name, severity, matched_event_ids,
                 attack_technique, attack_tactic, explanation, case_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                detection_id, rule_id, rule_name, severity,
                json.dumps(matched_event_ids),
                attack_technique, attack_tactic, explanation, case_id,
                _now_iso(),
            ),
        )
        self._conn.commit()
        log.debug(
            "Detection inserted",
            detection_id=detection_id,
            rule=rule_name,
            severity=severity,
        )

    def get_detections_by_case(self, case_id: str) -> list[dict[str, Any]]:
        """Return all detections for a given case."""
        rows = self._conn.execute(
            "SELECT * FROM detections WHERE case_id = ? ORDER BY created_at DESC",
            (case_id,),
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if d.get("matched_event_ids"):
                try:
                    d["matched_event_ids"] = json.loads(d["matched_event_ids"])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(d)
        return result

    def get_detection(self, detection_id: str) -> Optional[dict[str, Any]]:
        """Return a single detection by ID."""
        row = self._conn.execute(
            "SELECT * FROM detections WHERE id = ?", (detection_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("matched_event_ids"):
            try:
                d["matched_event_ids"] = json.loads(d["matched_event_ids"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> dict[str, Any]:
        """Return basic health / version info."""
        row = self._conn.execute("PRAGMA user_version").fetchone()
        entity_count = self._conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        edge_count = self._conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        detection_count = self._conn.execute("SELECT COUNT(*) FROM detections").fetchone()[0]
        return {
            "status": "ok",
            "user_version": row[0] if row else 0,
            "entity_count": entity_count,
            "edge_count": edge_count,
            "detection_count": detection_count,
        }

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Investigation case management (stubs — Phase 7 Plan 01 will implement)
    # ------------------------------------------------------------------

    def create_investigation_case(
        self,
        title: str,
        description: str = "",
        case_id: Optional[str] = None,
    ) -> str:
        """Create a new investigation case and return its ID."""
        cid = case_id or str(uuid4())
        now = _now_iso()
        self._conn.execute(
            """
            INSERT OR IGNORE INTO investigation_cases
                (case_id, title, description, case_status,
                 related_alerts, related_entities, timeline_events,
                 analyst_notes, tags, artifacts, created_at, updated_at)
            VALUES (?, ?, ?, 'open', ?, ?, ?, '', ?, ?, ?, ?)
            """,
            (
                cid, title, description,
                json.dumps([]), json.dumps([]), json.dumps([]),
                json.dumps([]), json.dumps([]),
                now, now,
            ),
        )
        self._conn.commit()
        log.debug("Investigation case created", case_id=cid, title=title)
        return cid

    def get_investigation_case(self, case_id: str) -> Optional[dict[str, Any]]:
        """Return an investigation case record as a dict, or None if not found."""
        row = self._conn.execute(
            "SELECT * FROM investigation_cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        if not row:
            return None
        return self._parse_investigation_case(dict(row))

    def list_investigation_cases(self, status: Optional[str] = None) -> list[dict[str, Any]]:
        """List investigation cases, optionally filtered by status."""
        if status:
            rows = self._conn.execute(
                "SELECT * FROM investigation_cases WHERE case_status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM investigation_cases ORDER BY created_at DESC"
            ).fetchall()
        return [self._parse_investigation_case(dict(r)) for r in rows]

    def update_investigation_case(self, case_id: str, updates: dict) -> None:
        """Update fields of an investigation case (partial update)."""
        _ARRAY_FIELDS = {
            "related_alerts", "related_entities", "timeline_events", "tags", "artifacts"
        }
        serialized: dict[str, Any] = {}
        for k, v in updates.items():
            if k in _ARRAY_FIELDS and isinstance(v, list):
                serialized[k] = json.dumps(v)
            else:
                serialized[k] = v

        set_clause = ", ".join(f"{k} = ?" for k in serialized)
        values = list(serialized.values())
        values.append(_now_iso())  # updated_at
        values.append(case_id)

        self._conn.execute(
            f"UPDATE investigation_cases SET {set_clause}, updated_at = ? WHERE case_id = ?",
            values,
        )
        self._conn.commit()

    def insert_artifact(
        self,
        artifact_id: str,
        case_id: str,
        filename: str,
        file_path: str,
        file_size: Optional[int] = None,
        mime_type: Optional[str] = None,
        description: str = "",
    ) -> None:
        """Insert an artifact record linked to an investigation case."""
        # Normalize path separators to forward slashes
        normalized_path = str(file_path).replace("\\", "/")
        self._conn.execute(
            """
            INSERT OR IGNORE INTO case_artifacts
                (artifact_id, case_id, filename, file_path, file_size,
                 mime_type, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id, case_id, filename, normalized_path,
                file_size, mime_type, description, _now_iso(),
            ),
        )
        self._conn.commit()

    def get_artifacts_by_case(self, case_id: str) -> list[dict[str, Any]]:
        """Return all artifact records for a given investigation case."""
        rows = self._conn.execute(
            "SELECT * FROM case_artifacts WHERE case_id = ? ORDER BY created_at DESC",
            (case_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _parse_investigation_case(d: dict[str, Any]) -> dict[str, Any]:
        """Parse JSON array fields in an investigation case dict."""
        _ARRAY_FIELDS = [
            "related_alerts", "related_entities", "timeline_events", "tags", "artifacts"
        ]
        for field in _ARRAY_FIELDS:
            if field in d and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except json.JSONDecodeError:
                    d[field] = []
        return d

    # ------------------------------------------------------------------
    # Saved investigations (Phase 9)
    # ------------------------------------------------------------------

    def save_investigation(
        self,
        detection_id: str,
        graph_snapshot: dict,
        metadata: dict,
    ) -> str:
        """Persist an investigation snapshot. Returns the new investigation ID."""
        from uuid import uuid4 as _uuid4
        inv_id = _uuid4().hex
        created_at = _now_iso()
        self._conn.execute(
            "INSERT INTO saved_investigations "
            "(id, detection_id, graph_snapshot, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                inv_id,
                detection_id,
                json.dumps(graph_snapshot),
                json.dumps(metadata),
                created_at,
            ),
        )
        self._conn.commit()
        return inv_id

    def list_saved_investigations(self) -> list[dict[str, Any]]:
        """Return all saved investigation records (newest first)."""
        rows = self._conn.execute(
            "SELECT id, detection_id, metadata, created_at "
            "FROM saved_investigations ORDER BY created_at DESC"
        ).fetchall()
        return [
            {
                "id": row[0],
                "detection_id": row[1],
                "metadata": json.loads(row[2] or "{}"),
                "created_at": row[3],
            }
            for row in rows
        ]

    def get_saved_investigation(self, investigation_id: str) -> Optional[dict[str, Any]]:
        """Return a single saved investigation by ID, or None if not found."""
        row = self._conn.execute(
            "SELECT id, detection_id, graph_snapshot, metadata, created_at "
            "FROM saved_investigations WHERE id = ?",
            (investigation_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "detection_id": row[1],
            "graph_snapshot": json.loads(row[2] or "{}"),
            "metadata": json.loads(row[3] or "{}"),
            "created_at": row[4],
        }

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the SQLite connection."""
        try:
            self._conn.close()
            log.info("SQLite store closed")
        except Exception as exc:
            log.warning("Error closing SQLite connection", error=str(exc))
