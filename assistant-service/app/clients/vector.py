"""Vector search: Qdrant Hybrid in prod, brute-force in-memory for tests.

Hybrid = one dense query + one sparse query (+ optionally a BM25 full-text
query) fused server-side with RRF. Exact-match filters (city/category/rubric)
are pushed into Qdrant; price stays a Python post-filter because unknown
prices must pass the filter.
"""
from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field

from ..models.search import PayloadDateRange
from ..sparse import SPARSE_VECTOR_NAME, SparseVector, sparse_dot, tokenize

log = logging.getLogger(__name__)

# Full-text payload index created by the collector (BM25, scoring=True).
TEXT_INDEX_NAME = "search_text"

# Retriever names used by RRF weights (and the prefetch -> weight mapping).
RETRIEVERS = ("dense", "sparse", "bm25")


def _resolved_weights(weights: Mapping[str, float] | None) -> dict[str, float]:
    """Neutral 1.0 for every retriever unless the caller overrides it."""
    resolved = {name: 1.0 for name in RETRIEVERS}
    for name, value in (weights or {}).items():
        if name not in resolved or value is None:
            continue
        try:
            resolved[name] = max(0.0, float(value))
        except (TypeError, ValueError):
            continue
    return resolved


def _weights_are_uniform(weights: Mapping[str, float]) -> bool:
    return len({round(value, 9) for value in weights.values()}) <= 1


@dataclass
class ScoredHit:
    id: str
    score: float
    payload: dict = field(default_factory=dict)


class VectorStore(ABC):
    @abstractmethod
    async def hybrid_search(self, dense: list[float] | None,
                            sparse: SparseVector | None, limit: int,
                            must: dict | None = None,
                            must_not: dict | None = None,
                            text_query: str | None = None,
                            weights: Mapping[str, float] | None = None,
                            ) -> list[ScoredHit]:
        """Fused dense+sparse(+BM25) search. Any side may be None.

        ``weights`` are per-retriever RRF weights (``dense``/``sparse``/
        ``bm25``); omitted or uniform weights keep plain RRF.
        """
        raise NotImplementedError


def _qdrant_conditions(models, spec: dict | None) -> list:
    """Payload dict -> Qdrant field conditions (dates as ranges)."""
    conditions = []
    for key, value in (spec or {}).items():
        if isinstance(value, PayloadDateRange):
            conditions.append(models.FieldCondition(
                key=key,
                range=models.DatetimeRange(gte=value.gte, lt=value.lt)))
        elif isinstance(value, (list, tuple, set)):
            conditions.append(models.FieldCondition(
                key=key, match=models.MatchAny(any=list(value))))
        else:
            conditions.append(models.FieldCondition(
                key=key, match=models.MatchValue(value=value)))
    return conditions


class QdrantStore(VectorStore):
    def __init__(self, url: str, collection: str,
                 dense_min_score: float = 0.0) -> None:
        from qdrant_client import AsyncQdrantClient, models
        self._client = AsyncQdrantClient(url=url)
        self._models = models
        self._collection = collection
        self._dense_min_score = dense_min_score

    async def hybrid_search(self, dense: list[float] | None,
                            sparse: SparseVector | None, limit: int,
                            must: dict | None = None,
                            must_not: dict | None = None,
                            text_query: str | None = None,
                            weights: Mapping[str, float] | None = None,
                            ) -> list[ScoredHit]:
        if dense is None and sparse is None and not text_query:
            return []
        models = self._models
        must_conditions = _qdrant_conditions(models, must)
        must_not_conditions = _qdrant_conditions(models, must_not)
        query_filter = None
        if must_conditions or must_not_conditions:
            query_filter = models.Filter(
                must=must_conditions or None,
                must_not=must_not_conditions or None)
        prefetches: list[tuple[str, object]] = []
        if dense is not None:
            prefetches.append(("dense", models.Prefetch(
                query=dense, limit=limit, filter=query_filter,
                score_threshold=self._dense_min_score)))
        if sparse is not None:
            prefetches.append(("sparse", models.Prefetch(
                query=models.SparseVector(indices=sparse.indices,
                                          values=sparse.values),
                using=SPARSE_VECTOR_NAME, limit=limit, filter=query_filter)))
        if text_query:
            prefetches.append(("bm25", models.Prefetch(
                query=models.TextQuery(text=text_query),
                using=TEXT_INDEX_NAME, limit=limit, filter=query_filter)))
        if not prefetches:
            return []
        resolved = _resolved_weights(weights)
        only_prefetch = [prefetch for _, prefetch in prefetches]
        if len(prefetches) == 1:
            only = only_prefetch[0]
            log.info("hybrid degraded to a single prefetch for %s",
                     self._collection)
            hits = await self._client.query_points(
                self._collection, query=only.query, using=only.using,
                limit=limit, query_filter=query_filter, with_payload=True,
                score_threshold=only.score_threshold)
        elif _weights_are_uniform(resolved):
            # Plain RRF stays server-side: one round trip, Qdrant's fusion.
            hits = await self._client.query_points(
                self._collection,
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                prefetch=only_prefetch,
                query_filter=query_filter, limit=limit, with_payload=True)
        else:
            return await self._weighted_fusion(prefetches, resolved, limit,
                                               query_filter)
        return [ScoredHit(id=str(point.id), score=point.score,
                           payload=dict(point.payload or {}))
                for point in hits.points]

    async def _weighted_fusion(self, prefetches: list[tuple[str, object]],
                               weights: Mapping[str, float], limit: int,
                               query_filter) -> list[ScoredHit]:
        """One query per enabled retriever, then weighted RRF in Python.

        Qdrant's server-side RRF has no per-branch weights, so unequal
        weights are the only case that pays for the extra round trips.
        """
        rankings: list[list[str]] = []
        rank_weights: list[float] = []
        payloads: dict[str, dict] = {}
        for name, prefetch in prefetches:
            weight = weights[name]
            if weight <= 0:
                continue
            hits = await self._client.query_points(
                self._collection, query=prefetch.query, using=prefetch.using,
                limit=limit, query_filter=query_filter, with_payload=True,
                score_threshold=prefetch.score_threshold)
            ranking: list[str] = []
            for point in hits.points:
                point_id = str(point.id)
                ranking.append(point_id)
                payloads.setdefault(point_id, dict(point.payload or {}))
            rankings.append(ranking)
            rank_weights.append(weight)
        if not rankings:
            return []
        log.info("weighted RRF client-side fusion over %s retrievers for %s",
                 len(rankings), self._collection)
        return [ScoredHit(id=point_id, score=score,
                          payload=payloads.get(point_id, {}))
                for point_id, score in _rrf(rankings, weights=rank_weights)[:limit]]


