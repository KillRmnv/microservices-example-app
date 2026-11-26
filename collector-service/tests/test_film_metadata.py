"""ByCard film metadata: parsing, matching, dry-run/apply, no overwrite."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from app.clients.http import PoliteClient
from app.parsing.bycard import (LISTING_URL, extract_movie_listing,
                                extract_movie_page, normalize_title,
                                parse_duration)
from app.services.film_metadata_service import FilmMetadataService
from conftest import pg_url

FIXTURES = Path(__file__).parent / "fixtures"
FILM_URL = "https://bycard.by/afisha/minsk/kino/5853485"


def _service(handler, interval_s=0.0) -> FilmMetadataService:
    http = PoliteClient(user_agent="test/0.1", default_min_interval_s=0,
                        transport=httpx.MockTransport(handler))
    return FilmMetadataService(http, pg_url(), interval_s=interval_s)


def _handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if url == LISTING_URL:
        return httpx.Response(200, text=(FIXTURES / "bycard_listing.html").read_text())
    if url == FILM_URL:
        return httpx.Response(200, text=(FIXTURES / "bycard_film.html").read_text())
    return httpx.Response(404, text="not found")


def _insert(conn, title="TheatreHD: Тестовый фильм", *, description=None,
            image_url=None, raw=None, embedded=True):
    return conn.execute(
        """INSERT INTO collected_events
               (source, source_id, source_url, title, category, description,
                image_url, raw, embedded_at)
           VALUES ('afisha_me', %s, 'https://afisha.me/film/x/', %s, 'film',
                   %s, %s, %s::jsonb, CASE WHEN %s THEN now() END)
           RETURNING id""",
        (f"test/{title}/{description}/{image_url}", title, description,
         image_url, json.dumps(raw) if raw is not None else None, embedded),
    ).fetchone()["id"]


def test_parse_listing_and_page():
    films = extract_movie_listing((FIXTURES / "bycard_listing.html").read_text())
    assert [film.name for film in films] == [
        "TheatreHD: Тестовый фильм", "Неизвестный фильм"]
    first = films[0]
    assert first.url == FILM_URL
    assert first.genre == ["TheatreHD", "Драма"]
    assert first.duration == "PT75M" and first.duration_minutes == 75
    assert first.age_limit == 12
    assert first.description and first.image

    page = extract_movie_page((FIXTURES / "bycard_film.html").read_text())
    assert page is not None
    assert page.name == "TheatreHD: Тестовый фильм"
    assert "Полное описание" in page.description
    assert page.duration_minutes == 105
    assert page.age_limit == 12
    assert page.genre == ["TheatreHD", "Драма", "Театр"]


def test_title_normalization_and_duration():
    assert parse_duration("PT75M") == 75
    assert parse_duration("PT1H45M") == 105
    assert parse_duration("garbage") is None
    assert normalize_title("«Ёлки 13»") == normalize_title('"ЕЛКИ-13"')
    assert normalize_title("THEATREHD: НОЙМАЙЕР: ЩЕЛКУНЧИК") == (
        "theatrehd ноймайер щелкунчик")


def test_dry_run_reports_without_writing(conn):
    event_id = _insert(conn, embedded=True)
    conn.commit()
    counters = asyncio.run(_service(_handler).enrich(limit=10, dry_run=True))

    assert counters["dry_run"] is True
    assert counters["listing_movies"] == 2
    assert counters["processed"] == 2
    assert counters["matched_films"] == 1
    assert counters["matched_events"] == 1
    assert counters["unmatched"] == 1
    assert counters["would_update"] == 1
    assert counters["updated"] == 0
    assert counters["fetched"] == 2  # listing + one matched film page
    row = conn.execute(
        """SELECT description, image_url, raw, embedded_at
             FROM collected_events WHERE id = %s""", (event_id,)).fetchone()
    assert row["description"] is None and row["image_url"] is None
    assert row["raw"] is None and row["embedded_at"] is not None


def test_apply_fills_empty_only_and_preserves_raw(conn):
    empty_id = _insert(conn, raw={"microdata": {"name": "x"}}, embedded=True)
    filled_id = _insert(
        conn, description="Уже есть описание",
        image_url="https://existing.example/poster.jpg",
        raw={"sessions": 3}, embedded=True)
    conn.commit()
    counters = asyncio.run(_service(_handler).enrich(limit=10, dry_run=False))

    assert counters["updated"] == 2
    assert counters["would_update"] == 0
    assert counters["description_filled"] == 1
    assert counters["image_filled"] == 1
    assert counters["raw_updated"] == 2

    empty = conn.execute(
        "SELECT description, image_url, raw, embedded_at"
        "  FROM collected_events WHERE id = %s", (empty_id,)).fetchone()
    assert empty["description"].startswith("Полное описание")
    assert empty["image_url"].endswith("test-film-page.jpg")
    assert empty["raw"]["microdata"] == {"name": "x"}
    assert empty["raw"]["film"] == {
        "genre": ["TheatreHD", "Драма", "Театр"],
        "duration": "PT1H45M", "duration_minutes": 105,
        "description_present": True}
    assert empty["embedded_at"] is None

    filled = conn.execute(
        "SELECT description, image_url, raw FROM collected_events WHERE id = %s",
        (filled_id,)).fetchone()
    assert filled["description"] == "Уже есть описание"
    assert filled["image_url"] == "https://existing.example/poster.jpg"
    assert filled["raw"]["sessions"] == 3
    assert filled["raw"]["film"]["duration"] == "PT1H45M"


def test_second_apply_is_a_no_op(conn):
    _insert(conn)
    conn.commit()
    first = asyncio.run(_service(_handler).enrich(limit=10, dry_run=False))
    assert first["updated"] == 1
    second = asyncio.run(_service(_handler).enrich(limit=10, dry_run=False))
    assert second["updated"] == 0
    assert second["unchanged"] == 1


def test_unmatched_movies_never_create_events(conn):
    counters = asyncio.run(_service(_handler).enrich(limit=10, dry_run=False))
    assert counters["matched_events"] == 0
    assert counters["unmatched"] == 2
    assert conn.execute(
        "SELECT count(*) AS n FROM collected_events").fetchone()["n"] == 0


def test_non_film_rows_are_not_matched(conn):
    conn.execute(
        """INSERT INTO collected_events
               (source, source_id, source_url, title, category)
           VALUES ('afisha_me', 'theatre-1', 'https://afisha.me/x/',
                   'TheatreHD: Тестовый фильм', 'theatre')""")
    conn.commit()
    counters = asyncio.run(_service(_handler).enrich(limit=10, dry_run=False))
    assert counters["matched_events"] == 0
    assert counters["unmatched"] == 2
