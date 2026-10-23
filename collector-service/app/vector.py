"""Qdrant access: one `events` collection, cosine, payload for filtering."""
from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class VectorPoint:
    id: str  # collected_events.id as text
    vector: list[float]
    payload: dict = field(default_factory=dict)


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
        raise NotImplementedError

    @abstractmethod
    async def search(self, vector: list[float], limit: int,
                     must: dict | None = None) -> list[ScoredHit]:
        """Cosine search, optional exact-match payload filters."""
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

    async def ensure(self, dim: int) -> None:
        models = self._models
        try:
            await self._client.get_collection(self._collection)
            return
        except Exception:  # noqa: BLE001 — missing collection, create it
            pass
        await self._client.create_collection(
            self._collection,
            vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
        )

    async def upsert(self, points: list[VectorPoint]) -> None:
        if not points:
            return
        models = self._models
        await self._client.upsert(
            self._collection,
            points=[models.PointStruct(id=p.id, vector=p.vector, payload=p.payload)
                    for p in points],
        )

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

    async def search(self, vector: list[float], limit: int,
                     must: dict | None = None) -> list[ScoredHit]:
        scored = []
        for point in self._points.values():
            if must and any(point.payload.get(k) != v for k, v in must.items()):
                continue
            scored.append(ScoredHit(id=point.id, score=_cosine(vector, point.vector),
                                    payload=point.payload))
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:limit]

    async def count(self) -> int:
        return len(self._points)


def _cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norm if norm else 0.0
