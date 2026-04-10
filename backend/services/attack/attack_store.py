"""
AttackStore — SQLite CRUD for the Phase 34 MITRE ATT&CK data layer.

Provides:
- AttackStore: SQLite CRUD for attack_techniques, attack_groups,
  attack_group_techniques, and detection_techniques tables.
- extract_attack_techniques_from_rule(): Sigma tag → normalised T-ID list.
- scan_rules_dir_for_coverage(): Map T-IDs to rule titles across a rules dir.

All AttackStore methods are synchronous — call via asyncio.to_thread() from
async handlers. bootstrap_from_objects() parses raw STIX JSON objects.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS attack_techniques (
    tech_id   TEXT PRIMARY KEY,
    name      TEXT NOT NULL,
    tactic    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attack_groups (
    stix_id   TEXT PRIMARY KEY,
    group_id  TEXT,
    name      TEXT NOT NULL,
    aliases   TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS attack_group_techniques (
    stix_group_id TEXT NOT NULL,
    tech_id       TEXT NOT NULL,
    PRIMARY KEY (stix_group_id, tech_id)
);

CREATE TABLE IF NOT EXISTS detection_techniques (
    detection_id  TEXT NOT NULL,
    tech_id       TEXT NOT NULL,
    PRIMARY KEY (detection_id, tech_id)
);
"""

# ---------------------------------------------------------------------------
# Tag extraction regex (module-level — shared with scan_rules_dir_for_coverage)
# ---------------------------------------------------------------------------

_TECH_RE = re.compile(r"^attack\.(t\d{4})(?:\.\d+)?$", re.IGNORECASE)
# Also match against the tag.name field alone (pySigma splits namespace.name)
_TECH_NAME_RE = re.compile(r"^(t\d{4})(?:\.\d+)?$", re.IGNORECASE)

# ---------------------------------------------------------------------------
# AttackStore
# ---------------------------------------------------------------------------


