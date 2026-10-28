"""Catalog read controllers."""
from __future__ import annotations

from fastapi import APIRouter, Request

from ..schemas import EventsResponse, VenuesResponse
from ...core import db
from ...repositories import queries

router = APIRouter(tags=["catalog"])


def _limit(value: int, cap: int) -> int:
    return max(1, min(cap, value))


@router.get("/events", response_model=EventsResponse)
def events(request: Request, source: str | None = None,
           city: str | None = None, limit: int = 50) -> dict:
    with db.get_conn(request.app.state.db_url) as conn:
        rows = queries.list_events(conn, source, city, _limit(limit, 500))
    return {"events": rows}


@router.get("/events/search", response_model=EventsResponse)
def events_search(request: Request, q: str, city: str | None = None,
                  category: str | None = None, limit: int = 20) -> dict:
    with db.get_conn(request.app.state.db_url) as conn:
        rows = queries.search_events(conn, q, city, category, _limit(limit, 100))
    return {"events": rows}


@router.get("/venues/search", response_model=VenuesResponse)
def venues_search(request: Request, q: str, city: str | None = None,
                  rubric: str | None = None, limit: int = 20) -> dict:
    with db.get_conn(request.app.state.db_url) as conn:
        rows = queries.search_venues(conn, q, city, rubric, _limit(limit, 100))
    return {"venues": rows}
