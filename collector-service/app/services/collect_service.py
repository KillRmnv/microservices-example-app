"""Collection use case: pick an adapter, run it, record the source_run."""
from __future__ import annotations

import logging
import time

from ..core import db
from ..errors import UnknownSource, UpstreamError
from ..http import PoliteClient
from ..repositories import queries, runs
from ..sources.afisha_me import AfishaMeAdapter
from ..sources.base import CollectContext, RunStats, SourceAdapter
from ..sources.relax import RelaxAdapter
from ..sources.telegram import TelegramAdapter
from ..sources.ticketpro import TicketproAdapter
from ..sources.twogis_places import TwogisPlacesAdapter

log = logging.getLogger(__name__)

ADAPTERS: dict[str, SourceAdapter] = {
    TicketproAdapter.name: TicketproAdapter(),
    RelaxAdapter.name: RelaxAdapter(),
    AfishaMeAdapter.name: AfishaMeAdapter(),
    TelegramAdapter.name: TelegramAdapter(),
    TwogisPlacesAdapter.name: TwogisPlacesAdapter(),
}


class CollectService:
    def __init__(self, http: PoliteClient, db_url: str) -> None:
        self._http = http
        self._db_url = db_url

    @property
    def sources(self) -> list[str]:
        return sorted(ADAPTERS)

    def adapter(self, source: str) -> SourceAdapter:
        adapter = ADAPTERS.get(source)
        if adapter is None:
            raise UnknownSource(f"unknown source: {source}")
        return adapter

    def record_run(self, source: str, status: str, stats: RunStats,
                   error: str | None, duration_s: float,
                   error_code: str | None = None) -> None:
        with db.get_conn(self._db_url) as conn:
            runs.record(conn, source, status, stats, error, duration_s,
                        error_code)

    @staticmethod
    def run_status(stats: RunStats) -> str:
        if stats.quota_stopped:
            return "quota_exhausted"
        if stats.parse_errors or stats.fetch_errors:
            return "partial"
        return "ok"

    async def collect(self, source: str, limit: int | None = None) -> RunStats:
        adapter = self.adapter(source)
        started = time.monotonic()
        stats = RunStats()
        try:
            stats = await adapter.collect(
                CollectContext(http=self._http, db_url=self._db_url,
                               max_urls=limit))
        except Exception as exc:  # noqa: BLE001 — recorded, then surfaced
            self.record_run(source, "error", stats, str(exc),
                            time.monotonic() - started)
            raise UpstreamError(f"collect failed: {exc}") from exc
        status = self.run_status(stats)
        self.record_run(source, status, stats, None, time.monotonic() - started)
        try:
            with db.get_conn(self._db_url) as conn:
                queries.link_event_venues(conn)
        except Exception as exc:  # noqa: BLE001 — linking is best-effort
            log.warning("venue linking failed: %s", exc)
        return stats

    async def probe(self, source: str, url: str) -> dict:
        started = time.monotonic()
        stats = RunStats()
        try:
            response = await self._http.get(source, url)
        except Exception as exc:  # noqa: BLE001 — recorded, then surfaced
            stats.fetch_errors = 1
            self.record_run(source, "error", stats, str(exc),
                            time.monotonic() - started)
            raise UpstreamError(f"fetch failed: {exc}") from exc
        stats.fetched = 1
        stats.parsed = 1 if response.status_code == 200 else 0
        self.record_run(source, "ok", stats, None, time.monotonic() - started)
        return {
            "source": source,
            "status_code": response.status_code,
            "bytes": len(response.content),
            "final_url": str(response.url),
        }
