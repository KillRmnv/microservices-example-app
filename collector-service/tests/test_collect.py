"""Adapter integration tests against a real Postgres.

Needs COLLECTOR_TEST_DATABASE_URL (default: local postgres/postgres db).
Skips when no database is reachable, so plain `pytest` stays green.
Uses httpx.MockTransport — no external network.
"""
from pathlib import Path

import httpx
import psycopg
import pytest

from app import db
from app.http import PoliteClient
from app.sources.afisha_me import AfishaMeAdapter
from app.sources.base import CollectContext
from app.sources.relax import RelaxAdapter
from app.sources.ticketpro import TicketproAdapter
from conftest import pg_url

FIXTURES = Path(__file__).parent / "fixtures"


def make_ctx(handler, max_urls=None) -> CollectContext:
    http = PoliteClient(
        user_agent="test/0.1",
        default_min_interval_s=0,
        transport=httpx.MockTransport(handler),
    )
    return CollectContext(http=http, db_url=pg_url(), max_urls=max_urls)


def test_ticketpro_collects_first_page_only(conn):
    listing = (FIXTURES / "ticketpro_listing.html").read_text()

    def handler(request: httpx.Request) -> httpx.Response:
        if "page=2" in str(request.url):
            return httpx.Response(200, text="<html></html>")
        return httpx.Response(200, text=listing)

    import asyncio
    stats = asyncio.run(TicketproAdapter().collect(make_ctx(handler)))
    assert stats.parsed == 6  # 1 Minsk event x 6 listings
    # Same card URL in every listing -> upserted once (idempotent re-crawl).
    assert stats.new_events == 1
    rows = conn.execute("SELECT title, category FROM collected_events").fetchall()
    assert len(rows) == 1
    # Same card re-crawled under every listing: last write wins (refresh).
    assert rows[0]["category"] == "sport"


def test_relax_collects_minsk_cards(conn):
    card = (FIXTURES / "relax_card.html").read_text()
    sitemap = ('<urlset><url><loc>https://afisha.relax.by/theatre/1-x/minsk/</loc></url>'
               '<url><loc>https://afisha.relax.by/theatre/2-y/grodno/</loc></url></urlset>')

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith(".xml.gz"):
            import gzip
            return httpx.Response(200, content=gzip.compress(sitemap.encode()))
        return httpx.Response(200, text=card)

    import asyncio
    stats = asyncio.run(RelaxAdapter().collect(make_ctx(handler)))
    assert stats.parsed == 1  # grodno url skipped by sitemap filter
    row = conn.execute("SELECT title, category FROM collected_events").fetchone()
    assert row["title"] == "Спектакль «Тестовый»"
    assert row["category"] == "theatre"


def test_collect_limit_caps_cards(conn):
    card = (FIXTURES / "relax_card.html").read_text()
    sitemap = ('<urlset><url><loc>https://afisha.relax.by/theatre/1-x/minsk/</loc></url>'
               '<url><loc>https://afisha.relax.by/theatre/2-y/minsk/</loc></url>'
               '<url><loc>https://afisha.relax.by/theatre/3-z/minsk/</loc></url></urlset>')
    fetched_cards = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith(".xml.gz"):
            import gzip
            return httpx.Response(200, content=gzip.compress(sitemap.encode()))
        fetched_cards.append(url)
        return httpx.Response(200, text=card)

    import asyncio
    stats = asyncio.run(RelaxAdapter().collect(make_ctx(handler, max_urls=2)))
    assert stats.parsed == 2
    assert len(fetched_cards) == 2


def test_afisha_me_collects_cards(conn):
    card = (FIXTURES / "afisha_me_card.html").read_text()
    sitemap = ("<urlset><url><loc>https://afisha.me/concert/test/</loc></url></urlset>")

    def handler(request: httpx.Request) -> httpx.Response:
        if "/sitemap/" in str(request.url):
            return httpx.Response(200, text=sitemap)
        return httpx.Response(200, text=card)

    import asyncio
    stats = asyncio.run(AfishaMeAdapter().collect(make_ctx(handler)))
    assert stats.parsed == 3  # same card url in 3 sitemaps
    assert stats.new_events == 1  # upserted once, re-crawls are not "duplicates"
    assert stats.duplicates == 0
    row = conn.execute(
        "SELECT title, venue_name, price_min, age_limit FROM collected_events").fetchone()
    assert row["title"] == "Тестовая группа"
    assert row["venue_name"] == "Тестовый зал"
    assert float(row["price_min"]) == 30.0
    assert row["age_limit"] == 12


def test_cross_source_merge_keeps_fuller_record(conn):
    from datetime import datetime, timezone

    from app.normalize import RawEvent
    from app.store import upsert_events

    start = datetime(2026, 12, 5, 16, 0, tzinfo=timezone.utc)
    thin = RawEvent(source="afisha_me", source_id="a1",
                    source_url="http://am/1", title="Тестовая группа",
                    start_at=start, venue_name="Тестовый зал")
    full = RawEvent(source="ticketpro", source_id="t1",
                    source_url="http://tp/1", title="Тестовая группа",
                    description="Полное описание", start_at=start,
                    venue_name="Тестовый зал", price_min=30.0)
    assert thin.dedup_key == full.dedup_key
    stats = upsert_events(conn, [thin])
    assert stats.new_events == 1 and stats.duplicates == 0
    stats = upsert_events(conn, [full])
    assert stats.new_events == 0 and stats.duplicates == 1
    conn.commit()
    rows = conn.execute("SELECT description, price_min FROM collected_events").fetchall()
    assert len(rows) == 1  # no second row: twin updated in place
    assert rows[0]["description"] == "Полное описание"
    sources = conn.execute("SELECT source FROM event_sources").fetchall()
    assert {row["source"] for row in sources} == {"afisha_me", "ticketpro"}
