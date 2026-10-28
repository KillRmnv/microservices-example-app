"""Request DTOs for the collector API."""
from __future__ import annotations

from pydantic import BaseModel, HttpUrl


class ProbeRequest(BaseModel):
    source: str = "probe"
    url: HttpUrl


class CollectResponse(BaseModel):
    source: str
    status: str
    fetched: int = 0
    parsed: int = 0
    parse_errors: int = 0
    duplicates: int = 0
    new_events: int = 0


class EmbedResponse(BaseModel):
    source: str | None = None
    embedded: int
    pending: int
    duration_s: float = 0.0


class ProbeResponse(BaseModel):
    source: str
    status_code: int
    bytes: int
    final_url: str


class EventsResponse(BaseModel):
    events: list[dict]


class VenuesResponse(BaseModel):
    venues: list[dict]


class AlertResponse(BaseModel):
    degraded: list[str]
    alert_sent: bool


class ReindexCollection(BaseModel):
    patched: int
    stored: int
    rows: int


class ReindexResponse(BaseModel):
    events: ReindexCollection
    venues: ReindexCollection
    duration_s: float = 0.0
