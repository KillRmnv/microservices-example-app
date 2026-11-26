"""Persistence: upserts + cross-source dedup merge.

Same (source, source_id) -> update mutable fields.
Same dedup_key from another source -> keep the fuller record, attach URL.
Source priority comes from the sources table, not a hardcoded list.
Booking mirrors take part in dedup but keep their bookable identity: a merge
never rewrites the survivor's source/source_id/booking_event_id.
"""
from __future__ import annotations

import logging

import psycopg

from ..models.catalog import CatalogEvent, RawEvent, VenueRow, dedup_key_for
from ..core.config import settings
from ..models.dedup import compare as dedup_compare
from ..sources.base import RunStats

log = logging.getLogger(__name__)

# Fallback order when the sources table is unreachable (tests, bootstrap).
FALLBACK_PRIORITY = ["ticketpro", "bycard", "relax", "afisha_me",
                     "24afisha", "telegram", "twogis_places", "probe"]

EVENT_COLUMNS = (
    "source, source_id, source_url, primary_source_id, "
    "title, description, category, category_id, "
    "start_at, end_at, venue_id, venue_name, address, city, city_id, "
    "latitude, longitude, "
    "price_min, price_max, currency, currency_code, age_limit, "
    "ticket_url, image_url, organizer, status, "
    "capacity, seats_left, availability, raw, dedup_key"
)

UPSERT_SQL = f"""
INSERT INTO collected_events ({EVENT_COLUMNS})
VALUES ({", ".join(["%s"] * len(EVENT_COLUMNS.split(",")))})
ON CONFLICT (source, source_id) DO UPDATE SET
    source_url = EXCLUDED.source_url, title = EXCLUDED.title,
    description = EXCLUDED.description, category = EXCLUDED.category,
    category_id = EXCLUDED.category_id,
    start_at = EXCLUDED.start_at, end_at = EXCLUDED.end_at,
    venue_id = EXCLUDED.venue_id, venue_name = EXCLUDED.venue_name,
    address = EXCLUDED.address, city_id = EXCLUDED.city_id,
    latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude,
    price_min = EXCLUDED.price_min, price_max = EXCLUDED.price_max,
    currency_code = EXCLUDED.currency_code,
    ticket_url = EXCLUDED.ticket_url, image_url = EXCLUDED.image_url,
    organizer = EXCLUDED.organizer, status = EXCLUDED.status,
    capacity = EXCLUDED.capacity, seats_left = EXCLUDED.seats_left,
    availability = EXCLUDED.availability,
    raw = EXCLUDED.raw, dedup_key = EXCLUDED.dedup_key,
    -- Every re-crawl resets the marker: the dense embedding, BM25 text and
    -- Qdrant payload are derived from this row (title/venue/description plus
    -- price, status, capacity and the linked venue's coords). Re-embedding an
    -- unchanged row is cheap; serving a stale payload is not.
    embedded_at = NULL,
    last_seen_at = now(), fetched_at = now()
RETURNING id, (xmax = 0) AS inserted
"""


class Lookups:
    """Cached id maps for the lookup tables (one query per upsert batch)."""

    def __init__(self, conn) -> None:
        self.sources = {row["code"]: row["id"] for row in conn.execute(
            "SELECT id, code FROM sources").fetchall()}
        self.categories = {row["code"]: row["id"] for row in conn.execute(
            "SELECT id, code FROM categories").fetchall()}
        self.currencies = {row["code"] for row in conn.execute(
            "SELECT code FROM currencies").fetchall()}
        self.cities = {row["name"]: row["id"] for row in conn.execute(
            "SELECT id, name FROM cities").fetchall()}
        self.rank = {row["code"]: row["priority"] for row in conn.execute(
            "SELECT code, priority FROM sources").fetchall()}
        if not self.rank:
            self.rank = {name: i for i, name in enumerate(FALLBACK_PRIORITY)}


