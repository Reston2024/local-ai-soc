"""
Main ingestion orchestrator.

IngestionLoader ties together:
1. Parser registry (file → NormalizedEvent stream)
2. Normalizer (field cleaning and canonicalization)
3. Deduplication (DuckDB event_id check)
4. Batch DuckDB INSERT (1 000 events/batch)
5. Batch Chroma embed (100 events/batch)
6. Entity + edge extraction → SQLite

All public methods are async.  Heavy CPU/IO work is wrapped in
asyncio.to_thread() to avoid blocking the event loop.

Usage::

    loader = IngestionLoader(stores, ollama_client)
    result = await loader.ingest_file("/data/security.evtx", case_id="case-001")
    print(result)
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path as _Path
from typing import Any
from uuid import uuid4 as _uuid4

from backend.core.deps import Stores
from backend.core.logging import get_logger
from backend.models.event import NormalizedEvent
from backend.services.attack.asset_store import AssetStore, _apply_asset_upsert
from backend.services.intel.ioc_store import IocStore
from backend.services.anomaly.scorer import AnomalyScorer, entity_key as _anomaly_entity_key
from backend.services.ollama_client import OllamaClient
from backend.stores.chroma_store import DEFAULT_COLLECTION
from ingestion.entity_extractor import extract_entities_and_edges, extract_perimeter_entities
from ingestion.hayabusa_scanner import scan_evtx, hayabusa_record_to_detection
from ingestion.chainsaw_scanner import scan_evtx as chainsaw_scan_evtx, chainsaw_record_to_detection
from ingestion.normalizer import normalize_event
from ingestion.registry import get_parser

log = get_logger(__name__)

def _sha256_file(path: str) -> str:
    """Return SHA-256 hex digest of file contents.  Runs in asyncio.to_thread."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# Batch sizes
_DUCKDB_BATCH  = 1_000   # events per DuckDB executemany batch
_CHROMA_BATCH  = 100     # events per Chroma embed+upsert batch

_INSERT_SQL = """
INSERT OR IGNORE INTO normalized_events (
    event_id, timestamp, ingested_at, source_type, source_file,
    hostname, username, process_name, process_id,
    parent_process_name, parent_process_id,
    file_path, file_hash_sha256, command_line,
    src_ip, src_port, dst_ip, dst_port, domain, url,
    event_type, severity, confidence, detection_source,
    attack_technique, attack_tactic,
    raw_event, tags, case_id,
    ocsf_class_uid, event_outcome, user_domain,
    process_executable, network_protocol, network_direction,
    dns_query, dns_query_type, dns_rcode, dns_answers, dns_ttl,
    tls_version, tls_ja3, tls_ja3s, tls_sni, tls_cipher, tls_cert_subject, tls_validation_status,
    file_md5, file_sha256_eve, file_mime_type, file_size_bytes,
    http_method, http_uri, http_status_code, http_user_agent,
    ioc_matched, ioc_confidence, ioc_actor_tag,
    conn_state, conn_duration, conn_orig_bytes, conn_resp_bytes,
    zeek_notice_note, zeek_notice_msg, zeek_weird_name,
    ssh_auth_success, ssh_version,
    kerberos_client, kerberos_service,
    ntlm_domain, ntlm_username,
    smb_path, smb_action,
    rdp_cookie, rdp_security_protocol,
    anomaly_score
) VALUES (
    ?, ?, ?, ?, ?,
    ?, ?, ?, ?,
    ?, ?,
    ?, ?, ?,
    ?, ?, ?, ?, ?, ?,
    ?, ?, ?, ?,
    ?, ?,
    ?, ?, ?,
    ?, ?, ?,
    ?, ?, ?,
    ?, ?, ?, ?, ?,
    ?, ?, ?, ?, ?, ?, ?,
    ?, ?, ?, ?,
    ?, ?, ?, ?,
    ?, ?, ?,
    ?, ?, ?, ?,
    ?, ?, ?,
    ?, ?,
    ?, ?,
    ?, ?,
    ?, ?,
    ?, ?,
    ?
)
"""

