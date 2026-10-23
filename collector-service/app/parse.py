"""HTML -> structured event extraction.

Priority (SCRAPPING.md §5): JSON-LD Event -> microdata -> nothing else.
No JS evaluation, no anti-bot circumvention.
"""
from __future__ import annotations

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


def clean_text(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"\s+", " ", value).strip()
    return text or None
