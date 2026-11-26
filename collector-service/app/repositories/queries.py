"""Read queries for the collected catalog."""
from __future__ import annotations

import json

EVENT_COLUMNS = (
    "id, source, source_url, booking_event_id, title, category, start_at,"
    " end_at, venue_name, address, city, price_min, price_max, currency"
)

# Everything the catalog UI needs for a card/detail view.
CARD_COLUMNS = (
    "e.id, e.source, e.source_url, e.booking_event_id, e.title,"
    " e.description, e.category, e.start_at, e.end_at, e.venue_name,"
    " e.address, e.city, e.price_min, e.price_max, e.currency,"
    " e.image_url, e.venue_id, e.status, e.availability, e.capacity,"
    " e.seats_left, e.age_limit, v.latitude, v.longitude, v.name AS venue_ref,"
    " v.rating AS venue_rating, v.review_count AS venue_review_count,"
    " v.schedule AS venue_schedule,"
    " e.raw->'film' AS film_meta,"
    " e.raw->'film'->'genre' AS film_genre,"
    " (e.raw->'film'->>'duration_minutes')::int AS film_duration_min"
)

VENUE_COLUMNS = (
    "id, source, source_url, name, rubric, address, city, latitude,"
    " longitude, rating, review_count, schedule, amenities, avg_check,"
    " price_level, district, atmosphere"
)

# Columns the embedding backfill needs for the Qdrant payload (venue joins add
# coordinates/rating used for map + ranking filters on the assistant side).
EMBED_EVENT_COLUMNS = (
    "e.id, e.source, e.booking_event_id, e.title, e.venue_name, e.description,"
    " e.address, e.city, e.category, e.price_min, e.price_max, e.start_at,"
    " e.end_at, e.status, e.age_limit, e.currency, e.capacity, e.seats_left,"
    " e.venue_id, v.latitude AS venue_lat, v.longitude AS venue_lon,"
    " v.rating AS venue_rating, v.review_count AS venue_review_count,"
    # Bycard film metadata (genre/duration) merged into raw.film.
    " e.raw->'film' AS film_meta,"
    # Availability freshness: when the source row was last fetched.
    " e.fetched_at"
)
EMBED_VENUE_COLUMNS = (
    "id, source, name, rubric, address, city, latitude, longitude, rating,"
    " review_count, schedule, amenities, avg_check, price_level, district,"
    " atmosphere"
)

# Normalised name matching: "Дворец Республики  Минск" -> "дворецреспубликиминск",
# which contains the 2GIS name "дворецреспублики".
_NORM = "regexp_replace(lower({}), '[^a-zа-я0-9]+', '', 'g')"
_EVENT_NORM = _NORM.format("coalesce(e.venue_name, '')")
_VENUE_NORM = _NORM.format("coalesce(v.name, '')")
# Second linking pass: a venue address contained in the event address. 2GIS
# stores `full_address_name` ("Минск, улица Ленина, 1") while scraped events
# often omit the city, so the city token is stripped from the venue side first.
_EVENT_ADDR_NORM = _NORM.format("coalesce(e.address, '')")
_VENUE_ADDR_NORM = _NORM.format(
    "replace(lower(coalesce(v.address, '')), lower(coalesce(v.city, '')), '')")
MIN_ADDRESS_MATCH = 8  # "Минск" (5) is too weak; "улицаЛенина12" is fine

_VENUE_JOIN = "LEFT JOIN collected_venues v ON v.id = e.venue_id"
# Single-row detail lookup keeps the legacy name fallback: one LATERAL loop
# is cheap, while list/search queries use the direct venue_id join.
_VENUE_LATERAL = f"""
    LEFT JOIN LATERAL (
        SELECT v.id, v.latitude, v.longitude, v.name, v.rating,
               v.review_count, v.schedule
        FROM collected_venues v
        WHERE v.city = e.city
          AND length({_VENUE_NORM}) >= 5
          AND ({_EVENT_NORM} LIKE '%%' || {_VENUE_NORM} || '%%'
               OR {_VENUE_NORM} LIKE '%%' || {_EVENT_NORM} || '%%')
        ORDER BY length(v.name) DESC
        LIMIT 1
    ) v ON true
"""


