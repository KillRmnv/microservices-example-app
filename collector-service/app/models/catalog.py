"""Catalog value objects shared by adapters and persistence."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime


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
    raw: dict = field(default_factory=dict)

    @property
    def dedup_key(self) -> str:
        base = "|".join([
            _norm(self.title),
            self.start_at.isoformat() if self.start_at else "",
            _norm(self.venue_name or ""),
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
    source_url: str | None = None
    raw: dict = field(default_factory=dict)
