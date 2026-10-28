"""Booking intent ("hold") use case.

A hold reserves an intent for 10 minutes; it is stored locally because
booking-service has no public hold API yet. The server validates the zone and
price against live tickets instead of trusting the client request.
"""
from __future__ import annotations

import logging

from ..clients.booking import BookingClient
from ..core import db
from ..errors import (
    BackendUnavailable,
    ConflictError,
    HoldGone,
    PriceMismatch,
    ValidationError,
)
from ..models.availability import SOLD_OUT, UNKNOWN
from ..models.hold import Hold
from ..repositories import holds as holds_repo

log = logging.getLogger(__name__)

PARTY_SIZE_MIN = 1
PARTY_SIZE_MAX = 20
PRICE_EPSILON = 0.01


class HoldService:
    def __init__(self, db_url: str, booking: BookingClient) -> None:
        self._db_url = db_url
        self._booking = booking

    async def create(self, *, session_id: str, event_id: int, zone: str,
                     price: float, party_size: int) -> Hold:
        party = max(PARTY_SIZE_MIN, min(PARTY_SIZE_MAX, int(party_size)))
        with db.get_conn(self._db_url) as conn:
            existing = holds_repo.find_pending(conn, session_id, event_id)
        if existing is not None:
            return existing
        availability = await self._booking.check_availability(event_id)
        if availability.status == UNKNOWN:
            raise BackendUnavailable("booking-service is unavailable")
        if availability.status == SOLD_OUT:
            raise ConflictError("event is sold out")
        self._validate(zone, price, availability)
        # TODO(stage-3b): replace this local intent with a real inventory
        # hold in booking-service once user-auth passthrough exists.
        with db.get_conn(self._db_url) as conn:
            existing = holds_repo.find_pending(conn, session_id, event_id)
            if existing is not None:
                return existing
            return holds_repo.create(conn, session_id, event_id, zone,
                                     float(price), party)

    @staticmethod
    def _validate(zone: str, price: float, availability) -> None:
        if not zone.strip():
            raise ValidationError("zone is required")
        if price <= 0:
            raise ValidationError("price must be positive")
        if not availability.zones:
            return
        match = next((slot for slot in availability.zones
                      if slot["zone"] == zone), None)
        if match is None:
            raise ValidationError(f"unknown zone: {zone}")
        min_price = match.get("min_price")
        if min_price is not None and price + PRICE_EPSILON < float(min_price):
            raise PriceMismatch(
                f"price {price} is below the {zone} minimum {min_price}")

    def confirm(self, hold_id: str) -> Hold:
        with db.get_conn(self._db_url) as conn:
            hold = holds_repo.confirm(conn, hold_id)
        if hold is None:
            raise HoldGone("hold missing, taken or expired")
        return hold

    def sweep(self) -> int:
        with db.get_conn(self._db_url) as conn:
            return holds_repo.expire(conn)
