"""
backend.startup.stores — Store and service initialisation.

Called once during the FastAPI lifespan startup.  All app.state.* assignments
that relate to stores and persistent services happen here.

Returns the Stores container so callers can reference it for workers/collectors.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from backend.core.config import Settings
from backend.core.deps import Stores
from backend.core.logging import get_logger
from backend.services.attack.asset_store import AssetStore
from backend.services.attack.attack_store import AttackStore
from backend.services.intel.feed_sync import (
    CisaKevWorker,
    FeodoWorker,
    MispWorker,
    ThreatFoxWorker,
)
from backend.services.intel.ioc_store import IocStore
from backend.services.ollama_client import OllamaClient
from backend.stores.chroma_store import ChromaStore
from backend.stores.duckdb_store import DuckDBStore
from backend.stores.sqlite_store import SQLiteStore

if TYPE_CHECKING:
    from fastapi import FastAPI

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# ATT&CK STIX bootstrap (helper used by init_stores)
# ---------------------------------------------------------------------------

_STIX_URL = (
    "https://raw.githubusercontent.com/mitre-attack/attack-stix-data"
    "/master/enterprise-attack/enterprise-attack.json"
)


async def bootstrap_attack_data(attack_store: AttackStore) -> None:
    """Download and parse MITRE ATT&CK STIX bundle at startup.

    Skips download if techniques are already seeded (idempotent).
    Failures are non-fatal — logged as warnings only.
    """
    count = await asyncio.to_thread(attack_store.technique_count)
    if count > 0:
        log.info(
            "ATT&CK data already seeded (%d techniques) — skipping download", count
        )
        return
    try:
        import httpx

        async with httpx.AsyncClient() as client:
            log.info("Downloading ATT&CK STIX bundle from GitHub...")
            resp = await client.get(_STIX_URL, timeout=60.0)
            resp.raise_for_status()
            bundle = resp.json()
        await asyncio.to_thread(attack_store.bootstrap_from_objects, bundle["objects"])
        count = await asyncio.to_thread(attack_store.technique_count)
        log.info("ATT&CK bootstrap complete: %d techniques loaded", count)
    except Exception as exc:
        log.warning("ATT&CK STIX bootstrap failed (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def init_stores(app: "FastAPI", settings: Settings) -> Stores:
    """Initialise all data stores and attached services; set app.state attributes.

    Startup order:
      1. DuckDB — start write worker FIRST, then initialise schema
      2. Chroma — default collections + feedback_verdicts
      3. SQLite — admin bootstrap + playbook seeding
      4. Stores container
      5. OllamaClient + model digest verification
      6. IocStore + feed workers (Phase 33)
      7. AssetStore / AttackStore / STIX bootstrap (Phase 34)
      8. CARStore + seed (Phase 39)
      9. AtomicsStore + seed (Phase 40)
     10. AnomalyScorer (Phase 42)
     11. CorrelationEngine (Phase 43)
     12. FeedbackClassifier (Phase 44)
     13. OsintInvestigationStore (Phase 51)
     14. TheHive client + APScheduler (Phase 52)
     15. Privacy blocklist store (Phase 53)

    Returns the Stores container.
    """
    # ------------------------------------------------------------------
    # 1. DuckDB — write worker MUST start before initialise_schema()
    # ------------------------------------------------------------------
    duckdb_store = DuckDBStore(data_dir=settings.DATA_DIR)
    write_worker_task = duckdb_store.start_write_worker()
    log.info("DuckDB write worker started")
    await duckdb_store.initialise_schema()

    # ------------------------------------------------------------------
    # 2. Chroma store
    # ------------------------------------------------------------------
    chroma_store = ChromaStore(
        data_dir=settings.DATA_DIR,
        chroma_url=settings.CHROMA_URL,
        chroma_token=settings.CHROMA_TOKEN,
    )
    await chroma_store.initialise_default_collections(embed_model=settings.OLLAMA_EMBED_MODEL)

    # Phase 44: feedback_verdicts collection for k-NN similar incident retrieval
    try:
        await chroma_store.get_or_create_collection_async(
            "feedback_verdicts",
            metadata={"embed_model": settings.OLLAMA_EMBED_MODEL, "hnsw:space": "cosine"},
        )
        log.info("feedback_verdicts Chroma collection ready (Phase 44)")
    except Exception as exc:
        log.warning("feedback_verdicts Chroma collection init failed (non-fatal): %s", exc)

    # ------------------------------------------------------------------
    # 3. SQLite store
    # ------------------------------------------------------------------
    sqlite_store = SQLiteStore(data_dir=settings.DATA_DIR)

    # Bootstrap legacy admin operator if operators table is empty
    sqlite_store.bootstrap_admin_if_empty(auth_token=settings.AUTH_TOKEN)
    log.info("Operator bootstrap complete")

    # Seed built-in playbooks (idempotent — no-op if already seeded)
    try:
        from backend.api.playbooks import seed_builtin_playbooks
        await seed_builtin_playbooks(sqlite_store)
    except Exception as exc:  # pragma: no cover
        log.warning("Built-in playbook seeding failed — continuing: %s", exc)

    # ------------------------------------------------------------------
    # 4. Stores container
    # ------------------------------------------------------------------
    stores = Stores(
        duckdb=duckdb_store,
        chroma=chroma_store,
        sqlite=sqlite_store,
    )

    # ------------------------------------------------------------------
    # 5. OllamaClient + model digest verification (E6-03)
    # ------------------------------------------------------------------
    ollama = OllamaClient(
        base_url=settings.OLLAMA_HOST,
        model=settings.OLLAMA_MODEL,
        embed_model=settings.OLLAMA_EMBED_MODEL,
        cybersec_model=settings.OLLAMA_CYBERSEC_MODEL,
        duckdb_store=duckdb_store,
        sqlite_store=sqlite_store,
    )

    if settings.OLLAMA_MODEL_DIGEST or settings.OLLAMA_EMBEDDING_DIGEST:
        log.info("Running Ollama model digest verification (E6-03)")
    # Always run for the primary model so the digest is always logged.
    if settings.OLLAMA_MODEL_DIGEST or not settings.OLLAMA_MODEL_DIGEST:
        await ollama.verify_model_digest(
            model_name=settings.OLLAMA_MODEL,
            expected_digest_prefix=settings.OLLAMA_MODEL_DIGEST,
            enforce=settings.OLLAMA_ENFORCE_DIGEST,
        )
    if settings.OLLAMA_EMBEDDING_DIGEST:
        await ollama.verify_model_digest(
            model_name=settings.OLLAMA_EMBED_MODEL,
            expected_digest_prefix=settings.OLLAMA_EMBEDDING_DIGEST,
            enforce=settings.OLLAMA_ENFORCE_DIGEST,
        )

    # Attach core handles to app.state
    app.state.settings = settings
    app.state.stores = stores
    app.state.ollama = ollama

    # Keep a reference to the write worker task on app.state so the lifespan
    # shutdown sequence can cancel it.
    app.state._duckdb_write_worker_task = write_worker_task

    # ------------------------------------------------------------------
    # 6. Phase 33: Threat Intelligence — IocStore + feed workers
    # ------------------------------------------------------------------
    ioc_store = IocStore(sqlite_store._conn)
    feodo_worker = FeodoWorker(ioc_store, sqlite_store._conn, duckdb_store=duckdb_store)
    cisa_kev_worker = CisaKevWorker(ioc_store, sqlite_store._conn, duckdb_store=duckdb_store)
    threatfox_worker = ThreatFoxWorker(ioc_store, sqlite_store._conn, duckdb_store=duckdb_store)
    misp_worker = MispWorker(
        ioc_store,
        sqlite_store._conn,
        interval_sec=settings.MISP_SYNC_INTERVAL_SEC,
        duckdb_store=duckdb_store,
        misp_url=settings.MISP_URL,
        misp_key=settings.MISP_KEY,
        misp_ssl=settings.MISP_SSL_VERIFY,
        last_hours=settings.MISP_SYNC_LAST_HOURS,
    )

    asyncio.ensure_future(feodo_worker.run())
    asyncio.ensure_future(cisa_kev_worker.run())
    asyncio.ensure_future(threatfox_worker.run())
    if settings.MISP_ENABLED:
        asyncio.create_task(misp_worker.run(), name="misp_worker")

    app.state.ioc_store = ioc_store
    log.info("Phase 33 feed workers registered (Feodo, CISA KEV, ThreatFox, MISP=%s)", settings.MISP_ENABLED)

    # CRITICAL (P33-T06): Wire ioc_store into EventIngester for at-ingest IOC matching.
    app.state._ioc_store_for_ingester = ioc_store

    # ------------------------------------------------------------------
    # 7. Phase 34: AssetStore / AttackStore / STIX bootstrap
    # ------------------------------------------------------------------
    asset_store = AssetStore(sqlite_store._conn)
    app.state.asset_store = asset_store
    log.info("AssetStore initialised (Phase 34)")

    attack_store = AttackStore(sqlite_store._conn)
    app.state.attack_store = attack_store
    log.info("AttackStore initialised (Phase 34)")

    asyncio.ensure_future(bootstrap_attack_data(attack_store))
    log.info("ATT&CK STIX bootstrap task scheduled (Phase 34)")

    # ------------------------------------------------------------------
    # 8. Phase 39: CARStore
    # ------------------------------------------------------------------
    from backend.services.car.car_store import CARStore, seed_car_analytics
    car_store = CARStore(sqlite_store._conn)
    app.state.car_store = car_store
    log.info("CARStore initialised (Phase 39)")
    asyncio.ensure_future(seed_car_analytics(car_store))
    log.info("CAR analytics seed task scheduled (Phase 39)")

    # ------------------------------------------------------------------
    # 9. Phase 40: AtomicsStore
    # ------------------------------------------------------------------
    from backend.services.atomics.atomics_store import AtomicsStore, seed_atomics
    atomics_store = AtomicsStore(sqlite_store._conn)
    app.state.atomics_store = atomics_store
    log.info("AtomicsStore initialised (Phase 40)")
    asyncio.ensure_future(seed_atomics(atomics_store))
    log.info("Atomics seed task scheduled (Phase 40)")

    # ------------------------------------------------------------------
    # 10. Phase 42: AnomalyScorer
    # ------------------------------------------------------------------
    try:
        from backend.services.anomaly.scorer import AnomalyScorer as _AnomalyScorer
        _anomaly_scorer = _AnomalyScorer(model_dir=settings.ANOMALY_MODEL_DIR)
        app.state.anomaly_scorer = _anomaly_scorer
        app.state._anomaly_scorer_for_ingester = _anomaly_scorer
        log.info("AnomalyScorer initialised (Phase 42)", model_dir=settings.ANOMALY_MODEL_DIR)
    except Exception as exc:
        log.warning("AnomalyScorer failed to initialise — anomaly scoring disabled: %s", exc)
        app.state.anomaly_scorer = None
        app.state._anomaly_scorer_for_ingester = None

    # ------------------------------------------------------------------
    # 11. Phase 43: CorrelationEngine
    # ------------------------------------------------------------------
    try:
        from detections.correlation_engine import CorrelationEngine as _CorrelationEngine
        from pathlib import Path as _CEPath
        _correlation_engine = _CorrelationEngine(stores=stores)
        app.state.correlation_engine = _correlation_engine
        app.state._correlation_engine_for_ingester = _correlation_engine
        _chains_path = _CEPath(__file__).parent.parent.parent / "detections" / "correlation_chains.yml"
        if _chains_path.exists():
            _chain_count = _correlation_engine.load_chains(str(_chains_path))
            log.info("Correlation chains loaded (Phase 43)", count=_chain_count)
        log.info("CorrelationEngine initialised (Phase 43)")
    except Exception as exc:
        log.warning("CorrelationEngine failed to initialise — correlation detection disabled: %s", exc)
        app.state.correlation_engine = None
        app.state._correlation_engine_for_ingester = None

    # ------------------------------------------------------------------
    # 12. Phase 44: FeedbackClassifier
    # ------------------------------------------------------------------
    try:
        from backend.services.feedback.classifier import FeedbackClassifier as _FeedbackClassifier
        app.state.feedback_classifier = _FeedbackClassifier()
        app.state.feedback_classifier.load()
        log.info("FeedbackClassifier loaded (Phase 44)", n_samples=app.state.feedback_classifier.n_samples)
    except Exception as exc:
        log.warning("FeedbackClassifier init failed — feedback scoring disabled: %s", exc)
        app.state.feedback_classifier = None

    # ------------------------------------------------------------------
    # 13. Phase 51: OSINT investigation store
    # ------------------------------------------------------------------
    try:
        from backend.services.osint_investigation_store import OsintInvestigationStore
        osint_store = OsintInvestigationStore(sqlite_store._conn)
        app.state.osint_store = osint_store
        log.info("osint_investigation_store ready")
    except Exception as exc:
        log.warning("osint_investigation_store init failed", error=str(exc))
        app.state.osint_store = None

    # ------------------------------------------------------------------
    # 14. Phase 52: TheHive client + APScheduler
    # ------------------------------------------------------------------
    _thehive_scheduler = None
    try:
        if settings.THEHIVE_ENABLED:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler as _AsyncIOScheduler
            from backend.services.thehive_client import TheHiveClient as _TheHiveClient
            from backend.services.thehive_sync import sync_thehive_closures, drain_pending_cases
            from datetime import timedelta as _timedelta
            from datetime import datetime as _datetime
            _thehive_client = _TheHiveClient(url=settings.THEHIVE_URL, api_key=settings.THEHIVE_API_KEY)
            app.state.thehive_client = _thehive_client
            _thehive_scheduler = _AsyncIOScheduler()
            _thehive_scheduler.add_job(
                lambda: sync_thehive_closures(_thehive_client, sqlite_store._conn),
                "interval",
                seconds=300,
                id="thehive_sync",
            )
            _thehive_scheduler.add_job(
                lambda: drain_pending_cases(_thehive_client, sqlite_store._conn),
                "interval",
                seconds=300,
                start_date=_datetime.now() + _timedelta(seconds=30),
                id="thehive_drain",
            )
            _thehive_scheduler.start()
            log.info("TheHive client + APScheduler sync jobs started (300s interval)")
        else:
            app.state.thehive_client = None
            log.info("TheHive disabled (THEHIVE_ENABLED=False)")
    except Exception as exc:
        app.state.thehive_client = None
        log.warning("TheHive setup failed (non-fatal): %s", exc)

    # Store scheduler on app.state for shutdown
    app.state._thehive_scheduler = _thehive_scheduler

    # ------------------------------------------------------------------
    # 15. Phase 53: Privacy blocklist store + worker + scan loop
    # ------------------------------------------------------------------
    try:
        from backend.services.intel.privacy_blocklist import (
            PrivacyBlocklistStore as _PrivacyBlocklistStore,
            PrivacyWorker as _PrivacyWorker,
        )
        if settings.PRIVACY_ENABLED:
            app.state.privacy_store = _PrivacyBlocklistStore(sqlite_store._conn)
            _privacy_worker = _PrivacyWorker(
                app.state.privacy_store,
                interval_sec=settings.PRIVACY_BLOCKLIST_REFRESH_INTERVAL_SEC,
            )
            asyncio.create_task(_privacy_worker.run())
            from backend.api.privacy import _privacy_scan_loop as _priv_loop
            asyncio.create_task(_priv_loop(app, interval_sec=300))
            log.info("Privacy blocklist store + worker + scan loop started (Phase 53)")
        else:
            app.state.privacy_store = None
            log.info("Privacy monitoring disabled (PRIVACY_ENABLED=False)")
    except Exception as _exc:
        log.warning("Phase 53 privacy store init failed (non-fatal): %s", _exc)
        app.state.privacy_store = None

    log.info("All stores and services initialised")
    return stores
