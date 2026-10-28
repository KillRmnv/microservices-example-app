"""Vector search: Qdrant Hybrid in prod, brute-force in-memory for tests.

Hybrid = one dense query + one sparse query fused server-side with RRF.
Exact-match filters (city/category/rubric) are pushed into Qdrant; price
stays a Python post-filter because unknown prices must pass the filter.
"""
from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..sparse import SPARSE_VECTOR_NAME, SparseVector, sparse_dot

log = logging.getLogger(__name__)


@dataclass
class ScoredHit:
    id: str
    score: float
    payload: dict = field(default_factory=dict)


class VectorStore(ABC):
    @abstractmethod
    async def hybrid_search(self, dense: list[float] | None,
                            sparse: SparseVector | None, limit: int,
                            must: dict | None = None) -> list[ScoredHit]:
        """Fused dense+sparse search. Either side may be None (degraded)."""
        raise NotImplementedError


class QdrantStore(VectorStore):
    def __init__(self, url: str, collection: str) -> None:
        from qdrant_client import AsyncQdrantClient, models
        self._client = AsyncQdrantClient(url=url)
        self._models = models
        self._collection = collection

    async def hybrid_search(self, dense: list[float] | None,
                            sparse: SparseVector | None, limit: int,
                            must: dict | None = None) -> list[ScoredHit]:
        if dense is None and sparse is None:
            return []
        models = self._models
        query_filter = None
        if must:
            query_filter = models.Filter(must=[
                models.FieldCondition(key=key, match=models.MatchValue(value=value))
                for key, value in must.items()
            ])
        if dense is not None and sparse is not None:
            hits = await self._client.query_points(
                self._collection,
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                prefetch=[
                    models.Prefetch(query=dense, limit=limit),
                    models.Prefetch(
                        query=models.SparseVector(indices=sparse.indices,
                                                  values=sparse.values),
                        using=SPARSE_VECTOR_NAME, limit=limit),
                ],
                query_filter=query_filter, limit=limit, with_payload=True)
        elif dense is not None:
            log.warning("hybrid degraded to dense-only for %s", self._collection)
            hits = await self._client.query_points(
                self._collection, query=dense, limit=limit,
                query_filter=query_filter, with_payload=True)
        else:
            assert sparse is not None
            log.warning("hybrid degraded to sparse-only for %s", self._collection)
            hits = await self._client.query_points(
                self._collection,
                query=models.SparseVector(indices=sparse.indices,
                                          values=sparse.values),
                using=SPARSE_VECTOR_NAME, limit=limit,
                query_filter=query_filter, with_payload=True)
        return [ScoredHit(id=str(point.id), score=point.score,
                           payload=dict(point.payload or {}))
                for point in hits.points]


class InMemoryStore(VectorStore):
    def __init__(self, points: list[tuple[str, list[float], dict]] | None = None,
                 sparse_points: dict[str, SparseVector | None] | None = None) -> None:
        self._points = points or []
        self._sparse = {pid: (vec or SparseVector())
                        for pid, vec in (sparse_points or {}).items()}

    async def hybrid_search(self, dense: list[float] | None,
                            sparse: SparseVector | None, limit: int,
                            must: dict | None = None) -> list[ScoredHit]:
        filtered = [(pid, vec, payload) for pid, vec, payload in self._points
                    if not must or all(payload.get(k) == v for k, v in must.items())]
        rankings: list[list[str]] = []
        if dense is not None:
            scored = sorted(filtered,
                            key=lambda item: _cosine(dense, item[1]), reverse=True)
            rankings.append([pid for pid, _, _ in scored])
        if sparse is not None:
            scored = sorted(
                filtered,
                key=lambda item: sparse_dot(sparse, self._sparse.get(item[0],
                                                             SparseVector())),
                reverse=True)
            # Qdrant sparse drops zero-score points; mirror that.
            rankings.append([pid for pid, _, _ in scored
                             if sparse_dot(sparse, self._sparse.get(
                                 pid, SparseVector())) > 0])
        if not rankings:
            return []
        payloads = {pid: payload for pid, _, payload in filtered}
        fused = _rrf(rankings)
        return [ScoredHit(id=pid, score=score, payload=dict(payloads.get(pid, {})))
                for pid, score in fused[:limit]]


def _rrf(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda item: item[1], reverse=True)


def _cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norm if norm else 0.0
