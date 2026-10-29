"""Collector-service read client (lexical fallback for hybrid search)."""
from __future__ import annotations

import logging

import httpx

from ..errors import UpstreamError

log = logging.getLogger(__name__)


class CollectorClient:
    """Thin wrapper over collector read endpoints (fakeable in tests)."""

    def __init__(self, base_url: str, transport: httpx.BaseTransport | None = None,
                 timeout_s: float = 15.0) -> None:
        self._base = base_url.rstrip("/")
        self._transport = transport
        self._timeout = timeout_s

    async def _get(self, path: str, params: dict) -> list[dict]:
        try:
            async with httpx.AsyncClient(base_url=self._base, timeout=self._timeout,
                                         transport=self._transport) as client:
                response = await client.get(path, params=params)
                response.raise_for_status()
                return response.json()
        except Exception as exc:  # noqa: BLE001 — one dead backend must not 500
            log.warning("collector request %s failed: %s", path, exc)
            raise UpstreamError(f"collector search failed: {exc}") from exc

    async def search_lexical(self, query: str, city: str | None,
                             category: str | None, limit: int,
                             *, date_from: str | None = None,
                             date_to: str | None = None) -> list[dict]:
        params = {"q": query, "limit": limit}
        if city:
            params["city"] = city
        if category:
            params["category"] = category
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        return (await self._get("/events/search", params))["events"]

    async def search_venues_lexical(self, query: str, city: str | None,
                                    rubric: str | None, limit: int) -> list[dict]:
        params = {"q": query, "limit": limit}
        if city:
            params["city"] = city
        if rubric:
            params["rubric"] = rubric
        return (await self._get("/venues/search", params))["venues"]