_EXISTS_SQL = "SELECT 1 FROM normalized_events WHERE event_id = ? LIMIT 1"


# ---------------------------------------------------------------------------
# Phase 33: IOC matching helpers
# ---------------------------------------------------------------------------


def _apply_ioc_matching(event: NormalizedEvent, ioc_store: IocStore) -> NormalizedEvent:
    """Check event src_ip/dst_ip against ioc_store. Mutates and returns event.

    THREADING NOTE: This is a synchronous function. It is safe to call ioc_store._record_hit()
    directly here (no asyncio.to_thread wrapper needed) because ingest_events() itself is
    dispatched via asyncio.to_thread() in the caller. _apply_ioc_matching() therefore runs
    inside a thread pool worker, not on the event loop thread. Direct synchronous SQLite
    writes from here are safe and consistent with CLAUDE.md's write-queue pattern.
    """
    matched, confidence, actor_tag = ioc_store.check_ioc_match(event.src_ip, event.dst_ip)
    if matched:
        event.ioc_matched = True
        event.ioc_confidence = confidence
        event.ioc_actor_tag = actor_tag
        # _record_hit is synchronous — safe to call directly here because this function
        # is only ever called from within asyncio.to_thread() context (see note above).
        ioc_store._record_hit(
            event_timestamp=str(event.timestamp),
            hostname=event.hostname,
            src_ip=event.src_ip,
            dst_ip=event.dst_ip,
            ioc_value=event.src_ip or event.dst_ip or "",
            ioc_type="ip",
            ioc_source=actor_tag or "unknown",
            risk_score=confidence,
            actor_tag=actor_tag,
            malware_family=None,
        )
    return event


async def retroactive_ioc_scan(
    ioc_value: str,
    ioc_type: str,
    bare_ip: str | None,
    confidence: int,
    ioc_store: IocStore,
    duckdb_store: Any,
) -> int:
    """Scan normalized_events from the last 30 days for events matching the given IOC.

    Called after each successful feed sync upsert (for new IOCs only).
    Updates ioc_matched in DuckDB and records hits in ioc_hits SQLite table.

    NOTE: This is an async function running on the event loop. asyncio.to_thread()
    wrappers are correct and required — retroactive scans are called via
    asyncio.create_task() from async context (unlike _apply_ioc_matching which is sync-in-thread).

    Returns:
        Count of DuckDB rows updated.
    """
    lookup_ip = bare_ip or ioc_value
    rows = await duckdb_store.fetch_all(
        "SELECT event_id, src_ip, dst_ip, hostname, timestamp FROM normalized_events "
        "WHERE timestamp >= now() - INTERVAL '30 days' "
        "AND (src_ip = ? OR dst_ip = ?) LIMIT 1000",
        [lookup_ip, lookup_ip],
    )
    count = 0
    for row in rows:
        # Support both dict-like (real DuckDB) and tuple (test mock) row access
        if hasattr(row, "__getitem__") and not isinstance(row, (list, tuple)):
            event_id = row["event_id"]
            row_hostname = row.get("hostname")
            row_src_ip = row.get("src_ip")
            row_dst_ip = row.get("dst_ip")
            row_timestamp = row.get("timestamp")
        else:
            # Tuple: (event_id, src_ip, dst_ip, ...)
            event_id = row[0]
            row_src_ip = row[1] if len(row) > 1 else None
            row_dst_ip = row[2] if len(row) > 2 else None
            row_hostname = row[3] if len(row) > 3 else None
            row_timestamp = row[4] if len(row) > 4 else None
        await asyncio.to_thread(
            duckdb_store.execute_write,
            "UPDATE normalized_events SET ioc_matched=TRUE, ioc_confidence=? WHERE event_id=?",
            [confidence, event_id],
        )
        await asyncio.to_thread(
            ioc_store._record_hit,
            str(row_timestamp or ""),
            row_hostname,
            row_src_ip,
            row_dst_ip,
            ioc_value,
            ioc_type,
            "retroactive",
            confidence,
            None,
            None,
        )
        count += 1
    return count


# ---------------------------------------------------------------------------
# Phase 42: Anomaly scoring helpers
# ---------------------------------------------------------------------------

