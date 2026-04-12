"""
CorrelationEngine — statistical detection of port scans, brute force, and beaconing.

Phase 43 — Plan 43-02: Core correlation engine implementation.

Three detection methods run after every ingest batch:
  - _detect_port_scans(): 60s tumbling window, 15+ distinct dst_ports from same src_ip
  - _detect_brute_force(): 60s tumbling window, 10+ failed auth events from same src_ip
  - _detect_beaconing(): CV < 0.3 over 20+ connections to same dst_ip:port

Chain detection (_detect_chains) and YAML loading are stubbed for Plan 43-03.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.core.config import settings
from backend.models.event import DetectionRecord


class CorrelationEngine:
    """Correlation-based detection engine producing DetectionRecord results.

    Instantiated once per app lifespan and wired into IngestionLoader so it
    runs after every ingest batch (see loader.py Step 5).

    Args:
        stores: Container holding .duckdb (DuckDBStore) and .sqlite (SQLiteStore).
    """

    def __init__(self, stores) -> None:
        self.stores = stores
        self._chains: list[dict] = []

    async def run(self) -> list[DetectionRecord]:
        """Run all correlation detectors. Returns detections not suppressed by dedup."""
        results: list[DetectionRecord] = []
        for batch in [
            await self._detect_port_scans(),
            await self._detect_brute_force(),
            await self._detect_beaconing(),
            await self._detect_chains(),
        ]:
            for det in batch:
                entity = det.entity_key or ""
                if not await self._is_dedup_suppressed(
                    det.rule_id, entity,
                    settings.CORRELATION_DEDUP_WINDOW_MINUTES
                ):
                    results.append(det)
        return results

    async def save_detections(self, detections: list[DetectionRecord]) -> int:
        """Persist correlation detections to SQLite. Returns count saved."""
        def _save():
            count = 0
            for det in detections:
                self.stores.sqlite.insert_detection(
                    det.id,
                    det.rule_id or "",
                    det.rule_name or "",
                    det.severity,
                    det.matched_event_ids,
                    det.attack_technique,
                    det.attack_tactic,
                    det.explanation,
                    None,   # case_id
                    entity_key=getattr(det, "entity_key", None),
                )
                count += 1
            return count
        return await asyncio.to_thread(_save)

    async def _is_dedup_suppressed(
        self, rule_id: str, entity_key: str, dedup_minutes: int
    ) -> bool:
        """Return True if same rule_id + entity_key fired within dedup window."""
        cutoff = (
            datetime.now(tz=timezone.utc) - timedelta(minutes=dedup_minutes)
        ).isoformat()

        def _check():
            row = self.stores.sqlite._conn.execute(
                """SELECT id FROM detections
                   WHERE rule_id = ?
                     AND entity_key = ?
                     AND created_at >= ?
                   LIMIT 1""",
                (rule_id, entity_key, cutoff),
            ).fetchone()
            return row is not None

        return await asyncio.to_thread(_check)

    async def _detect_port_scans(self) -> list[DetectionRecord]:
        """Detect horizontal port scans: 15+ distinct dst_ports from same src_ip in 60s."""
        lookback = f"INTERVAL '{settings.CORRELATION_LOOKBACK_HOURS} hours'"
        sql = f"""
            SELECT
              src_ip,
              COUNT(DISTINCT dst_port) AS distinct_ports,
              LIST(CAST(event_id AS VARCHAR)) AS event_ids,
              MIN(timestamp) AS window_start,
              MAX(timestamp) AS window_end
            FROM normalized_events
            WHERE timestamp >= now() - {lookback}
              AND src_ip IS NOT NULL
              AND dst_port IS NOT NULL
            GROUP BY src_ip, CAST(epoch(timestamp) / 60 AS BIGINT)
            HAVING COUNT(DISTINCT dst_port) >= 15
        """
        rows = await self.stores.duckdb.fetch_all(sql)
        results = []
        for row in rows:
            src_ip = row["src_ip"]
            event_ids = [str(e) for e in (row["event_ids"] or [])]
            det = DetectionRecord(
                id=str(uuid4()),
                rule_id="corr-portscan",
                rule_name="Correlation: Port Scan",
                severity="medium",
                matched_event_ids=event_ids,
                attack_technique="T1046",
                attack_tactic="discovery",
                explanation=f"Port scan from {src_ip} ({row['distinct_ports']} ports in 60s)",
                entity_key=src_ip,
            )
            results.append(det)
        return results

    async def _detect_brute_force(self) -> list[DetectionRecord]:
        """Detect brute force: 10+ failed auth events from same src_ip+dst_ip in 60s."""
        lookback = f"INTERVAL '{settings.CORRELATION_LOOKBACK_HOURS} hours'"
        sql = f"""
            SELECT
              src_ip,
              dst_ip,
              COUNT(*) AS failed_auth_count,
              LIST(CAST(event_id AS VARCHAR)) AS event_ids,
              MIN(timestamp) AS window_start,
              MAX(timestamp) AS window_end
            FROM normalized_events
            WHERE timestamp >= now() - {lookback}
              AND src_ip IS NOT NULL
              AND (
                event_outcome = 'failure'
                OR event_type = 'logon_failure'
                OR (event_type = 'ssh' AND ssh_auth_success = false)
              )
            GROUP BY src_ip, dst_ip, CAST(epoch(timestamp) / 60 AS BIGINT)
            HAVING COUNT(*) >= 10
        """
        rows = await self.stores.duckdb.fetch_all(sql)
        results = []
        for row in rows:
            src_ip = row["src_ip"]
            dst_ip = row["dst_ip"] or "unknown"
            event_ids = [str(e) for e in (row["event_ids"] or [])]
            det = DetectionRecord(
                id=str(uuid4()),
                rule_id="corr-bruteforce",
                rule_name="Correlation: Brute Force",
                severity="high",
                matched_event_ids=event_ids,
                attack_technique="T1110",
                attack_tactic="credential-access",
                explanation=(
                    f"Brute force from {src_ip} to {dst_ip} "
                    f"({row['failed_auth_count']} failures in 60s)"
                ),
                entity_key=src_ip,
            )
            results.append(det)
        return results

    async def _detect_beaconing(self) -> list[DetectionRecord]:
        """Detect beaconing: CV < 0.3 for inter-arrival times over 20+ connections."""
        lookback = f"INTERVAL '{settings.CORRELATION_LOOKBACK_HOURS} hours'"
        sql = f"""
            WITH intervals AS (
              SELECT
                CAST(event_id AS VARCHAR) AS event_id,
                src_ip, dst_ip, dst_port, timestamp,
                epoch(timestamp) - LAG(epoch(timestamp)) OVER (
                  PARTITION BY src_ip, dst_ip, dst_port
                  ORDER BY timestamp
                ) AS interval_secs
              FROM normalized_events
              WHERE timestamp >= now() - {lookback}
                AND src_ip IS NOT NULL
                AND dst_ip IS NOT NULL
                AND dst_port IS NOT NULL
                AND event_type IN ('conn', 'network_connect', 'tls', 'ssl', 'http')
            ),
            agg AS (
              SELECT
                src_ip, dst_ip, dst_port,
                COUNT(*) AS conn_count,
                AVG(interval_secs) AS mean_interval,
                STDDEV_POP(interval_secs) AS stddev_interval,
                LIST(event_id ORDER BY timestamp) AS event_ids
              FROM intervals
              WHERE interval_secs IS NOT NULL
              GROUP BY src_ip, dst_ip, dst_port
              HAVING COUNT(*) >= 19
                AND AVG(interval_secs) > 0
                AND STDDEV_POP(interval_secs) / NULLIF(AVG(interval_secs), 0) < 0.3
            )
            SELECT * FROM agg
        """
        rows = await self.stores.duckdb.fetch_all(sql)
        results = []
        for row in rows:
            src_ip = row["src_ip"]
            dst_ip = row["dst_ip"]
            cv = (row["stddev_interval"] or 0) / (row["mean_interval"] or 1)
            event_ids = list(row["event_ids"] or [])
            det = DetectionRecord(
                id=str(uuid4()),
                rule_id="corr-beacon",
                rule_name="Correlation: Beaconing",
                severity="high",
                matched_event_ids=event_ids,
                attack_technique="T1071",
                attack_tactic="command-and-control",
                explanation=(
                    f"Beaconing from {src_ip} to {dst_ip}:{row['dst_port']} "
                    f"(CV={cv:.2f}, {row['conn_count'] + 1} connections)"
                ),
                entity_key=src_ip,
            )
            results.append(det)
        return results

    def load_chains(self, yml_path: str) -> int:
        """Load chain definitions from YAML. Returns count loaded. Called by Plan 43-03."""
        import yaml  # lazy import — only needed when chains feature is used
        with open(yml_path) as f:
            data = yaml.safe_load(f) or {}
        self._chains = data.get("chains", [])
        return len(self._chains)

    async def _detect_chains(self) -> list[DetectionRecord]:
        """Detect multi-stage chains. Implemented in Plan 43-03."""
        return []
