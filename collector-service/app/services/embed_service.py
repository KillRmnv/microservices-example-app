"""Embedding backfill use case (events + venues collections)."""
from __future__ import annotations

import logging

from ..core import db
from ..core.config import Settings
from ..embeddings import EmbeddingProvider, embeddable_text
from ..repositories import queries
from ..vector import VectorPoint, VectorStore

log = logging.getLogger(__name__)


class EmbedService:
    def __init__(self, db_url: str, embedder: EmbeddingProvider,
                 vector: VectorStore, vector_venues: VectorStore,
                 settings: Settings) -> None:
        self._db_url = db_url
        self._embedder = embedder
        self._vector = vector
        self._vector_venues = vector_venues
        self._batch_size = max(1, settings.embed_batch_size)

    async def embed_events(self, source: str = "all",
                           limit: int | None = None,
                           cap: int | None = None) -> tuple[int, int]:
        """Embed unembedded event rows; returns (embedded, pending)."""
        fetch_limit = limit
        if cap is not None:
            fetch_limit = min(limit or cap, cap)
        with db.get_conn(self._db_url) as conn:
            rows = queries.unembedded_events(conn, source, fetch_limit)
        embedded = 0
        for offset in range(0, len(rows), self._batch_size):
            batch = rows[offset:offset + self._batch_size]
            texts = [embeddable_text(row["title"], row["venue_name"],
                                     row["description"]) for row in batch]
            points = [
                VectorPoint(
                    id=str(row["id"]),
                    vector=vector,
                    payload={
                        "title": row["title"],
                        "city": row["city"],
                        "category": row["category"],
                        "venue": row["venue_name"] or "",
                        "start_at": row["start_at"].isoformat()
                        if row["start_at"] else "",
                    },
                )
                for row, vector in zip(batch, await self._embedder.embed(texts))
            ]
            try:
                await self._vector.upsert(points)
            except Exception as exc:  # noqa: BLE001 — keep stored batches
                log.warning("event embed batch failed: %s", exc)
                break
            with db.get_conn(self._db_url) as conn:
                queries.mark_events_embedded(conn, [row["id"] for row in batch])
            embedded += len(batch)
        return embedded, len(rows) - embedded

    async def embed_venues(self, limit: int | None = None) -> tuple[int, int]:
        with db.get_conn(self._db_url) as conn:
            rows = queries.unembedded_venues(conn, limit)
        embedded = 0
        for offset in range(0, len(rows), self._batch_size):
            batch = rows[offset:offset + self._batch_size]
            texts = ["\n".join(part for part in
                               [row["name"], row["rubric"], row["address"]]
                               if part) for row in batch]
            vectors = await self._embedder.embed(texts)
            points = [
                VectorPoint(
                    id=str(row["id"]),
                    vector=vector,
                    payload={
                        "name": row["name"],
                        "city": row["city"],
                        "rubric": row["rubric"] or "",
                        "address": row["address"] or "",
                    },
                )
                for row, vector in zip(batch, vectors)
            ]
            try:
                await self._vector_venues.upsert(points)
            except Exception as exc:  # noqa: BLE001 — keep stored batches
                log.warning("venue embed batch failed: %s", exc)
                break
            with db.get_conn(self._db_url) as conn:
                queries.mark_venues_embedded(conn, [row["id"] for row in batch])
            embedded += len(batch)
        return embedded, len(rows) - embedded
