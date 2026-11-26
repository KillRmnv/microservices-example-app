"""Retention: drop old scraped events and their vector points.

Booking rows are mirrored from Kafka and are deleted by tombstones, never by
this service. The job is idempotent: a missing row simply returns no id.
"""
from __future__ import annotations

import logging

from ..core import db
from ..core.config import Settings

log = logging.getLogger(__name__)


class RetentionService:
    def __init__(self, db_url: str, settings: Settings) -> None:
        self._db_url = db_url
        self._settings = settings

    def purge(self) -> list[str]:
        """Delete one batch of expired rows; returns Qdrant point ids."""
        retention = self._settings.event_retention_days
        stale = self._settings.stale_event_days
        limit = self._settings.cleanup_batch
        with db.get_conn(self._db_url) as conn:
            rows = conn.execute(
                """DELETE FROM collected_events
                   WHERE id IN (
                       SELECT id FROM collected_events
                       WHERE source <> 'booking'
                         AND (
                             (COALESCE(end_at, start_at) IS NOT NULL
                              AND COALESCE(end_at, start_at)
                                  < now() - make_interval(days => %s))
                             OR (start_at IS NULL
                                 AND last_seen_at
                                     < now() - make_interval(days => %s))
                         )
                       ORDER BY COALESCE(end_at, start_at) NULLS LAST
                       LIMIT %s
                   )
                   RETURNING id""",
                (retention, stale, limit),
            ).fetchall()
            conn.commit()
        ids = [str(row["id"]) for row in rows]
        if ids:
            log.info("retention: removed %d events older than %dd/%dd",
                     len(ids), retention, stale)
        return ids
