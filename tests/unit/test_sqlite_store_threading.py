"""Concurrency tests for SQLiteStore's shared-connection lock.

SQLiteStore shares one sqlite3 connection (check_same_thread=False) across the
asyncio.to_thread worker pool.  These tests hammer it from many threads through
public methods and assert no errors and consistent results.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.stores.sqlite_store import SQLiteStore

N_THREADS = 8
OPS_PER_THREAD = 60


@pytest.fixture()
def store(tmp_path):
    s = SQLiteStore(str(tmp_path))
    yield s
    s.close()


def _worker(store: SQLiteStore, tid: int, barrier: threading.Barrier) -> None:
    barrier.wait()
    for i in range(OPS_PER_THREAD):
        det_id = f"det-{tid}-{i}"
        store.insert_detection(
            detection_id=det_id,
            rule_id=f"rule-{tid}",
            rule_name="threading test",
            severity="high",
            matched_event_ids=[f"evt-{tid}-{i}"],
        )
        got = store.get_detection(det_id)
        assert got is not None and got["id"] == det_id

        ip = f"10.{tid}.{i // 250}.{i % 250}"
        store.set_osint_cache(ip, '{"ok": true}', "2026-01-01T00:00:00Z", "2099-01-01T00:00:00Z")
        cached = store.get_osint_cache(ip)
        assert cached is not None and cached["ip"] == ip

        store.upsert_feedback(det_id, "TP" if i % 2 == 0 else "FP")
        store.set_kv(f"k-{tid}", str(i))
        store.get_feedback_stats()
        store.health_check()


def test_concurrent_mixed_reads_and_writes(store):
    barrier = threading.Barrier(N_THREADS)
    with ThreadPoolExecutor(max_workers=N_THREADS) as pool:
        futures = [pool.submit(_worker, store, t, barrier) for t in range(N_THREADS)]
        for f in futures:
            f.result()  # re-raises any worker exception

    total = N_THREADS * OPS_PER_THREAD
    assert len(store.list_detections()) == total
    assert store.health_check()["detection_count"] == total
    stats = store.get_feedback_stats()
    assert stats["verdicts_given"] == total
    for t in range(N_THREADS):
        assert store.get_kv(f"k-{t}") == str(OPS_PER_THREAD - 1)
    assert store._conn.in_transaction is False


def test_busy_timeout_pragma_set(store):
    with store.locked_conn() as conn:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_locked_conn_blocks_other_threads(store):
    """While one thread holds locked_conn(), store methods in other threads wait."""
    entered = threading.Event()
    release = threading.Event()
    done = threading.Event()

    def holder():
        with store.locked_conn():
            entered.set()
            release.wait(5)

    def writer():
        store.set_kv("blocked", "yes")
        done.set()

    t1 = threading.Thread(target=holder)
    t1.start()
    assert entered.wait(5)
    t2 = threading.Thread(target=writer)
    t2.start()
    assert not done.wait(0.3), "method ran while another thread held the lock"
    release.set()
    t1.join(5)
    t2.join(5)
    assert done.is_set()
    assert store.get_kv("blocked") == "yes"


def test_failed_call_rolls_back_open_transaction(store):
    """A method that raises mid-transaction must not leave writes pending."""

    def boom(self):
        self._conn.execute("INSERT INTO system_kv (key, value, updated_at) VALUES ('leak', 'x', 'now')")
        raise RuntimeError("fail after write")

    from backend.stores.sqlite_store import _synchronized

    bad = _synchronized(boom)
    with pytest.raises(RuntimeError):
        bad(store)
    assert store._conn.in_transaction is False
    store.set_kv("other", "1")  # commits — must not carry the leaked row
    assert store.get_kv("leak") is None