def _filters(city, category, source, date_from, date_to, q, ids,
             categories=None, include_cancelled=False):
    clauses, params = [], []
    # Cancelled events stay in the DB (detail pages, history) but not in the
    # public listing/search.
    if not include_cancelled:
        clauses.append("e.status <> 'cancelled'")
    if city:
        clauses.append("e.city = %s")
        params.append(city)
    selected = categories or ([category] if category else None)
    if selected:
        clauses.append("e.category = ANY(%s::TEXT[])")
        params.append(selected)
    if source:
        clauses.append("e.source = %s")
        params.append(source)
    if date_from:
        clauses.append("e.start_at IS NOT NULL")
        clauses.append("COALESCE(e.end_at, e.start_at) >= %s::date")
        params.append(date_from)
    if date_to:
        clauses.append("e.start_at < (%s::date + INTERVAL '1 day')")
        params.append(date_to)
    if q:
        clauses.append("e.search_vector @@ plainto_tsquery('russian', %s)")
        params.append(q)
    if ids:
        clauses.append("e.id = ANY(%s::uuid[])")
        params.append(ids)
    return clauses, params


def list_events(conn, *, city=None, category=None, source=None,
                date_from=None, date_to=None, q=None, ids=None,
                categories=None, include_cancelled=False,
                limit=40, offset=0) -> tuple[list[dict], int]:
    clauses, params = _filters(city, category, source, date_from, date_to,
                               q, ids, categories, include_cancelled)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    total = conn.execute(
        f"SELECT count(*) AS n FROM collected_events e {where}",
        params).fetchone()["n"]
    order = "e.start_at NULLS LAST, e.title"
    if ids:
        order = "array_position(%s::uuid[], e.id)"
        params = params + [ids]
    rows = conn.execute(
        f"""SELECT {CARD_COLUMNS}
            FROM collected_events e
            {_VENUE_JOIN}
            {where}
            ORDER BY {order}
            LIMIT %s OFFSET %s""",
        params + [limit, offset]).fetchall()
    return [dict(row) for row in rows], total


def get_event(conn, event_id: str) -> dict | None:
    row = conn.execute(
        f"""SELECT {CARD_COLUMNS}
            FROM collected_events e
            {_VENUE_LATERAL}
            WHERE e.id = %s""", (event_id,)).fetchone()
    return dict(row) if row is not None else None


def search_events(conn, q: str, city: str | None, category: str | None,
                  limit: int, date_from: str | None = None,
                  date_to: str | None = None,
                  categories: list[str] | None = None,
                  include_cancelled: bool = False) -> list[dict]:
    """Lexical half of hybrid search: tsvector rank + filters."""
    selected = categories or ([category] if category else None)
    rows = conn.execute(
        f"""SELECT {CARD_COLUMNS},
                   ts_rank_cd(e.search_vector,
                              plainto_tsquery('russian', %s)) AS rank
            FROM collected_events e
            {_VENUE_JOIN}
            WHERE e.search_vector @@ plainto_tsquery('russian', %s)
            AND (%s::BOOLEAN OR e.status <> 'cancelled')
            AND (%s::TEXT IS NULL OR e.city = %s)
            AND (%s::TEXT[] IS NULL OR e.category = ANY(%s::TEXT[]))
            AND (%s::TIMESTAMPTZ IS NULL OR e.start_at < %s::TIMESTAMPTZ)
            AND (%s::TIMESTAMPTZ IS NULL
                 OR e.start_at IS NOT NULL
                    AND COALESCE(e.end_at, e.start_at) >= %s::TIMESTAMPTZ)
            ORDER BY rank DESC LIMIT %s""",
        (q, q, include_cancelled, city, city, selected, selected,
         date_to, date_to, date_from, date_from, limit)).fetchall()
    return [dict(row) for row in rows]


