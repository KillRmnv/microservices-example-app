"""Vector search: Qdrant in prod, brute-force in-memory for tests."""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ScoredHit:
    id: str
    score: float
    payload: dict = field(default_factory=dict)


class VectorStore(ABC):
    @abstractmethod
    async def search(self, vector: list[float], limit: int,
                     must: dict | None = None) -> list[ScoredHit]:
        raise NotImplementedError


class QdrantStore(VectorStore):
    def __init__(self, url: str, collection: str) -> None:
        from qdrant_client import AsyncQdrantClient, models
        self._client = AsyncQdrantClient(url=url)
        self._models = models
        self._collection = collection

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


class InMemoryStore(VectorStore):
    def __init__(self, points: list[tuple[str, list[float], dict]] | None = None) -> None:
        self._points = points or []

    async def search(self, vector: list[float], limit: int,
                     must: dict | None = None) -> list[ScoredHit]:
        scored = []
        for point_id, point_vector, payload in self._points:
            if must and any(payload.get(k) != v for k, v in must.items()):
                continue
            scored.append(ScoredHit(id=point_id,
                                    score=_cosine(vector, point_vector),
                                    payload=payload))
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:limit]


def _cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norm if norm else 0.0
