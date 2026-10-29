"""Read queries for the collected catalog."""
from __future__ import annotations

EVENT_COLUMNS = (
    "id, source, source_url, booking_event_id, title, category, start_at,"
    " end_at, venue_name, address, city, price_min, price_max, currency"
)

# Everything the catalog UI needs for a card/detail view.
CARD_COLUMNS = (
    "e.id, e.source, e.source_url, e.booking_event_id, e.title,"
    " e.description, e.category, e.start_at, e.end_at, e.venue_name,"
    " e.address, e.city, e.price_min, e.price_max, e.currency,"
    " e.image_url, e.venue_id, v.latitude, v.longitude, v.name AS venue_ref"
)

VENUE_COLUMNS = (
    "id, source, source_url, name, rubric, address, city, latitude,"
    " longitude, rating, review_count, schedule"
)

# Normalised name matching: "Дворец Республики  Минск" -> "дворецреспубликиминск",
# which contains the 2GIS name "дворецреспублики".
_NORM = "regexp_replace(lower({}), '[^a-zа-я0-9]+', '', 'g')"
_EVENT_NORM = _NORM.format("coalesce(e.venue_name, '')")
_VENUE_NORM = _NORM.format("coalesce(v.name, '')")

_VENUE_LATERAL = f"""
    LEFT JOIN LATERAL (
        SELECT v.id, v.latitude, v.longitude, v.name
        FROM collected_venues v
        WHERE v.city = e.city
          AND length({_VENUE_NORM}) >= 5
          AND ({_EVENT_NORM} LIKE '%%' || {_VENUE_NORM} || '%%'
               OR {_VENUE_NORM} LIKE '%%' || {_EVENT_NORM} || '%%')
        ORDER BY length(v.name) DESC
        LIMIT 1
    ) v ON true
"""


def _filters(city, category, source, date_from, date_to, q, ids):
    clauses, params = [], []
    if city:
        clauses.append("e.city = %s")
        params.append(city)
    if category:
        clauses.append("e.category = %s")
        params.append(category)
    if source:
        clauses.append("e.source = %s")
        params.append(source)
    if date_from:
        clauses.append("e.start_at >= %s::date")
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
                limit=40, offset=0) -> tuple[list[dict], int]:
    clauses, params = _filters(city, category, source, date_from, date_to,
                               q, ids)
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
            {_VENUE_LATERAL}
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
                  date_to: str | None = None) -> list[dict]:
    """Lexical half of hybrid search: tsvector rank + filters."""
    rows = conn.execute(
        f"""SELECT {CARD_COLUMNS},
                   ts_rank_cd(e.search_vector,
                              plainto_tsquery('russian', %s)) AS rank
            FROM collected_events e
            {_VENUE_LATERAL}
            WHERE e.search_vector @@ plainto_tsquery('russian', %s)
            AND (%s::TEXT IS NULL OR e.city = %s)
            AND (%s::TEXT IS NULL OR e.category = %s)
            AND (%s::TIMESTAMPTZ IS NULL OR e.start_at >= %s::TIMESTAMPTZ)
            AND (%s::TIMESTAMPTZ IS NULL OR e.start_at < %s::TIMESTAMPTZ)
            ORDER BY rank DESC LIMIT %s""",
        (q, q, city, city, category, category,
         date_from, date_from, date_to, date_to, limit)).fetchall()
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
            {_VENUE_LATERAL}
            WHERE v.id = %s
            ORDER BY e.start_at NULLS LAST, e.title
            LIMIT %s""", (venue_id, limit)).fetchall()
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
    query = ("SELECT id, source, booking_event_id, title, venue_name, description,"
             " city, category, price_min, price_max, start_at"
             " FROM collected_events WHERE embedded_at IS NULL")
    if source != "all":
        query += " AND source = %s"
        params.append(source)
    query += " ORDER BY fetched_at"
    if limit:
        query += " LIMIT %s"
        params.append(max(1, limit))
    return conn.execute(query, params).fetchall()


def unembedded_venues(conn, limit: int | None) -> list:
    query = ("SELECT id, name, rubric, address, city FROM collected_venues"
             " WHERE embedded_at IS NULL ORDER BY fetched_at")
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
        "SELECT id, source, booking_event_id, title, venue_name, description,"
        " city, category, price_min, price_max, start_at FROM collected_events"
        " ORDER BY fetched_at").fetchall()


def all_venues_for_reindex(conn) -> list:
    return conn.execute(
        "SELECT id, name, rubric, address, city FROM collected_venues"
        " ORDER BY fetched_at").fetchall()


def link_event_venues(conn) -> int:
    """Backfill summary.venue_id for events whose venue name contains a 2GIS name."""
    cur = conn.execute(
        f"""WITH ev AS (
                SELECT e.id, e.city, {_EVENT_NORM} AS n
                FROM collected_events e
                WHERE e.venue_id IS NULL AND e.venue_name IS NOT NULL
            ), v AS (
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
               SET venue_id = best.venue_id
              FROM best
             WHERE e.id = best.event_id""")
    conn.commit()
    return cur.rowcount