def _row(event: RawEvent, lookups: Lookups) -> tuple:
    import json
    city = event.city or settings.default_city
    currency = event.currency or settings.default_currency
    return (
        event.source, event.source_id, event.source_url,
        lookups.sources.get(event.source),
        event.title, event.description,
        event.category, lookups.categories.get(event.category),
        event.start_at, event.end_at,
        event.venue_id, event.venue_name, event.address,
        city, lookups.cities.get(city),
        event.latitude, event.longitude,
        event.price_min, event.price_max,
        currency, currency if currency in lookups.currencies else None,
        event.age_limit,
        event.ticket_url, event.image_url, event.organizer, event.status,
        event.capacity, event.seats_left, event.availability,
        json.dumps(event.raw, ensure_ascii=False, default=str), event.dedup_key,
    )


def fullness(event: RawEvent) -> int:
    """How complete a record is — merge keeps the fuller one."""
    fields = [event.description, event.start_at, event.end_at, event.venue_name,
              event.address, event.price_min, event.image_url, event.ticket_url]
    return sum(1 for value in fields if value not in (None, ""))


def merge_decision(existing_source: str, existing_fullness: int,
                   new_source: str, new_fullness: int,
                   rank: dict | None = None) -> bool:
    """True when the incoming record should replace the stored one."""
    if new_fullness != existing_fullness:
        return new_fullness > existing_fullness
    order = rank if rank is not None else {
        name: i for i, name in enumerate(FALLBACK_PRIORITY)}
    return order.get(new_source, 99) < order.get(existing_source, 99)


_TWIN_FIELDS = ("description", "start_at", "end_at", "venue_name",
                 "address", "price_min", "image_url", "ticket_url")


def _twin_fullness(twin) -> int:
    return sum(1 for key in _TWIN_FIELDS if twin[key] not in (None, ""))


def _attach_source(conn, lookups: Lookups, event_id, source: str,
                   source_url: str, is_primary: bool) -> None:
    conn.execute(
        """INSERT INTO event_sources
               (event_id, source, source_id, source_url, is_primary)
           VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (event_id, source, source_url) DO UPDATE SET
               last_seen_at = now(),
               is_primary = event_sources.is_primary OR EXCLUDED.is_primary""",
        (event_id, source, lookups.sources.get(source), source_url, is_primary),
    )


def _link_venue(conn, lookups: Lookups, event: RawEvent) -> None:
    """Exact (name, city) match against the 2GIS directory, else NULL."""
    if event.venue_id is not None or not event.venue_name:
        return
    city = event.city or settings.default_city
    row = conn.execute(
        "SELECT id FROM collected_venues WHERE name = %s AND city = %s LIMIT 1",
        (event.venue_name, city)).fetchone()
    if row is not None:
        event.venue_id = row["id"]


def upsert_events(conn, events: list[RawEvent]) -> RunStats:
    stats = RunStats()
    lookups = Lookups(conn)
    for event in events:
        # One bad card must not poison the batch: isolate each write in a
        # savepoint so a constraint violation rolls back only that event.
        try:
            with conn.transaction():
                _upsert_one(conn, lookups, event, stats)
        except psycopg.Error as exc:
            stats.parse_errors += 1
            log.warning("skipping %s/%s: %s", event.source,
                        event.source_id, exc)
    return stats


def _upsert_one(conn, lookups: Lookups, event: RawEvent, stats: RunStats) -> None:
    # Serialize candidate lookup + insert. A single key avoids lock-order
    # deadlocks when batches contain different dates, and also protects
    # undated rows from racing the exact dedup_key unique index.
    conn.execute("SELECT pg_advisory_xact_lock(hashtext('dedup:events'))")
    _link_venue(conn, lookups, event)
    own = conn.execute(
        "SELECT id FROM collected_events WHERE source = %s AND source_id = %s",
        (event.source, event.source_id),
    ).fetchone()
    if own is not None:
        # Re-crawl of a known card: refresh fields.
        conn.execute(UPSERT_SQL, _row(event, lookups))
        _attach_source(conn, lookups, own["id"], event.source,
                       event.source_url, True)
        stats.rows_updated += 1
        return
    twin = conn.execute(
        f"""SELECT id, source, venue_id, category, title,
                   {", ".join(_TWIN_FIELDS)}
            FROM collected_events WHERE dedup_key = %s
            ORDER BY fetched_at LIMIT 1""",
        (event.dedup_key,),
    ).fetchone()
    if twin is None:
        twin = _fuzzy_twin(conn, event)
    if twin is None:
        row = conn.execute(UPSERT_SQL, _row(event, lookups)).fetchone()
        _attach_source(conn, lookups, row["id"], event.source,
                       event.source_url, True)
        if row["inserted"]:
            stats.rows_inserted += 1
        return
    _merge_twin(conn, lookups, event, twin, stats)


