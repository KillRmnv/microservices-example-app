"""Ticket availability returned by booking-service."""
from __future__ import annotations

from dataclasses import dataclass, field

AVAILABLE = "available"
FEW_LEFT = "few_left"
# Not enough seats for the requested party (new availability endpoint).
INSUFFICIENT = "insufficient"
SOLD_OUT = "sold_out"
UNKNOWN = "unknown"


@dataclass
class Availability:
    event_id: int
    status: str
    min_price: float | None = None
    zones: list[dict] = field(default_factory=list)
    # New endpoint fields; None when the old ticket-search path answered.
    capacity: int | None = None
    seats_left: int | None = None
