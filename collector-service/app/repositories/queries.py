"""Read queries for the collected catalog."""
from __future__ import annotations

EVENT_COLUMNS = (
    "id, source, source_url, title, category, start_at, end_at,"
    " venue_name, address, city, price_min, price_max, currency"
)
VENUE_COLUMNS = (
    "id, source, name, rubric, address, city, lat, lon,"
    " rating, review_count"
)


def list_events(conn, source: str | None, city: str | None,
                limit: int) -> list[dict]:
    query = (f"SELECT {EVENT_COLUMNS} FROM collected_events"
             " WHERE (%s::TEXT IS NULL OR source = %s)"
             " AND (%s::TEXT IS NULL OR city = %s)"
             " ORDER BY start_at NULLS LAST LIMIT %s")
    return [dict(row) for row in conn.execute(
        query, (source, source, city, city, limit)).fetchall()]


def search_events(conn, q: str, city: str | None, category: str | None,
                  limit: int) -> list[dict]:
    """Lexical half of hybrid search: tsvector rank + filters."""
    query = (f"""SELECT {EVENT_COLUMNS},
                        ts_rank_cd(search_vector, plainto_tsquery('russian', %s)) AS rank
                 FROM collected_events
                 WHERE search_vector @@ plainto_tsquery('russian', %s)
                 AND (%s::TEXT IS NULL OR city = %s)
                 AND (%s::TEXT IS NULL OR category = %s)
                 ORDER BY rank DESC LIMIT %s""")
    return [dict(row) for row in conn.execute(
        query, (q, q, city, city, category, category, limit)).fetchall()]


def search_venues(conn, q: str, city: str | None, rubric: str | None,
                  limit: int) -> list[dict]:
    query = (f"""SELECT {VENUE_COLUMNS},
                        ts_rank_cd(search_vector, plainto_tsquery('russian', %s)) AS rank
                 FROM collected_venues
                 WHERE search_vector @@ plainto_tsquery('russian', %s)
                 AND (%s::TEXT IS NULL OR city = %s)
                 AND (%s::TEXT IS NULL OR rubric = %s)
                 ORDER BY rank DESC LIMIT %s""")
    return [dict(row) for row in conn.execute(
        query, (q, q, city, city, rubric, rubric, limit)).fetchall()]


def unembedded_events(conn, source: str, limit: int | None) -> list:
    params: list = []
    query = ("SELECT id, title, venue_name, description, city, category,"
             " start_at FROM collected_events WHERE embedded_at IS NULL")
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
