"""Search DTOs."""
from __future__ import annotations

from pydantic import BaseModel


class SearchRequest(BaseModel):
    vector_query: str
    city: str | None = None
    category: str | None = None
    max_price_per_person: float | None = None
    limit: int = 10


class SearchHit(BaseModel):
    event_id: str
    title: str
    score: float
    origins: list[str]


class VenueSearchRequest(BaseModel):
    vector_query: str
    city: str | None = None
    rubric: str | None = None
    limit: int = 10


class VenueHit(BaseModel):
    venue_id: str
    name: str
    rubric: str
    address: str
    score: float
    origins: list[str]
