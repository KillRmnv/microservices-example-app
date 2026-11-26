"""Venue atmosphere enrichment use case.

Sources, in priority order: review texts (2GIS reviews object, when the API
actually returns text) -> descriptions of linked events (Telegram first) ->
name/rubric heuristics. Only the first source that yields tags wins, so an
explicit description is never overridden by a generic rubric guess.

Re-running is safe: a row is rewritten only when its computed tags differ from
the stored array (or when ``force`` is set). Nothing runs at startup.
"""
from __future__ import annotations

import json
import logging

from ..core import db
from ..parsing.atmosphere import atmosphere_from_rubric, atmosphere_tags
from ..repositories import queries

log = logging.getLogger(__name__)

DEFAULT_LIMIT = 200
MAX_LIMIT = 1000


def _stored_tags(value) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return []
        return _stored_tags(parsed)
    return []


def review_texts(raw) -> str:
    """Reviews object text, when present (catalog API currently omits it)."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return ""
    if not isinstance(raw, dict):
        return ""
    reviews = raw.get("reviews")
    items = reviews.get("items") if isinstance(reviews, dict) else None
    if not isinstance(items, list):
        return ""
    parts = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = (item.get("text") or item.get("comment")
                or item.get("review_text"))
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n".join(parts)


def tags_for_row(row) -> list[str]:
    """Deterministic tags for one candidate row (dict-like).

    Strict source priority: review text, then linked event descriptions, then
    name/rubric heuristics. An empty source falls through, but a non-empty one
    is authoritative — a generic description never dilutes explicit reviews.
    """
    tags = atmosphere_tags(review_texts(row.get("raw")))
    if not tags:
        tags = atmosphere_tags(row.get("event_text"))
    if not tags:
        tags = atmosphere_from_rubric(row.get("name"), row.get("rubric"))
    return tags


class AtmosphereService:
    def __init__(self, db_url: str) -> None:
        self._db_url = db_url

    def enrich(self, limit: int = DEFAULT_LIMIT,
               force: bool = False) -> dict:
        limit = max(1, min(MAX_LIMIT, int(limit or DEFAULT_LIMIT)))
        updated = tagged = unchanged = 0
        with db.get_conn(self._db_url) as conn:
            rows = queries.atmosphere_candidates(conn, limit)
            for row in rows:
                tags = tags_for_row(row)
                if tags:
                    tagged += 1
                current = _stored_tags(row["atmosphere"])
                if (not force and row["atmosphere"] is not None
                        and current == tags):
                    unchanged += 1
                    continue
                if queries.set_venue_atmosphere(conn, row["id"], tags):
                    updated += 1
                else:
                    unchanged += 1
            conn.commit()
        return {"venues": len(rows), "tagged": tagged, "updated": updated,
                "unchanged": unchanged, "limit": limit, "force": force}
