"""Embedding backfill use case (events + venues collections).

Each point carries dense + sparse vectors and a filterable payload, so the
assistant can run hybrid search fully inside Qdrant.
"""
from __future__ import annotations

import logging

from ..core import db
from ..core.config import Settings
from ..embeddings import EmbeddingProvider, embeddable_text
from ..repositories import queries
from ..sparse import encode_sparse
from ..vector import VectorPoint, VectorStore

log = logging.getLogger(__name__)


def _batches(rows: list, size: int):
    for offset in range(0, len(rows), size):
        yield rows[offset:offset + size]


def _event_text(row) -> str:
    return embeddable_text(row["title"], row["venue_name"], row["description"])


def _venue_text(row) -> str:
    return "\n".join(part for part in
                     [row["name"], row["rubric"], row["address"]] if part)


def _event_payload(row) -> dict:
    return {
        "title": row["title"],
        "source": row["source"],
        "city": row["city"],
        "category": row["category"],
        "venue": row["venue_name"] or "",
        "start_at": row["start_at"].isoformat() if row["start_at"] else "",
        "price_min": float(row["price_min"]) if row["price_min"] is not None else None,
        "price_max": float(row["price_max"]) if row["price_max"] is not None else None,
        "booking_event_id": (int(row["booking_event_id"])
                             if row["booking_event_id"] is not None else None),
    }


def _venue_payload(row) -> dict:
    return {
        "name": row["name"],
        "source": row["source"],
        "city": row["city"],
        "rubric": row["rubric"] or "",
        "address": row["address"] or "",
    }


def _to_points(rows, vectors: list[list[float]], texts: list[str],
               payload_of) -> list[VectorPoint]:
    return [
        VectorPoint(id=str(row["id"]), vector=vector,
                    payload=payload_of(row), sparse=encode_sparse(text))
        for row, vector, text in zip(rows, vectors, texts)
    ]


class EmbedService:
    def __init__(self, db_url: str, embedder: EmbeddingProvider,
                 vector: VectorStore, vector_venues: VectorStore,
                 settings: Settings) -> None:
        self._db_url = db_url
        self._embedder = embedder
        self._vector = vector
        self._vector_venues = vector_venues
        self._batch_size = max(1, settings.embed_batch_size)

    async def _embed_batch(self, rows, store: VectorStore, texts: list[str],
                           payload_of, marker) -> int:
        """Embed one batch, upsert, mark; returns embedded count (0 on error)."""
        vectors = await self._embedder.embed(texts)
        try:
            await store.upsert(_to_points(rows, vectors, texts, payload_of))
        except Exception as exc:  # noqa: BLE001 — keep stored batches
            log.warning("embed batch failed: %s", exc)
            return 0
        with db.get_conn(self._db_url) as conn:
            marker(conn, [row["id"] for row in rows])
        return len(rows)

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
        for batch in _batches(rows, self._batch_size):
            texts = [_event_text(row) for row in batch]
            try:
                done = await self._embed_batch(
                    batch, self._vector, texts, _event_payload,
                    queries.mark_events_embedded)
            except Exception as exc:  # noqa: BLE001 — embedder down, stop
                log.warning("event embed batch failed: %s", exc)
                break
            if not done:
                break
            embedded += done
        return embedded, len(rows) - embedded

    async def embed_venues(self, limit: int | None = None) -> tuple[int, int]:
        with db.get_conn(self._db_url) as conn:
            rows = queries.unembedded_venues(conn, limit)
        embedded = 0
        for batch in _batches(rows, self._batch_size):
            texts = [_venue_text(row) for row in batch]
            try:
                done = await self._embed_batch(
                    batch, self._vector_venues, texts, _venue_payload,
                    queries.mark_venues_embedded)
            except Exception as exc:  # noqa: BLE001 — embedder down, stop
                log.warning("venue embed batch failed: %s", exc)
                break
            if not done:
                break
            embedded += done
        return embedded, len(rows) - embedded

    async def reindex_hybrid(self) -> dict:
        """Backfill sparse vectors + payload into existing Qdrant points.

        Dense vectors are preserved (no LLM re-embed): sparse/payload are
        merged from Postgres rows. Qdrant-only orphans keep dense-only.
        """
        events = await self._reindex_collection(
            self._vector, "events", queries.all_events_for_reindex,
            _event_text, _event_payload)
        venues = await self._reindex_collection(
            self._vector_venues, "venues", queries.all_venues_for_reindex,
            _venue_text, _venue_payload)
        return {"events": events, "venues": venues}

    async def _reindex_collection(self, store: VectorStore, name: str,
                                  fetch_rows, text_of, payload_of) -> dict:
        with db.get_conn(self._db_url) as conn:
            rows = fetch_rows(conn)
        stored = {point.id: point for point in await store.scroll_all()}
        patched = 0
        patches = []
        for row in rows:
            row_id = str(row["id"])
            if row_id not in stored:
                continue  # gap rows are healed by the next /embed run
            patches.append(VectorPoint(id=row_id, sparse=encode_sparse(text_of(row)),
                                       payload=payload_of(row)))
            if len(patches) >= self._batch_size:
                await store.patch_points(patches)
                patched += len(patches)
                patches = []
        if patches:
            await store.patch_points(patches)
            patched += len(patches)
        log.info("hybrid reindex %s: %d patched, %d stored, %d rows",
                 name, patched, len(stored), len(rows))
        return {"patched": patched, "stored": len(stored), "rows": len(rows)}
