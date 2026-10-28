"""Weather use case: cache first, provider with retries, stale fallback."""
from __future__ import annotations

import logging
from datetime import date as date_cls, datetime, timedelta
from zoneinfo import ZoneInfo

from ..clients.cache import WeatherCache
from ..clients.weather import OpenMeteoClient
from ..models.weather import Weather

log = logging.getLogger(__name__)

STALE_TTL_MIN_S = 60
STALE_WINDOW = timedelta(days=7)


class WeatherService:
    def __init__(self, client: OpenMeteoClient, cache: WeatherCache, *,
                 ttl_s: int, timezone: str) -> None:
        self._client = client
        self._cache = cache
        self._ttl_s = max(STALE_TTL_MIN_S, ttl_s)
        self._timezone = timezone

    @staticmethod
    def _key(date: str, lat: float, lon: float) -> str:
        return f"{date}:{lat:.3f}:{lon:.3f}"

    async def forecast(self, date: str, lat: float, lon: float) -> Weather:
        key = self._key(date, lat, lon)
        cached = await self._cache.get(key)
        if cached:
            return Weather.from_cache(cached)
        weather = await self._client.forecast(date, lat, lon)
        if weather is None:
            stale = await self._cache.get_stale(key)
            if stale:
                log.info("weather provider down, serving stale forecast for %s", date)
                return Weather.from_cache(stale, stale=True)
            return Weather(date=date, available=False)
        await self._cache.set(key, weather.to_cache(), self._ttl_for(date))
        return weather

    def _ttl_for(self, date: str) -> int:
        """Cap the TTL by the end of the forecast day."""
        try:
            target = date_cls.fromisoformat(date)
        except ValueError:
            return self._ttl_s
        now = datetime.now(ZoneInfo(self._timezone))
        if target < now.date():
            return STALE_TTL_MIN_S
        end_of_day = datetime.combine(target + timedelta(days=1),
                                      datetime.min.time(), tzinfo=now.tzinfo)
        remaining = int((end_of_day - now).total_seconds())
        return max(STALE_TTL_MIN_S, min(self._ttl_s, remaining))
