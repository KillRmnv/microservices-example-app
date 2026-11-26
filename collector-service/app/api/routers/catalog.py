"""Catalog read controllers (public: browsing, cards and detail pages)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_catalog_service
from ..schemas import (EventListResponse, EventsResponse, VenueListResponse,
                       VenuesResponse)
from ...services.catalog_service import CatalogService

router = APIRouter(tags=["catalog"])


@router.get("/events", response_model=EventListResponse)
def events(service: CatalogService = Depends(get_catalog_service),
           city: str | None = None, category: str | None = None,
           source: str | None = None, categories: str | None = None,
           date_from: str | None = None, date_to: str | None = None,
           q: str | None = None, ids: str | None = None,
           include_cancelled: bool = False,
           limit: int = 40, offset: int = 0) -> dict:
    id_list = [value for value in (ids or "").split(",") if value.strip()]
    selected = [item.strip() for item in (categories or "").split(",")
                if item.strip()]
    return service.list_events(
        city=city, category=category, source=source,
        categories=selected, date_from=date_from, date_to=date_to, q=q,
        ids=id_list, include_cancelled=include_cancelled,
        limit=limit, offset=offset)


@router.get("/events/search", response_model=EventsResponse)
def events_search(q: str,
                  service: CatalogService = Depends(get_catalog_service),
                  city: str | None = None,
                  category: str | None = None, categories: str | None = None,
                  date_from: str | None = None, date_to: str | None = None,
                  include_cancelled: bool = False,
                  limit: int = 20) -> dict:
    selected = [item.strip() for item in (categories or "").split(",")
                if item.strip()]
    return service.search_events(
        q=q, city=city, category=category, categories=selected,
        date_from=date_from, date_to=date_to,
        include_cancelled=include_cancelled, limit=limit)


@router.get("/events/{event_id}")
def event_detail(event_id: str,
                 service: CatalogService = Depends(get_catalog_service)) -> dict:
    return service.event(event_id)


@router.get("/venues", response_model=VenueListResponse)
def venues(service: CatalogService = Depends(get_catalog_service),
           city: str | None = None, rubric: str | None = None,
           q: str | None = None, limit: int = 60, offset: int = 0) -> dict:
    return service.list_venues(city=city, rubric=rubric, q=q,
                               limit=limit, offset=offset)


@router.get("/venues/search", response_model=VenuesResponse)
def venues_search(q: str,
                  service: CatalogService = Depends(get_catalog_service),
                  city: str | None = None,
                  rubric: str | None = None, limit: int = 20) -> dict:
    return service.search_venues(q=q, city=city, rubric=rubric, limit=limit)


@router.get("/venues/{venue_id}")
def venue_detail(venue_id: str,
                 service: CatalogService = Depends(get_catalog_service)) -> dict:
    return service.venue(venue_id)