_SEVERITY_MAP = {
    "critical": 1.0, "high": 0.75, "medium": 0.5,
    "low": 0.25, "informational": 0.0,
}


def _extract_features(event: NormalizedEvent) -> dict:
    """Extract numeric features from event for HalfSpaceTrees. All values float in [0, 1]."""
    return {
        "severity": _SEVERITY_MAP.get((event.severity or "").lower(), 0.25),
        "event_type_hash": (hash(event.event_type or "") % 100) / 100.0,
        "src_port": ((event.src_port or 0) % 65536) / 65535.0,
        "dst_port": ((event.dst_port or 0) % 65536) / 65535.0,
        "http_status": ((event.http_status_code or 0) % 1000) / 999.0,
        "conn_dur": min((event.conn_duration or 0.0), 3600.0) / 3600.0,
        "pid": ((event.process_id or 0) % 65536) / 65535.0,
    }


def _apply_anomaly_scoring(
    event: NormalizedEvent,
    scorer: AnomalyScorer,
    sqlite_store=None,
    anomaly_threshold: float = 0.7,
) -> NormalizedEvent:
    """Score event and learn from it. Mutates event.anomaly_score. Sync — called from asyncio.to_thread.

    When score > anomaly_threshold and sqlite_store is provided, creates a synthetic
    detection row (rule_id prefixed with 'anomaly-') so high-anomaly events surface
    in DetectionsView regardless of Sigma rules.
    """
    key = _anomaly_entity_key(event.src_ip or event.hostname, event.process_name)
    features = _extract_features(event)
    score = scorer.score_one(features, entity=key)
    scorer.learn_one(features, entity=key)
    scorer.save_model(key)
    event.anomaly_score = score

    # Synthetic detection for high-anomaly events (P42-T04)
    if score > anomaly_threshold and sqlite_store is not None:
        try:
            detection_id = str(_uuid4())
            key_str = f"{key[0]}__{key[1]}"
            severity = "high" if score > 0.85 else "medium"
            sqlite_store.insert_detection(
                detection_id,
                f"anomaly-{key_str}",
                f"Anomaly: {key[0]} / {key[1]} (score={score:.2f})",
                severity,
                [event.event_id],
                None,  # attack_technique
                None,  # attack_tactic
                f"Behavioral anomaly score {score:.2f} exceeds threshold {anomaly_threshold}",
                None,  # case_id
            )
        except Exception as exc:
            log.warning("Failed to create anomaly detection", error=str(exc))

    return event


@dataclass
class IngestionResult:
    """Summary of a completed ingestion run."""

    file_path: str
    parsed: int = 0
    loaded: int = 0
    embedded: int = 0
    edges_created: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    hayabusa_findings: int = 0  # Phase 48: Hayabusa threat hunting findings count
    chainsaw_findings: int = 0  # Phase 49: Chainsaw threat hunting findings count

    def __str__(self) -> str:
        return (
            f"IngestionResult(file={self.file_path!r}, "
            f"parsed={self.parsed}, loaded={self.loaded}, "
            f"embedded={self.embedded}, edges={self.edges_created}, "
            f"errors={len(self.errors)}, "
            f"duration={self.duration_seconds:.2f}s)"
        )


# ---------------------------------------------------------------------------
# Job tracker (in-memory, process-scoped)
# ---------------------------------------------------------------------------

_JOBS: dict[str, dict[str, Any]] = {}


def get_job_status(job_id: str) -> dict[str, Any] | None:
    return _JOBS.get(job_id)


