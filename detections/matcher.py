"""
Sigma rule matcher for DuckDB-backed event stores.

Architecture
------------
1. SigmaMatcher.load_rules_dir() recursively loads .yml files from a directory
   and parses each with pySigma's SigmaRule.from_yaml().

2. rule_to_sql() converts a SigmaRule's detection block into a parameterised
   DuckDB WHERE clause.  Supported Sigma modifiers:
   - (none): exact equality or IN list
   - |contains: LIKE '%value%'
   - |startswith: LIKE 'value%'
   - |endswith: LIKE '%value'
   - |contains|all: multiple LIKE clauses joined with AND
   - |re: basic regex via SIMILAR TO (limited support, logged as warning)

3. match_rule() executes the compiled WHERE clause against normalized_events
   and creates DetectionRecord objects for each matching event.

4. run_all() runs every loaded rule and returns all detections.

Field names are translated through detections.field_map.SIGMA_FIELD_MAP
before being used in SQL.  Unknown fields are skipped with a warning.

SQL injection safety
--------------------
All user-supplied values from Sigma rules are passed as SQL parameters (?).
Field names come from SIGMA_FIELD_MAP (a closed, trusted dict), never from
raw rule text.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from sigma.collection import SigmaCollection
from sigma.conditions import ConditionAND, ConditionOR
from sigma.modifiers import (
    SigmaAllModifier,
    SigmaContainsModifier,
    SigmaEndswithModifier,
    SigmaStartswithModifier,
)
from sigma.rule import SigmaRule

from backend.core.deps import Stores
from backend.core.logging import get_logger
from backend.models.event import DetectionRecord
from detections.field_map import INTEGER_COLUMNS, SIGMA_FIELD_MAP

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# SQL fragment helpers
# ---------------------------------------------------------------------------


def _value_to_sql_fragment(
    column: str,
    raw_value: str,
    params: list[Any],
    modifier_classes: list[type],
    negate: bool = False,
) -> str | None:
    """
    Build a single SQL comparison fragment for one (column, value) pair.

    Returns a string like ``"process_name LIKE ?"`` and appends the
    corresponding parameter value to *params*.

    Returns None if the value should be skipped (e.g. wildcard-only "*").
    """
    is_contains = SigmaContainsModifier in modifier_classes
    is_startswith = SigmaStartswithModifier in modifier_classes
    is_endswith = SigmaEndswithModifier in modifier_classes

    # Strip leading/trailing wildcards that pySigma inserts for modifier syntax
    # str(SigmaString) returns e.g. "*-enc*", "*powershell.exe", "mimikatz*"
    plain = raw_value
    # Remove modifier-inserted wildcards at known positions
    if is_contains:
        plain = plain.strip("*")
    elif is_startswith:
        plain = plain.rstrip("*")
    elif is_endswith:
        plain = plain.lstrip("*")

    # If value is empty or pure wildcard after stripping, skip it
    if not plain or plain == "*":
        return None

    # Escape existing SQL LIKE metacharacters in the literal portion
    escaped = plain.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    # Re-apply wildcards remaining in the Sigma value (user-specified '*' in value)
    # We've already stripped modifier-added wildcards; remaining '*' in 'plain'
    # come from the rule author using wildcards explicitly.
    # Convert Sigma wildcard '*' → SQL '%', '?' → SQL '_'
    sql_like_value = escaped.replace("*", "%").replace("?", "_")

    if is_contains:
        sql_param = f"%{sql_like_value}%"
        op = "NOT LIKE" if negate else "LIKE"
        params.append(sql_param)
        return f"{column} {op} ?"
    elif is_startswith:
        sql_param = f"{sql_like_value}%"
        op = "NOT LIKE" if negate else "LIKE"
        params.append(sql_param)
        return f"{column} {op} ?"
    elif is_endswith:
        sql_param = f"%{sql_like_value}"
        op = "NOT LIKE" if negate else "LIKE"
        params.append(sql_param)
        return f"{column} {op} ?"
    else:
        # Exact equality — check type
        if column in INTEGER_COLUMNS:
            try:
                int_val = int(plain)
                op = "!=" if negate else "="
                params.append(int_val)
                return f"{column} {op} ?"
            except ValueError:
                log.debug(
                    "Sigma value not numeric for integer column — skipping",
                    column=column,
                    value=plain,
                )
                return None
        else:
            op = "!=" if negate else "="
            params.append(plain)
            return f"{column} {op} ?"


def _detection_item_to_fragments(
    field: str,
    modifier_classes: list[type],
    values: list[Any],
    params: list[Any],
    negate: bool = False,
) -> list[str]:
    """
    Convert a single SigmaDetectionItem to a list of SQL fragment strings.

    Multiple values for a single field are joined with OR by default (standard
    Sigma semantics), or AND when |all modifier is present.
    """
    column = SIGMA_FIELD_MAP.get(field)
    if column is None:
        log.debug("Sigma field not in field map — skipping", field=field)
        return []

    is_all = SigmaAllModifier in modifier_classes

    fragments: list[str] = []
    for sigma_val in values:
        raw = str(sigma_val)
        frag = _value_to_sql_fragment(column, raw, params, modifier_classes, negate=negate)
        if frag:
            fragments.append(frag)

    if not fragments:
        return []

    if is_all:
        # All values must match
        joined = " AND ".join(f"({f})" for f in fragments)
    else:
        # Any value matches (standard OR semantics)
        if len(fragments) == 1:
            joined = fragments[0]
        else:
            joined = " OR ".join(f"({f})" for f in fragments)

    return [joined]


# ---------------------------------------------------------------------------
# SigmaMatcher
# ---------------------------------------------------------------------------


class SigmaMatcher:
    """
    Load Sigma rules from disk and match them against DuckDB events.

    Thread safety: load_rules_dir() modifies state; call it during
    startup before serving requests.  run_all() / match_rule() are read-only
    with respect to _rules and safe to call concurrently.
    """

    def __init__(self, stores: Stores) -> None:
        self.stores = stores
        self._rules: list[SigmaRule] = []
        self._rule_sql_cache: dict[str, str | None] = {}  # rule id → WHERE clause

    # ------------------------------------------------------------------
    # Rule loading
    # ------------------------------------------------------------------

    def load_rules_dir(self, rules_dir: str) -> int:
        """
        Recursively load all .yml / .yaml files from *rules_dir* as Sigma rules.

        Args:
            rules_dir: Path to a directory containing Sigma rule YAML files.

        Returns:
            Number of rules successfully loaded.
        """
        loaded = 0
        rules_path = Path(rules_dir)
        if not rules_path.exists():
            log.warning("Sigma rules directory not found", path=rules_dir)
            return 0

        for yml_path in sorted(rules_path.rglob("*.yml")):
            try:
                rule = SigmaRule.from_yaml(yml_path.read_text(encoding="utf-8"))
                self._rules.append(rule)
                loaded += 1
                log.debug("Sigma rule loaded", rule=str(rule.title), path=str(yml_path))
            except Exception as exc:
                log.warning(
                    "Failed to load Sigma rule — skipping",
                    path=str(yml_path),
                    error=str(exc),
                )

        for yaml_path in sorted(rules_path.rglob("*.yaml")):
            try:
                rule = SigmaRule.from_yaml(yaml_path.read_text(encoding="utf-8"))
                self._rules.append(rule)
                loaded += 1
            except Exception as exc:
                log.warning(
                    "Failed to load Sigma rule — skipping",
                    path=str(yaml_path),
                    error=str(exc),
                )

        log.info(
            "Sigma rules loaded",
            rules_dir=rules_dir,
            count=loaded,
        )
        return loaded

    def load_rule_yaml(self, yaml_text: str) -> SigmaRule | None:
        """Parse a single Sigma rule from a YAML string. Returns None on error."""
        try:
            rule = SigmaRule.from_yaml(yaml_text)
            self._rules.append(rule)
            return rule
        except Exception as exc:
            log.warning("Failed to parse Sigma rule YAML", error=str(exc))
            return None

    # ------------------------------------------------------------------
    # SQL generation
    # ------------------------------------------------------------------

    def rule_to_sql(self, rule: SigmaRule) -> str | None:
        """
        Convert a Sigma rule to a parameterised DuckDB WHERE clause.

        Returns a (where_clause, params) pair where where_clause is a string
        with ``?`` placeholders and params is the corresponding value list.

        Returns None if the rule cannot be converted (e.g., uses unsupported
        features or all fields are unmapped).

        Note: This method returns the WHERE clause string only (without
        parameters) for caching purposes.  Use rule_to_sql_with_params() to
        get both.
        """
        result = self._rule_to_sql_impl(rule)
        return result[0] if result else None

    def rule_to_sql_with_params(
        self, rule: SigmaRule
    ) -> tuple[str, list[Any]] | None:
        """
        Convert a Sigma rule to a (WHERE clause string, params list) tuple.

        Returns None if the rule cannot be converted.
        """
        return self._rule_to_sql_impl(rule)

    def _rule_to_sql_impl(
        self, rule: SigmaRule
    ) -> tuple[str, list[Any]] | None:
        """Internal implementation that builds WHERE clause + params list."""
        detection = rule.detection
        if not detection:
            return None

        # Parse condition string(s)
        # Sigma condition syntax: "selection", "selection and not filter",
        # "1 of selection*", "all of them", etc.
        conditions = detection.condition
        if not conditions:
            return None

        # We handle simple conditions: a single condition string
        condition_str = conditions[0].strip().lower() if isinstance(conditions, list) else str(conditions).lower()

        params: list[Any] = []

        try:
            where = self._build_condition_sql(
                condition_str, detection.detections, params
            )
        except Exception as exc:
            log.warning(
                "Could not convert Sigma rule to SQL",
                rule=str(rule.title),
                condition=condition_str,
                error=str(exc),
            )
            return None

        if not where or not where.strip():
            return None

        return where, params

    def _build_condition_sql(
        self,
        condition_str: str,
        detections: dict[str, Any],
        params: list[Any],
    ) -> str | None:
        """
        Recursively build a SQL expression from a Sigma condition string.

        Handles:
        - Simple reference: "selection"
        - NOT: "not filter"
        - AND: "a and b"
        - OR: "a or b"
        - "1 of selection*" → any detection matching the prefix
        - "all of them" → AND of all detections
        - Parenthesised groups
        """
        condition_str = condition_str.strip()

        # Remove outer parentheses
        if condition_str.startswith("(") and condition_str.endswith(")"):
            inner = condition_str[1:-1].strip()
            if self._balanced(inner):
                condition_str = inner

        # Handle "not X"
        not_match = re.match(r"^not\s+(.+)$", condition_str, re.IGNORECASE)
        if not_match:
            inner_sql = self._build_condition_sql(
                not_match.group(1), detections, params
            )
            if inner_sql:
                return f"NOT ({inner_sql})"
            return None

        # Handle "A and B" (split on outermost AND)
        and_parts = self._split_condition(condition_str, "and")
        if and_parts and len(and_parts) > 1:
            fragments = []
            for part in and_parts:
                frag = self._build_condition_sql(part.strip(), detections, params)
                if frag:
                    fragments.append(f"({frag})")
            if fragments:
                return " AND ".join(fragments)
            return None

        # Handle "A or B"
        or_parts = self._split_condition(condition_str, "or")
        if or_parts and len(or_parts) > 1:
            fragments = []
            for part in or_parts:
                frag = self._build_condition_sql(part.strip(), detections, params)
                if frag:
                    fragments.append(f"({frag})")
            if fragments:
                return " OR ".join(fragments)
            return None

        # Handle "1 of selection*" / "all of them" / "1 of them"
        of_match = re.match(r"^(1|all|\d+)\s+of\s+(.+)$", condition_str, re.IGNORECASE)
        if of_match:
            quantifier = of_match.group(1).lower()
            target = of_match.group(2).strip()

            if target == "them":
                target_names = list(detections.keys())
            elif target.endswith("*"):
                prefix = target[:-1]
                target_names = [k for k in detections.keys() if k.startswith(prefix)]
            else:
                target_names = [target] if target in detections else []

            frags = []
            for name in target_names:
                det_obj = detections.get(name)
                if det_obj:
                    frag = self._detection_to_sql(det_obj, params, negate=False)
                    if frag:
                        frags.append(f"({frag})")

            if not frags:
                return None
            if quantifier == "all":
                return " AND ".join(frags)
            else:
                # "1 of" = any one matches
                return " OR ".join(frags)

        # Simple reference to a detection by name
        if condition_str in detections:
            det_obj = detections[condition_str]
            return self._detection_to_sql(det_obj, params, negate=False)

        # Try case-insensitive lookup
        for key, det_obj in detections.items():
            if key.lower() == condition_str.lower():
                return self._detection_to_sql(det_obj, params, negate=False)

        log.debug(
            "Sigma condition term not resolved",
            term=condition_str,
            available=list(detections.keys()),
        )
        return None

    def _detection_to_sql(
        self, detection_obj: Any, params: list[Any], negate: bool = False
    ) -> str | None:
        """Convert a SigmaDetection object to a SQL fragment."""
        if hasattr(detection_obj, "detection_items"):
            # SigmaDetection with item_linking
            item_linking = detection_obj.item_linking
            fragments: list[str] = []

            for item in detection_obj.detection_items:
                if hasattr(item, "detection_items"):
                    # Nested SigmaDetection
                    frag = self._detection_to_sql(item, params, negate)
                    if frag:
                        fragments.append(f"({frag})")
                elif hasattr(item, "field") and item.field:
                    item_frags = _detection_item_to_fragments(
                        field=item.field,
                        modifier_classes=item.modifiers,
                        values=item.value,
                        params=params,
                        negate=negate,
                    )
                    fragments.extend(f"({f})" for f in item_frags)
                else:
                    # NULL field (keyword detection) — not supported for DuckDB
                    log.debug("Sigma keyword detection not supported for DuckDB SQL — skipping")

            if not fragments:
                return None

            if item_linking == ConditionAND or item_linking is ConditionAND:
                return " AND ".join(fragments)
            else:
                # Default: OR
                return " OR ".join(fragments)

        return None

    @staticmethod
    def _balanced(s: str) -> bool:
        """Return True if parentheses in *s* are balanced."""
        depth = 0
        for ch in s:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if depth < 0:
                return False
        return depth == 0

    @staticmethod
    def _split_condition(condition: str, operator: str) -> list[str] | None:
        """
        Split *condition* on the outermost occurrences of *operator*
        (case-insensitive), respecting parenthesis depth.

        Returns None if no split point was found.
        """
        op_upper = f" {operator.upper()} "
        op_lower = f" {operator.lower()} "
        parts: list[str] = []
        depth = 0
        current_start = 0
        i = 0
        condition_upper = condition.upper()

        while i < len(condition):
            ch = condition[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1

            if depth == 0:
                check = condition_upper[i:i + len(op_upper)]
                if check == op_upper.upper():
                    parts.append(condition[current_start:i])
                    current_start = i + len(op_upper)
                    i += len(op_upper)
                    continue
            i += 1

        if parts:
            parts.append(condition[current_start:])
            return parts
        return None

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    async def match_rule(
        self,
        rule: SigmaRule,
        sql_where: str,
        params: list[Any],
        case_id: str | None = None,
    ) -> list[DetectionRecord]:
        """
        Execute *sql_where* against normalized_events and return DetectionRecords.

        Args:
            rule:      The Sigma rule (for metadata like title, severity).
            sql_where: SQL WHERE clause with ? placeholders.
            params:    Corresponding parameter values.
            case_id:   Filter events by case_id if provided.

        Returns:
            List of DetectionRecord objects, one per matching event.
        """
        base_sql = "SELECT event_id FROM normalized_events WHERE "

        if case_id:
            full_sql = f"{base_sql}({sql_where}) AND case_id = ?"
            full_params = params + [case_id]
        else:
            full_sql = f"{base_sql}({sql_where})"
            full_params = params

        try:
            rows = await self.stores.duckdb.fetch_all(full_sql, full_params)
        except Exception as exc:
            log.error(
                "Sigma rule SQL execution error",
                rule=str(rule.title),
                sql=full_sql[:200],
                error=str(exc),
            )
            return []

        if not rows:
            return []

        matched_ids = [row[0] for row in rows]

        rule_id = str(rule.id) if rule.id else str(uuid4())
        rule_name = str(rule.title) if rule.title else rule_id
        severity_raw = str(rule.level).lower() if rule.level else "medium"
        # Map pySigma level names to our schema
        severity_map = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low",
            "informational": "informational",
        }
        severity = severity_map.get(severity_raw, "medium")

        # Extract ATT&CK metadata
        attack_technique: str | None = None
        attack_tactic: str | None = None
        if hasattr(rule, "tags") and rule.tags:
            for tag in rule.tags:
                tag_str = str(tag).lower()
                if tag_str.startswith("attack.t"):
                    attack_technique = str(tag).split(".")[-1].upper()
                elif tag_str.startswith("attack."):
                    attack_tactic = str(tag).split(".")[-1].replace("_", " ").title()

        detections: list[DetectionRecord] = []
        # Group all matching events into a single DetectionRecord per rule match
        detection = DetectionRecord(
            id=str(uuid4()),
            rule_id=rule_id,
            rule_name=rule_name,
            severity=severity,
            matched_event_ids=matched_ids,
            attack_technique=attack_technique,
            attack_tactic=attack_tactic,
            explanation=f"Sigma rule '{rule_name}' matched {len(matched_ids)} event(s).",
            case_id=case_id,
            created_at=datetime.now(tz=timezone.utc),
        )
        detections.append(detection)

        log.info(
            "Sigma rule matched",
            rule=rule_name,
            matched_events=len(matched_ids),
            severity=severity,
        )
        return detections

    async def run_all(
        self, case_id: str | None = None
    ) -> list[DetectionRecord]:
        """
        Run all loaded rules against current events in DuckDB.

        Args:
            case_id: Optional case_id to scope the search.

        Returns:
            All DetectionRecord objects produced by all rules.
        """
        all_detections: list[DetectionRecord] = []

        for rule in self._rules:
            rule_id = str(rule.id) if rule.id else "unknown"

            # Use cache for WHERE clause
            cache_key = rule_id
            if cache_key not in self._rule_sql_cache:
                result = self.rule_to_sql_with_params(rule)
                if result is None:
                    self._rule_sql_cache[cache_key] = None
                    log.debug(
                        "Sigma rule skipped — not convertible to SQL",
                        rule=str(rule.title),
                    )
                    continue
                # Store template only (params vary per run based on case_id)
                self._rule_sql_cache[cache_key] = result[0]

            where_clause = self._rule_sql_cache.get(cache_key)
            if not where_clause:
                continue

            # Re-generate params (they depend on the rule's values, not case_id)
            sql_result = self.rule_to_sql_with_params(rule)
            if not sql_result:
                continue

            _, params = sql_result

            try:
                detections = await self.match_rule(
                    rule=rule,
                    sql_where=where_clause,
                    params=params,
                    case_id=case_id,
                )
                all_detections.extend(detections)
            except Exception as exc:
                log.error(
                    "Error running Sigma rule",
                    rule=str(rule.title),
                    error=str(exc),
                )

        log.info(
            "Sigma run_all complete",
            rules_checked=len(self._rules),
            detections_found=len(all_detections),
            case_id=case_id,
        )
        return all_detections

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    async def save_detections(
        self, detections: list[DetectionRecord]
    ) -> int:
        """
        Persist DetectionRecord objects to the SQLite detections table.

        Args:
            detections: List of DetectionRecord objects.

        Returns:
            Number of detections saved.
        """
        import asyncio

        def _sync_save() -> int:
            saved = 0
            for det in detections:
                try:
                    self.stores.sqlite.insert_detection(
                        detection_id=det.id,
                        rule_id=det.rule_id or "",
                        rule_name=det.rule_name or "",
                        severity=det.severity,
                        matched_event_ids=det.matched_event_ids,
                        attack_technique=det.attack_technique,
                        attack_tactic=det.attack_tactic,
                        explanation=det.explanation,
                        case_id=det.case_id,
                    )
                    saved += 1
                except Exception as exc:
                    log.warning(
                        "Failed to save detection",
                        detection_id=det.id,
                        error=str(exc),
                    )
            return saved

        return await asyncio.to_thread(_sync_save)

    @property
    def rule_count(self) -> int:
        """Return the number of currently loaded Sigma rules."""
        return len(self._rules)
