"""Afisha.me film pages: Movie heading + schema.org Event sessions.

The generic microdata extractor returns the cinema as `name` on film pages
(the Event scope wraps the venue), so films need their own extractor. Film
entries are modelled as cinema runs (earliest session + a sensible end), not
exact showtimes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from selectolax.lexbor import LexborHTMLParser

from .html import clean_text
from .normalize import parse_age

MOVIE_SCOPE = '[itemtype="http://schema.org/Movie"]'
EVENT_SCOPE = '[itemtype="http://schema.org/Event"]'
TITLE_SUFFIX_RE = re.compile(
    r"\s*[-–—|]\s*(?:премьера|расписание|купить|билеты|трейлер).*$", re.I)
TITLE_PREFIX_RE = re.compile(r"^(?:Балет|Фильм|Кино|Спектакль)\s+", re.I)


@dataclass
class FilmSession:
    cinema: str
    start_at: str | None
    price: str | None = None
    address: str | None = None


@dataclass
class FilmPage:
    title: str
    sessions: list[FilmSession] = field(default_factory=list)
    image: str | None = None
    age_limit: int | None = None


def _attr(node, name: str) -> str | None:
    if node is None:
        return None
    value = node.attributes.get(name)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _title(tree, movie) -> str | None:
    node = (tree.css_first("#event-name")
            or tree.css_first(f"{MOVIE_SCOPE} [itemprop='name']")
            or tree.css_first("h1"))
    title = clean_text(node.text(strip=True) if node is not None else None)
    if title:
        return title
    raw = clean_text(tree.css_first("title").text(strip=True)
                     if tree.css_first("title") is not None else None)
    if not raw:
        return None
    raw = TITLE_SUFFIX_RE.sub("", raw)
    return clean_text(TITLE_PREFIX_RE.sub("", raw).strip())


def _session(scope) -> FilmSession | None:
    cinema = clean_text(scope.css_first('[itemprop="name"]').text(strip=True)
                        if scope.css_first('[itemprop="name"]') is not None
                        else None)
    if not cinema:
        return None
    start_node = scope.css_first('[itemprop="startDate"]')
    start_at = _attr(start_node, "datetime") or _attr(start_node, "content")
    ticket = scope.css_first("[data-price]") or scope.css_first(".js-ticket")
    price = _attr(ticket, "data-price")
    address_node = scope.css_first('[itemprop="address"]')
    parts = []
    if address_node is not None:
        for prop in ("streetAddress", "addressLocality"):
            node = address_node.css_first(f'[itemprop="{prop}"]')
            if node is not None:
                parts.append(_attr(node, "content") or node.text(strip=True))
    address = clean_text(", ".join(part for part in parts if part))
    return FilmSession(cinema=cinema, start_at=start_at, price=price,
                       address=address)


def extract_film_page(markup: str) -> FilmPage | None:
    """Film title + cinema sessions; None when the page is not a film page."""
    tree = LexborHTMLParser(markup)
    movie = tree.css_first(MOVIE_SCOPE)
    if movie is None:
        return None
    title = _title(tree, movie)
    if not title:
        return None
    sessions = [session for scope in tree.css(EVENT_SCOPE)
                if (session := _session(scope)) is not None]
    if not sessions:
        return None
    image = _attr(movie.css_first("img[itemprop='image']"), "src")
    if image is None:
        image = _attr(tree.css_first("img[itemprop='image']"), "src")
    age_limit = None
    for genre in movie.css("[itemprop='genre']"):
        age_limit = parse_age(genre.text(strip=True))
        if age_limit is not None:
            break
    return FilmPage(title=title, sessions=sessions, image=image,
                    age_limit=age_limit)
