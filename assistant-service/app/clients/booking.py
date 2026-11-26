"""booking-service read client (public catalog reads, no auth)."""
from __future__ import annotations

import logging
from dataclasses import asdict

import httpx

from ..models.availability import (
    AVAILABLE,
    FEW_LEFT,
    INSUFFICIENT,
    SOLD_OUT,
    UNKNOWN,
    Availability,
)
from .cache import AvailabilityCache

log = logging.getLogger(__name__)

# Fallback pagination: never trust a single page=1&size=500 window.
TICKET_PAGE_SIZE = 200
MAX_TICKET_PAGES = 50
FEW_LEFT_THRESHOLD = 10
KNOWN_STATUSES = {AVAILABLE, FEW_LEFT, INSUFFICIENT, SOLD_OUT, UNKNOWN}
AVAILABILITY_TTL_S = 30


def availability_key(event_id: int, party: int | None) -> str:
    return f"availability:{event_id}:{int(party) if party else 0}"


def _as_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def _as_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class BookingClient:
    def __init__(self, base_url: str, transport: httpx.BaseTransport | None = None,
                 timeout_s: float = 15.0,
                 few_left_threshold: int = FEW_LEFT_THRESHOLD,
                 availability_cache: AvailabilityCache | None = None,
                 availability_ttl_s: int = AVAILABILITY_TTL_S) -> None:
        self._base = base_url.rstrip("/")
        self._transport = transport
        self._timeout = timeout_s
        self._few_left = max(1, int(few_left_threshold))
        self._availability_cache = availability_cache
        self._availability_ttl_s = max(1, int(availability_ttl_s))

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

    async def check_availability(self, event_id: int,
                                 party: int | None = None) -> Availability:
        """Availability for an optional party size.

        The new single endpoint knows about capacity and party size; when it
        is missing or broken (404/5xx/network) the old two-index ticket count
        answers instead. `insufficient` means "no seats for this party".
        Known answers are cached briefly; `unknown` is retried every turn.
        """
        cache = self._availability_cache
        key = availability_key(event_id, party)
        if cache is not None:
            cached = await cache.get(key)
            if isinstance(cached, dict):
                # Deserialize on every hit: callers may mutate `zones`.
                return self._from_cache(cached)
        availability = await self._availability_probe(event_id, party)
        if availability is None:
            availability = await self._availability_from_tickets(event_id)
        if cache is not None and availability.status != UNKNOWN:
            await cache.set(key, asdict(availability),
                            self._availability_ttl_s)
        return availability

    @staticmethod
    def _from_cache(data: dict) -> Availability:
        zones = [dict(zone) for zone in data.get("zones") or []
                 if isinstance(zone, dict)]
        return Availability(
            event_id=int(data.get("event_id") or 0),
            status=str(data.get("status") or UNKNOWN),
            min_price=_as_float(data.get("min_price")),
            zones=zones,
            capacity=_as_int(data.get("capacity")),
            seats_left=_as_int(data.get("seats_left")),
        )

    async def _availability_probe(self, event_id: int,
                                  party: int | None) -> Availability | None:
        params = {"party": int(party)} if party and party >= 1 else None
        try:
            data = (await self._get(
                f"/booking/events/{event_id}/availability", params)).json()
        except Exception as exc:  # noqa: BLE001 — fall back to ticket count
            log.info("availability probe %s failed, falling back: %s",
                     event_id, exc)
            return None
        if not isinstance(data, dict) or "status" not in data:
            # Old booking-service (or a misrouted mock): use the fallback.
            return None
        return self._from_payload(event_id, data)

    @staticmethod
    def _from_payload(event_id: int, data: dict) -> Availability:
        status = str(data.get("status") or UNKNOWN).strip().lower()
        if status not in KNOWN_STATUSES:
            status = UNKNOWN
        zones: list[dict] = []
        prices: list[float] = []
        seats: list[int] = []
        for raw in data.get("zones") or []:
            if not isinstance(raw, dict):
                continue
            min_price = _as_float(raw.get("minPrice",
                                          raw.get("min_price")))
            seats_left = _as_int(raw.get("seatsLeft", raw.get("seats_left")))
            zones.append({
                "zone": str(raw.get("zone") or "BASIC"),
                "count": seats_left,
                "seats_left": seats_left,
                "min_price": min_price,
            })
            if min_price is not None:
                prices.append(min_price)
            if seats_left is not None:
                seats.append(seats_left)
        capacity = _as_int(data.get("capacity"))
        return Availability(
            event_id=event_id,
            status=status,
            min_price=min(prices) if prices else None,
            zones=sorted(zones, key=lambda zone: zone["min_price"] or 0),
            capacity=capacity,
            # Zones are the source of truth; a null zone count means the
            # total is unknown rather than zero.
            seats_left=sum(seats) if seats else None,
        )

    async def _availability_from_tickets(self, event_id: int) -> Availability:
        """Legacy path: count active tickets in both search indexes.

        Both indexes count towards availability, otherwise seatable events
        look sold out. Pages are walked until a short page so a large event
        is not silently capped at the first 500 tickets.
        """
        tickets: list[dict] = []
        failed = 0
        for path in ("/booking/tickets/search",
                     "/booking/seatable-tickets/search"):
            page_tickets, page_failed = await self._all_pages(path, event_id)
            tickets.extend(page_tickets)
            failed += page_failed
        if failed == 2:
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
            status=AVAILABLE if count >= self._few_left else FEW_LEFT,
            min_price=min(prices) if prices else None,
            zones=sorted(by_zone.values(), key=lambda zone: zone["min_price"] or 0),
            seats_left=count,
        )

    async def _all_pages(self, path: str, event_id: int
                         ) -> tuple[list[dict], int]:
        tickets: list[dict] = []
        for page in range(1, MAX_TICKET_PAGES + 1):
            params = {"eventId": event_id, "active": True,
                      "page": page, "size": TICKET_PAGE_SIZE}
            try:
                batch = (await self._get(path, params)).json()
            except Exception as exc:  # noqa: BLE001 — one index may be empty
                log.warning("availability %s (%s) failed: %s",
                            event_id, path, exc)
                return tickets, 1
            if not isinstance(batch, list):
                return tickets, 1
            tickets.extend(batch)
            if len(batch) < TICKET_PAGE_SIZE:
                return tickets, 0
        return tickets, 0
