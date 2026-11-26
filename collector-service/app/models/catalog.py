"""Catalog value objects shared by adapters and persistence."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime

from ..core.text import clean_text

CATEGORIES = {"concert", "theatre", "exhibition", "film", "sport", "kids", "other"}

# Ticket availability vocabulary shared by adapters, the DB CHECK and the
# Qdrant payload. `unknown` means "the source said something we cannot map".
AVAILABILITY_VALUES = {"in_stock", "limited", "sold_out", "unknown"}


@dataclass
class RawEvent:
    source: str
    source_id: str
    source_url: str
    title: str
    description: str | None = None
    category: str = "other"
    start_at: datetime | None = None
    end_at: datetime | None = None
    venue_id: str | None = None
    venue_name: str | None = None
    address: str | None = None
    city: str = ""
    latitude: float | None = None
    longitude: float | None = None
    price_min: float | None = None
    price_max: float | None = None
    currency: str = ""
    age_limit: int | None = None
    ticket_url: str | None = None
    image_url: str | None = None
    organizer: str | None = None
    status: str = "scheduled"
    availability: str | None = None
    capacity: int | None = None
    seats_left: int | None = None
    raw: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Single cleanup point for every adapter: dedup keys and persistence
        # both see decoration-free text. clean_text is idempotent.
        if self.title:
            self.title = clean_text(self.title) or ""
        if self.description is not None:
            self.description = clean_text(self.description)
        if self.availability not in AVAILABILITY_VALUES:
            self.availability = None
        # Availability is the source of truth for the public status; an
        # adapter may still set `status` directly (eventStatus: cancelled).
        if self.status == "scheduled" and self.availability == "sold_out":
            self.status = "sold_out"

    @property
    def dedup_key(self) -> str:
        return dedup_key_for(self.title, self.start_at, self.venue_name or "")


def dedup_key_for(title: str | None, start_at: datetime | None,
                  venue_name: str | None) -> str:
    """Normalized title | ISO start | normalized venue, shared with the
    booking mirror so both paths produce identical keys."""
    base = "|".join([
        _norm(title or ""),
        start_at.isoformat() if start_at else "",
        _norm(venue_name or ""),
    ])
    return hashlib.sha1(base.encode()).hexdigest()


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


@dataclass
class VenueRow:
    source: str = "twogis"
    source_id: str = ""
    name: str = ""
    rubric: str | None = None
    address: str | None = None
    city: str = ""
    latitude: float | None = None
    longitude: float | None = None
    schedule: dict | None = None
    rating: float | None = None
    review_count: int | None = None
    # Enrichment (2GIS attribute_groups / adm_div; absent -> None).
    hours: dict | None = None
    is_24_7: bool = False
    amenities: list[str] | None = None
    avg_check: float | None = None
    price_level: str | None = None
    district: str | None = None
    source_url: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class CatalogEvent:
    """A bookable event mirrored from booking-service (Kafka `booking.catalog`)."""

    id: int
    title: str
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    venue_name: str = ""
    city: str = ""
    category: str = "other"
    raw: dict = field(default_factory=dict)