def _fuzzy_twin(conn, event: RawEvent):
    """Nearest same-city candidate around the event date, if confident.

    Booking mirrors take part: the same concert sold by booking-service and
    scraped from Ticketpro must collapse into one row (the booking row keeps
    its `booking_event_id`; a merge never rewrites source/source_id).
    """
    city = event.city or settings.default_city
    start = event.start_at
    rows = conn.execute(
        f"""SELECT id, source, venue_id, category, title,
                   {", ".join(_TWIN_FIELDS)}
            FROM collected_events
            WHERE city = %s
              AND (%s::TIMESTAMPTZ IS NULL
                   OR start_at IS NULL
                   OR start_at BETWEEN %s::TIMESTAMPTZ - INTERVAL '2 days'
                                    AND %s::TIMESTAMPTZ + INTERVAL '2 days')
            ORDER BY fetched_at DESC
            LIMIT 250""",
        (city, start, start, start),
    ).fetchall()
    best = None
    best_score = 0.0
    for row in rows:
        decision = dedup_compare(event, row)
        if decision.merge and decision.score > best_score:
            best, best_score = row, decision.score
    if best is not None:
        log.info("fuzzy duplicate %s/%s -> %s (score %.3f)",
                 event.source, event.source_id, best["id"], best_score)
    return best


def _merge_twin(conn, lookups: Lookups, event: RawEvent, twin, stats: RunStats) -> None:
    # Same logical event from another source: attach URL, keep fuller record.
    # The survivor keeps its identity (source/source_id/booking_event_id) —
    # only descriptive fields are borrowed.
    stats.duplicates += 1
    _attach_source(conn, lookups, twin["id"], event.source,
                   event.source_url, False)
    if merge_decision(twin["source"], _twin_fullness(twin),
                      event.source, fullness(event), lookups.rank):
        conn.execute(
            """UPDATE collected_events SET
                   description = %s, start_at = %s, end_at = %s,
                   venue_name = %s, address = %s, price_min = %s,
                   price_max = %s, image_url = %s, ticket_url = %s,
                   title = %s, source_url = %s, status = %s,
                   capacity = %s, seats_left = %s, availability = %s,
                   embedded_at = NULL,
                   last_seen_at = now(), fetched_at = now()
               WHERE id = %s""",
            (event.description, event.start_at, event.end_at,
             event.venue_name, event.address, event.price_min,
             event.price_max, event.image_url, event.ticket_url,
             event.title, event.source_url, event.status,
             event.capacity, event.seats_left, event.availability,
             twin["id"]),
        )
        stats.rows_updated += 1
        return
    # The survivor stays authoritative (e.g. a booking row), but capacity and
    # seats are additive facts the other source may be the only one to know.
    # Availability is intentionally not filled here: it drives `status`, which
    # belongs to the survivor (booking owns its inventory and republishes is).
    if any(value is not None for value in (event.capacity, event.seats_left)):
        conn.execute(
            """UPDATE collected_events SET
                   capacity = COALESCE(capacity, %s),
                   seats_left = COALESCE(seats_left, %s),
                   embedded_at = NULL
               WHERE id = %s
                 AND ((capacity IS NULL AND %s IS NOT NULL)
                   OR (seats_left IS NULL AND %s IS NOT NULL))""",
            (event.capacity, event.seats_left, twin["id"],
             event.capacity, event.seats_left),
        )


