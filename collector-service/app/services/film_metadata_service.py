"""ByCard film metadata enrichment (never creates events).

ByCard exposes a ``Movie`` JSON-LD block on ``/afisha/kino`` and on each film
page, but no showtimes. The service matches those movies to existing
``category = 'film'`` rows by normalized title and fills only what is missing:

* ``description`` — only when the row has none;
* ``image_url`` — only when the row has none;
* ``raw.film = {genre, duration, description_present}`` — merged into the
  existing raw object, other keys (microdata, sessions, channel) untouched.

Every write resets ``embedded_at`` so the derived dense vector / BM25 text /
Qdrant payload is rebuilt. Dry-run is the default: it performs the same fetches
and matching and reports the counters without touching the database.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

from ..core import db
from ..core.config import settings
from ..parsing.bycard import (LISTING_URL, BycardFilm, extract_movie_listing,
                              extract_movie_page, normalize_title)
from ..repositories import queries

log = logging.getLogger(__name__)

SOURCE = "bycard"
DEFAULT_LIMIT = 10
MIN_LIMIT = 10
MAX_LIMIT = 50


def _empty(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _raw_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except ValueError:
            return {}
        if isinstance(decoded, dict):
            return decoded
    return {}


def _merge(listing: BycardFilm, page: BycardFilm | None) -> BycardFilm:
    """Detail page wins for non-empty fields; listing fills the gaps."""
    if page is None:
        return listing
    return BycardFilm(
        name=page.name or listing.name,
        url=page.url or listing.url,
        image=page.image or listing.image,
        genre=page.genre or listing.genre,
        description=page.description or listing.description,
        duration=page.duration or listing.duration,
        duration_minutes=page.duration_minutes or listing.duration_minutes,
        age_limit=page.age_limit if page.age_limit is not None else listing.age_limit,
    )


class FilmMetadataService:
    def __init__(self, http, db_url: str, interval_s: float | None = None) -> None:
        self._http = http
        self._db_url = db_url
        self._interval = (settings.film_metadata_interval_s
                          if interval_s is None else interval_s)
        self._last_at = 0.0

    async def _get(self, url: str):
        wait = self._interval - (time.monotonic() - self._last_at)
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            return await self._http.get(SOURCE, url)
        finally:
            self._last_at = time.monotonic()

    async def enrich(self, limit: int = DEFAULT_LIMIT,
                     dry_run: bool = True) -> dict:
        limit = max(MIN_LIMIT, min(MAX_LIMIT, int(limit or DEFAULT_LIMIT)))
        counters = {
            "dry_run": dry_run, "limit": limit, "fetched": 0, "failed": 0,
            "listing_movies": 0, "processed": 0, "matched_films": 0,
            "unmatched": 0, "matched_events": 0, "would_update": 0,
            "updated": 0, "unchanged": 0, "description_filled": 0,
            "image_filled": 0, "raw_updated": 0, "changed_ids": [],
        }
        with db.get_conn(self._db_url) as conn:
            rows = queries.film_events_for_metadata(conn)
        index: dict[str, list] = {}
        for row in rows:
            index.setdefault(normalize_title(row["title"]), []).append(row)
        try:
            response = await self._get(LISTING_URL)
        except Exception as exc:  # noqa: BLE001 — one run must not crash the API
            counters["failed"] += 1
            log.warning("bycard listing failed: %s", exc)
            return counters
        counters["fetched"] += 1
        if response.status_code != 200:
            counters["failed"] += 1
            return counters
        films = extract_movie_listing(response.text)
        counters["listing_movies"] = len(films)
        for listing in films[:limit]:
            counters["processed"] += 1
            targets = index.get(normalize_title(listing.name), [])
            if not targets:
                counters["unmatched"] += 1
                continue
            counters["matched_films"] += 1
            details = listing
            if listing.url:
                try:
                    page_response = await self._get(listing.url)
                except Exception as exc:  # noqa: BLE001 — listing data is enough
                    counters["failed"] += 1
                    log.warning("bycard film page failed %s: %s", listing.url, exc)
                else:
                    counters["fetched"] += 1
                    if page_response.status_code == 200:
                        details = _merge(
                            listing, extract_movie_page(page_response.text))
                    else:
                        counters["failed"] += 1
            for row in targets:
                counters["matched_events"] += 1
                outcome = self._plan(row, details)
                if outcome is None:
                    counters["unchanged"] += 1
                    continue
                description, image_url, raw, filled = outcome
                counters["description_filled"] += int(filled["description"])
                counters["image_filled"] += int(filled["image"])
                counters["raw_updated"] += int(filled["raw"])
                if dry_run:
                    counters["would_update"] += 1
                    counters["changed_ids"].append(str(row["id"]))
                    continue
                with db.get_conn(self._db_url) as conn:
                    queries.update_film_metadata(
                        conn, row["id"], description, image_url, raw)
                    conn.commit()
                counters["updated"] += 1
                counters["changed_ids"].append(str(row["id"]))
        counters["changed_ids"] = counters["changed_ids"][:20]
        return counters

    @staticmethod
    def _plan(row, film: BycardFilm):
        """(description, image_url, raw, filled) or None when nothing changes."""
        description = row["description"]
        image_url = row["image_url"]
        filled = {"description": False, "image": False, "raw": False}
        if _empty(description) and film.description:
            description = film.description
            filled["description"] = True
        if _empty(image_url) and film.image:
            image_url = film.image
            filled["image"] = True
        raw = dict(_raw_dict(row["raw"]))
        film_meta = {
            "genre": film.genre,
            "duration": film.duration,
            "duration_minutes": film.duration_minutes,
            "description_present": bool(film.description),
        }
        if raw.get("film") != film_meta:
            raw["film"] = film_meta
            filled["raw"] = True
        if not any(filled.values()):
            return None
        return description, image_url, raw, filled