def _set_job(
    job_id: str,
    status: str,
    result: IngestionResult | None = None,
    error: str | None = None,
    filename: str = "",
) -> None:
    _JOBS[job_id] = {
        "job_id": job_id,
        "status": status,
        "filename": filename,
        "result": {
            "parsed": result.parsed if result else 0,
            "loaded": result.loaded if result else 0,
            "embedded": result.embedded if result else 0,
            "edges_created": result.edges_created if result else 0,
            "errors": result.errors if result else [],
            "duration_seconds": result.duration_seconds if result else 0.0,
        } if result else None,
        "error": error,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Phase 48: Hayabusa EVTX scanning helper (sync — runs inside asyncio.to_thread)
# ---------------------------------------------------------------------------


def _run_hayabusa_scan(
    file_path: str,
    raw_sha256: str,
    case_id: str | None,
    stores,
) -> int:
    """Run Hayabusa against one EVTX file. Returns number of findings inserted.

    Checks hayabusa_scanned_files dedup table first; skips without subprocess if
    already scanned. Runs in asyncio.to_thread — must be purely synchronous.
    """
    sqlite = stores.sqlite
    if sqlite.is_already_scanned(raw_sha256):
        log.debug("Hayabusa scan skipped (already scanned)", file_path=file_path)
        return 0
    count = 0
    for rec in scan_evtx(file_path):
        det = hayabusa_record_to_detection(rec, file_path, case_id)
        sqlite.insert_detection(
            detection_id=det.id,
            rule_id=det.rule_id or "",
            rule_name=det.rule_name or "",
            severity=det.severity,
            matched_event_ids=det.matched_event_ids,
            attack_technique=det.attack_technique,
            attack_tactic=det.attack_tactic,
            explanation=det.explanation,
            case_id=det.case_id,
            detection_source="hayabusa",
        )
        count += 1
    sqlite.mark_scanned(raw_sha256, file_path, count)
    log.info("Hayabusa scan complete", file_path=file_path, findings=count)
    return count


# ---------------------------------------------------------------------------
# Phase 49: Chainsaw EVTX scanning helper (sync — runs inside asyncio.to_thread)
# ---------------------------------------------------------------------------


def _run_chainsaw_scan(
    file_path: str,
    raw_sha256: str,
    case_id: str | None,
    stores,
) -> int:
    """Run Chainsaw against one EVTX file. Returns number of findings inserted.

    Checks chainsaw_scanned_files dedup table first; skips without subprocess if
    already scanned. Runs in asyncio.to_thread — must be purely synchronous.
    """
    sqlite = stores.sqlite
    if sqlite.is_chainsaw_scanned(raw_sha256):
        log.debug("Chainsaw scan skipped (already scanned)", file_path=file_path)
        return 0
    count = 0
    for rec in chainsaw_scan_evtx(file_path):
        det = chainsaw_record_to_detection(rec, file_path, case_id)
        sqlite.insert_detection(
            detection_id=det.id,
            rule_id=det.rule_id or "",
            rule_name=det.rule_name or "",
            severity=det.severity,
            matched_event_ids=det.matched_event_ids,
            attack_technique=det.attack_technique,
            attack_tactic=det.attack_tactic,
            explanation=det.explanation,
            case_id=det.case_id,
            detection_source="chainsaw",
        )
        count += 1
    sqlite.mark_chainsaw_scanned(raw_sha256, file_path, count)
    log.info("Chainsaw scan complete", file_path=file_path, findings=count)
    return count


# ---------------------------------------------------------------------------
# IngestionLoader
# ---------------------------------------------------------------------------


class IngestionLoader:
    """
    Orchestrates the full ingestion pipeline for files and event batches.

    Args:
        stores:        Container holding DuckDB, Chroma, and SQLite stores.
        ollama_client: For generating text embeddings (non-fatal if offline).
    """

    def __init__(
        self,
        stores: Stores,
        ollama_client: OllamaClient,
        ioc_store: IocStore | None = None,
        asset_store: AssetStore | None = None,
        anomaly_scorer: AnomalyScorer | None = None,
        correlation_engine=None,
    ) -> None:
        self._stores = stores
        self._ollama = ollama_client
        self._ioc_store: IocStore | None = ioc_store
        self._asset_store: AssetStore | None = asset_store
        self._anomaly_scorer: AnomalyScorer | None = anomaly_scorer
        self._correlation_engine = correlation_engine

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ingest_file(
        self,
        file_path: str,
        case_id: str | None = None,
        job_id: str | None = None,
        operator_id: str | None = None,
    ) -> IngestionResult:
        """
        Full ingestion pipeline for a single file.

        1. Compute SHA-256 of raw file bytes
        2. Detect parser via registry
        3. Stream-parse → normalize → deduplicate → DuckDB INSERT
        4. Embed new events → Chroma
        5. Extract entities + edges → SQLite
        6. Record ingest provenance (non-fatal on failure)

        Args:
            file_path:   Path to the file on disk.
            case_id:     Optional investigation case.
            job_id:      Optional job ID for status tracking.
            operator_id: Optional operator performing the ingest.

        Returns:
            IngestionResult with counts and any errors.
        """
        t0 = time.monotonic()
        result = IngestionResult(file_path=file_path)

        if job_id:
            _set_job(job_id, "running")

        if not os.path.exists(file_path):
            msg = f"File not found: {file_path}"
            log.error(msg, file_path=file_path, job_id=job_id)
            result.errors.append(msg)
            if job_id:
                _set_job(job_id, "error", error=msg)
            result.duration_seconds = time.monotonic() - t0
            return result

        # Compute SHA-256 of raw file bytes before any parsing occurs
        raw_sha256 = await asyncio.to_thread(_sha256_file, file_path)

        parser = get_parser(file_path)
        if parser is None:
            msg = f"No parser found for file: {file_path}"
            log.error(msg, file_path=file_path)
            result.errors.append(msg)
            if job_id:
                _set_job(job_id, "error", error=msg)
            result.duration_seconds = time.monotonic() - t0
            return result

        parser_name = type(parser).__name__

        log.info(
            "Ingestion started",
            file_path=file_path,
            parser=parser_name,
            case_id=case_id,
            job_id=job_id,
        )

        # Stream-parse in a thread (parsers do blocking file I/O)
        try:
            raw_events: list[NormalizedEvent] = await asyncio.to_thread(
                self._stream_parse_all, parser, file_path, case_id
            )
        except Exception as exc:
            msg = f"Parse failed: {exc}"
            log.error(msg, file_path=file_path, error=str(exc))
            result.errors.append(msg)
            if job_id:
                _set_job(job_id, "error", error=msg)
            result.duration_seconds = time.monotonic() - t0
            return result

        result.parsed = len(raw_events)
        log.info(
            "Parsing complete",
            file_path=file_path,
            parsed=result.parsed,
        )

        # Normalize
        normalized: list[NormalizedEvent] = [normalize_event(e) for e in raw_events]

        # Ingest normalised events
        sub_result = await self.ingest_events(normalized)
        result.loaded = sub_result.loaded
        result.embedded = sub_result.embedded
        result.edges_created = sub_result.edges_created
        result.errors.extend(sub_result.errors)

        # Record ingest provenance (non-fatal — failure must not abort pipeline)
        if result.loaded > 0:
            try:
                prov_id = str(_uuid4())
                new_event_ids = [e.event_id for e in normalized]
                await asyncio.to_thread(
                    self._stores.sqlite.record_ingest_provenance,
                    prov_id,
                    raw_sha256,
                    file_path,
                    parser_name,
                    new_event_ids,
                    None,        # parser_version — no __version__ on parsers yet
                    operator_id,
                )
            except Exception as exc:
                log.warning(
                    "Ingest provenance write failed (non-fatal)", error=str(exc)
                )

        # Phase 48: Hayabusa EVTX threat hunting (non-fatal — failure must not abort pipeline)
        if _Path(file_path).suffix.lower() == ".evtx":
            try:
                result.hayabusa_findings = await asyncio.to_thread(
                    _run_hayabusa_scan, file_path, raw_sha256, case_id, self._stores
                )
            except Exception as exc:
                log.warning(
                    "Hayabusa scan failed (non-fatal)", file_path=file_path, error=str(exc)
                )

        # Phase 49: Chainsaw EVTX threat hunting (non-fatal — failure must not abort pipeline)
        if _Path(file_path).suffix.lower() == ".evtx":
            try:
                result.chainsaw_findings = await asyncio.to_thread(
                    _run_chainsaw_scan, file_path, raw_sha256, case_id, self._stores
                )
            except Exception as exc:
                log.warning(
                    "Chainsaw scan failed (non-fatal)", file_path=file_path, error=str(exc)
                )

        result.duration_seconds = time.monotonic() - t0
        log.info("Ingestion complete", **{
            "file_path": file_path,
            "parsed": result.parsed,
            "loaded": result.loaded,
            "embedded": result.embedded,
            "edges_created": result.edges_created,
            "errors": len(result.errors),
            "duration_seconds": round(result.duration_seconds, 2),
        })

        if job_id:
            _set_job(job_id, "complete", result=result)

        return result

    async def ingest_events(
        self,
        events: list[NormalizedEvent],
    ) -> IngestionResult:
        """
        Ingest a batch of already-parsed and normalised NormalizedEvent objects.

        Performs deduplication, DuckDB batch INSERT, Chroma embedding, and
        entity/edge extraction.

        Args:
            events: List of NormalizedEvent objects.  They should already be
                    normalised (run through normalizer.normalize_event()); this
                    method normalises them again cheaply as a safety measure.

        Returns:
            IngestionResult (file_path is set to "<batch>").
        """
        result = IngestionResult(file_path="<batch>")

        if not events:
            # Still run correlation engine even on empty batches so chain detection
            # can fire based on previously-stored SQLite detections.
            if self._correlation_engine is not None:
                try:
                    corr_detections = await self._correlation_engine.run()
                    if corr_detections:
                        await self._correlation_engine.save_detections(corr_detections)
                        log.debug(
                            "Correlation detections saved (empty batch)",
                            count=len(corr_detections),
                        )
                except Exception as exc:
                    log.warning("Correlation engine error (non-fatal)", error=str(exc))
            return result

        # Ensure normalisation
        events = [normalize_event(e) for e in events]

        # Phase 33: IOC matching + Phase 34: asset upsert + Phase 42: anomaly scoring
        # All are synchronous helpers called inside a single asyncio.to_thread block.
        ioc_store_ref = self._ioc_store
        asset_store_ref = self._asset_store
        anomaly_scorer_ref = self._anomaly_scorer
        sqlite_store_ref = self._stores.sqlite

        # Resolve ANOMALY_THRESHOLD from settings (fallback to 0.7 if unavailable)
        anomaly_threshold_val: float = 0.7
        try:
            from backend.core.config import settings as _settings
            anomaly_threshold_val = _settings.ANOMALY_THRESHOLD
        except Exception:
            pass

        if ioc_store_ref is not None or asset_store_ref is not None or anomaly_scorer_ref is not None:

            def _apply_enrichment_batch(evts: list[NormalizedEvent]) -> list[NormalizedEvent]:
                result: list[NormalizedEvent] = []
                for e in evts:
                    if ioc_store_ref is not None:
                        e = _apply_ioc_matching(e, ioc_store_ref)
                    if asset_store_ref is not None:
                        _apply_asset_upsert(e, asset_store_ref)
                    if anomaly_scorer_ref is not None:
                        e = _apply_anomaly_scoring(
                            e, anomaly_scorer_ref,
                            sqlite_store=sqlite_store_ref,
                            anomaly_threshold=anomaly_threshold_val,
                        )
                    result.append(e)
                return result

            events = await asyncio.to_thread(_apply_enrichment_batch, events)

        # Step 1: Deduplicate against DuckDB
        new_events = await self._deduplicate(events)
        log.debug(
            "Deduplication complete",
            total=len(events),
            new=len(new_events),
            duplicates=len(events) - len(new_events),
        )

        if not new_events:
            return result

        # Step 2: Batch INSERT to DuckDB
        loaded, load_errors = await self._batch_insert_duckdb(new_events)
        result.loaded = loaded
        result.errors.extend(load_errors)

        # Events that actually made it into DuckDB
        stored_events = new_events[:loaded] if loaded < len(new_events) else new_events

        # Step 3: Batch embed to Chroma — fire as background task so DuckDB write
        # latency is not held hostage by Ollama embed time during bulk backfill.
        # Chroma embeds will complete asynchronously; result.embedded stays 0 for
        # fire-and-forget batches which is acceptable (DuckDB is the source of truth).
        async def _fire_embed(evts: list) -> None:
            try:
                await self._batch_embed_chroma(evts)
            except Exception as _exc:
                pass  # embed errors already logged inside _batch_embed_chroma

        asyncio.create_task(_fire_embed(stored_events))
        result.embedded = len(stored_events)  # optimistic count

        # Step 4: Extract entities + edges → SQLite
        edges_created, graph_errors = await self._write_graph(stored_events)
        result.edges_created = edges_created
        result.errors.extend(graph_errors)

        # Step 5: Correlation detection (Phase 43)
        if self._correlation_engine is not None:
            try:
                corr_detections = await self._correlation_engine.run()
                if corr_detections:
                    await self._correlation_engine.save_detections(corr_detections)
                    log.debug(
                        "Correlation detections saved",
                        count=len(corr_detections),
                    )
            except Exception as exc:
                log.warning("Correlation engine error (non-fatal)", error=str(exc))

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _stream_parse_all(
        parser: Any,
        file_path: str,
        case_id: str | None,
    ) -> list[NormalizedEvent]:
        """Collect all events from the parser generator (runs in thread)."""
        return list(parser.parse(file_path, case_id=case_id))

    async def _deduplicate(
        self, events: list[NormalizedEvent]
    ) -> list[NormalizedEvent]:
        """
        Return only events whose event_id is NOT already in DuckDB.

        Uses a single batched query for efficiency.
        """
        if not events:
            return []

        ids = [e.event_id for e in events]

        # Build a multi-value IN query
        placeholders = ",".join("?" * len(ids))
        check_sql = f"SELECT event_id FROM normalized_events WHERE event_id IN ({placeholders})"

        try:
            existing_rows = await self._stores.duckdb.fetch_all(check_sql, ids)
            existing_ids: set[str] = {row[0] for row in existing_rows}
        except Exception as exc:
            log.warning(
                "Deduplication query failed — treating all events as new",
                error=str(exc),
            )
            existing_ids = set()

        return [e for e in events if e.event_id not in existing_ids]

    async def _batch_insert_duckdb(
        self, events: list[NormalizedEvent]
    ) -> tuple[int, list[str]]:
        """
        Insert events into DuckDB in batches of _DUCKDB_BATCH.

        Returns (loaded_count, error_messages).
        """
        loaded = 0
        errors: list[str] = []

        for i in range(0, len(events), _DUCKDB_BATCH):
            batch = events[i : i + _DUCKDB_BATCH]
            # All 35 columns — _INSERT_SQL now includes the 6 new ECS/OCSF columns.
            rows = [list(e.to_duckdb_row()) for e in batch]

            try:
                # DuckDB executemany goes through the write queue
                # Use multiple single inserts via the write worker
                for row in rows:
                    await self._stores.duckdb.execute_write(_INSERT_SQL, row)
                loaded += len(batch)
                log.debug(
                    "DuckDB batch inserted",
                    batch_start=i,
                    batch_size=len(batch),
                )
            except Exception as exc:
                msg = f"DuckDB batch insert error (batch {i}): {exc}"
                log.error(msg, batch_start=i, error=str(exc))
                errors.append(msg)

        return loaded, errors

    async def _batch_embed_chroma(
        self, events: list[NormalizedEvent]
    ) -> tuple[int, list[str]]:
        """
        Generate embeddings and upsert into Chroma in batches of _CHROMA_BATCH.

        Events with empty embedding text are skipped.
        Already-present IDs are handled via upsert (Chroma deduplicates).

        Returns (embedded_count, error_messages).
        """
        embedded = 0
        errors: list[str] = []

        for i in range(0, len(events), _CHROMA_BATCH):
            batch = events[i : i + _CHROMA_BATCH]

            # Filter events with non-empty embedding text
            embeddable = [(e, e.to_embedding_text()) for e in batch]
            embeddable = [(e, txt) for e, txt in embeddable if txt.strip()]

            if not embeddable:
                continue

            batch_texts = [txt for _, txt in embeddable]

            try:
                embeddings = await self._ollama.embed_batch(batch_texts)
                # Filter out empty embeddings (Ollama may return [] on error)
                valid: list[tuple[NormalizedEvent, str, list[float]]] = [
                    (e, txt, emb)
                    for (e, txt), emb in zip(embeddable, embeddings)
                    if emb
                ]

                if valid:
                    ids = [e.event_id for e, _, _ in valid]
                    docs = [txt for _, txt, _ in valid]
                    vecs = [emb for _, _, emb in valid]
                    metadatas = [
                        {
                            "event_id": e.event_id,
                            "event_type": e.event_type or "",
                            "hostname": e.hostname or "",
                            "severity": e.severity or "",
                            "case_id": e.case_id or "",
                        }
                        for e, _, _ in valid
                    ]
                    await self._stores.chroma.add_documents_async(
                        collection_name=DEFAULT_COLLECTION,
                        ids=ids,
                        documents=docs,
                        embeddings=vecs,
                        metadatas=metadatas,
                    )
                    embedded += len(valid)
                    log.debug(
                        "Chroma batch embedded",
                        batch_start=i,
                        embedded=len(valid),
                    )
            except Exception as exc:
                msg = f"Chroma embed batch error (batch {i}): {exc}"
                log.warning(msg, batch_start=i, error=str(exc))
                errors.append(msg)

        return embedded, errors

    async def _write_graph(
        self, events: list[NormalizedEvent]
    ) -> tuple[int, list[str]]:
        """
        Extract entities and edges from events and write to SQLite.

        Returns (edges_created_count, error_messages).
        """
        edges_created = 0
        errors: list[str] = []

        def _sync_write_graph() -> tuple[int, list[str]]:
            local_edges = 0
            local_errors: list[str] = []
            sqlite = self._stores.sqlite

            for event in events:
                try:
                    entity_list, edge_list = extract_entities_and_edges(event)

                    for entity in entity_list:
                        attrs = entity.get("attributes") or {}
                        sqlite.upsert_entity(
                            entity_id=entity["id"],
                            entity_type=entity["type"],
                            name=entity["name"],
                            attributes=attrs,
                            case_id=entity.get("case_id"),
                        )

                    for edge in edge_list:
                        result = sqlite.insert_edge(
                            source_type=edge["source_type"],
                            source_id=edge["source_id"],
                            edge_type=edge["edge_type"],
                            target_type=edge["target_type"],
                            target_id=edge["target_id"],
                            properties=edge.get("properties"),
                        )
                        if result is not None:
                            local_edges += 1

                    # Perimeter entities/edges for IPFire syslog events (Phase 26 — P26-T03)
                    if event.source_type == "ipfire_syslog":
                        perim_entities, perim_edges = extract_perimeter_entities(event)

                        for entity in perim_entities:
                            attrs = entity.get("attributes") or {}
                            sqlite.upsert_entity(
                                entity_id=entity["id"],
                                entity_type=entity["type"],
                                name=entity["name"],
                                attributes=attrs,
                                case_id=entity.get("case_id"),
                            )

                        for edge in perim_edges:
                            result = sqlite.insert_edge(
                                source_type=edge["source_type"],
                                source_id=edge["source_id"],
                                edge_type=edge["edge_type"],
                                target_type=edge["target_type"],
                                target_id=edge["target_id"],
                                properties=edge.get("properties"),
                            )
                            if result is not None:
                                local_edges += 1

                except Exception as exc:
                    msg = f"Graph write error for event {event.event_id}: {exc}"
                    local_errors.append(msg)
                    log.warning(msg, event_id=event.event_id, error=str(exc))

            return local_edges, local_errors

        try:
            edges_created, errors = await asyncio.to_thread(_sync_write_graph)
        except Exception as exc:
            msg = f"Graph write thread error: {exc}"
            log.error(msg, error=str(exc))
            errors.append(msg)

        return edges_created, errors


# ---------------------------------------------------------------------------
# EventIngester — alias for IngestionLoader with ioc_store parameter
# ---------------------------------------------------------------------------

#: EventIngester is the Phase 33 name for the IngestionLoader.
#: It accepts an optional ioc_store parameter (added to IngestionLoader.__init__)
#: for at-ingest IOC matching. Use it anywhere you need IOC-aware ingestion.
EventIngester = IngestionLoader
