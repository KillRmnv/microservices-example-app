"""Booking catalog stream: mirroring booking-service events into the index."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.clients.kafka import BookingCatalogConsumer
from app.core.config import Settings
from app.models.catalog import CatalogEvent, RawEvent, dedup_key_for
from app.repositories import store
from app.clients.vector import MemoryStore, VectorPoint

from conftest import pg_url


def _event(**overrides) -> CatalogEvent:
    base = dict(
        id=42,
        title="Симфонический вечер",
        starts_at=datetime(2026, 11, 5, 19, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 11, 5, 21, 0, tzinfo=timezone.utc),
        venue_name="Minsk Arena",
        city="Минск",
        category="concert",
        raw={"id": 42, "title": "Симфонический вечер"},
    )
    base.update(overrides)
    return CatalogEvent(**base)


def _scraped(source_id="tp-77", **overrides) -> RawEvent:
    base = dict(
        source="ticketpro",
        source_id=source_id,
        source_url=f"https://ticketpro.by/event/{source_id}",
        title="Симфонический вечер",
        start_at=datetime(2026, 11, 5, 19, 0, tzinfo=timezone.utc),
        venue_name="Minsk Arena",
        category="concert",
        city="Минск",
    )
    base.update(overrides)
    return RawEvent(**base)


def test_catalog_event_upsert_is_idempotent(conn):
    row_id = store.upsert_catalog_event(conn, _event())
    conn.commit()
    assert row_id is not None

    row = conn.execute(
        "SELECT source, source_id, booking_event_id, title, category, city,"
        " city_id, currency_code, dedup_key FROM collected_events"
        " WHERE source = 'booking'").fetchone()
    assert row["source_id"] == "42"
    assert row["booking_event_id"] == 42
    assert row["title"] == "Симфонический вечер"
    assert row["category"] == "concert"
    assert row["city_id"] is not None
    assert row["currency_code"] == "BYN"
    assert row["dedup_key"] == dedup_key_for(
        "Симфонический вечер", _event().starts_at, "Minsk Arena")

    # Republishing the same payload must not rewrite the row.
    assert store.upsert_catalog_event(conn, _event()) is None

    # A real change updates and resets the embedding marker.
    conn.execute("UPDATE collected_events SET embedded_at = now()")
    changed = store.upsert_catalog_event(conn, _event(title="Новое название"))
    conn.commit()
    assert changed == row_id
    refreshed = conn.execute(
        "SELECT title, embedded_at FROM collected_events WHERE id = %s",
        (row_id,)).fetchone()
    assert refreshed["title"] == "Новое название"
    assert refreshed["embedded_at"] is None


def test_scraped_event_merges_into_existing_booking_mirror(conn):
    """Booking first: the scrape collapses into the bookable row."""
    row_id = store.upsert_catalog_event(conn, _event())
    conn.commit()

    stats = store.upsert_events(conn, [_scraped()])
    conn.commit()

    assert stats.duplicates == 1
    rows = conn.execute(
        "SELECT id, source, source_id, booking_event_id"
        " FROM collected_events").fetchall()
    assert len(rows) == 1
    assert rows[0]["id"] == row_id
    assert rows[0]["source"] == "booking"      # identity is untouched
    assert rows[0]["source_id"] == "42"
    assert rows[0]["booking_event_id"] == 42   # bookable id survives
    sources = conn.execute(
        "SELECT source, is_primary FROM event_sources ORDER BY source").fetchall()
    assert [row["source"] for row in sources] == ["ticketpro"]


def test_booking_mirror_adopts_existing_scraped_row(conn):
    """Scraper first: the mirror adopts the row instead of duplicating it."""
    store.upsert_events(conn, [_scraped()])
    conn.commit()
    original = conn.execute(
        "SELECT id, source, source_id, dedup_key FROM collected_events").fetchone()
    conn.execute("UPDATE collected_events SET embedded_at = now()")
    conn.commit()

    adopted = store.upsert_catalog_event(conn, _event(id=77))
    conn.commit()

    assert adopted == original["id"]
    rows = conn.execute(
        "SELECT id, source, source_id, booking_event_id, dedup_key, embedded_at"
        " FROM collected_events").fetchall()
    assert len(rows) == 1
    assert rows[0]["source"] == "ticketpro"    # identity is untouched
    assert rows[0]["source_id"] == "tp-77"
    assert rows[0]["booking_event_id"] == 77   # bookable id lands on survivor
    assert rows[0]["dedup_key"] == original["dedup_key"]
    assert rows[0]["embedded_at"] is None      # payload gains the bookable id
    # Republishing the same booking event is a no-op.
    assert store.upsert_catalog_event(conn, _event(id=77)) is None


def test_booking_tombstone_clears_adopted_id_but_keeps_row(conn):
    store.upsert_events(conn, [_scraped()])
    store.upsert_catalog_event(conn, _event(id=77))
    conn.commit()

    assert store.delete_catalog_event(conn, 77) is None  # no point to delete
    conn.commit()
    row = conn.execute(
        "SELECT source, booking_event_id, embedded_at"
        " FROM collected_events").fetchone()
    assert row["source"] == "ticketpro"
    assert row["booking_event_id"] is None
    assert row["embedded_at"] is None


def test_catalog_event_delete_returns_point_id(conn):
    row_id = store.upsert_catalog_event(conn, _event())
    conn.commit()

    assert store.delete_catalog_event(conn, 42) == row_id
    conn.commit()
    assert conn.execute(
        "SELECT count(*) AS n FROM collected_events").fetchone()["n"] == 0
    assert store.delete_catalog_event(conn, 42) is None


def test_consumer_applies_upsert_and_tombstone(conn):
    vector = MemoryStore()
    consumer = BookingCatalogConsumer(pg_url(), vector, Settings())

    payload = {
        "id": 42,
        "title": "Симфонический вечер",
        "startsAt": "2026-11-05T19:00:00Z",
        "endsAt": "2026-11-05T21:00:00Z",
        "venuePlace": "Minsk Arena",
        "townName": "Minsk",
        "category": "concert",
        "admissionMode": "SEATABLE",
        "deleted": False,
    }
    asyncio.run(consumer.handle(payload))

    row = conn.execute(
        "SELECT id, city, start_at FROM collected_events"
        " WHERE booking_event_id = 42").fetchone()
    assert row is not None
    assert row["city"] == "Минск"  # configurable town alias
    assert row["start_at"] == datetime(2026, 11, 5, 19, 0, tzinfo=timezone.utc)

    asyncio.run(vector.upsert([VectorPoint(id=row["id"], vector=[1.0])]))
    asyncio.run(consumer.handle({"id": 42, "deleted": True}))
    assert asyncio.run(vector.count()) == 0
    assert conn.execute(
        "SELECT count(*) AS n FROM collected_events"
        " WHERE booking_event_id = 42").fetchone()["n"] == 0