class AttackStore:
    """
    Manages ATT&CK technique, group, and detection-tagging tables in SQLite.

    Constructor accepts a sqlite3.Connection directly for testability —
    the shared SQLiteStore connection is passed in from app.state in production.
    __init__ runs DDL to ensure all tables exist.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.executescript(DDL)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Technique CRUD
    # ------------------------------------------------------------------

    def upsert_technique(self, tech_id: str, name: str, tactic: str) -> None:
        """Insert a technique; ignore if already present (INSERT OR IGNORE)."""
        self._conn.execute(
            "INSERT OR IGNORE INTO attack_techniques (tech_id, name, tactic) VALUES (?, ?, ?)",
            (tech_id, name, tactic),
        )
        self._conn.commit()

    def technique_count(self) -> int:
        """Return total number of technique rows."""
        cursor = self._conn.execute("SELECT COUNT(*) FROM attack_techniques")
        return cursor.fetchone()[0]

    # ------------------------------------------------------------------
    # Group CRUD
    # ------------------------------------------------------------------

    def upsert_group(
        self,
        stix_id: str,
        group_id: str | None,
        name: str,
        aliases: str,
    ) -> None:
        """Insert a group; ignore if already present (INSERT OR IGNORE)."""
        self._conn.execute(
            "INSERT OR IGNORE INTO attack_groups (stix_id, group_id, name, aliases) VALUES (?, ?, ?, ?)",
            (stix_id, group_id, name, aliases),
        )
        self._conn.commit()

    def group_count(self) -> int:
        """Return total number of group rows."""
        cursor = self._conn.execute("SELECT COUNT(*) FROM attack_groups")
        return cursor.fetchone()[0]

    def upsert_group_technique(self, stix_group_id: str, tech_id: str) -> None:
        """Link a group to a technique; idempotent (INSERT OR IGNORE)."""
        self._conn.execute(
            "INSERT OR IGNORE INTO attack_group_techniques (stix_group_id, tech_id) VALUES (?, ?)",
            (stix_group_id, tech_id),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # STIX bootstrap
    # ------------------------------------------------------------------

    def bootstrap_from_objects(self, objects: list[dict[str, Any]]) -> None:
        """
        Parse a list of raw STIX JSON objects and populate the ATT&CK tables.

        Filtering rules:
        - attack-pattern: NOT revoked, NOT x_mitre_is_subtechnique, must have
          mitre-attack external reference with an external_id.
        - intrusion-set: NOT revoked.
        - relationship uses: NOT revoked, source=intrusion-set, target=attack-pattern.
        """
        # Build lookup for relationship resolution
        by_id: dict[str, dict[str, Any]] = {obj.get("id", ""): obj for obj in objects}

        # Techniques
        for obj in objects:
            if obj.get("type") != "attack-pattern":
                continue
            if obj.get("revoked", False):
                continue
            if obj.get("x_mitre_is_subtechnique", False):
                continue

            tech_id = _extract_mitre_id(obj)
            if not tech_id:
                continue

            tactic = ""
            phases = obj.get("kill_chain_phases", [])
            if phases:
                tactic = phases[0].get("phase_name", "")

            self.upsert_technique(tech_id=tech_id, name=obj.get("name", ""), tactic=tactic)

        # Groups (intrusion-sets)
        for obj in objects:
            if obj.get("type") != "intrusion-set":
                continue
            if obj.get("revoked", False):
                continue

            stix_id = obj.get("id", "")
            group_id = _extract_mitre_id(obj)  # e.g. "G0016"
            name = obj.get("name", "")
            aliases_list = obj.get("aliases", [])
            aliases_json = json.dumps(aliases_list)

            self.upsert_group(
                stix_id=stix_id,
                group_id=group_id,
                name=name,
                aliases=aliases_json,
            )

        # Relationships: intrusion-set → uses → attack-pattern
        for obj in objects:
            if obj.get("type") != "relationship":
                continue
            if obj.get("revoked", False):
                continue
            if obj.get("relationship_type") != "uses":
                continue

            src_id = obj.get("source_ref", "")
            tgt_id = obj.get("target_ref", "")

            src = by_id.get(src_id, {})
            tgt = by_id.get(tgt_id, {})

            if src.get("type") != "intrusion-set":
                continue
            if tgt.get("type") != "attack-pattern":
                continue

            # Only link if both sides were successfully inserted (not revoked/filtered)
            tgt_tech_id = _extract_mitre_id(tgt)
            if not tgt_tech_id:
                continue
            if tgt.get("revoked", False) or tgt.get("x_mitre_is_subtechnique", False):
                continue

            self.upsert_group_technique(
                stix_group_id=src_id,
                tech_id=tgt_tech_id,
            )

    # ------------------------------------------------------------------
    # Actor matching
    # ------------------------------------------------------------------

    def actor_matches(self, tech_ids: list[str]) -> list[dict[str, Any]]:
        """
        Return top-3 groups whose technique sets best overlap with *tech_ids*.

        Args:
            tech_ids: List of normalised technique IDs, e.g. ["T1059", "T1071"].

        Returns:
            List of up to 3 dicts, sorted by overlap_pct descending.
            Each dict has keys:
              name, aliases, group_id, overlap_pct (float), confidence (str),
              matched_count (int), total_count (int).
        """
        input_set = set(tech_ids)

        # Fetch all groups
        group_rows = self._conn.execute(
            "SELECT stix_id, group_id, name, aliases FROM attack_groups"
        ).fetchall()

        results: list[dict[str, Any]] = []

        for row in group_rows:
            stix_id = row[0]
            group_id = row[1]
            name = row[2]
            aliases_json = row[3] or "[]"

            # Fetch techniques for this group
            tech_rows = self._conn.execute(
                "SELECT tech_id FROM attack_group_techniques WHERE stix_group_id = ?",
                (stix_id,),
            ).fetchall()
            group_techs = {r[0] for r in tech_rows}

            if not group_techs:
                continue

            matched = input_set & group_techs
            overlap_pct = len(matched) / len(group_techs)

            if overlap_pct >= 0.60:
                confidence = "High"
            elif overlap_pct >= 0.30:
                confidence = "Medium"
            else:
                confidence = "Low"

            try:
                aliases = json.loads(aliases_json)
            except (json.JSONDecodeError, TypeError):
                aliases = []

            results.append(
                {
                    "name": name,
                    "aliases": aliases,
                    "group_id": group_id,
                    "overlap_pct": overlap_pct,
                    "confidence": confidence,
                    "matched_count": len(matched),
                    "total_count": len(group_techs),
                }
            )

        # Sort by overlap_pct descending, top 3
        results.sort(key=lambda r: r["overlap_pct"], reverse=True)
        return results[:3]

    # ------------------------------------------------------------------
    # Coverage query
    # ------------------------------------------------------------------

    def list_techniques_by_tactic(self, tactic: str) -> list[dict[str, Any]]:
        """
        Return all technique rows for a given tactic slug.

        Args:
            tactic: e.g. "execution", "persistence" — matches tactic column exactly.

        Returns:
            List of dicts with keys: tech_id, name.
        """
        cursor = self._conn.execute(
            "SELECT tech_id, name FROM attack_techniques WHERE tactic = ? ORDER BY tech_id",
            (tactic,),
        )
        return [{"tech_id": row[0], "name": row[1]} for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Detection technique tagging
    # ------------------------------------------------------------------

    def tag_detection_techniques(
        self, detection_id: str, tech_ids: list[str]
    ) -> None:
        """
        Write ATT&CK technique IDs to detection_techniques for a given detection.

        Called after a DetectionRecord is persisted to SQLite. Idempotent
        via INSERT OR IGNORE.
        """
        for tid in tech_ids:
            self._conn.execute(
                "INSERT OR IGNORE INTO detection_techniques (detection_id, tech_id) VALUES (?, ?)",
                (detection_id, tid),
            )
        self._conn.commit()


# ---------------------------------------------------------------------------
# Module-level tag extraction helpers (imported by matcher.py and API routes)
# ---------------------------------------------------------------------------


def extract_attack_techniques_from_rule(rule: Any) -> list[str]:
    """
    Extract normalised ATT&CK technique IDs from a SigmaRule's tags.

    - Tactic-only tags (e.g. attack.execution) are ignored.
    - Sub-technique tags (e.g. attack.t1059.001) return parent ID only (T1059).
    - Case-insensitive: attack.T1059 == attack.t1059.

    Args:
        rule: A sigma.rule.SigmaRule object.

    Returns:
        List of uppercase technique IDs (e.g. ["T1059"]).
    """
    result: list[str] = []
    if not hasattr(rule, "tags") or not rule.tags:
        return result
    for tag in rule.tags:
        # pySigma SigmaRuleTag stores namespace and name separately.
        # tag.name is e.g. "t1059" or "t1059.001"; tag.namespace is "attack".
        # Try matching against the full "namespace.name" string first (robust),
        # then fall back to name-only if the namespace is "attack".
        tag_namespace = getattr(tag, "namespace", "")
        tag_name = getattr(tag, "name", "")
        full_tag = f"{tag_namespace}.{tag_name}" if tag_namespace else tag_name

        # Try full "attack.t1059" pattern
        m = _TECH_RE.match(full_tag)
        if m:
            result.append(m.group(1).upper())
            continue

        # Fallback: if namespace == "attack", match name alone "t1059"
        if tag_namespace.lower() == "attack":
            m2 = _TECH_NAME_RE.match(tag_name)
            if m2:
                result.append(m2.group(1).upper())
    return result


def scan_rules_dir_for_coverage(rules_dir: Path) -> dict[str, list[str]]:
    """
    Scan a directory of Sigma YAML rules and build an ATT&CK coverage map.

    Args:
        rules_dir: Path to directory containing .yml Sigma rule files.

    Returns:
        Dict mapping technique ID → list of rule titles that reference it.
        Example: {"T1059": ["PowerShell Execution", "Script Block Logging"]}
    """
    from sigma.rule import SigmaRule

    coverage: dict[str, list[str]] = {}

    for yml_path in Path(rules_dir).rglob("*.yml"):
        try:
            yaml_text = yml_path.read_text(encoding="utf-8")
            rule = SigmaRule.from_yaml(yaml_text)
            title = str(rule.title) if rule.title else str(yml_path.stem)
            tech_ids = extract_attack_techniques_from_rule(rule)
            for tid in tech_ids:
                coverage.setdefault(tid, [])
                if title not in coverage[tid]:
                    coverage[tid].append(title)
        except Exception:
            # Skip malformed rule files silently
            pass

    return coverage


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_MITRE_ID_RE = re.compile(r"^[TGS]\d{4}$")


def _extract_mitre_id(obj: dict[str, Any]) -> str | None:
    """Extract the MITRE ATT&CK external ID from a STIX object's external_references."""
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            ext_id = ref.get("external_id", "")
            if ext_id:
                return ext_id
    return None
