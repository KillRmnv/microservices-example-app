"""Catalog read queries: filtering, pagination and venue matching."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.repositories import queries


def _insert_event(conn, *, slug: str, title: str, start, city="Минск",
                  category="concert", venue_name=None, price=50.0):
    row = conn.execute(
        """INSERT INTO collected_events
               (source, source_id, source_url, title, category, city,
                start_at, venue_name, price_min, currency)
           VALUES ('ticketpro', %s, %s, %s, %s, %s, %s, %s, %s, 'BYN')
           RETURNING id""",
        (slug, f"https://example.com/{slug}", title, category, city,
         start, venue_name, price)).fetchone()
    conn.commit()
    return row["id"]


def _insert_venue(conn, *, name: str, city="Минск", lat=53.9, lon=27.5):
    row = conn.execute(
        """INSERT INTO collected_venues
               (source, source_id, name, rubric, address, city, latitude, longitude)
           VALUES ('twogis', %s, %s, 'Театры', %s, %s, %s, %s)
           RETURNING id""",
        (name, name, f"{city}, ул. Театральная 1", city, lat, lon)).fetchone()
    conn.commit()
    return row["id"]


def test_list_events_filters_pages_and_counts(conn):
    now = datetime.now(timezone.utc)
    _insert_event(conn, slug="past", title="Прошлое", start=now - timedelta(days=30))
    _insert_event(conn, slug="soon", title="Скоро", start=now + timedelta(days=1))
    _insert_event(conn, slug="later", title="Потом", start=now + timedelta(days=5),
                  category="theatre")
    _insert_event(conn, slug="other-city", title="Гродно", start=now + timedelta(days=2),
                  city="Гродно")

    rows, total = queries.list_events(conn, city="Минск",
                                      date_from=now.date().isoformat(), limit=1)
    assert total == 2
    assert len(rows) == 1
    assert rows[0]["title"] == "Скоро"

    rows, total = queries.list_events(conn, city="Минск",
                                      date_from=now.date().isoformat(),
                                      offset=1, limit=1)
    assert total == 2
    assert rows[0]["title"] == "Потом"

    rows, total = queries.list_events(conn, category="theatre",
                                      date_from=now.date().isoformat())
    assert total == 1
    assert rows[0]["category"] == "theatre"


def test_get_event_links_venue_by_normalised_name(conn):
    venue_id = _insert_venue(conn, name="Драматический театр Белорусской Армии")
    event_id = _insert_event(
        conn, slug="groza", title="Гроза",
        start=datetime.now(timezone.utc) + timedelta(days=1),
        venue_name="Драматический театр Белорусской Армии  Минск")

    row = queries.get_event(conn, event_id)
    assert row is not None
    assert row["venue_ref"] == "Драматический театр Белорусской Армии"
    assert float(row["latitude"]) == 53.9
    assert float(row["longitude"]) == 27.5

    events = queries.venue_events(conn, venue_id)
    assert [item["id"] for item in events] == [event_id]


def test_list_venues_filters_and_paginates(conn):
    _insert_venue(conn, name="Минск-Арена")
    _insert_venue(conn, name="Театр киноактера")
    _insert_venue(conn, name="Гродненский драмтеатр", city="Гродно")

    rows, total = queries.list_venues(conn, city="Минск", limit=1)
    assert total == 2
    assert len(rows) == 1
    assert rows[0]["latitude"] is not None

    rows, total = queries.list_venues(conn, city="Гродно")
    assert total == 1
    assert rows[0]["name"] == "Гродненский драмтеатр"


def test_link_event_venues_backfills_summary(conn):
    venue_id = _insert_venue(conn, name="Дворец Республики")
    event_id = _insert_event(
        conn, slug="concert", title="Концерт",
        start=datetime.now(timezone.utc) + timedelta(days=2),
        venue_name="Дворец Республики  Минск")

    assert queries.link_event_venues(conn) == 1
    stored = conn.execute(
        "SELECT venue_id FROM collected_events WHERE id = %s",
        (event_id,)).fetchone()["venue_id"]
    assert stored == venue_id
