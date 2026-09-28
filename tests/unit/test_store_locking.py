"""Concurrency tests: service stores sharing SQLiteStore's locked connection.

Multi-statement sequences (SELECT-then-write, execute … commit) must run under
conn_lock() so threads cannot interleave on the single shared connection.
"""
from __future__ import annotations

import sqlite3
import threading

from backend.services.attack.asset_store import AssetStore
from backend.services.intel.ioc_store import IocStore
from backend.stores.sqlite_store import SQLiteStore, conn_lock

N_THREADS = 8
PER_THREAD = 50


def _run_threads(target) -> list[BaseException]:
    errors: list[BaseException] = []
    barrier = threading.Barrier(N_THREADS)

    def worker(tid: int) -> None:
        try:
            barrier.wait()
            target(tid)
        except BaseException as exc:  # noqa: BLE001 - collected for assertion
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not any(t.is_alive() for t in threads), "worker thread hung"
    return errors


def test_ioc_upsert_concurrent_threads(tmp_path) -> None:
    store = SQLiteStore(str(tmp_path))
    iocs = IocStore(store._conn)
    inserted: list[bool] = []
    inserted_lock = threading.Lock()

    def target(tid: int) -> None:
        for i in range(PER_THREAD):
            # Unique IOC per (thread, i) plus one shared IOC per i that every
            # thread races to upsert (SELECT-then-INSERT/UPDATE).
            new = iocs.upsert_ioc(
                value=f"10.{tid}.0.{i}", ioc_type="ip", confidence=50,
                first_seen=None, last_seen=None, malware_family=None,
                actor_tag=None, feed_source="feodo", extra_json=None,
            )
            shared_new = iocs.upsert_ioc(
                value=f"192.0.2.{i}", ioc_type="ip", confidence=60,
                first_seen=None, last_seen=None, malware_family=None,
                actor_tag=None, feed_source="threatfox", extra_json=None,
            )
            iocs._record_hit(
                "2026-01-01T00:00:00Z", f"host{tid}", f"10.{tid}.0.{i}", None,
                f"10.{tid}.0.{i}", "ip", "feodo", 50, None, None,
            )
            with inserted_lock:
                inserted.append(new)
                if shared_new:
                    inserted.append(shared_new)

    errors = _run_threads(target)
    assert errors == []

    total = store._conn.execute("SELECT COUNT(*) FROM ioc_store").fetchone()[0]
    assert total == N_THREADS * PER_THREAD + PER_THREAD
    hits = store._conn.execute("SELECT COUNT(*) FROM ioc_hits").fetchone()[0]
    assert hits == N_THREADS * PER_THREAD
    # Each shared IOC reported as "new" exactly once across all threads.
    assert sum(inserted) == N_THREADS * PER_THREAD + PER_THREAD
    assert not store._conn.in_transaction


def test_ioc_decay_concurrent_with_upserts(tmp_path) -> None:
    store = SQLiteStore(str(tmp_path))
    iocs = IocStore(store._conn)

    def target(tid: int) -> None:
        for i in range(PER_THREAD):
            if tid % 2:
                iocs.decay_confidence()
            else:
                iocs.upsert_ioc(
                    value=f"10.{tid}.1.{i}", ioc_type="ip", confidence=90,
                    first_seen=None, last_seen=None, malware_family=None,
                    actor_tag=None, feed_source="feodo", extra_json=None,
                )

    assert _run_threads(target) == []
    total = store._conn.execute("SELECT COUNT(*) FROM ioc_store").fetchone()[0]
    assert total == (N_THREADS // 2) * PER_THREAD
    assert not store._conn.in_transaction


def test_asset_upsert_concurrent_threads(tmp_path) -> None:
    store = SQLiteStore(str(tmp_path))
    assets = AssetStore(store._conn)

    def target(tid: int) -> None:
        for i in range(PER_THREAD):
            assets.upsert_asset(f"10.{tid}.2.{i}", None, "internal", "2026-01-01T00:00:00Z")
            assets.set_tag(f"10.{tid}.2.{i}", "server")

    assert _run_threads(target) == []
    assert assets.asset_count() == N_THREADS * PER_THREAD
    tagged = store._conn.execute(
        "SELECT COUNT(*) FROM assets WHERE tag='server'"
    ).fetchone()[0]
    assert tagged == N_THREADS * PER_THREAD


def test_conn_lock_is_noop_for_plain_connection() -> None:
    conn = sqlite3.connect(":memory:")
    with conn_lock(conn):
        conn.execute("SELECT 1")
    conn.close()