def list_venues(conn, *, city=None, rubric=None, q=None,
                limit=60, offset=0) -> tuple[list[dict], int]:
    clauses, params = [], []
    if city:
        clauses.append("city = %s")
        params.append(city)
    if rubric:
        clauses.append("rubric = %s")
        params.append(rubric)
    if q:
        clauses.append("search_vector @@ plainto_tsquery('russian', %s)")
        params.append(q)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    total = conn.execute(
        f"SELECT count(*) AS n FROM collected_venues {where}",
        params).fetchone()["n"]
    rows = conn.execute(
        f"""SELECT {VENUE_COLUMNS} FROM collected_venues {where}
            ORDER BY name LIMIT %s OFFSET %s""",
        params + [limit, offset]).fetchall()
    return [dict(row) for row in rows], total


def get_venue(conn, venue_id: str) -> dict | None:
    row = conn.execute(
        f"SELECT {VENUE_COLUMNS} FROM collected_venues WHERE id = %s",
        (venue_id,)).fetchone()
    return dict(row) if row is not None else None


def venue_events(conn, venue_id: str, limit: int = 20) -> list[dict]:
    rows = conn.execute(
        f"""SELECT {CARD_COLUMNS}
            FROM collected_events e
            {_VENUE_JOIN}
            WHERE e.venue_id = %s
            ORDER BY e.start_at NULLS LAST, e.title
            LIMIT %s""", (venue_id, limit)).fetchall()
    if rows:
        return [dict(row) for row in rows]
    # Legacy rows collected before venue linking: fall back to a name match.
    # pg_trgm index on venue_name keeps this from scanning the whole table.
    venue = conn.execute(
        "SELECT name FROM collected_venues WHERE id = %s",
        (venue_id,)).fetchone()
    if venue is None or not venue["name"]:
        return []
    rows = conn.execute(
        f"""SELECT {CARD_COLUMNS}
            FROM collected_events e
            {_VENUE_JOIN}
            WHERE e.venue_id IS NULL
              AND e.venue_name ILIKE %s
            ORDER BY e.start_at NULLS LAST, e.title
            LIMIT %s""", (f"%{venue['name']}%", limit)).fetchall()
    return [dict(row) for row in rows]


def search_venues(conn, q: str, city: str | None, rubric: str | None,
                  limit: int) -> list[dict]:
    rows = conn.execute(
        f"""SELECT {VENUE_COLUMNS},
                   ts_rank_cd(search_vector,
                              plainto_tsquery('russian', %s)) AS rank
            FROM collected_venues
            WHERE search_vector @@ plainto_tsquery('russian', %s)
            AND (%s::TEXT IS NULL OR city = %s)
            AND (%s::TEXT IS NULL OR rubric = %s)
            ORDER BY rank DESC LIMIT %s""",
        (q, q, city, city, rubric, rubric, limit)).fetchall()
    return [dict(row) for row in rows]


def unembedded_events(conn, source: str, limit: int | None) -> list:
    params: list = []
    query = (f"SELECT {EMBED_EVENT_COLUMNS}"
             " FROM collected_events e"
             " LEFT JOIN collected_venues v ON v.id = e.venue_id"
             " WHERE e.embedded_at IS NULL")
    if source != "all":
        query += " AND e.source = %s"
        params.append(source)
    query += " ORDER BY e.fetched_at"
    if limit:
        query += " LIMIT %s"
        params.append(max(1, limit))
    return conn.execute(query, params).fetchall()


def unembedded_venues(conn, limit: int | None) -> list:
    query = (f"SELECT {EMBED_VENUE_COLUMNS}"
             " FROM collected_venues WHERE embedded_at IS NULL ORDER BY fetched_at")
    params: list = []
    if limit:
        query += " LIMIT %s"
        params.append(max(1, limit))
    return conn.execute(query, params).fetchall()


def mark_events_embedded(conn, ids: list) -> None:
    conn.execute(
        "UPDATE collected_events SET embedded_at = now() WHERE id = ANY(%s)",
        (ids,))
    conn.commit()


