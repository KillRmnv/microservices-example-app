"""Persistence: upserts + cross-source dedup merge.

Same (source, source_id) -> update mutable fields.
Same dedup_key from another source -> keep the fuller record, attach URL.
Priority on ties: ticketpro > bycard > relax > afisha_me > 24afisha > telegram.
"""
from __future__ import annotations

import logging

from ..models.catalog import RawEvent, VenueRow
from ..core.config import settings
from ..sources.base import RunStats

log = logging.getLogger(__name__)

SOURCE_PRIORITY = ["ticketpro", "bycard", "relax", "afisha_me", "24afisha", "telegram"]

EVENT_COLUMNS = (
    "source, source_id, source_url, title, description, category, "
    "start_at, end_at, venue_name, address, city, lat, lon, "
    "price_min, price_max, currency, age_limit, ticket_url, image_url, "
    "organizer, status, raw, dedup_key"
)

UPSERT_SQL = f"""
INSERT INTO collected_events ({EVENT_COLUMNS})
VALUES ({", ".join(["%s"] * 23)})
ON CONFLICT (source, source_id) DO UPDATE SET
    source_url = EXCLUDED.source_url, title = EXCLUDED.title,
    description = EXCLUDED.description, category = EXCLUDED.category,
    start_at = EXCLUDED.start_at, end_at = EXCLUDED.end_at,
    venue_name = EXCLUDED.venue_name, address = EXCLUDED.address,
    price_min = EXCLUDED.price_min, price_max = EXCLUDED.price_max,
    ticket_url = EXCLUDED.ticket_url, image_url = EXCLUDED.image_url,
    organizer = EXCLUDED.organizer, status = EXCLUDED.status,
    raw = EXCLUDED.raw, dedup_key = EXCLUDED.dedup_key,
    fetched_at = now()
RETURNING id, (xmax = 0) AS inserted
"""


def _row(event: RawEvent) -> tuple:
    import json
    return (
        event.source, event.source_id, event.source_url, event.title,
        event.description, event.category,
        event.start_at, event.end_at, event.venue_name, event.address,
        event.city or settings.default_city, event.lat, event.lon,
        event.price_min, event.price_max,
        event.currency or settings.default_currency, event.age_limit,
        event.ticket_url, event.image_url, event.organizer, event.status,
        json.dumps(event.raw, ensure_ascii=False, default=str), event.dedup_key,
    )


def fullness(event: RawEvent) -> int:
    """How complete a record is — merge keeps the fuller one."""
    fields = [event.description, event.start_at, event.end_at, event.venue_name,
              event.address, event.price_min, event.image_url, event.ticket_url]
    return sum(1 for value in fields if value not in (None, ""))


def merge_decision(existing_source: str, existing_fullness: int,
                   new_source: str, new_fullness: int) -> bool:
    """True when the incoming record should replace the stored one."""
    if new_fullness != existing_fullness:
        return new_fullness > existing_fullness
    rank = {name: i for i, name in enumerate(SOURCE_PRIORITY)}
    return rank.get(new_source, 99) < rank.get(existing_source, 99)


_TWIN_FIELDS = ("description", "start_at", "end_at", "venue_name",
                 "address", "price_min", "image_url", "ticket_url")


def _twin_fullness(twin) -> int:
    return sum(1 for key in _TWIN_FIELDS if twin[key] not in (None, ""))


def upsert_events(conn, events: list[RawEvent]) -> RunStats:
    stats = RunStats()
    for event in events:
        own = conn.execute(
            "SELECT id FROM collected_events WHERE source = %s AND source_id = %s",
            (event.source, event.source_id),
        ).fetchone()
        if own is not None:
            # Re-crawl of a known card: refresh fields, no counters.
            conn.execute(UPSERT_SQL, _row(event))
            conn.execute(
                """INSERT INTO event_sources (event_id, source, source_url)
                   VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
                (own["id"], event.source, event.source_url),
            )
            continue
        twin = conn.execute(
            f"""SELECT id, source, {", ".join(_TWIN_FIELDS)}
                FROM collected_events WHERE dedup_key = %s
                ORDER BY fetched_at LIMIT 1""",
            (event.dedup_key,),
        ).fetchone()
        if twin is None:
            row = conn.execute(UPSERT_SQL, _row(event)).fetchone()
            conn.execute(
                """INSERT INTO event_sources (event_id, source, source_url)
                   VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
                (row["id"], event.source, event.source_url),
            )
            if row["inserted"]:
                stats.new_events += 1
            continue
        # Same logical event from another source: attach URL, keep fuller record.
        stats.duplicates += 1
        conn.execute(
            """INSERT INTO event_sources (event_id, source, source_url)
               VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
            (twin["id"], event.source, event.source_url),
        )
        if merge_decision(twin["source"], _twin_fullness(twin),
                          event.source, fullness(event)):
            conn.execute(
                """UPDATE collected_events SET
                       description = %s, start_at = %s, end_at = %s,
                       venue_name = %s, address = %s, price_min = %s,
                       price_max = %s, image_url = %s, ticket_url = %s,
                       title = %s, source_url = %s, fetched_at = now()
                   WHERE id = %s""",
                (event.description, event.start_at, event.end_at,
                 event.venue_name, event.address, event.price_min,
                 event.price_max, event.image_url, event.ticket_url,
                 event.title, event.source_url, twin["id"]),
            )
    return stats


VENUE_UPSERT_SQL = """
INSERT INTO collected_venues
    (source, source_id, name, rubric, address, city, lat, lon,
     schedule, rating, review_count, source_url, raw)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (source, source_id) DO UPDATE SET
    name = EXCLUDED.name, rubric = EXCLUDED.rubric,
    address = EXCLUDED.address, lat = EXCLUDED.lat, lon = EXCLUDED.lon,
    schedule = EXCLUDED.schedule, rating = EXCLUDED.rating,
    review_count = EXCLUDED.review_count, source_url = EXCLUDED.source_url,
    raw = EXCLUDED.raw, fetched_at = now()
RETURNING (xmax = 0) AS inserted
"""


def upsert_venues(conn, venues: list[VenueRow]) -> RunStats:
    import json
    stats = RunStats()
    for venue in venues:
        row = conn.execute(VENUE_UPSERT_SQL, (
            venue.source, venue.source_id, venue.name, venue.rubric,
            venue.address, venue.city, venue.lat, venue.lon,
            json.dumps(venue.schedule, ensure_ascii=False) if venue.schedule else None,
            venue.rating, venue.review_count, venue.source_url,
            json.dumps(venue.raw, ensure_ascii=False, default=str),
        )).fetchone()
        stats.parsed += 1
        if row["inserted"]:
            stats.new_events += 1
    return stats
