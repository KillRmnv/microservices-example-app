"""Bounded Ticketpro detail-page enrichment.

Listing cards carry no description, so rows are created with
``description = NULL``. The detail URL comes from ``raw.externalUrl``; live
rows currently store it as null but always carry ``raw.slug``, so the event URL
is rebuilt from the slug (see :func:`detail_url`). This job fetches those pages
through the regular polite client (per-source interval, retries, contact UA),
extracts a description and writes it back. It is never called from the regular
collect run; the manager triggers the endpoint.
"""
from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse

from ..core import db
from ..parsing.html import extract_event_description
from ..repositories import queries

log = logging.getLogger(__name__)

DEFAULT_LIMIT = 10
MAX_LIMIT = 50
SOURCE = "ticketpro"
BASE = "https://www.ticketpro.by"


def absolute_url(value) -> str | None:
    """`raw.externalUrl` -> absolute http(s) URL, or None when unusable."""
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if value.startswith("//"):
        value = f"https:{value}"
    elif value.startswith("/"):
        value = urljoin(BASE, value)
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return value


def detail_url(row) -> str | None:
    """Detail page for one row.

    Live listings carry ``raw.externalUrl = null``; every row has a slug, so
    the event URL is rebuilt from it. ``source_url`` is used only when it is
    an event page — falling back to a listing URL would scrape the wrong
    event's description.
    """
    url = absolute_url(row.get("external_url"))
    if url is not None:
        return url
    slug = row.get("slug")
    if isinstance(slug, str) and slug.strip():
        url = absolute_url(f"/ru/event/{slug.strip()}")
        if url is not None:
            return url
    url = absolute_url(row.get("source_url"))
    if url is not None and "/event/" in urlparse(url).path:
        return url
    return None


class TicketproDetailsService:
    def __init__(self, http, db_url: str) -> None:
        self._http = http
        self._db_url = db_url

    async def enrich(self, limit: int = DEFAULT_LIMIT) -> dict:
        """Fetch up to `limit` detail pages; failures never abort the batch.

        `fetched` counts HTTP responses (including 4xx/5xx), `updated` counts
        written descriptions, `skipped` covers missing URL/HTTP error/no text,
        `failed` counts transport errors.
        """
        limit = max(1, min(MAX_LIMIT, int(limit or DEFAULT_LIMIT)))
        counters = {"fetched": 0, "updated": 0, "skipped": 0, "failed": 0,
                    "limit": limit}
        with db.get_conn(self._db_url) as conn:
            rows = queries.ticketpro_missing_descriptions(conn, limit)
        for row in rows:
            url = detail_url(row)
            if url is None:
                counters["skipped"] += 1
                continue
            try:
                response = await self._http.get(SOURCE, url)
            except Exception as exc:  # noqa: BLE001 — one page must not kill the run
                counters["failed"] += 1
                log.warning("ticketpro detail failed %s: %s", url, exc)
                continue
            counters["fetched"] += 1
            if response.status_code != 200:
                counters["skipped"] += 1
                continue
            description = extract_event_description(response.text)
            if not description:
                counters["skipped"] += 1
                continue
            with db.get_conn(self._db_url) as conn:
                changed = queries.set_event_description(
                    conn, row["id"], description)
                conn.commit()
            if changed:
                counters["updated"] += 1
            else:
                counters["skipped"] += 1
        return counters
