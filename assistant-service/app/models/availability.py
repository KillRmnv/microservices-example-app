"""Ticket availability returned by booking-service."""
from __future__ import annotations

from dataclasses import dataclass, field

AVAILABLE = "available"
FEW_LEFT = "few_left"
SOLD_OUT = "sold_out"
UNKNOWN = "unknown"


@dataclass
class Availability:
    event_id: int
    status: str
    min_price: float | None = None
    zones: list[dict] = field(default_factory=list)
