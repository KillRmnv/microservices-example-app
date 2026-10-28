"""Weather cache backends: Redis in the cluster, a no-op for tests/local."""
from __future__ import annotations

import json
import logging
from typing import Protocol

log = logging.getLogger(__name__)

STALE_TTL_S = 7 * 24 * 3600


class WeatherCache(Protocol):
    async def get(self, key: str) -> dict | None: ...

    async def get_stale(self, key: str) -> dict | None: ...

    async def set(self, key: str, value: dict, ttl_s: int) -> None: ...

    async def close(self) -> None: ...


class NullWeatherCache:
    """Disabled cache: always a miss, never fails."""

    async def get(self, key: str) -> dict | None:
        return None

    async def get_stale(self, key: str) -> dict | None:
        return None

    async def set(self, key: str, value: dict, ttl_s: int) -> None:
        return None

    async def close(self) -> None:
        return None


class RedisWeatherCache:
    def __init__(self, url: str, *, prefix: str = "assistant:weather:") -> None:
        from redis.asyncio import Redis

        self._client = Redis.from_url(url, decode_responses=True)
        self._prefix = prefix

    def _fresh_key(self, key: str) -> str:
        return self._prefix + "fresh:" + key

    def _stale_key(self, key: str) -> str:
        return self._prefix + "stale:" + key

    async def _read(self, key: str) -> dict | None:
        try:
            raw = await self._client.get(key)
        except Exception as exc:  # noqa: BLE001 — cache must not break a turn
            log.warning("weather cache read failed: %s", exc)
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            return None

    async def get(self, key: str) -> dict | None:
        return await self._read(self._fresh_key(key))

    async def get_stale(self, key: str) -> dict | None:
        return await self._read(self._stale_key(key))

    async def set(self, key: str, value: dict, ttl_s: int) -> None:
        payload = json.dumps(value)
        try:
            await self._client.set(self._fresh_key(key), payload,
                                   ex=max(1, int(ttl_s)))
            await self._client.set(self._stale_key(key), payload, ex=STALE_TTL_S)
        except Exception as exc:  # noqa: BLE001
            log.warning("weather cache write failed: %s", exc)

    async def close(self) -> None:
        try:
            await self._client.aclose()
        except Exception:  # noqa: BLE001
            pass


def build_weather_cache(url: str | None) -> WeatherCache:
    if not url:
        return NullWeatherCache()
    return RedisWeatherCache(url)
