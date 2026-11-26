"""Ticketpro.by: listings with embedded Event JSON-LD, ?page=N pagination.

~25 events per page. Observed maxima are capped by MAX_PAGES as a guard;
collection stops early on the first page with zero new cards.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..core import db
from ..errors.domain import SourceFetchError
from ..parsing.normalize import RawEvent, normalize_jsonld, normalize_next_event
from ..parsing.html import extract_json_ld_events, extract_next_events
from ..repositories.store import upsert_events
from .base import CollectContext, RunStats, SourceAdapter

log = logging.getLogger(__name__)

BASE = "https://www.ticketpro.by"

# Listing path -> our category. Cinema cards are film *runs* (startTime..endTime
# intervals per cinema), not exact showtimes; one row per film+cinema+interval
# keeps date search useful without multiplying every screening.
LISTINGS = {
    "/bilety-na-koncert/": "concert",
    "/bilety-v-teatr/": "theatre",
    "/bilety-na-shou/": "other",
    "/festivali/": "concert",
    "/detskie-meropriyatiya/": "kids",
    "/bilety-v-kino/": "film",
    "/bilety-na-sportivnye-meropriyatiya/": "sport",
}

MAX_PAGES = 20
# A cinema catalogue is long and low-yield per page: cap it separately.
LISTING_PAGE_CAPS = {"/bilety-v-kino/": 5}


class TicketproAdapter(SourceAdapter):
    name = "ticketpro"

    async def collect(self, ctx: CollectContext) -> RunStats:
        stats = RunStats()
        now = datetime.now(timezone.utc)
        with db.get_conn(ctx.db_url) as conn:
            for path, category in LISTINGS.items():
                try:
                    await self._collect_listing(ctx, conn, stats, now, path, category)
                except Exception as exc:  # noqa: BLE001 — one listing must not kill the run
                    stats.fetch_errors += 1
                    conn.rollback()
                    log.warning("ticketpro listing %s failed: %s", path, exc)
        if stats.fetched == 0:
            raise SourceFetchError("all ticketpro listings failed")
        return stats

    async def _collect_listing(self, ctx, conn, stats, now, path, category) -> None:
        page = 1
        max_pages = LISTING_PAGE_CAPS.get(path, MAX_PAGES)
        while page <= max_pages:
            url = f"{BASE}{path}" + (f"?page={page}" if page > 1 else "")
            response = await ctx.http.get(self.name, url)
            stats.fetched += 1
            if response.status_code != 200:
                raise SourceFetchError(f"{url} -> HTTP {response.status_code}")
            cards = extract_json_ld_events(response.text)
            if not cards:
                items = extract_next_events(response.text)
                if items:
                    events: list[RawEvent] = []
                    for item in items:
                        slug = item.get("slug") or ""
                        source_id = str(item.get("externalId")
                                        or item.get("id") or slug)
                        event = normalize_next_event(
                            self.name,
                            source_id=source_id,
                            source_url=f"{BASE}/ru/event/{slug}" if slug else url,
                            category=category,
                            data=item,
                            now_utc=now,
                        )
                        if event is None:
                            continue
                        stats.parsed += 1
                        events.append(event)
                    merged = upsert_events(conn, events)
                    stats.rows_inserted += merged.rows_inserted
                    stats.rows_updated += merged.rows_updated
                    stats.duplicates += merged.duplicates
                    conn.commit()
                    log.info("ticketpro %s page %d: %d next cards",
                             path, page, len(items))
                break
            events: list[RawEvent] = []
            for card in cards:
                if card.get("@type") != "Event":
                    continue
                event = normalize_jsonld(
                    self.name,
                    source_id=card.get("url") or f"{url}#{len(events)}",
                    source_url=url,
                    category=category,
                    data=card,
                    now_utc=now,
                )
                if event is None:
                    continue
                stats.parsed += 1
                events.append(event)
            merged = upsert_events(conn, events)
            stats.rows_inserted += merged.rows_inserted
            stats.rows_updated += merged.rows_updated
            stats.duplicates += merged.duplicates
            conn.commit()
            log.info("ticketpro %s page %d: %d cards", path, page, len(cards))
            page += 1
