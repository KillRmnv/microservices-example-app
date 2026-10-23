"""Tool implementations behind the dialogue (course.md tool set).

Real I/O only here; orchestration lives in dialogue.py. Every tool degrades
to a structured miss instead of raising, so one dead backend never kills
the whole turn.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

log = logging.getLogger(__name__)

MINSK_TZ = ZoneInfo("Europe/Minsk")
MINSK_CENTER = (53.9056, 27.5539)

# Folk landmarks + metro stations (Nominatim is 403 from our network).
LANDMARKS: dict[str, tuple[float, float]] = {
    "немига": (53.9056, 27.5539),
    "троицкое предместье": (53.9083, 27.5566),
    "троицкое": (53.9083, 27.5566),
    "парк челюскинцев": (53.9247, 27.6136),
    "парк горького": (53.9036, 27.5716),
    "октябрьская площадь": (53.9028, 27.5618),
    "ст. м. октябрьская": (53.9028, 27.5618),
    "ст м октябрьская": (53.9028, 27.5618),
    "октябрьская": (53.9028, 27.5618),
    "площадь победы": (53.9085, 27.5746),
    "верхний город": (53.9025, 27.5546),
    "комаровка": (53.9167, 27.5803),
    "минск-арена": (53.9431, 27.4822),
    "дворец республики": (53.9028, 27.5618),
    "дворец спорта": (53.9342, 27.5540),
    "ботанический сад": (53.9167, 27.6136),
    "лошицкий парк": (53.8500, 27.6200),
}

WMO_RAIN = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 95, 96, 99}
WMO_SNOW = {71, 73, 75, 77, 85, 86}


@dataclass
class Weather:
    date: str
    temp_max: float | None = None
    precipitation_probability: int | None = None
    weathercode: int | None = None
    available: bool = True

    @property
    def is_rainy(self) -> bool:
        return (self.weathercode in WMO_RAIN
                or (self.precipitation_probability or 0) >= 60)

    def advice_ru(self) -> str:
        if not self.available:
            return "Прогноз недоступен."
        if self.is_rainy:
            return (f"{self.date}: дождь вероятен "
                    f"({self.precipitation_probability}%), "
                    f"макс. {self.temp_max}°. Уличное лучше перенести в помещение.")
        return (f"{self.date}: без дождя ({self.precipitation_probability}%), "
                f"макс. {self.temp_max}°. Для прогулки подходит.")


def get_current_datetime(timezone: str = "Europe/Minsk") -> datetime:
    """Tool: anchor for relative expressions (завтра, в выходные)."""
    try:
        return datetime.now(ZoneInfo(timezone))
    except Exception:  # noqa: BLE001 — bad tz name from a model
        log.warning("bad timezone %r, falling back to Europe/Minsk", timezone)
        return datetime.now(MINSK_TZ)


def resolve_location(query: str | None, city: str = "Минск") -> dict:
    """Tool: folk landmark -> coords. Falls back to the city center.

    Matches by 5-letter stem so inflections work (Немига/Немиги/Немиге).
    """
    if query:
        normalized = query.strip().casefold()
        for name, coords in LANDMARKS.items():
            stem = name[:5] if len(name) >= 5 else name
            if stem and (stem in normalized or normalized in name):
                return {"lat": coords[0], "lon": coords[1],
                        "label": query.strip(), "city": city}
    return {"lat": MINSK_CENTER[0], "lon": MINSK_CENTER[1],
            "label": "центр Минска", "city": city}


async def get_weather_forecast(date: str, lat: float, lon: float,
                               transport: httpx.BaseTransport | None = None) -> Weather:
    """Tool: Open-Meteo daily forecast, no key needed."""
    url = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={lat}&longitude={lon}"
           "&daily=temperature_2m_max,precipitation_probability_max,weathercode"
           "&timezone=Europe%2FMinsk"
           f"&start_date={date}&end_date={date}")
    try:
        async with httpx.AsyncClient(timeout=15.0, transport=transport) as client:
            response = await client.get(url)
            response.raise_for_status()
            daily = response.json().get("daily", {})
        return Weather(
            date=date,
            temp_max=(daily.get("temperature_2m_max") or [None])[0],
            precipitation_probability=(daily.get("precipitation_probability_max") or [None])[0],
            weathercode=(daily.get("weathercode") or [None])[0],
        )
    except Exception as exc:  # noqa: BLE001 — weather is advisory, not fatal
        log.warning("weather lookup failed for %s: %s", date, exc)
        return Weather(date=date, available=False)


@dataclass
class Availability:
    event_id: int
    status: str  # available | few_left | sold_out | unknown
    min_price: float | None = None
    zones: list[dict] = field(default_factory=list)


class BookingClient:
    """booking-service read calls (no auth needed for public catalog reads)."""

    def __init__(self, base_url: str, transport: httpx.BaseTransport | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._transport = transport

    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        async with httpx.AsyncClient(base_url=self._base, timeout=15.0,
                                     transport=self._transport) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response

    async def get_event(self, event_id: int) -> dict | None:
        try:
            return (await self._get(f"/booking/events/{event_id}")).json()
        except Exception as exc:  # noqa: BLE001
            log.warning("get_event %s failed: %s", event_id, exc)
            return None

    async def check_availability(self, event_id: int) -> Availability:
        """Tool: active tickets for the event -> availability status."""
        try:
            tickets = (await self._get("/booking/tickets/search",
                                       {"eventId": event_id, "active": True,
                                        "page": 1, "size": 500})).json()
        except Exception as exc:  # noqa: BLE001
            log.warning("availability %s failed: %s", event_id, exc)
            return Availability(event_id=event_id, status="unknown")
        active = [t for t in tickets if t.get("active")]
        if not active:
            exists = await self.get_event(event_id)
            return Availability(
                event_id=event_id,
                status="sold_out" if exists is not None else "unknown")
        prices = [t["price"] for t in active if t.get("price") is not None]
        by_zone: dict[str, dict] = {}
        for ticket in active:
            zone = str(ticket.get("zone", "BASIC"))
            slot = by_zone.setdefault(zone, {"zone": zone, "count": 0, "min_price": None})
            slot["count"] += 1
            if ticket.get("price") is not None and (
                    slot["min_price"] is None or ticket["price"] < slot["min_price"]):
                slot["min_price"] = ticket["price"]
        count = len(active)
        return Availability(
            event_id=event_id,
            status="available" if count >= 10 else "few_left",
            min_price=min(prices) if prices else None,
            zones=sorted(by_zone.values(), key=lambda z: z["min_price"] or 0),
        )
