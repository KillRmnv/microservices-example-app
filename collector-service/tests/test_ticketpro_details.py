"""Ticketpro detail enrichment: HTML extraction and bounded job counters."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx

from app.clients.http import PoliteClient
from app.parsing.html import extract_event_description
from app.repositories import queries
from app.services import ticketpro_details_service as details_module
from app.services.ticketpro_details_service import (TicketproDetailsService,
                                                      absolute_url, detail_url)


def test_extract_json_ld_description_wins():
    html = """
    <html><head><meta name="description" content="meta fallback"></head>
    <body><script type="application/ld+json">
    {"@type": "Event", "name": "Концерт",
     "description": "<p>Большой <b>концерт</b> в Минске</p>"}
    </script></body></html>"""
    assert extract_event_description(html) == "Большой концерт в Минске"


def test_extract_meta_description_only():
    html = """<html><head>
      <meta name="description" content="  Премьера &amp; встреча с артистами ">
    </head><body></body></html>"""
    assert extract_event_description(html) == "Премьера & встреча с артистами"


def test_extract_og_description_fallback():
    html = """<html><head>
      <meta property="og:description" content="Описание из Open Graph">
    </head></html>"""
    assert extract_event_description(html) == "Описание из Open Graph"


def test_extract_microdata_description():
    html = """<div itemscope itemtype="http://schema.org/Event">
      <div itemprop="description">Камерный вечер</div>
    </div>"""
    assert extract_event_description(html) == "Камерный вечер"


def test_extract_missing_description_returns_none():
    assert extract_event_description("<html><body>пусто</body></html>") is None


def test_absolute_url_handles_relative_and_bad_values():
    assert absolute_url("/ru/event/abc") == \
        "https://www.ticketpro.by/ru/event/abc"
    assert absolute_url("//cdn.example/event") == "https://cdn.example/event"
    assert absolute_url("https://www.ticketpro.by/ru/event/abc") == \
        "https://www.ticketpro.by/ru/event/abc"
    assert absolute_url("javascript:alert(1)") is None
    assert absolute_url("") is None
    assert absolute_url(None) is None


def test_detail_url_prefers_external_then_slug_then_event_source():
    # Live Ticketpro rows store externalUrl=null but always have a slug.
    assert detail_url({
        "external_url": None, "slug": "abc",
        "source_url": "https://www.ticketpro.by/bilety-na-koncert/",
    }) == "https://www.ticketpro.by/ru/event/abc"
    assert detail_url({
        "external_url": "https://example.com/x", "slug": "abc",
        "source_url": "https://www.ticketpro.by/ru/event/abc",
    }) == "https://example.com/x"
    assert detail_url({
        "external_url": None, "slug": None,
        "source_url": "https://www.ticketpro.by/ru/event/abc",
    }) == "https://www.ticketpro.by/ru/event/abc"
    # A listing URL must never be fetched as if it were a detail page.
    assert detail_url({
        "external_url": None, "slug": None,
        "source_url": "https://www.ticketpro.by/bilety-na-koncert/",
    }) is None


class _Result:
    def __init__(self, rows=None, row=None, rowcount=0):
        self._rows = rows or []
        self._row = row
        self.rowcount = rowcount

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._row


class FakeConn:
    def __init__(self, rows):
        self.rows = rows
        self.descriptions: list[tuple] = []

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        if normalized.startswith("SELECT id, raw->>'externalUrl'"):
            return _Result(rows=self.rows)
        if normalized.startswith("UPDATE collected_events"):
            self.descriptions.append(params)
            return _Result(row={"id": params[1]})
        raise AssertionError(f"unexpected SQL: {normalized[:80]}")

    def commit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_enrichment_counts_skip_and_failure_paths(monkeypatch):
    rows = [
        {"id": "id-ok", "external_url": "https://www.ticketpro.by/ok"},
        {"id": "id-missing", "external_url": None},
        {"id": "id-404", "external_url": "https://www.ticketpro.by/missing"},
        {"id": "id-boom", "external_url": "https://www.ticketpro.by/boom"},
    ]
    fake = FakeConn(rows)
    monkeypatch.setattr(details_module.db, "get_conn", lambda url: fake)

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/ok"):
            return httpx.Response(200, text="""<html><head>
              <script type="application/ld+json">
              {"@type": "Event", "name": "X", "description": "Описание"}
              </script></head></html>""")
        if url.endswith("/missing"):
            return httpx.Response(404, text="nope")
        raise httpx.ConnectError("boom")

    http = PoliteClient(user_agent="test/0.1", default_min_interval_s=0,
                        max_attempts=1, backoff_base_s=0,
                        transport=httpx.MockTransport(handler))
    service = TicketproDetailsService(http, "postgresql://unused")
    result = asyncio.run(service.enrich(limit=99))

    assert result == {"fetched": 2, "updated": 1, "skipped": 2,
                      "failed": 1, "limit": 50}  # clamped
    assert fake.descriptions == [("Описание", "id-ok")]


def test_ticketpro_candidates_future_first_and_update(conn):
    now = datetime.now(timezone.utc)

    def insert(slug: str, start, description=None, url=None):
        raw = {"externalUrl": url} if url else {}
        conn.execute(
            """INSERT INTO collected_events
                   (source, source_id, source_url, title, start_at,
                    description, raw)
               VALUES ('ticketpro', %s, 'https://x/' || %s, %s, %s, %s,
                       %s::jsonb)""",
            (slug, slug, slug, start, description, json.dumps(raw)))

    insert("past", now - timedelta(days=5),
           url="https://www.ticketpro.by/past")
    insert("future-a", now + timedelta(days=1),
           url="https://www.ticketpro.by/a")
    insert("future-b", now + timedelta(days=5),
           url="https://www.ticketpro.by/b")
    insert("undated", None, url="https://www.ticketpro.by/undated")
    insert("done", now + timedelta(days=2), description="уже есть",
           url="https://www.ticketpro.by/done")
    insert("no-url", now + timedelta(days=3))
    conn.commit()

    rows = queries.ticketpro_missing_descriptions(conn, 10)
    assert [row["external_url"] for row in rows] == [
        "https://www.ticketpro.by/b",
        "https://www.ticketpro.by/a",
        "https://www.ticketpro.by/past",
        "https://www.ticketpro.by/undated",
    ]

    event_id = conn.execute(
        "SELECT id FROM collected_events WHERE source_id = 'future-a'"
    ).fetchone()["id"]
    conn.execute("UPDATE collected_events SET embedded_at = now()"
                 " WHERE id = %s", (event_id,))
    conn.commit()

    assert queries.set_event_description(conn, event_id, "Новое описание")
    conn.commit()
    stored = conn.execute(
        "SELECT description, embedded_at FROM collected_events WHERE id = %s",
        (event_id,)).fetchone()
    assert stored["description"] == "Новое описание"
    assert stored["embedded_at"] is None
    # The null guard makes a re-run a no-op.
    assert not queries.set_event_description(conn, event_id, "Ещё текст")
