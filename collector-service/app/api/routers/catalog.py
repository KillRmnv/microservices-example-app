"""Catalog read controllers (public: browsing, cards and detail pages)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from ..schemas import EventListResponse, EventsResponse, VenueListResponse, VenuesResponse
from ...core import db
from ...errors import NotFoundError
from ...repositories import queries

router = APIRouter(tags=["catalog"])


def _limit(value: int, cap: int) -> int:
    return max(1, min(cap, value))


def _offset(value: int) -> int:
    return max(0, value)


def _uuid(value: str, what: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError) as exc:
        raise NotFoundError(f"{what} not found") from exc


@router.get("/events", response_model=EventListResponse)
def events(request: Request, city: str | None = None,
           category: str | None = None, source: str | None = None,
           date_from: str | None = None, date_to: str | None = None,
           q: str | None = None, ids: str | None = None,
           limit: int = 40, offset: int = 0) -> dict:
    id_list = [value for value in (ids or "").split(",") if value.strip()]
    with db.get_conn(request.app.state.db_url) as conn:
        rows, total = queries.list_events(
            conn, city=city, category=category, source=source,
            date_from=date_from, date_to=date_to, q=q,
            ids=id_list or None, limit=_limit(limit, 200),
            offset=_offset(offset))
    return {"events": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/events/search", response_model=EventsResponse)
def events_search(request: Request, q: str, city: str | None = None,
                  category: str | None = None, limit: int = 20) -> dict:
    with db.get_conn(request.app.state.db_url) as conn:
        rows = queries.search_events(conn, q, city, category, _limit(limit, 100))
    return {"events": rows}


@router.get("/events/{event_id}")
def event_detail(request: Request, event_id: str) -> dict:
    with db.get_conn(request.app.state.db_url) as conn:
        row = queries.get_event(conn, _uuid(event_id, "event"))
    if row is None:
        raise NotFoundError("event not found")
    return row


@router.get("/venues", response_model=VenueListResponse)
def venues(request: Request, city: str | None = None,
           rubric: str | None = None, q: str | None = None,
           limit: int = 60, offset: int = 0) -> dict:
    with db.get_conn(request.app.state.db_url) as conn:
        rows, total = queries.list_venues(
            conn, city=city, rubric=rubric, q=q, limit=_limit(limit, 200),
            offset=_offset(offset))
    return {"venues": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/venues/search", response_model=VenuesResponse)
def venues_search(request: Request, q: str, city: str | None = None,
                  rubric: str | None = None, limit: int = 20) -> dict:
    with db.get_conn(request.app.state.db_url) as conn:
        rows = queries.search_venues(conn, q, city, rubric, _limit(limit, 100))
    return {"venues": rows}


@router.get("/venues/{venue_id}")
def venue_detail(request: Request, venue_id: str) -> dict:
    with db.get_conn(request.app.state.db_url) as conn:
        row = queries.get_venue(conn, _uuid(venue_id, "venue"))
        if row is None:
            raise NotFoundError("venue not found")
        row["events"] = queries.venue_events(conn, row["id"])
    return row
