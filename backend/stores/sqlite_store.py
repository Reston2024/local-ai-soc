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

CREATE TABLE IF NOT EXISTS chat_messages (
    id               TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    role             TEXT NOT NULL,
    content          TEXT NOT NULL,
    created_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_inv ON chat_messages (investigation_id);

CREATE TABLE IF NOT EXISTS playbooks (
    playbook_id         TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    description         TEXT DEFAULT '',
    trigger_conditions  TEXT NOT NULL DEFAULT '[]',  -- JSON array of strings
    steps               TEXT NOT NULL DEFAULT '[]',  -- JSON array of step dicts
    version             TEXT NOT NULL DEFAULT '1.0',
    is_builtin          INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS playbook_runs (
    run_id              TEXT PRIMARY KEY,
    playbook_id         TEXT NOT NULL,
    investigation_id    TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'running',
    started_at          TEXT NOT NULL,
    completed_at        TEXT,
    steps_completed     TEXT NOT NULL DEFAULT '[]',  -- JSON array of step result dicts
    analyst_notes       TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (playbook_id) REFERENCES playbooks (playbook_id)
);

CREATE INDEX IF NOT EXISTS idx_playbook_runs_pb   ON playbook_runs (playbook_id);
CREATE INDEX IF NOT EXISTS idx_playbook_runs_inv  ON playbook_runs (investigation_id);
CREATE INDEX IF NOT EXISTS idx_playbooks_builtin  ON playbooks (is_builtin);

CREATE TABLE IF NOT EXISTS reports (
    id              TEXT PRIMARY KEY,
    type            TEXT NOT NULL,
    title           TEXT NOT NULL,
    subject_id      TEXT,
    period_start    TEXT,
    period_end      TEXT,
    content_json    TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_type       ON reports (type);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports (created_at);

CREATE TABLE IF NOT EXISTS operators (
    operator_id     TEXT PRIMARY KEY,
    username        TEXT NOT NULL UNIQUE,
    hashed_key      TEXT NOT NULL,
    key_prefix      TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'analyst',
    totp_secret     TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    last_seen_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_operators_username  ON operators (username);
CREATE INDEX IF NOT EXISTS idx_operators_key_prefix ON operators (key_prefix);

CREATE TABLE IF NOT EXISTS ingest_provenance (
    prov_id         TEXT PRIMARY KEY,
    raw_sha256      TEXT NOT NULL,
    source_file     TEXT NOT NULL,
    parser_name     TEXT NOT NULL,
    parser_version  TEXT,
    operator_id     TEXT,
    ingested_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_provenance_events (
    prov_id     TEXT NOT NULL,
    event_id    TEXT NOT NULL,
    PRIMARY KEY (prov_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_ingest_prov_event ON ingest_provenance_events (event_id);

CREATE TABLE IF NOT EXISTS detection_provenance (
    prov_id             TEXT PRIMARY KEY,
    detection_id        TEXT NOT NULL,
    rule_id             TEXT,
    rule_title          TEXT,
    rule_sha256         TEXT NOT NULL,
    pysigma_version     TEXT NOT NULL,
    field_map_version   TEXT NOT NULL,
    operator_id         TEXT,
    detected_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_det_prov_detection ON detection_provenance (detection_id);

CREATE TABLE IF NOT EXISTS llm_audit_provenance (
    audit_id                TEXT PRIMARY KEY,
    model_id                TEXT NOT NULL,
    prompt_template_name    TEXT,
    prompt_template_sha256  TEXT,
    response_sha256         TEXT,
    operator_id             TEXT,
    grounding_event_ids     TEXT NOT NULL DEFAULT '[]',
    confidence_score        REAL,
    created_at              TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_prov_created ON llm_audit_provenance (created_at);

CREATE TABLE IF NOT EXISTS playbook_run_provenance (
    prov_id                 TEXT PRIMARY KEY,
    run_id                  TEXT NOT NULL,
    playbook_id             TEXT,
    playbook_file_sha256    TEXT NOT NULL,
    playbook_version        TEXT,
    trigger_event_ids       TEXT NOT NULL DEFAULT '[]',
    operator_id_who_approved TEXT,
    created_at              TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pb_prov_run ON playbook_run_provenance (run_id);
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
        # Support ":memory:" for unit tests — skip directory creation.
        if data_dir == ":memory:":
            self._db_path = ":memory:"
        else:
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

        # Backward-compatible migration: add confidence_score to llm_audit_provenance if absent
        try:
            self._conn.execute(
                "ALTER TABLE llm_audit_provenance ADD COLUMN confidence_score REAL"
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
    # Chat messages (Phase 14 Plan 05 — AI Copilot)
    # ------------------------------------------------------------------

    def insert_chat_message(
        self,
        investigation_id: str,
        role: str,
        content: str,
    ) -> None:
        """Persist one chat turn to chat_messages."""
        from uuid import uuid4
        msg_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO chat_messages (id, investigation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (msg_id, investigation_id, role, content, now),
        )
        self._conn.commit()

    def get_chat_history(
        self, investigation_id: str, limit: int = 50
    ) -> list[dict]:
        """Return chat messages for an investigation, oldest first."""
        rows = self._conn.execute(
            "SELECT id, investigation_id, role, content, created_at FROM chat_messages WHERE investigation_id = ? ORDER BY created_at ASC LIMIT ?",
            (investigation_id, limit),
        ).fetchall()
        return [
            {"id": r[0], "investigation_id": r[1], "role": r[2], "content": r[3], "created_at": r[4]}
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Playbook management (Phase 17)
    # ------------------------------------------------------------------

    def create_playbook(self, data: dict) -> dict:
        """Insert a new playbook record and return it as a dict."""
        playbook_id = str(uuid4())
        now = _now_iso()
        trigger_conditions = json.dumps(data.get("trigger_conditions", []))
        steps = json.dumps(data.get("steps", []))
        is_builtin = 1 if data.get("is_builtin") else 0
        version = data.get("version", "1.0")
        name = data["name"]
        description = data.get("description", "")

        self._conn.execute(
            """
            INSERT INTO playbooks
                (playbook_id, name, description, trigger_conditions, steps,
                 version, is_builtin, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (playbook_id, name, description, trigger_conditions, steps,
             version, is_builtin, now),
        )
        self._conn.commit()
        log.debug("Playbook created", playbook_id=playbook_id, name=name)
        return self.get_playbook(playbook_id)  # type: ignore[return-value]

    def get_playbooks(self) -> list[dict]:
        """Return all playbooks with JSON fields deserialized."""
        rows = self._conn.execute(
            "SELECT * FROM playbooks ORDER BY created_at DESC"
        ).fetchall()
        return [self._parse_playbook(dict(r)) for r in rows]

    def get_playbook(self, playbook_id: str) -> dict | None:
        """Return a single playbook by primary key, or None if not found."""
        row = self._conn.execute(
            "SELECT * FROM playbooks WHERE playbook_id = ?", (playbook_id,)
        ).fetchone()
        if row is None:
            return None
        return self._parse_playbook(dict(row))

    def create_playbook_run(self, data: dict) -> dict:
        """Insert a new playbook run record and return it as a dict."""
        run_id = str(uuid4())
        now = _now_iso()
        self._conn.execute(
            """
            INSERT INTO playbook_runs
                (run_id, playbook_id, investigation_id, status,
                 started_at, completed_at, steps_completed, analyst_notes)
            VALUES (?, ?, ?, 'running', ?, NULL, '[]', '')
            """,
            (run_id, data["playbook_id"], data["investigation_id"], now),
        )
        self._conn.commit()
        log.debug(
            "Playbook run created",
            run_id=run_id,
            playbook_id=data["playbook_id"],
        )
        return self.get_playbook_run(run_id)  # type: ignore[return-value]

    def get_playbook_run(self, run_id: str) -> dict | None:
        """Return a single playbook run by primary key, or None if not found."""
        row = self._conn.execute(
            "SELECT * FROM playbook_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        return self._parse_playbook_run(dict(row))

    def get_playbook_runs(self, playbook_id: str) -> list[dict]:
        """Return all runs for a given playbook, newest first."""
        rows = self._conn.execute(
            "SELECT * FROM playbook_runs WHERE playbook_id = ? ORDER BY started_at DESC",
            (playbook_id,),
        ).fetchall()
        return [self._parse_playbook_run(dict(r)) for r in rows]

    def update_playbook_run(self, run_id: str, updates: dict) -> dict:
        """Update a playbook run's mutable fields and return the updated record."""
        _ALLOWED = {"status", "completed_at", "steps_completed", "analyst_notes"}
        set_parts: list[str] = []
        values: list[Any] = []

        for key, val in updates.items():
            if key not in _ALLOWED:
                continue
            if key == "steps_completed" and isinstance(val, list):
                set_parts.append(f"{key} = ?")
                values.append(json.dumps(val))
            else:
                set_parts.append(f"{key} = ?")
                values.append(val)

        if set_parts:
            values.append(run_id)
            self._conn.execute(
                f"UPDATE playbook_runs SET {', '.join(set_parts)} WHERE run_id = ?",
                values,
            )
            self._conn.commit()

        return self.get_playbook_run(run_id)  # type: ignore[return-value]

    @staticmethod
    def _parse_playbook(d: dict) -> dict:
        """Deserialize JSON fields in a playbook row dict."""
        for field in ("trigger_conditions", "steps"):
            if field in d and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
        return d

    @staticmethod
    def _parse_playbook_run(d: dict) -> dict:
        """Deserialize JSON fields in a playbook_run row dict."""
        if "steps_completed" in d and isinstance(d["steps_completed"], str):
            try:
                d["steps_completed"] = json.loads(d["steps_completed"])
            except (json.JSONDecodeError, TypeError):
                d["steps_completed"] = []
        return d

    # ------------------------------------------------------------------
    # MITRE ATT&CK analytics helpers (Phase 18 Plan 02)
    # ------------------------------------------------------------------

    def get_detection_techniques(self) -> list[dict]:
        """Return all detections with non-null attack_technique.

        Each dict has keys: attack_technique, attack_tactic.
        """
        rows = self._conn.execute(
            "SELECT attack_technique, attack_tactic FROM detections "
            "WHERE attack_technique IS NOT NULL AND attack_technique != ''"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_playbook_trigger_conditions(self) -> list[str]:
        """Return a flat list of all trigger_conditions JSON strings from all playbooks."""
        rows = self._conn.execute(
            "SELECT trigger_conditions FROM playbooks"
        ).fetchall()
        return [r["trigger_conditions"] for r in rows]

    # ------------------------------------------------------------------
    # KPI snapshot helpers (Phase 18 Plan 03)
    # ------------------------------------------------------------------

    def list_investigations(self) -> list[dict]:
        """Return minimal investigation_cases rows for count purposes."""
        rows = self._conn.execute(
            "SELECT case_id FROM investigation_cases"
        ).fetchall()
        return [dict(r) for r in rows]

    def list_detections(self) -> list[dict]:
        """Return minimal detections rows for count purposes."""
        rows = self._conn.execute(
            "SELECT id FROM detections"
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Report management (Phase 18)
    # ------------------------------------------------------------------

    def insert_report(self, data: dict) -> None:
        """Insert or replace a report record."""
        self._conn.execute(
            """
            INSERT OR REPLACE INTO reports
                (id, type, title, subject_id, period_start, period_end,
                 content_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["type"],
                data["title"],
                data.get("subject_id"),
                data.get("period_start"),
                data.get("period_end"),
                data.get("content_json", "{}"),
                data["created_at"],
            ),
        )
        self._conn.commit()
        log.debug("Report inserted", report_id=data["id"], report_type=data["type"])

    def list_reports(self) -> list[dict]:
        """Return all report records ordered by created_at DESC."""
        rows = self._conn.execute(
            "SELECT * FROM reports ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_report(self, report_id: str) -> Optional[dict]:
        """Return a single report by id, or None if not found."""
        row = self._conn.execute(
            "SELECT * FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Operator management (Phase 19)
    # ------------------------------------------------------------------

    def get_operator_by_prefix(self, prefix: str) -> Optional[dict]:
        """Return active operator whose key_prefix matches, or None."""
        row = self._conn.execute(
            "SELECT * FROM operators WHERE key_prefix = ? AND is_active = 1",
            (prefix,),
        ).fetchone()
        return dict(row) if row else None

    def create_operator(
        self,
        operator_id: str,
        username: str,
        hashed_key: str,
        key_prefix: str,
        role: str = "analyst",
    ) -> None:
        """Insert a new operator record."""
        self._conn.execute(
            """
            INSERT INTO operators
                (operator_id, username, hashed_key, key_prefix, role, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (operator_id, username, hashed_key, key_prefix, role, _now_iso()),
        )
        self._conn.commit()

    def list_operators(self) -> list[dict]:
        """Return all operators (safe fields only — no hashed_key)."""
        rows = self._conn.execute(
            "SELECT operator_id, username, role, is_active, created_at, last_seen_at FROM operators"
        ).fetchall()
        return [dict(r) for r in rows]

    def update_operator_key(
        self, operator_id: str, hashed_key: str, key_prefix: str
    ) -> None:
        """Replace the hashed key and prefix for a given operator."""
        self._conn.execute(
            "UPDATE operators SET hashed_key = ?, key_prefix = ? WHERE operator_id = ?",
            (hashed_key, key_prefix, operator_id),
        )
        self._conn.commit()

    def deactivate_operator(self, operator_id: str) -> None:
        """Set is_active = 0 for the given operator."""
        self._conn.execute(
            "UPDATE operators SET is_active = 0 WHERE operator_id = ?",
            (operator_id,),
        )
        self._conn.commit()

    def update_last_seen(self, operator_id: str) -> None:
        """Stamp last_seen_at with the current UTC timestamp."""
        self._conn.execute(
            "UPDATE operators SET last_seen_at = ? WHERE operator_id = ?",
            (_now_iso(), operator_id),
        )
        self._conn.commit()

    def set_totp_secret(self, operator_id: str, secret: str | None) -> None:
        """Set or clear the TOTP secret for the given operator.

        Pass secret=None to disable TOTP (clears the column).
        """
        self._conn.execute(
            "UPDATE operators SET totp_secret = ? WHERE operator_id = ?",
            (secret, operator_id),
        )
        self._conn.commit()

    def bootstrap_admin_if_empty(self, auth_token: str) -> None:
        """Seed a legacy 'admin' operator if the operators table is empty.

        Called once at startup.  Idempotent — no-op when operators already exist.
        The hashed_key is derived from auth_token so existing tokens continue to
        work transparently.
        """
        from backend.core.operator_utils import hash_api_key, key_prefix as _key_prefix

        count = self._conn.execute("SELECT COUNT(*) FROM operators").fetchone()[0]
        if count > 0:
            return

        import uuid
        oid = str(uuid.uuid4())
        hashed = hash_api_key(auth_token)
        prefix = _key_prefix(auth_token)
        self._conn.execute(
            """
            INSERT INTO operators
                (operator_id, username, hashed_key, key_prefix, role, is_active, created_at)
            VALUES (?, 'admin', ?, ?, 'admin', 1, ?)
            """,
            (oid, hashed, prefix, _now_iso()),
        )
        self._conn.commit()
        log.info("Bootstrapped legacy admin operator", operator_id=oid)

    # ------------------------------------------------------------------
    # Ingest provenance
    # ------------------------------------------------------------------

    def record_ingest_provenance(
        self,
        prov_id: str,
        raw_sha256: str,
        source_file: str,
        parser_name: str,
        event_ids: list[str],
        parser_version: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> None:
        """
        Write an ingest provenance record and its associated event-junction rows.

        Inserts into ingest_provenance and ingest_provenance_events in a single
        transaction.  Uses INSERT OR IGNORE so re-running is safe.

        Callers must wrap this in try/except — this method does NOT suppress
        exceptions itself.
        """
        self._conn.execute(
            """
            INSERT OR IGNORE INTO ingest_provenance
                (prov_id, raw_sha256, source_file, parser_name,
                 parser_version, operator_id, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prov_id,
                raw_sha256,
                source_file,
                parser_name,
                parser_version,
                operator_id,
                _now_iso(),
            ),
        )
        for event_id in event_ids:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO ingest_provenance_events (prov_id, event_id)
                VALUES (?, ?)
                """,
                (prov_id, event_id),
            )
        self._conn.commit()

    def get_ingest_provenance(self, event_id: str) -> Optional[dict[str, Any]]:
        """
        Return the ingest_provenance record for the given event_id, or None.

        Joins ingest_provenance_events to ingest_provenance on prov_id.
        """
        row = self._conn.execute(
            """
            SELECT ip.prov_id, ip.raw_sha256, ip.source_file, ip.parser_name,
                   ip.parser_version, ip.operator_id, ip.ingested_at
            FROM ingest_provenance_events ipe
            JOIN ingest_provenance ip ON ipe.prov_id = ip.prov_id
            WHERE ipe.event_id = ?
            LIMIT 1
            """,
            (event_id,),
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Detection provenance
    # ------------------------------------------------------------------

    def record_detection_provenance(
        self,
        prov_id: str,
        detection_id: str,
        rule_id: Optional[str],
        rule_title: Optional[str],
        rule_sha256: str,
        pysigma_version: str,
        field_map_version: str,
        operator_id: Optional[str] = None,
    ) -> None:
        """
        Insert a detection provenance row.

        Uses INSERT OR IGNORE so re-running is idempotent.
        Callers must wrap in try/except — this method does NOT suppress exceptions.
        """
        self._conn.execute(
            """
            INSERT OR IGNORE INTO detection_provenance
                (prov_id, detection_id, rule_id, rule_title,
                 rule_sha256, pysigma_version, field_map_version,
                 operator_id, detected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prov_id,
                detection_id,
                rule_id,
                rule_title,
                rule_sha256,
                pysigma_version,
                field_map_version,
                operator_id,
                _now_iso(),
            ),
        )
        self._conn.commit()

    def get_detection_provenance(self, detection_id: str) -> Optional[dict[str, Any]]:
        """Return the detection_provenance record for the given detection_id, or None."""
        row = self._conn.execute(
            "SELECT * FROM detection_provenance WHERE detection_id = ?",
            (detection_id,),
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # LLM audit provenance
    # ------------------------------------------------------------------

    def record_llm_provenance(
        self,
        audit_id: str,
        model_id: str,
        prompt_template_name: Optional[str],
        prompt_template_sha256: Optional[str],
        response_sha256: Optional[str],
        grounding_event_ids: list[str],
        operator_id: Optional[str] = None,
    ) -> None:
        """Insert one LLM audit provenance row.

        Uses INSERT OR IGNORE so duplicate audit_ids are silently discarded,
        preventing duplicate rows when called more than once for the same call.
        """
        grounding_json = json.dumps(grounding_event_ids)
        self._conn.execute(
            """INSERT OR IGNORE INTO llm_audit_provenance
               (audit_id, model_id, prompt_template_name, prompt_template_sha256,
                response_sha256, operator_id, grounding_event_ids, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                audit_id,
                model_id,
                prompt_template_name,
                prompt_template_sha256,
                response_sha256,
                operator_id,
                grounding_json,
                _now_iso(),
            ),
        )
        self._conn.commit()

    def get_llm_provenance(self, audit_id: str) -> Optional[dict[str, Any]]:
        """Return the llm_audit_provenance record for the given audit_id, or None.

        The grounding_event_ids field is returned as a parsed list[str].
        """
        row = self._conn.execute(
            "SELECT * FROM llm_audit_provenance WHERE audit_id = ?",
            (audit_id,),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["grounding_event_ids"] = json.loads(result["grounding_event_ids"])
        return result

    def update_confidence_score(self, audit_id: str, score: float) -> None:
        """Update the confidence_score for an existing llm_audit_provenance row."""
        self._conn.execute(
            "UPDATE llm_audit_provenance SET confidence_score = ? WHERE audit_id = ?",
            (score, audit_id),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Playbook run provenance
    # ------------------------------------------------------------------

    def record_playbook_provenance(
        self,
        prov_id: str,
        run_id: str,
        playbook_id: Optional[str],
        playbook_file_sha256: str,
        playbook_version: Optional[str],
        trigger_event_ids: list[str],
        operator_id_who_approved: Optional[str] = None,
    ) -> None:
        """
        Insert a playbook run provenance row.

        trigger_event_ids is stored as a JSON array string.
        Uses INSERT OR IGNORE so re-running is idempotent.
        Callers must wrap in try/except — this method does NOT suppress exceptions.
        """
        trigger_json = json.dumps(trigger_event_ids)
        self._conn.execute(
            """
            INSERT OR IGNORE INTO playbook_run_provenance
                (prov_id, run_id, playbook_id, playbook_file_sha256,
                 playbook_version, trigger_event_ids, operator_id_who_approved,
                 created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prov_id,
                run_id,
                playbook_id,
                playbook_file_sha256,
                playbook_version,
                trigger_json,
                operator_id_who_approved,
                _now_iso(),
            ),
        )
        self._conn.commit()

    def get_playbook_provenance(self, run_id: str) -> Optional[dict[str, Any]]:
        """
        Return the playbook_run_provenance record for the given run_id, or None.

        trigger_event_ids is deserialized from JSON to list[str].
        """
        row = self._conn.execute(
            "SELECT * FROM playbook_run_provenance WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        try:
            d["trigger_event_ids"] = json.loads(d.get("trigger_event_ids") or "[]")
        except (json.JSONDecodeError, TypeError):
            d["trigger_event_ids"] = []
        return d

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
