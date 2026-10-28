"""Booking hold (reservation intent) domain model."""
from __future__ import annotations

from dataclasses import dataclass

PENDING = "PENDING"
CONFIRMED = "CONFIRMED"
EXPIRED = "EXPIRED"


@dataclass
class Hold:
    id: str
    session_id: str
    event_id: int
    zone: str
    price: float
    party_size: int
    status: str