class InMemoryStore(VectorStore):
    def __init__(self, points: list[tuple[str, list[float], dict]] | None = None,
                 sparse_points: dict[str, SparseVector | None] | None = None) -> None:
        self._points = points or []
        self._sparse = {pid: (vec or SparseVector())
                        for pid, vec in (sparse_points or {}).items()}

    async def hybrid_search(self, dense: list[float] | None,
                            sparse: SparseVector | None, limit: int,
                            must: dict | None = None,
                            must_not: dict | None = None,
                            text_query: str | None = None,
                            weights: Mapping[str, float] | None = None,
                            ) -> list[ScoredHit]:
        filtered = [(pid, vec, payload) for pid, vec, payload in self._points
                    if (not must or _matches_must(payload, must))
                    and (not must_not or not _matches_any(payload, must_not))]
        resolved = _resolved_weights(weights)
        rankings: list[list[str]] = []
        ranking_weights: list[float] = []

        def add(ranking: list[str], name: str) -> None:
            weight = resolved[name]
            if weight <= 0:
                return
            rankings.append(ranking)
            ranking_weights.append(weight)

        if dense is not None:
            scored = sorted(filtered,
                            key=lambda item: _cosine(dense, item[1]), reverse=True)
            add([pid for pid, _, _ in scored], "dense")
        if sparse is not None:
            scored = sorted(
                filtered,
                key=lambda item: sparse_dot(sparse, self._sparse.get(item[0],
                                                             SparseVector())),
                reverse=True)
            # Qdrant sparse drops zero-score points; mirror that.
            add([pid for pid, _, _ in scored
                 if sparse_dot(sparse, self._sparse.get(
                     pid, SparseVector())) > 0], "sparse")
        query_terms = set(tokenize(text_query or ""))
        if query_terms:
            # Stand-in for the BM25 text index: term overlap over `search_text`.
            scored = sorted(
                ((pid, _term_overlap(query_terms, payload))
                 for pid, _, payload in filtered),
                key=lambda item: item[1], reverse=True)
            add([pid for pid, score in scored if score > 0], "bm25")
        if not rankings:
            return []
        payloads = {pid: payload for pid, _, payload in filtered}
        fused = _rrf(rankings, weights=ranking_weights)
        return [ScoredHit(id=pid, score=score, payload=dict(payloads.get(pid, {})))
                for pid, score in fused[:limit]]


def _term_overlap(query_terms: set[str], payload: dict) -> float:
    """Cheap BM25 stand-in: count of query terms present in the payload text."""
    text = (payload.get("search_text") or payload.get("title")
            or payload.get("name") or "")
    document = set(tokenize(str(text)))
    return float(len(query_terms & document))


def _field_matches(value, expected) -> bool:
    if isinstance(expected, PayloadDateRange):
        return _in_range(value, expected)
    if isinstance(expected, (list, tuple, set)):
        return value in expected
    return value == expected


def _matches_must(payload: dict, must: dict) -> bool:
    for key, expected in must.items():
        value = payload.get(key)
        if key == "end_at" and not value:
            # Older points were embedded without end_at; a single-day event
            # ends when it starts.
            value = payload.get("start_at")
        if not _field_matches(value, expected):
            return False
    return True


def _matches_any(payload: dict, must_not: dict) -> bool:
    """True when any negative condition matches (Qdrant `must_not` is OR)."""
    for key, expected in must_not.items():
        if _field_matches(payload.get(key), expected):
            return True
    return False


def _in_range(value, window: PayloadDateRange) -> bool:
    from datetime import datetime
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        start = (datetime.fromisoformat(window.gte)
                 if window.gte else None)
        end = (datetime.fromisoformat(window.lt)
               if window.lt else None)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        return False
    if start is not None and parsed < start:
        return False
    if end is not None and parsed >= end:
        return False
    return True


def _rrf(rankings: list[list[str]], k: int = 60,
         weights: list[float] | None = None) -> list[tuple[str, float]]:
    """Weighted reciprocal rank fusion; bare RRF when `weights` is omitted.

    Each ranking contributes ``weight / (k + rank)``; matching Qdrant's
    server-side RRF when every weight is 1.0.
    """
    fused: dict[str, float] = {}
    for index, ranking in enumerate(rankings):
        weight = 1.0 if weights is None else weights[index]
        if weight <= 0:
            continue
        for rank, doc_id in enumerate(ranking, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + weight / (k + rank)
    return sorted(fused.items(), key=lambda item: item[1], reverse=True)


def _cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norm if norm else 0.0
