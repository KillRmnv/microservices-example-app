"""HTML -> structured event extraction.

Priority: JSON-LD Event -> microdata -> nothing else.
No JS evaluation, no anti-bot circumvention.
"""
from __future__ import annotations

import html as html_std
import json
import logging
import re

from selectolax.lexbor import LexborHTMLParser

log = logging.getLogger(__name__)

LD_JSON_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
    re.S | re.I,
)
# JSON forbids ALL literal C0 controls inside strings (including \n \t),
# but they are harmless as whitespace between tokens — blank them all.
CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def _walk_json_ld(node, found: list[dict]) -> None:
    if isinstance(node, dict):
        if node.get("@type") == "Event":
            found.append(node)
        graph = node.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                _walk_json_ld(item, found)
    elif isinstance(node, list):
        for item in node:
            _walk_json_ld(item, found)


def extract_json_ld_events(html: str) -> list[dict]:
    """All @type Event objects from every ld+json block (skips Movie etc.)."""
    events: list[dict] = []
    for block in LD_JSON_RE.findall(html):
        # Relax.by embeds raw control chars in description — clean first.
        try:
            data = json.loads(CONTROL_CHARS_RE.sub(" ", block))
        except json.JSONDecodeError:
            continue
        _walk_json_ld(data, events)
    return events


NEXT_PUSH_RE = re.compile(
    r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', re.S)
_NEXT_EVENTS_KEY = '"eventsPage":'


def _decode_next_chunks(html: str) -> str:
    parts = []
    for raw in NEXT_PUSH_RE.findall(html):
        try:
            parts.append(json.loads(f'"{raw}"'))
        except json.JSONDecodeError:
            continue
    return "\n".join(parts)


def extract_next_events(html: str) -> list[dict]:
    """Ticketpro's Next.js RSC payload: eventsPage.items with real fields."""
    text = _decode_next_chunks(html)
    if not text:
        return []
    decoder = json.JSONDecoder()
    events: list[dict] = []
    cursor = 0
    while True:
        pos = text.find(_NEXT_EVENTS_KEY, cursor)
        if pos < 0:
            break
        brace = text.find("{", pos)
        if brace < 0:
            break
        try:
            data, consumed = decoder.raw_decode(text[brace:])
        except json.JSONDecodeError:
            cursor = pos + len(_NEXT_EVENTS_KEY)
            continue
        if isinstance(data, dict):
            events.extend(item for item in data.get("items", [])
                          if isinstance(item, dict))
        cursor = brace + consumed
    return events


def extract_microdata_event(html: str) -> dict | None:
    """Afisha.me card shape: name / time[datetime] / .b-shedule-place / tags."""
    tree = LexborHTMLParser(html)
    scope = tree.css_first('[itemtype="http://schema.org/Event"]')
    if scope is None:
        return None
    name = scope.css_first('[itemprop="name"]')
    time_node = scope.css_first('time[itemprop="startDate"]')
    venue = scope.css_first(".b-shedule-place")
    venue_addr = scope.css_first(".b-shedule-place__address")
    ticket = scope.css_first(".b-shedule-day_ticket")
    tags = [t.text(strip=True) for t in scope.css(".b-event-tag .tag")]
    image = scope.css_first(".poster-media img, .b-event-poster img")

    def attr(node, key: str) -> str | None:
        if node is None:
            return None
        value = node.attributes.get(key)
        return value if isinstance(value, str) else None

    return {
        "name": name.text(strip=True) if name else None,
        "startDate": attr(time_node, "datetime"),
        "venue_name": venue.text(strip=True) if venue else None,
        "venue_url": attr(venue, "href"),
        "address": venue_addr.text(strip=True) if venue_addr else None,
        "price_text": ticket.text(strip=True) if ticket else None,
        "tags": tags,
        "image": attr(image, "src"),
    }


META_DESCRIPTION_SELECTORS = (
    'meta[name="description"]',
    'meta[property="og:description"]',
)


def _plain_description(value) -> str | None:
    """JSON-LD/meta text -> plain single-line text (tags and entities gone)."""
    if not isinstance(value, str):
        return None
    text = html_std.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    return clean_text(text)


def extract_event_description(html: str) -> str | None:
    """Description from JSON-LD Event, then meta description, then microdata."""
    for event in extract_json_ld_events(html):
        description = _plain_description(event.get("description"))
        if description:
            return description
    tree = LexborHTMLParser(html)
    for selector in META_DESCRIPTION_SELECTORS:
        node = tree.css_first(selector)
        if node is not None:
            description = _plain_description(node.attributes.get("content"))
            if description:
                return description
    node = tree.css_first('[itemprop="description"]')
    if node is not None:
        description = _plain_description(
            node.attributes.get("content") or node.text(strip=True))
        if description:
            return description
    return None


def clean_text(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"\s+", " ", value).strip()
    return text or None