CATALOG_UPSERT_SQL = """
INSERT INTO collected_events
    (source, source_id, source_url, primary_source_id, booking_event_id,
     title, description, category, category_id, start_at, end_at,
     venue_name, city, city_id, currency, currency_code, status, raw, dedup_key)
VALUES ('booking', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        'scheduled', %s, %s)
ON CONFLICT (source, source_id) DO UPDATE SET
    booking_event_id = EXCLUDED.booking_event_id,
    title = EXCLUDED.title,
    category = EXCLUDED.category,
    category_id = EXCLUDED.category_id,
    start_at = EXCLUDED.start_at,
    end_at = EXCLUDED.end_at,
    venue_name = EXCLUDED.venue_name,
    city = EXCLUDED.city,
    city_id = EXCLUDED.city_id,
    dedup_key = EXCLUDED.dedup_key,
    raw = EXCLUDED.raw,
    last_seen_at = now(),
    fetched_at = now(),
    embedded_at = NULL
WHERE collected_events.title IS DISTINCT FROM EXCLUDED.title
   OR collected_events.category IS DISTINCT FROM EXCLUDED.category
   OR collected_events.start_at IS DISTINCT FROM EXCLUDED.start_at
   OR collected_events.end_at IS DISTINCT FROM EXCLUDED.end_at
   OR collected_events.venue_name IS DISTINCT FROM EXCLUDED.venue_name
   OR collected_events.city IS DISTINCT FROM EXCLUDED.city
RETURNING id
"""


def _adopt_catalog_event(conn, row_id, booking_id: int, raw: str) -> str | None:
    """Attach a bookable id to an existing scraped row (identity untouched)."""
    adopted = conn.execute(
        """UPDATE collected_events SET
               booking_event_id = %s, raw = %s,
               last_seen_at = now(), fetched_at = now(),
               embedded_at = NULL
           WHERE id = %s
             AND (booking_event_id IS DISTINCT FROM %s
                  OR raw IS DISTINCT FROM %s::jsonb)
           RETURNING id""",
        (booking_id, raw, row_id, booking_id, raw),
    ).fetchone()
    return adopted["id"] if adopted is not None else None


def upsert_catalog_event(conn, event: CatalogEvent) -> str | None:
    """Mirror one booking-service event; returns the row id when it changed.

    Mirrored rows carry the same dedup_key as scraped rows so the same event
    collapses into one search result. If a scraper got there first, the
    scraped row is *adopted* (it keeps source/source_id, gains the bookable id)
    instead of inserting a duplicate; the unique dedup index covers scraped
    rows only, so two bookable performances with identical title/time/venue
    can still coexist.
    """
    import json

    lookups = Lookups(conn)
    raw = json.dumps(event.raw, ensure_ascii=False, default=str)
    dedup_key = dedup_key_for(event.title, event.starts_at, event.venue_name)
    # Same serialisation key as scraped upserts: the dedup lookup and the
    # insert must be atomic against a concurrent crawl of the same event.
    conn.execute("SELECT pg_advisory_xact_lock(hashtext('dedup:events'))")
    own = conn.execute(
        "SELECT id, source FROM collected_events WHERE booking_event_id = %s",
        (event.id,),
    ).fetchone()
    if own is not None and own["source"] != "booking":
        # Already adopted by a scraped row; refresh is a no-op when unchanged.
        return _adopt_catalog_event(conn, own["id"], event.id, raw)
    if own is None:
        twin = conn.execute(
            """SELECT id FROM collected_events
               WHERE dedup_key = %s AND source <> 'booking'
                 AND booking_event_id IS NULL
               ORDER BY fetched_at LIMIT 1""",
            (dedup_key,),
        ).fetchone()
        if twin is not None:
            return _adopt_catalog_event(conn, twin["id"], event.id, raw)
    row = conn.execute(CATALOG_UPSERT_SQL, (
        str(event.id),
        f"booking://events/{event.id}",
        lookups.sources.get("booking"),
        event.id,
        event.title,
        None,
        event.category,
        lookups.categories.get(event.category),
        event.starts_at,
        event.ends_at,
        event.venue_name or None,
        event.city or settings.default_city,
        lookups.cities.get(event.city or settings.default_city),
        settings.default_currency,
        settings.default_currency,
        raw,
        dedup_key,
    )).fetchone()
    return row["id"] if row is not None else None


