"""Concurrency regressions: quota counter and cross-source dedup."""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core import db
from app.core.config import settings
from app.models.catalog import RawEvent
from app.repositories.quota import try_consume, used
from app.repositories import store


@pytest.fixture(autouse=True)
def _clean_catalog(database_url):
    with db.get_conn(database_url) as conn:
        conn.execute(
            "TRUNCATE event_sources, screenings, collected_events, source_runs,"
            " collected_venues, api_quota, twogis_rubrics, collector_kv")
        conn.commit()
    yield
    with db.get_conn(database_url) as conn:
        conn.execute(
            "TRUNCATE event_sources, screenings, collected_events, source_runs,"
            " collected_venues, api_quota, twogis_rubrics, collector_kv")
        conn.commit()


def _consume(url: str, provider: str, month: str, cap: int, reserve: int) -> bool:
    with db.get_conn(url) as conn:
        ok = try_consume(conn, provider, month, cap, reserve)
        conn.commit()
        return ok


def test_quota_never_exceeds_cap_under_parallel_requests(database_url):
    provider = f"test-{uuid4()}"
    month = "2026-11"
    workers = 24
    barrier = threading.Barrier(workers)

    def worker() -> bool:
        barrier.wait(timeout=10)
        return _consume(database_url, provider, month, cap=5, reserve=0)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda _: worker(), range(workers)))

    with db.get_conn(database_url) as conn:
        consumed = used(conn, provider, month)
    assert consumed <= 5
    assert sum(results) == consumed


def _insert_duplicate(url: str, source: str, source_id: str, title: str,
                      start: datetime) -> None:
    with db.get_conn(url) as conn:
        from app.repositories import store as store_module
        store_module.upsert_events(conn, [RawEvent(
            source=source, source_id=source_id,
            source_url=f"https://example.com/{source_id}",
            title=title, start_at=start, venue_name="Дворец спорта",
            category="concert", city=settings.default_city,
        )])
        conn.commit()


def test_parallel_cross_source_duplicates_merge_into_one_event(
        database_url, monkeypatch):
    start = datetime(2026, 12, 16, 19, tzinfo=timezone.utc)
    original = store._fuzzy_twin

    def slow_fuzzy(conn, event):
        # Widen the window between candidate lookup and insert.
        time.sleep(0.2)
        return original(conn, event)

    monkeypatch.setattr(store, "_fuzzy_twin", slow_fuzzy)

    barrier = threading.Barrier(2)

    def worker(args):
        source, source_id, title = args
        barrier.wait(timeout=10)
        _insert_duplicate(database_url, source, source_id, title, start)

    jobs = [("telegram", "tg-race", "Кипелов"),
            ("ticketpro", "tp-race", "Концерт «Кипелов»")]
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(worker, jobs))

    with db.get_conn(database_url) as conn:
        rows = conn.execute("SELECT id, title FROM collected_events").fetchall()
        sources = conn.execute(
            "SELECT source FROM event_sources ORDER BY source").fetchall()
    assert len(rows) == 1, rows
    assert [row["source"] for row in sources] == ["telegram", "ticketpro"]
