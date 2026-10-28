"""Polite HTTP client: per-source rate limiting, retries with backoff.

Never hammer a source: obey Crawl-delay style intervals, honour
Retry-After and identify with a contact User-Agent.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from urllib.parse import urlparse

import httpx

from .core.logging import redact_url

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class PoliteClient:
    def __init__(
        self,
        user_agent: str,
        default_min_interval_s: float = 1.0,
        max_attempts: int = 4,
        backoff_base_s: float = 2.0,
        timeout_s: float = 20.0,
        intervals: dict[str, float] | None = None,
        transport: httpx.BaseTransport | None = None,
        verify: bool = True,
    ) -> None:
        self._client = httpx.AsyncClient(
            headers={"User-Agent": user_agent},
            timeout=timeout_s,
            follow_redirects=True,
            transport=transport,
            verify=verify,
        )
        self._default_interval = default_min_interval_s
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base_s
        self._intervals = intervals or {}
        self._last_at: dict[str, float] = {}
        self._lock = asyncio.Lock()

    def _key(self, source: str, url: str) -> str:
        return f"{source}|{urlparse(url).netloc}"

    def _interval(self, source: str) -> float:
        return self._intervals.get(source, self._default_interval)

    async def _pace(self, key: str, interval: float) -> None:
        async with self._lock:
            wait = interval - (time.monotonic() - self._last_at.get(key, 0.0))
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_at[key] = time.monotonic()

    async def get(self, source: str, url: str, *,
                  before_attempt: Callable[[], None] | None = None,
                  **kwargs) -> httpx.Response:
        """GET with pacing + retry. Raises the last error after max_attempts.

        `before_attempt` runs before every HTTP attempt (billable APIs use it
        to consume one quota unit per attempt, retries included).
        """
        key = self._key(source, url)
        interval = self._interval(source)
        last_exc: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            await self._pace(key, interval)
            if before_attempt is not None:
                before_attempt()
            try:
                response = await self._client.get(url, **kwargs)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.PoolTimeout) as exc:
                last_exc = exc
                log.warning("fetch %s failed (attempt %d): %s",
                            redact_url(url), attempt, exc)
            else:
                if response.status_code not in RETRYABLE_STATUS:
                    return response
                last_exc = RuntimeError(
                    f"HTTP {response.status_code} for {redact_url(url)}")
                log.warning("fetch %s -> %s (attempt %d)",
                            redact_url(url), response.status_code, attempt)
                retry_after = response.headers.get("retry-after")
                if retry_after and retry_after.isdigit():
                    await asyncio.sleep(float(retry_after))
                    continue
            await asyncio.sleep(self._backoff_base * (2 ** (attempt - 1)))
        assert last_exc is not None
        raise last_exc

    async def aclose(self) -> None:
        await self._client.aclose()
