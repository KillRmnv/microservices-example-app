"""Afisha.relax.by: sitemap inventory -> cards with Event JSON-LD.

Card JSON-LD needs control-char cleaning; repertoire cards carry stale
startDate, so endDate >= now is required. Crawl-delay: 10s (robots + §6).
"""
from __future__ import annotations

import gzip
import logging
import re
from datetime import datetime, timezone

from ..core import db
from ..normalize import RawEvent, normalize_jsonld
from ..parse import extract_json_ld_events
from ..repositories.store import upsert_events
from .base import CollectContext, RunStats, SourceAdapter

log = logging.getLogger(__name__)

SITEMAP = "https://afisha.relax.by/sitemap-eventsAfisha.xml.gz"
LOC_RE = re.compile(r"<loc>([^<]+)</loc>")

# /theatre/4774-buratino-by/minsk/ -> theatre.
CATEGORY_BY_SEGMENT = {
    "theatre": "theatre",
    "concerts": "concert",
    "concert": "concert",
    "exhibitions": "exhibition",
    "cinema": "film",
    "sport": "sport",
    "kids": "kids",
}


def category_for(url: str) -> str:
    segment = url.split("afisha.relax.by/")[1].split("/")[0] if "afisha.relax.by/" in url else ""
    return CATEGORY_BY_SEGMENT.get(segment, "other")


class RelaxAdapter(SourceAdapter):
    name = "relax"

    async def collect(self, ctx: CollectContext) -> RunStats:
        stats = RunStats()
        now = datetime.now(timezone.utc)
        response = await ctx.http.get(self.name, SITEMAP)
        stats.fetched += 1
        if response.status_code != 200:
            raise RuntimeError(f"sitemap -> HTTP {response.status_code}")
        try:
            xml = gzip.decompress(response.content).decode("utf-8", errors="replace")
        except OSError:
            xml = response.text
        urls = [loc for loc in LOC_RE.findall(xml) if "/minsk/" in loc]
        if ctx.max_urls:
            urls = urls[:ctx.max_urls]
        log.info("relax sitemap: %d minsk urls", len(urls))
        with db.get_conn(ctx.db_url) as conn:
            for url in urls:
                try:
                    card = await ctx.http.get(self.name, url)
                except Exception as exc:  # noqa: BLE001 — one card must not kill the run
                    stats.fetch_errors += 1
                    log.warning("relax card %s failed: %s", url, exc)
                    continue
                stats.fetched += 1
                if card.status_code != 200:
                    stats.fetch_errors += 1
                    continue
                found = extract_json_ld_events(card.text)
                if not found:
                    # Page without any Event markup: broken card, not a filter hit.
                    stats.parse_errors += 1
                    continue
                events: list[RawEvent] = []
                for data in found:
                    event = normalize_jsonld(
                        self.name, source_id=url, source_url=url,
                        category=category_for(url), data=data, now_utc=now)
                    if event is None:
                        continue  # stale repertoire / non-Minsk: intentional skip
                    stats.parsed += 1
                    events.append(event)
                if not events:
                    continue
                merged = upsert_events(conn, events)
                stats.rows_inserted += merged.rows_inserted
                stats.rows_updated += merged.rows_updated
                stats.duplicates += merged.duplicates
                conn.commit()
        return stats
