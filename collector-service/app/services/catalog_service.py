"""Catalog read use cases: controllers stay thin, SQL stays in repositories."""
from __future__ import annotations

from uuid import UUID

from ..core import db
from ..errors.domain import EventNotFound, VenueNotFound
from ..repositories import queries


def _limit(value: int, cap: int) -> int:
    return max(1, min(cap, value))


def _offset(value: int) -> int:
    return max(0, value)


def _uuid(value: str, not_found: type[Exception]) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError) as exc:
        raise not_found() from exc


class CatalogService:
    def __init__(self, db_url: str) -> None:
        self._db_url = db_url

    def list_events(self, *, city=None, category=None, source=None,
                    categories=None, date_from=None, date_to=None, q=None,
                    ids=None, include_cancelled=False,
                    limit=40, offset=0) -> dict:
        with db.get_conn(self._db_url) as conn:
            rows, total = queries.list_events(
                conn, city=city, category=category, source=source,
                date_from=date_from, date_to=date_to, q=q,
                ids=ids or None, categories=categories or None,
                include_cancelled=include_cancelled,
                limit=_limit(limit, 200), offset=_offset(offset))
        return {"events": rows, "total": total, "limit": limit,
                "offset": offset}

    def search_events(self, *, q, city=None, category=None, categories=None,
                      date_from=None, date_to=None, include_cancelled=False,
                      limit=20) -> dict:
        with db.get_conn(self._db_url) as conn:
            rows = queries.search_events(
                conn, q, city, category, _limit(limit, 100),
                date_from=date_from, date_to=date_to,
                categories=categories or None,
                include_cancelled=include_cancelled)
        return {"events": rows}

    def event(self, event_id: str) -> dict:
        event_id = _uuid(event_id, EventNotFound)
        with db.get_conn(self._db_url) as conn:
            row = queries.get_event(conn, event_id)
        if row is None:
            raise EventNotFound()
        return row

    def list_venues(self, *, city=None, rubric=None, q=None,
                    limit=60, offset=0) -> dict:
        with db.get_conn(self._db_url) as conn:
            rows, total = queries.list_venues(
                conn, city=city, rubric=rubric, q=q,
                limit=_limit(limit, 200), offset=_offset(offset))
        return {"venues": rows, "total": total, "limit": limit,
                "offset": offset}

    def search_venues(self, *, q, city=None, rubric=None, limit=20) -> dict:
        with db.get_conn(self._db_url) as conn:
            rows = queries.search_venues(
                conn, q, city, rubric, _limit(limit, 100))
        return {"venues": rows}

    def venue(self, venue_id: str) -> dict:
        venue_id = _uuid(venue_id, VenueNotFound)
        with db.get_conn(self._db_url) as conn:
            row = queries.get_venue(conn, venue_id)
            if row is None:
                raise VenueNotFound()
            row["events"] = queries.venue_events(conn, row["id"])
        return row
