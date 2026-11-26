"""Afisha.me: per-category sitemaps -> cards with schema.org microdata.

No JSON-LD here; robots forbids query pagination, so inventory comes
exclusively from the sitemaps. Crawl-delay: 10s.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from ..core import db
from ..errors.domain import SourceFetchError
from ..parsing.film import FilmPage, extract_film_page
from ..parsing.normalize import RawEvent, parse_age, parse_datetime, parse_price
from ..parsing.html import clean_text, extract_microdata_event
from ..repositories.store import upsert_events
from .base import CollectContext, RunStats, SourceAdapter

log = logging.getLogger(__name__)

SITEMAPS = {
    "https://afisha.me/sitemap/map-concert-minsk-1.xml": "concert",
    "https://afisha.me/sitemap/map-theatre-minsk-1.xml": "theatre",
    "https://afisha.me/sitemap/map-exhibition-minsk-1.xml": "exhibition",
    # Live-verified page shape: Movie scope h1 + Event sessions per cinema.
    # Entries are cinema runs (earliest session..latest + 2h), not showtimes.
    "https://afisha.me/sitemap/map-film-minsk-1.xml": "film",
}
FILM_DURATION = timedelta(hours=2)
LOC_RE = re.compile(r"<loc>([^<]+)</loc>")


class AfishaMeAdapter(SourceAdapter):
    name = "afisha_me"

    async def collect(self, ctx: CollectContext) -> RunStats:
        stats = RunStats()
        now = datetime.now(timezone.utc)
        done = 0
        with db.get_conn(ctx.db_url) as conn:
            for sitemap, category in SITEMAPS.items():
                if ctx.max_urls is not None and done >= ctx.max_urls:
                    break
                response = await ctx.http.get(self.name, sitemap)
                stats.fetched += 1
                if response.status_code != 200:
                    raise SourceFetchError(f"sitemap {sitemap} -> HTTP {response.status_code}")
                urls = LOC_RE.findall(response.text)
                if ctx.max_urls is not None:
                    urls = urls[:max(0, ctx.max_urls - done)]
                log.info("afisha.me %s: %d urls", sitemap, len(urls))
                for url in urls:
                    done += 1
                    try:
                        card = await ctx.http.get(self.name, url)
                    except Exception as exc:  # noqa: BLE001 — per-card resilience
                        stats.fetch_errors += 1
                        log.warning("afisha.me card %s failed: %s", url, exc)
                        continue
                    stats.fetched += 1
                    if card.status_code != 200:
                        stats.fetch_errors += 1
                        continue
                    if category == "film":
                        page = extract_film_page(card.text)
                        if page is None:
                            stats.parse_errors += 1
                            continue
                        events = self.film_events(url, page, now)
                        if not events:
                            continue  # run already ended: intentional skip
                        stats.parsed += len(events)
                        merged = upsert_events(conn, events)
                        stats.rows_inserted += merged.rows_inserted
                        stats.rows_updated += merged.rows_updated
                        stats.duplicates += merged.duplicates
                        conn.commit()
                        continue
                    event = self.normalize(url, category, card.text, now)
                    if event is None:
                        if extract_microdata_event(card.text) is None:
                            stats.parse_errors += 1  # markup gone, not a filter hit
                        continue  # past showtime / unparsable: intentional skip
                    stats.parsed += 1
                    merged = upsert_events(conn, [event])
                    stats.rows_inserted += merged.rows_inserted
                    stats.rows_updated += merged.rows_updated
                    stats.duplicates += merged.duplicates
                    conn.commit()
        return stats

    def film_events(self, url: str, page: FilmPage, now) -> list[RawEvent]:
        """One run per (film, cinema): earliest start .. latest start or +2h."""
        grouped: dict[str, list] = {}
        for session in page.sessions:
            start = parse_datetime(session.start_at)
            if start is not None:
                grouped.setdefault(session.cinema, []).append((start, session))
        events: list[RawEvent] = []
        for cinema, entries in grouped.items():
            entries.sort(key=lambda item: item[0])
            starts = [item[0] for item in entries]
            earliest, latest = starts[0], starts[-1]
            if latest + FILM_DURATION < now:
                continue  # the whole cinema run has ended
            prices = [parse_price(item[1].price) for item in entries]
            lows = [low for low, _ in prices if low is not None]
            highs = [high for _, high in prices if high is not None]
            end_at = max(latest, earliest + FILM_DURATION)
            events.append(RawEvent(
                source=self.name,
                source_id=f"{url}#{cinema}",
                source_url=url,
                title=page.title,
                category="film",
                start_at=earliest,
                end_at=end_at,
                venue_name=cinema,
                address=entries[0][1].address,
                price_min=min(lows) if lows else None,
                price_max=max(highs) if highs else None,
                age_limit=page.age_limit,
                ticket_url=url,
                image_url=page.image,
                raw={"film": page.title, "cinema": cinema,
                     "sessions": len(entries), "url": url},
            ))
        return events

    def normalize(self, url: str, category: str, html: str, now) -> RawEvent | None:
        data = extract_microdata_event(html)
        if data is None or not data.get("name"):
            return None
        start_at = parse_datetime(data.get("startDate"))
        if start_at is not None and start_at < now:
            return None  # past showtime
        # Cards come from minsk-only sitemaps, so the city is implied.
        venue = clean_text(data.get("venue_name"))
        price_min, price_max = parse_price(data.get("price_text"))
        age_limit = None
        for tag in data.get("tags", []):
            age_limit = parse_age(tag)
            if age_limit is not None:
                break
        title = clean_text(data["name"])
        if not title:
            return None
        return RawEvent(
            source=self.name,
            source_id=url,
            source_url=url,
            title=title,
            description=None,
            category=category,
            start_at=start_at,
            venue_name=venue,
            address=clean_text(data.get("address")),
            price_min=price_min,
            price_max=price_max,
            age_limit=age_limit,
            ticket_url=url,
            image_url=data.get("image"),
            raw={"microdata": data, "url": url},
        )
