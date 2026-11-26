"""ByCard film metadata (schema.org Movie JSON-LD).

ByCard does not publish showtimes on its film pages: the listing and detail
pages only carry poster/title/genre/duration/description. The parser therefore
returns *metadata* only; the collector uses it to fill empty fields of film
events discovered elsewhere and never creates events from it.

Robots.txt (live check) disallows only ``/tmp/`` and a few crawlers, so
``/afisha/kino`` is allowed. Every request still goes through the polite client
with a 1.5 s source interval.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from selectolax.lexbor import LexborHTMLParser

from .html import clean_text
from .normalize import parse_age

BASE = "https://bycard.by"
LISTING_URL = f"{BASE}/afisha/kino"
JSONLD_SELECTOR = 'script[type="application/ld+json"]'

_TITLE_STRIP_RE = re.compile(r"[^0-9a-zа-я]+")
_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?)?$",
    re.I)


@dataclass
class BycardFilm:
    name: str
    url: str | None = None
    image: str | None = None
    genre: list[str] = field(default_factory=list)
    description: str | None = None
    duration: str | None = None
    duration_minutes: int | None = None
    age_limit: int | None = None


def normalize_title(value: str | None) -> str:
    """Case/punctuation-insensitive title key used for cross-source matching.

    ``«Ёлки 13»``, ``"ЕЛКИ 13"`` and ``Ёлки-13`` all map to ``елки 13``.
    """
    text = str(value or "").casefold().replace("ё", "е")
    return _TITLE_STRIP_RE.sub(" ", text).strip()


def parse_duration(value: str | None) -> int | None:
    """ISO-8601 ``PT75M`` / ``PT1H15M`` -> minutes."""
    if not isinstance(value, str) or not value.strip():
        return None
    match = _DURATION_RE.match(value.strip())
    if match is None:
        return None
    parts = {key: int(number or 0) for key, number in match.groupdict().items()}
    minutes = parts["days"] * 24 * 60 + parts["hours"] * 60 + parts["minutes"]
    return minutes or None


def _absolute(value) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if value.startswith("//"):
        value = f"https:{value}"
    return urljoin(BASE, value)


def _genres(value) -> list[str]:
    values = value if isinstance(value, list) else [value]
    result = []
    for item in values:
        cleaned = clean_text(str(item)) if item is not None else None
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def _age(movie: dict) -> int | None:
    value = movie.get("typicalAgeRange")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        age = int(value)
        return age if 0 <= age <= 21 else None
    return parse_age(value if isinstance(value, str) else None)


def _film(movie: dict) -> BycardFilm | None:
    name = clean_text(movie.get("name"))
    if not name:
        return None
    duration = movie.get("duration")
    duration = duration.strip() if isinstance(duration, str) and duration.strip() else None
    return BycardFilm(
        name=name,
        url=_absolute(movie.get("url")),
        image=_absolute(movie.get("image")),
        genre=_genres(movie.get("genre")),
        description=clean_text(movie.get("description")),
        duration=duration,
        duration_minutes=parse_duration(duration),
        age_limit=_age(movie),
    )


def _jsonld(markup: str) -> list[dict]:
    tree = LexborHTMLParser(markup)
    blocks: list[dict] = []
    for node in tree.css(JSONLD_SELECTOR):
        try:
            data = json.loads(node.text())
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict):
            blocks.append(data)
        elif isinstance(data, list):
            blocks.extend(item for item in data if isinstance(item, dict))
    return blocks


def extract_movie_listing(markup: str) -> list[BycardFilm]:
    """All unique ``Movie`` entries from the /afisha/kino listing."""
    films: list[BycardFilm] = []
    seen: set[str] = set()
    for block in _jsonld(markup):
        if block.get("@type") != "Movie":
            continue
        film = _film(block)
        if film is None:
            continue
        key = film.url or normalize_title(film.name)
        if key in seen:
            continue
        seen.add(key)
        films.append(film)
    return films


def extract_movie_page(markup: str) -> BycardFilm | None:
    """The page's primary ``Movie`` (the Organization block is ignored)."""
    for block in _jsonld(markup):
        if block.get("@type") == "Movie":
            return _film(block)
    return None