def delete_catalog_event(conn, booking_id: int) -> str | None:
    """Drop a mirrored event; returns the Qdrant point id to delete."""
    row = conn.execute(
        "DELETE FROM collected_events"
        " WHERE source = 'booking' AND source_id = %s RETURNING id",
        (str(booking_id),)).fetchone()
    if row is not None:
        return row["id"]
    # The mirror may live on a scraped row that adopted it (see
    # upsert_catalog_event). The row itself is still a legitimate scraped
    # event, so keep its Qdrant point (return None) and only drop the now
    # dangling bookable id; embedded_at reset refreshes its payload.
    conn.execute(
        """UPDATE collected_events SET
               booking_event_id = NULL, embedded_at = NULL, last_seen_at = now()
           WHERE booking_event_id = %s""",
        (booking_id,),
    )
    return None


VENUE_UPSERT_SQL = """
INSERT INTO collected_venues
    (source, source_id, name, rubric, address, city, city_id,
     latitude, longitude, schedule, rating, review_count,
     avg_check, amenities, price_level, district, source_url, raw)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s)
ON CONFLICT (source, source_id) DO UPDATE SET
    name = EXCLUDED.name, rubric = EXCLUDED.rubric,
    address = EXCLUDED.address, city_id = EXCLUDED.city_id,
    latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude,
    schedule = EXCLUDED.schedule, rating = EXCLUDED.rating,
    review_count = EXCLUDED.review_count,
    avg_check = EXCLUDED.avg_check, amenities = EXCLUDED.amenities,
    price_level = EXCLUDED.price_level, district = EXCLUDED.district,
    source_url = EXCLUDED.source_url,
    raw = EXCLUDED.raw, fetched_at = now(),
    -- Rebuild the venue point only when a payload/embedding input changed.
    embedded_at = CASE WHEN
        collected_venues.name IS DISTINCT FROM EXCLUDED.name
        OR collected_venues.rubric IS DISTINCT FROM EXCLUDED.rubric
        OR collected_venues.address IS DISTINCT FROM EXCLUDED.address
        OR collected_venues.city IS DISTINCT FROM EXCLUDED.city
        OR collected_venues.latitude IS DISTINCT FROM EXCLUDED.latitude
        OR collected_venues.longitude IS DISTINCT FROM EXCLUDED.longitude
        OR collected_venues.schedule IS DISTINCT FROM EXCLUDED.schedule
        OR collected_venues.rating IS DISTINCT FROM EXCLUDED.rating
        OR collected_venues.review_count IS DISTINCT FROM EXCLUDED.review_count
        OR collected_venues.amenities IS DISTINCT FROM EXCLUDED.amenities
        OR collected_venues.avg_check IS DISTINCT FROM EXCLUDED.avg_check
        OR collected_venues.price_level IS DISTINCT FROM EXCLUDED.price_level
        OR collected_venues.district IS DISTINCT FROM EXCLUDED.district
        THEN NULL ELSE collected_venues.embedded_at END
RETURNING (xmax = 0) AS inserted
"""


def upsert_venues(conn, venues: list[VenueRow]) -> RunStats:
    import json
    stats = RunStats()
    lookups = Lookups(conn)
    for venue in venues:
        city = venue.city or settings.default_city
        row = conn.execute(VENUE_UPSERT_SQL, (
            venue.source, venue.source_id, venue.name, venue.rubric,
            venue.address, city, lookups.cities.get(city),
            venue.latitude, venue.longitude,
            json.dumps(venue.schedule, ensure_ascii=False) if venue.schedule else None,
            venue.rating, venue.review_count,
            venue.avg_check,
            json.dumps(venue.amenities, ensure_ascii=False) if venue.amenities else None,
            venue.price_level, venue.district, venue.source_url,
            json.dumps(venue.raw, ensure_ascii=False, default=str),
        )).fetchone()
        stats.parsed += 1
        if row["inserted"]:
            stats.rows_inserted += 1
        else:
            stats.rows_updated += 1
    return stats
