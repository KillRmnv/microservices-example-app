"""booking-service read client (public catalog reads, no auth)."""
from __future__ import annotations

import logging

import httpx

from ..models.availability import AVAILABLE, FEW_LEFT, SOLD_OUT, UNKNOWN, Availability

log = logging.getLogger(__name__)

TICKET_PAGE_SIZE = 500
FEW_LEFT_THRESHOLD = 10


class BookingClient:
    def __init__(self, base_url: str, transport: httpx.BaseTransport | None = None,
                 timeout_s: float = 15.0) -> None:
        self._base = base_url.rstrip("/")
        self._transport = transport
        self._timeout = timeout_s

    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        async with httpx.AsyncClient(base_url=self._base, timeout=self._timeout,
                                     transport=self._transport) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response

    async def get_event(self, event_id: int) -> dict | None:
        try:
            return (await self._get(f"/booking/events/{event_id}")).json()
        except Exception as exc:  # noqa: BLE001 — a miss is a valid answer
            log.warning("get_event %s failed: %s", event_id, exc)
            return None

    async def check_availability(self, event_id: int) -> Availability:
        """Active tickets for the event -> availability status + zone prices."""
        try:
            tickets = (await self._get(
                "/booking/tickets/search",
                {"eventId": event_id, "active": True,
                 "page": 1, "size": TICKET_PAGE_SIZE})).json()
        except Exception as exc:  # noqa: BLE001
            log.warning("availability %s failed: %s", event_id, exc)
            return Availability(event_id=event_id, status=UNKNOWN)
        active = [ticket for ticket in tickets if ticket.get("active")]
        if not active:
            exists = await self.get_event(event_id)
            return Availability(
                event_id=event_id,
                status=SOLD_OUT if exists is not None else UNKNOWN)
        prices = [ticket["price"] for ticket in active
                  if ticket.get("price") is not None]
        by_zone: dict[str, dict] = {}
        for ticket in active:
            zone = str(ticket.get("zone", "BASIC"))
            slot = by_zone.setdefault(
                zone, {"zone": zone, "count": 0, "min_price": None})
            slot["count"] += 1
            price = ticket.get("price")
            if price is not None and (slot["min_price"] is None
                                      or price < slot["min_price"]):
                slot["min_price"] = price
        count = len(active)
        return Availability(
            event_id=event_id,
            status=AVAILABLE if count >= FEW_LEFT_THRESHOLD else FEW_LEFT,
            min_price=min(prices) if prices else None,
            zones=sorted(by_zone.values(), key=lambda zone: zone["min_price"] or 0),
        )