def mark_venues_embedded(conn, ids: list) -> None:
    conn.execute(
        "UPDATE collected_venues SET embedded_at = now() WHERE id = ANY(%s)",
        (ids,))
    conn.commit()


def all_events_for_reindex(conn) -> list:
    """Every event row with the fields needed for hybrid reindex."""
    return conn.execute(
        f"SELECT {EMBED_EVENT_COLUMNS}"
        " FROM collected_events e"
        " LEFT JOIN collected_venues v ON v.id = e.venue_id"
        " ORDER BY e.fetched_at").fetchall()


def all_venues_for_reindex(conn) -> list:
    return conn.execute(
        f"SELECT {EMBED_VENUE_COLUMNS} FROM collected_venues"
        " ORDER BY fetched_at").fetchall()


def atmosphere_candidates(conn, limit: int) -> list:
    """Venues with the text sources needed for atmosphere enrichment.

    Unenriched rows (``atmosphere IS NULL``) come first, then the oldest ones,
    so repeated bounded runs eventually cover the whole directory. Linked
    event descriptions are aggregated with Telegram first (the desktop editor
    of most catalog copy) and newest first.
    """
    return conn.execute(
        """SELECT v.id, v.name, v.rubric, v.atmosphere, v.raw,
                  (SELECT string_agg(e.description, E'\n'
                                     ORDER BY (e.source = 'telegram') DESC,
                                              e.fetched_at DESC)
                     FROM collected_events e
                    WHERE e.venue_id = v.id
                      AND e.description IS NOT NULL
                      AND e.description <> '') AS event_text
             FROM collected_venues v
            ORDER BY (v.atmosphere IS NOT NULL), v.fetched_at
            LIMIT %s""",
        (limit,)).fetchall()


def set_venue_atmosphere(conn, venue_id, tags: list[str]) -> bool:
    """Write the tag array and reset the embed marker only when it changed."""
    payload = json.dumps(tags, ensure_ascii=False)
    result = conn.execute(
        """UPDATE collected_venues
              SET atmosphere = %s::jsonb, embedded_at = NULL
            WHERE id = %s
              AND atmosphere IS DISTINCT FROM %s::jsonb""",
        (payload, venue_id, payload))
    return result.rowcount > 0


def ticketpro_missing_descriptions(conn, limit: int) -> list:
    """Ticketpro rows that still need a detail-page description.

    Future/newest events first (they are the ones users browse). A row needs
    at least one detail-page source: `externalUrl`, a slug (live rows store
    `externalUrl = null`), or an event-page `source_url`.
    """
    return conn.execute(
        """SELECT id, raw->>'externalUrl' AS external_url,
                  raw->>'slug' AS slug, source_url
             FROM collected_events
            WHERE source = 'ticketpro'
              AND description IS NULL
              AND (NULLIF(raw->>'externalUrl', '') IS NOT NULL
                   OR NULLIF(raw->>'slug', '') IS NOT NULL
                   OR source_url LIKE '%%/event/%%')
            ORDER BY (start_at IS NULL OR start_at < now()),
                     start_at DESC NULLS LAST, fetched_at DESC
            LIMIT %s""",
        (limit,)).fetchall()


def set_event_description(conn, event_id, description: str) -> bool:
    """Fill a missing description; the null guard makes re-runs no-ops."""
    row = conn.execute(
        """UPDATE collected_events
              SET description = %s, embedded_at = NULL
            WHERE id = %s AND description IS NULL
          RETURNING id""",
        (description, event_id)).fetchone()
    return row is not None


def film_events_for_metadata(conn) -> list:
    """Every film row, with the fields the ByCard enrichment may fill."""
    return conn.execute(
        """SELECT id, title, description, image_url, raw
             FROM collected_events
            WHERE category = 'film'
            ORDER BY fetched_at DESC""").fetchall()


