"""Kafka consumer for the booking-service catalog stream.

booking-service publishes a compacted `booking.catalog` topic (key = event id,
value = full event state, deletes are tombstones). Replaying it from offset
zero is the bootstrap path, so no snapshot endpoint is needed.
"""
from __future__ import annotations

import json
import logging

from ..core import db
from ..core.config import Settings
from ..models.catalog import CatalogEvent
from ..normalize import parse_datetime
from ..repositories import store
from ..vector import VectorStore

log = logging.getLogger(__name__)


class BookingCatalogConsumer:
    def __init__(self, db_url: str, vector: VectorStore,
                 settings: Settings) -> None:
        self._db_url = db_url
        self._vector = vector
        self._settings = settings
        self._consumer = None
        self._task = None

    async def start(self) -> None:
        if not self._settings.booking_catalog_enabled:
            log.info("booking catalog consumer disabled")
            return
        from aiokafka import AIOKafkaConsumer
        import asyncio

        self._consumer = AIOKafkaConsumer(
            self._settings.booking_catalog_topic,
            bootstrap_servers=self._settings.kafka_bootstrap_servers,
            group_id=self._settings.booking_catalog_group,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )
        await self._consumer.start()
        self._task = asyncio.create_task(self._run())
        log.info("booking catalog consumer started: topic=%s group=%s",
                 self._settings.booking_catalog_topic,
                 self._settings.booking_catalog_group)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None

    async def _run(self) -> None:
        assert self._consumer is not None
        try:
            async for message in self._consumer:
                try:
                    payload = json.loads(message.value)
                except (TypeError, ValueError) as exc:
                    log.warning("booking catalog: bad payload at offset %s: %s",
                                message.offset, exc)
                    continue
                try:
                    await self.handle(payload)
                except Exception as exc:  # noqa: BLE001 — one event must not stop the stream
                    log.warning("booking catalog: event %s failed: %s",
                                payload.get("id"), exc)
        except Exception:  # noqa: BLE001 — surface a crashed loop, keep the app up
            log.exception("booking catalog consumer loop stopped")

    async def handle(self, payload: dict) -> None:
        """Apply one message: tombstone -> delete, otherwise upsert."""
        booking_id = int(payload["id"])
        if payload.get("deleted"):
            point_id = self._delete(booking_id)
            if point_id is not None:
                await self._vector.delete([point_id])
            return
        event = self._to_catalog_event(payload)
        changed = self._upsert(event)
        if changed is None:
            log.debug("booking catalog: event %s unchanged", booking_id)
        else:
            # Embedding is a separate periodic catch-up: the consumer must
            # never block on a missing/slow model server.
            log.info("booking catalog: event %s indexed", booking_id)

    def _upsert(self, event: CatalogEvent) -> str | None:
        with db.get_conn(self._db_url) as conn:
            row_id = store.upsert_catalog_event(conn, event)
            conn.commit()
        return row_id

    def _delete(self, booking_id: int) -> str | None:
        with db.get_conn(self._db_url) as conn:
            point_id = store.delete_catalog_event(conn, booking_id)
            conn.commit()
        return point_id

    def _to_catalog_event(self, payload: dict) -> CatalogEvent:
        town = payload.get("townName") or ""
        return CatalogEvent(
            id=int(payload["id"]),
            title=payload.get("title") or "",
            starts_at=parse_datetime(payload.get("startsAt")),
            ends_at=parse_datetime(payload.get("endsAt")),
            venue_name=payload.get("venuePlace") or "",
            city=self._settings.city_alias(town),
            category=payload.get("category") or "other",
            raw=payload,
        )
