"""Booking catalog stream: mirroring booking-service events into the index."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.clients.kafka import BookingCatalogConsumer
from app.core.config import Settings
from app.models.catalog import CatalogEvent
from app.repositories import store
from app.vector import MemoryStore, VectorPoint

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
    assert row["dedup_key"] is None  # mirrored rows never join cross-source dedup

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
