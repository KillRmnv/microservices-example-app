"""Catalog read queries: filtering, pagination and venue matching."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.repositories import queries


def _insert_event(conn, *, slug: str, title: str, start, end=None, city="Минск",
                  category="concert", venue_name=None, price=50.0):
    row = conn.execute(
        """INSERT INTO collected_events
               (source, source_id, source_url, title, category, city,
                start_at, end_at, venue_name, price_min, currency)
           VALUES ('ticketpro', %s, %s, %s, %s, %s, %s, %s, %s, %s, 'BYN')
           RETURNING id""",
        (slug, f"https://example.com/{slug}", title, category, city,
         start, end, venue_name, price)).fetchone()
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


def test_search_events_respects_date_window(conn):
    inside = datetime(2026, 10, 31, 18, tzinfo=timezone.utc)
    outside = datetime(2027, 1, 24, 18, tzinfo=timezone.utc)
    _insert_event(conn, slug="inside", title="Концерт сегодня", start=inside)
    _insert_event(conn, slug="outside", title="Концерт в январе", start=outside)
    _insert_event(conn, slug="undated", title="Концерт без даты", start=None)

    rows = queries.search_events(
        conn, "концерт", "Минск", None, 10,
        date_from="2026-10-31T00:00:00+00:00",
        date_to="2026-11-01T00:00:00+00:00")

    assert [row["title"] for row in rows] == ["Концерт сегодня"]


def test_list_events_hides_cancelled_by_default(conn):
    now = datetime.now(timezone.utc)
    _insert_event(conn, slug="cancelled", title="Отменённый",
                  start=now + timedelta(days=1))
    conn.execute("UPDATE collected_events SET status = 'cancelled'"
                 " WHERE source_id = 'cancelled'")
    _insert_event(conn, slug="live", title="Живой",
                  start=now + timedelta(days=1))
    conn.commit()
    date_from = now.date().isoformat()

    rows, total = queries.list_events(conn, date_from=date_from)
    assert total == 1
    assert rows[0]["title"] == "Живой"
    assert rows[0]["status"] == "scheduled"

    rows, total = queries.list_events(conn, date_from=date_from,
                                      include_cancelled=True)
    assert total == 2


def test_search_events_hides_cancelled_by_default(conn):
    start = datetime(2026, 10, 31, 18, tzinfo=timezone.utc)
    _insert_event(conn, slug="live", title="Концерт живой", start=start)
    _insert_event(conn, slug="cancelled", title="Концерт отменённый",
                  start=start)
    conn.execute("UPDATE collected_events SET status = 'cancelled'"
                 " WHERE source_id = 'cancelled'")
    conn.commit()

    rows = queries.search_events(conn, "концерт", "Минск", None, 10)
    assert [row["title"] for row in rows] == ["Концерт живой"]

    rows = queries.search_events(conn, "концерт", "Минск", None, 10,
                                 include_cancelled=True)
    assert len(rows) == 2


def test_card_columns_expose_availability_and_venue(conn):
    venue_id = conn.execute(
        """INSERT INTO collected_venues
               (source, source_id, name, rubric, address, city, latitude,
                longitude, rating, review_count, schedule)
           VALUES ('twogis', 'v-rating', 'Филармония', 'Театры', 'Минск, ул. 1',
                   'Минск', 53.9, 27.5, 4.9, 321,
                   '{"Tue": {"working_hours": [{"from": "10:00", "to": "20:00"}]}}'::jsonb)
           RETURNING id""").fetchone()["id"]
    event_id = _insert_event(
        conn, slug="sold", title="Аншлаг",
        start=datetime.now(timezone.utc) + timedelta(days=1))
    conn.execute(
        """UPDATE collected_events SET venue_id = %s, status = 'sold_out',
               availability = 'sold_out', capacity = 300, seats_left = 0,
               age_limit = 16
           WHERE id = %s""", (venue_id, event_id))
    conn.commit()

    rows, _ = queries.list_events(
        conn, date_from=datetime.now(timezone.utc).date().isoformat())
    card = rows[0]
    assert card["venue_id"] == venue_id
    assert card["status"] == "sold_out"
    assert card["availability"] == "sold_out"
    assert (card["capacity"], card["seats_left"], card["age_limit"]) == (300, 0, 16)
    assert card["venue_ref"] == "Филармония"
    assert float(card["venue_rating"]) == 4.9
    assert card["venue_review_count"] == 321
    assert card["venue_schedule"]["Tue"]["working_hours"][0]["from"] == "10:00"


def test_venue_columns_include_enrichment(conn):
    _insert_venue(conn, name="Минск-Арена")
    conn.execute(
        """UPDATE collected_venues SET amenities = '["wifi", "parking"]'::jsonb,
               avg_check = 40, price_level = 'medium', district = 'Центральный'""")
    conn.commit()

    rows, _ = queries.list_venues(conn, city="Минск")
    venue = rows[0]
    assert venue["amenities"] == ["wifi", "parking"]
    assert float(venue["avg_check"]) == 40.0
    assert venue["price_level"] == "medium"
    assert venue["district"] == "Центральный"


def test_multiday_event_matches_a_day_inside_its_period(conn):
    _insert_event(
        conn, slug="dolphinarium", title="Дельфинарий",
        start=datetime(2026, 10, 29, 9, tzinfo=timezone.utc),
        end=datetime(2026, 11, 28, 21, tzinfo=timezone.utc))
    _insert_event(
        conn, slug="past", title="Прошлое",
        start=datetime(2026, 10, 1, 9, tzinfo=timezone.utc),
        end=datetime(2026, 10, 2, 21, tzinfo=timezone.utc))

    rows, total = queries.list_events(
        conn, date_from="2026-11-04", date_to="2026-11-04")
    assert total == 1
    assert rows[0]["title"] == "Дельфинарий"

    found = queries.search_events(
        conn, "дельфинарий", "Минск", None, 10,
        date_from="2026-11-04T00:00:00+00:00",
        date_to="2026-11-05T00:00:00+00:00")
    assert [row["title"] for row in found] == ["Дельфинарий"]


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
    conn.execute("UPDATE collected_events SET embedded_at = now()")
    conn.commit()

    assert queries.link_event_venues(conn) == 1
    stored = conn.execute(
        "SELECT venue_id, embedded_at FROM collected_events WHERE id = %s",
        (event_id,)).fetchone()
    assert stored["venue_id"] == venue_id
    # The payload gains lat/lon/rating through the venue join.
    assert stored["embedded_at"] is None


def test_link_event_venues_falls_back_to_address(conn):
    venue_id = conn.execute(
        """INSERT INTO collected_venues
               (source, source_id, name, rubric, address, city)
           VALUES ('twogis', 'v-addr', 'Галерея Арт', 'Галереи',
                   'Минск, улица Октябрьская, 16', 'Минск')
           RETURNING id""").fetchone()["id"]
    # The venue name does not match, only the address does (event omits city).
    event_id = conn.execute(
        """INSERT INTO collected_events
               (source, source_id, source_url, title, venue_name, address, city)
           VALUES ('ticketpro', 'addr-1', 'http://x/a1', 'Выставка',
                   'Площадка без названия', 'улица Октябрьская 16, Минск', 'Минск')
           RETURNING id""").fetchone()["id"]
    conn.execute("UPDATE collected_events SET embedded_at = now()")
    conn.commit()

    assert queries.link_event_venues(conn) == 1
    stored = conn.execute(
        "SELECT venue_id, embedded_at FROM collected_events WHERE id = %s",
        (event_id,)).fetchone()
    assert stored["venue_id"] == venue_id
    assert stored["embedded_at"] is None


def test_link_event_venues_name_pass_wins_and_skips_linked_rows(conn):
    by_name = _insert_venue(conn, name="Дворец Республики")
    by_address = conn.execute(
        """INSERT INTO collected_venues
               (source, source_id, name, rubric, address, city)
           VALUES ('twogis', 'v-addr-2', 'Другое имя', 'Залы',
                   'Минск, проспект Победителей, 1', 'Минск')
           RETURNING id""").fetchone()["id"]
    event_id = conn.execute(
        """INSERT INTO collected_events
               (source, source_id, source_url, title, venue_name, address, city)
           VALUES ('ticketpro', 'both', 'http://x/b', 'Концерт',
                   'Дворец Республики Минск', 'проспект Победителей 1', 'Минск')
           RETURNING id""").fetchone()["id"]
    conn.commit()

    assert queries.link_event_venues(conn) == 1
    stored = conn.execute(
        "SELECT venue_id FROM collected_events WHERE id = %s",
        (event_id,)).fetchone()
    assert stored["venue_id"] == by_name
    assert by_name != by_address

    # An already-linked row is never re-matched, even after a new venue with a
    # matching address appears; its payload marker stays intact.
    conn.execute("UPDATE collected_events SET embedded_at = now() WHERE id = %s",
                 (event_id,))
    conn.commit()
    assert queries.link_event_venues(conn) == 0
    stored = conn.execute(
        "SELECT venue_id, embedded_at FROM collected_events WHERE id = %s",
        (event_id,)).fetchone()
    assert stored["venue_id"] == by_name
    assert stored["embedded_at"] is not None


def test_venue_link_coverage_counts_per_source(conn):
    venue_id = _insert_venue(conn, name="Минск-Арена")
    now = datetime.now(timezone.utc)
    _insert_event(conn, slug="linked", title="Матч", start=now + timedelta(days=1))
    conn.execute("UPDATE collected_events SET venue_id = %s"
                 " WHERE source_id = 'linked'", (venue_id,))
    _insert_event(conn, slug="unlinked", title="Концерт",
                  start=now + timedelta(days=2))
    conn.commit()

    coverage = queries.venue_link_coverage(conn)
    assert coverage["total"] == 2
    assert coverage["linked"] == 1
    assert coverage["by_source"]["ticketpro"] == {"linked": 1, "total": 2}
