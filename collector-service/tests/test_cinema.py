"""Cinema listings: Ticketpro film runs and Afisha.me film pages."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.clients.http import PoliteClient
from app.parsing.film import extract_film_page
from app.sources.afisha_me import SITEMAPS, AfishaMeAdapter
from app.sources.base import CollectContext
from app.sources.ticketpro import LISTING_PAGE_CAPS, TicketproAdapter
from conftest import pg_url

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)


def _ctx(handler, max_urls=None):
    http = PoliteClient(user_agent="test/0.1", default_min_interval_s=0,
                        transport=httpx.MockTransport(handler))
    return CollectContext(http=http, db_url=pg_url(), max_urls=max_urls)


def _ticketpro_handler(cinema_html: str, capture: list | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/bilety-v-kino/" in url:
            if capture is not None:
                capture.append(url)
            if "page=2" in url:
                return httpx.Response(200, text="<html></html>")
            return httpx.Response(200, text=cinema_html)
        return httpx.Response(200, text="<html></html>")
    return handler


def test_ticketpro_cinema_runs_normalize_and_dedup(conn):
    cinema = (FIXTURES / "ticketpro_cinema_listing.html").read_text()
    stats = asyncio.run(TicketproAdapter().collect(_ctx(
        _ticketpro_handler(cinema))))

    assert stats.parsed == 4  # 2 films x 2 cinemas; past + Brest dropped
    rows = conn.execute(
        """SELECT title, venue_name, category, price_min, price_max,
                  age_limit, start_at, end_at
             FROM collected_events ORDER BY title, venue_name""").fetchall()
    assert len(rows) == 4
    assert {row["category"] for row in rows} == {"film"}
    assert {row["title"] for row in rows} == {"Фильм Первый", "Фильм Второй"}
    assert {row["venue_name"] for row in rows} == {
        "SKYLINE Cinema", "Silver Screen"}
    first = next(row for row in rows
                 if row["title"] == "Фильм Первый"
                 and row["venue_name"] == "SKYLINE Cinema")
    assert (float(first["price_min"]), float(first["price_max"])) == (12.0, 25.0)
    assert first["age_limit"] == 12
    assert first["start_at"].date().isoformat() == "2026-11-26"
    assert first["end_at"].date().isoformat() == "2026-12-02"

    keys = {row["dedup_key"] for row in conn.execute(
        "SELECT dedup_key FROM collected_events").fetchall()}
    assert len(keys) == 4

    again = asyncio.run(TicketproAdapter().collect(_ctx(
        _ticketpro_handler(cinema))))
    assert again.rows_updated == 4 and again.duplicates == 0
    assert conn.execute(
        "SELECT count(*) AS n FROM collected_events").fetchone()["n"] == 4


def test_ticketpro_cinema_pages_are_capped(conn):
    cinema = (FIXTURES / "ticketpro_cinema_listing.html").read_text()
    seen: list[str] = []
    stats = asyncio.run(TicketproAdapter().collect(_ctx(
        _ticketpro_handler(cinema, seen))))
    cinema_urls = [url for url in seen if "/bilety-v-kino/" in url]
    # The Next.js card payload stops after the first page by design; the cap
    # still guards a future JSON-LD/paginated cinema listing.
    assert len(cinema_urls) == 1
    assert LISTING_PAGE_CAPS["/bilety-v-kino/"] == 5
    assert stats.parsed == 4
    assert conn.execute(
        "SELECT count(*) AS n FROM collected_events").fetchone()["n"] == 4


def test_extract_film_page_title_sessions_and_metadata():
    page = extract_film_page((FIXTURES / "afisha_me_film.html").read_text())
    assert page is not None
    assert page.title == "TheatreHD: Тестовый фильм"
    assert page.age_limit == 12
    assert page.image == "https://img.afisha.me/media/cover/test-film.jpg"
    assert len(page.sessions) == 3
    assert {session.cinema for session in page.sessions} == {
        "mooon в ТРЦ Palazzo", "Silver Screen в ТРЦ Galileo"}
    assert page.sessions[0].start_at == "2026-12-02T18:40:00+03:00"
    assert page.sessions[0].price == "от 30 руб."
    assert page.sessions[0].address == "ул. Тимирязева 74A, Минск"


def test_film_events_aggregate_one_run_per_cinema():
    page = extract_film_page((FIXTURES / "afisha_me_film.html").read_text())
    assert page is not None
    events = AfishaMeAdapter().film_events("https://afisha.me/film/x/", page, NOW)
    assert len(events) == 2
    assert {event.venue_name for event in events} == {
        "mooon в ТРЦ Palazzo", "Silver Screen в ТРЦ Galileo"}
    assert {event.category for event in events} == {"film"}
    mooon = next(event for event in events
                 if event.venue_name == "mooon в ТРЦ Palazzo")
    assert mooon.start_at == datetime(2026, 12, 2, 15, 40, tzinfo=timezone.utc)
    assert mooon.end_at == datetime(2026, 12, 3, 17, 0, tzinfo=timezone.utc)
    assert (mooon.price_min, mooon.price_max) == (30.0, 35.0)
    silver = next(event for event in events
                  if event.venue_name == "Silver Screen в ТРЦ Galileo")
    # Single session: a two-hour interval instead of a zero-length event.
    assert silver.end_at == datetime(2026, 12, 4, 18, 10, tzinfo=timezone.utc)
    assert (silver.price_min, silver.price_max) == (20.0, 20.0)
    assert silver.age_limit == 12


def test_film_events_drop_ended_runs():
    page = extract_film_page((FIXTURES / "afisha_me_film.html").read_text())
    assert page is not None
    later = datetime(2027, 2, 1, tzinfo=timezone.utc)
    assert AfishaMeAdapter().film_events("https://afisha.me/film/x/", page,
                                         later) == []


def test_extract_film_page_rejects_non_film_markup():
    concert = (FIXTURES / "afisha_me_card.html").read_text()
    assert extract_film_page(concert) is None
    assert extract_film_page("<html><body>пусто</body></html>") is None


def test_film_sitemap_is_enabled_and_collects_runs(conn):
    assert SITEMAPS["https://afisha.me/sitemap/map-film-minsk-1.xml"] == "film"
    film = (FIXTURES / "afisha_me_film.html").read_text()
    sitemap = ("<urlset><url><loc>https://afisha.me/film/test-film/</loc></url>"
               "</urlset>")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("map-film-minsk-1.xml"):
            return httpx.Response(200, text=sitemap)
        if "/sitemap/" in url:
            return httpx.Response(200, text="<urlset></urlset>")
        return httpx.Response(200, text=film)

    stats = asyncio.run(AfishaMeAdapter().collect(_ctx(handler)))
    assert stats.parsed == 2
    assert stats.rows_inserted == 2
    rows = conn.execute(
        "SELECT title, venue_name, category FROM collected_events").fetchall()
    assert {row["title"] for row in rows} == {"TheatreHD: Тестовый фильм"}
    assert {row["venue_name"] for row in rows} == {
        "mooon в ТРЦ Palazzo", "Silver Screen в ТРЦ Galileo"}
    assert {row["category"] for row in rows} == {"film"}