def update_film_metadata(conn, event_id, description, image_url, raw: dict) -> bool:
    """Write enrichment values and drop the embedding marker (payload derive)."""
    row = conn.execute(
        """UPDATE collected_events
              SET description = %s, image_url = %s, raw = %s::jsonb,
                  embedded_at = NULL
            WHERE id = %s
          RETURNING id""",
        (description, image_url, json.dumps(raw, ensure_ascii=False), event_id),
    ).fetchone()
    return row is not None


def telegram_channel_stats(conn) -> dict:
    """Last-run per-channel Telegram counters (stored in collector_kv)."""
    rows = conn.execute(
        "SELECT key, value FROM collector_kv"
        " WHERE key LIKE 'telegram:stats:%%'").fetchall()
    stats = {}
    for row in rows:
        handle = row["key"].split(":", 2)[-1]
        try:
            value = json.loads(row["value"])
        except (TypeError, ValueError):
            continue
        if isinstance(value, dict):
            stats[handle] = value
    return stats


def link_event_venues(conn) -> int:
    """Backfill summary.venue_id from the 2GIS venue directory.

    Pass 1 (name) wins: an event whose venue name contains a normalised 2GIS
    name is linked first. Pass 2 only sees rows still unlinked and matches the
    normalised venue address inside the normalised event address (same city,
    venue address >= 8 chars). Both passes reset ``embedded_at`` because the
    point payload gains the venue join (coords/rating) through it.
    """
    by_name = conn.execute(
        f"""WITH ev AS MATERIALIZED (
                SELECT e.id, e.city, {_EVENT_NORM} AS n
                FROM collected_events e
                WHERE e.venue_id IS NULL AND e.venue_name IS NOT NULL
            ), v AS MATERIALIZED (
                SELECT v.id, v.city, {_VENUE_NORM} AS n
                FROM collected_venues v
            ), best AS (
                SELECT DISTINCT ON (ev.id) ev.id AS event_id, v.id AS venue_id
                FROM ev JOIN v
                  ON v.city = ev.city
                 AND length(v.n) >= 5
                 AND (ev.n LIKE '%' || v.n || '%' OR v.n LIKE '%' || ev.n || '%')
                ORDER BY ev.id, length(v.n) DESC
            )
            UPDATE collected_events e
               SET venue_id = best.venue_id,
                   -- The payload gains lat/lon/rating through the join, so the
                   -- point must be rebuilt after a bulk link.
                   embedded_at = NULL
              FROM best
             WHERE e.id = best.event_id""").rowcount
    by_address = conn.execute(
        f"""WITH ev AS MATERIALIZED (
                SELECT e.id, e.city, {_EVENT_ADDR_NORM} AS a
                FROM collected_events e
                WHERE e.venue_id IS NULL AND e.address IS NOT NULL
            ), v AS MATERIALIZED (
                SELECT v.id, v.city, {_VENUE_ADDR_NORM} AS a
                FROM collected_venues v
                WHERE v.address IS NOT NULL
            ), best AS (
                SELECT DISTINCT ON (ev.id) ev.id AS event_id, v.id AS venue_id
                FROM ev JOIN v
                  ON v.city = ev.city
                 AND length(v.a) >= {MIN_ADDRESS_MATCH}
                 AND ev.a LIKE '%' || v.a || '%'
                ORDER BY ev.id, length(v.a) DESC
            )
            UPDATE collected_events e
               SET venue_id = best.venue_id,
                   embedded_at = NULL
              FROM best
             WHERE e.id = best.event_id""").rowcount
    conn.commit()
    return by_name + by_address


def venue_link_coverage(conn) -> dict:
    """`venue_id` coverage for /collect/health: linked / total per source."""
    rows = conn.execute(
        """SELECT source,
                  count(*) AS total,
                  count(venue_id) AS linked
           FROM collected_events
           GROUP BY source
           ORDER BY source""").fetchall()
    by_source = {row["source"]: {"linked": row["linked"], "total": row["total"]}
                 for row in rows}
    return {"linked": sum(entry["linked"] for entry in by_source.values()),
            "total": sum(entry["total"] for entry in by_source.values()),
            "by_source": by_source}
