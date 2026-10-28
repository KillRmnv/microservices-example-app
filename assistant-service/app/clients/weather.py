"""Open-Meteo client with a bounded retry policy.

The forecast is advisory: callers get ``None`` only when every attempt
failed; retries cover transport errors and 5xx responses, never 4xx.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from ..models.weather import Weather

log = logging.getLogger(__name__)

DAILY_FIELDS = "temperature_2m_max,precipitation_probability_max,weathercode"


class OpenMeteoClient:
    def __init__(self, base_url: str, timezone: str, *,
                 attempts: int = 3, backoff_base_s: float = 0.5,
                 timeout_s: float = 15.0,
                 transport: httpx.BaseTransport | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._timezone = timezone
        self._attempts = max(1, attempts)
        self._backoff_base = backoff_base_s
        self._timeout = timeout_s
        self._transport = transport

    def params(self, date: str, lat: float, lon: float) -> dict:
        return {
            "latitude": lat,
            "longitude": lon,
            "daily": DAILY_FIELDS,
            "timezone": self._timezone,
            "start_date": date,
            "end_date": date,
        }

    async def forecast(self, date: str, lat: float, lon: float) -> Weather | None:
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self._timeout,
                                     transport=self._transport) as client:
            for attempt in range(1, self._attempts + 1):
                try:
                    response = await client.get(self._base,
                                                params=self.params(date, lat, lon))
                    if 400 <= response.status_code < 500:
                        # Bad request/date: retrying cannot help.
                        log.warning("weather %s rejected: HTTP %s",
                                    date, response.status_code)
                        return None
                    response.raise_for_status()
                    daily = response.json().get("daily", {})
                    return Weather(
                        date=date,
                        temp_max=(daily.get("temperature_2m_max") or [None])[0],
                        precipitation_probability=(
                            daily.get("precipitation_probability_max") or [None])[0],
                        weathercode=(daily.get("weathercode") or [None])[0],
                    )
                except Exception as exc:  # noqa: BLE001 — retried, then advisory
                    last_error = exc
                    log.warning("weather attempt %d/%d failed for %s: %s",
                                attempt, self._attempts, date, exc)
                    if attempt < self._attempts:
                        await asyncio.sleep(
                            self._backoff_base * (2 ** (attempt - 1)))
        log.warning("weather lookup failed for %s: %s", date, last_error)
        return None
