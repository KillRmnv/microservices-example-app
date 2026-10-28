"""Qdrant access: dense + sparse (`text-sparse`) vectors, cosine, payload.

New collections are created hybrid-ready. Existing dense-only collections
cannot gain a sparse config in place (Qdrant limitation), so `ensure`
recreates them only when empty; non-empty legacy collections keep serving
dense-only until an explicit `/embed/reindex-hybrid` run.
"""
from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .sparse import SPARSE_VECTOR_NAME, SparseVector

log = logging.getLogger(__name__)

PAYLOAD_INDEXES = {
    "city": "keyword",
    "category": "keyword",
    "rubric": "keyword",
    "price_min": "float",
}


@dataclass
class VectorPoint:
    id: str  # collected_events.id as text
    vector: list[float] | None = None
    payload: dict | None = None
    sparse: SparseVector | None = None


@dataclass
class ScoredHit:
    id: str
    score: float
    payload: dict = field(default_factory=dict)


class VectorStore(ABC):
    @abstractmethod
    async def ensure(self, dim: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def upsert(self, points: list[VectorPoint]) -> None:
        """Full replace of vectors+payload (points must carry dense)."""
        raise NotImplementedError

    @abstractmethod
    async def patch_points(self, points: list[VectorPoint]) -> None:
        """Merge sparse vectors and payload into existing points."""
        raise NotImplementedError

    @abstractmethod
    async def scroll_all(self) -> list[VectorPoint]:
        """All points with dense vectors and payloads (for reindex)."""
        raise NotImplementedError

    @abstractmethod
    async def search(self, vector: list[float], limit: int,
                     must: dict | None = None) -> list[ScoredHit]:
        """Cosine search, optional exact-match payload filters."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, ids: list[str]) -> None:
        """Drop points by id (catalog tombstones)."""
        raise NotImplementedError

    @abstractmethod
    async def count(self) -> int:
        raise NotImplementedError


class QdrantStore(VectorStore):
    def __init__(self, url: str, collection: str) -> None:
        from qdrant_client import AsyncQdrantClient, models
        self._client = AsyncQdrantClient(url=url)
        self._models = models
        self._collection = collection

    async def _has_sparse(self) -> bool:
        info = await self._client.get_collection(self._collection)
        return bool((info.config.params.sparse_vectors or {}).get(SPARSE_VECTOR_NAME))

    async def _create_hybrid(self, dim: int) -> None:
        models = self._models
        await self._client.create_collection(
            self._collection,
            vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
            sparse_vectors_config={SPARSE_VECTOR_NAME: models.SparseVectorParams()},
        )
        await self._ensure_payload_indexes()

    async def _ensure_payload_indexes(self) -> None:
        models = self._models
        schema = {"keyword": models.PayloadSchemaType.KEYWORD,
                  "float": models.PayloadSchemaType.FLOAT}
        for field_name, kind in PAYLOAD_INDEXES.items():
            try:
                await self._client.create_payload_index(
                    self._collection, field_name=field_name,
                    field_schema=schema[kind])
            except Exception as exc:  # noqa: BLE001 — already exists
                log.debug("payload index %s skipped: %s", field_name, exc)

    async def ensure(self, dim: int) -> None:
        try:
            await self._client.get_collection(self._collection)
        except Exception:  # noqa: BLE001 — missing collection, create it
            await self._create_hybrid(dim)
            return
        if await self._has_sparse():
            await self._ensure_payload_indexes()
            return
        count = await self.count()
        if count == 0:
            log.warning("recreating empty collection %s as hybrid",
                        self._collection)
            await self._client.delete_collection(self._collection)
            await self._create_hybrid(dim)
            return
        log.warning("collection %s has %d dense-only points and no sparse "
                    "config; hybrid search stays unavailable until "
                    "POST /embed/reindex-hybrid", self._collection, count)

    def _point_vector(self, point: VectorPoint):
        models = self._models
        if point.sparse:
            assert point.vector is not None
            return {"": point.vector,
                    SPARSE_VECTOR_NAME: models.SparseVector(
                        indices=point.sparse.indices, values=point.sparse.values)}
        return point.vector

    async def upsert(self, points: list[VectorPoint]) -> None:
        if not points:
            return
        models = self._models
        await self._client.upsert(
            self._collection,
            points=[models.PointStruct(id=p.id, vector=self._point_vector(p),
                                       payload=p.payload or {})
                    for p in points],
        )

    async def patch_points(self, points: list[VectorPoint]) -> None:
        """Sparse vectors via update (dense untouched), payload merged."""
        models = self._models
        with_sparse = [p for p in points if p.sparse]
        if with_sparse:
            await self._client.update_vectors(
                self._collection,
                points=[models.PointVectors(
                    id=p.id, vector={SPARSE_VECTOR_NAME: models.SparseVector(
                        indices=p.sparse.indices,  # type: ignore[union-attr]
                        values=p.sparse.values)})  # type: ignore[union-attr]
                    for p in with_sparse],
            )
        for point in points:
            if point.payload:
                await self._client.set_payload(
                    self._collection, payload=point.payload, points=[point.id])

    async def scroll_all(self) -> list[VectorPoint]:
        points: list[VectorPoint] = []
        offset = None
        while True:
            batch, offset = await self._client.scroll(
                self._collection, limit=256, offset=offset,
                with_vectors=True, with_payload=True)
            for point in batch:
                vector = point.vector
                dense = vector.get("") if isinstance(vector, dict) else vector
                points.append(VectorPoint(id=str(point.id), vector=dense,
                                          payload=dict(point.payload or {})))
            if offset is None:
                break
        return points

    async def search(self, vector: list[float], limit: int,
                     must: dict | None = None) -> list[ScoredHit]:
        models = self._models
        query_filter = None
        if must:
            query_filter = models.Filter(must=[
                models.FieldCondition(key=key, match=models.MatchValue(value=value))
                for key, value in must.items()
            ])
        hits = await self._client.query_points(
            self._collection, query=vector, limit=limit, query_filter=query_filter,
            with_payload=True)
        return [ScoredHit(id=str(point.id), score=point.score,
                           payload=dict(point.payload or {}))
                for point in hits.points]

    async def delete(self, ids: list[str]) -> None:
        if not ids:
            return
        models = self._models
        await self._client.delete(
            self._collection,
            points_selector=models.PointIdsList(points=ids))

    async def count(self) -> int:
        return (await self._client.count(self._collection)).count


class MemoryStore(VectorStore):
    """Brute-force store for tests (and tiny local runs)."""

    def __init__(self) -> None:
        self._points: dict[str, VectorPoint] = {}
        self._dim = 0

    async def ensure(self, dim: int) -> None:
        self._dim = dim

    async def upsert(self, points: list[VectorPoint]) -> None:
        for point in points:
            self._points[point.id] = point

    async def patch_points(self, points: list[VectorPoint]) -> None:
        for point in points:
            stored = self._points.get(point.id)
            if stored is None:
                continue
            if point.sparse:
                stored.sparse = point.sparse
            if point.payload:
                stored.payload = {**(stored.payload or {}), **point.payload}

    async def scroll_all(self) -> list[VectorPoint]:
        return list(self._points.values())

    async def search(self, vector: list[float], limit: int,
                     must: dict | None = None) -> list[ScoredHit]:
        scored = []
        for point in self._points.values():
            payload = point.payload or {}
            if must and any(payload.get(k) != v for k, v in must.items()):
                continue
            scored.append(ScoredHit(id=point.id, score=_cosine(vector, point.vector or []),
                                    payload=payload))
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:limit]

    async def delete(self, ids: list[str]) -> None:
        for point_id in ids:
            self._points.pop(point_id, None)

    async def count(self) -> int:
        return len(self._points)


def _cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norm if norm else 0.0
