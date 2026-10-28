"""Hybrid search engine: Qdrant dense+sparse fused server-side (RRF).

One Qdrant hybrid call carries exact-match filters; price stays a Python
post-filter because unknown prices must pass. When Qdrant hybrid fails
(missing sparse config, outage), the engine falls back to the collector
lexical endpoint fused in Python — the old path, kept for resilience.
"""
from __future__ import annotations

import asyncio
import logging

from ..clients.collector import CollectorClient
from ..clients.embeddings import EmbeddingProvider
from ..clients.vector import VectorStore
from ..filters import (
    CategoryFilter,
    CityFilter,
    ExcludeCategoriesFilter,
    FilterPipeline,
    MaxPriceFilter,
    RubricFilter,
)
from ..models.search import FusedHit, SearchPlan
from ..sparse import SparseVector, encode_sparse
from .fusion import fuse_search

log = logging.getLogger(__name__)

HYBRID_ORIGIN = "hybrid"


class SearchService:
    def __init__(self, embedder: EmbeddingProvider, store: VectorStore,
                 collector: CollectorClient, *,
                 candidate_multiplier: int = 2,
                 query_timeout_s: float = 2.0) -> None:
        self._embedder = embedder
        self._store = store
        self._collector = collector
        self._candidate_multiplier = max(1, candidate_multiplier)
        self._query_timeout_s = query_timeout_s

    async def _encode_query(self, query: str) -> tuple[list[float] | None,
                                                      SparseVector | None]:
        """Dense via embedder (optional), sparse local (never fails)."""
        dense: list[float] | None = None
        if query.strip():
            try:
                # A query embedding must never stall the turn: without a
                # model server the sparse half still answers in milliseconds.
                dense = (await asyncio.wait_for(
                    self._embedder.embed([query]),
                    timeout=self._query_timeout_s))[0]
            except Exception as exc:  # noqa: BLE001 — sparse still works
                log.warning("dense embed failed, sparse only: %s", exc)
        return dense, encode_sparse(query)

    async def events(self, plan: SearchPlan) -> list[FusedHit]:
        pipeline = FilterPipeline()
        if plan.city:
            pipeline.add(CityFilter(plan.city))
        if plan.category:
            pipeline.add(CategoryFilter(plan.category))
        if plan.exclude_categories:
            pipeline.add(ExcludeCategoriesFilter(plan.exclude_categories))
        return await self._search(plan, pipeline, venues=False)

    async def venues(self, plan: SearchPlan) -> list[FusedHit]:
        pipeline = FilterPipeline()
        if plan.city:
            pipeline.add(CityFilter(plan.city))
        if plan.rubric:
            pipeline.add(RubricFilter(plan.rubric))
        return await self._search(plan, pipeline, venues=True)

    async def _search(self, plan: SearchPlan, pipeline: FilterPipeline,
                      *, venues: bool) -> list[FusedHit]:
        candidates = plan.limit * self._candidate_multiplier
        must = pipeline.qdrant_must()
        dense, sparse = await self._encode_query(plan.vector_query)
        try:
            if dense is None and sparse is None:
                raise ValueError("empty query")
            hits = await self._store.hybrid_search(dense, sparse, candidates,
                                                   must or None)
            fused = [FusedHit(id=hit.id, score=hit.score, origins=[HYBRID_ORIGIN],
                              payload=dict(hit.payload)) for hit in hits]
        except Exception as exc:  # noqa: BLE001 — lexical fallback
            log.warning("qdrant hybrid failed, lexical fallback: %s", exc)
            fused = await self._lexical_fallback(plan, pipeline, candidates,
                                                 venues)
            return self._finish_fallback(fused, pipeline, plan, venues)
        if not fused:
            # Empty vector index (fresh volume, embeddings not backfilled yet)
            # must not hide rows that the lexical half can still find.
            log.info("hybrid returned no hits, lexical fallback")
            fused = await self._lexical_fallback(plan, pipeline, candidates,
                                                 venues)
            return self._finish_fallback(fused, pipeline, plan, venues)
        if plan.max_price_per_person is not None and not venues:
            prices = {hit.id: hit.payload.get("price_min") for hit in fused}
            pipeline.add(MaxPriceFilter(plan.max_price_per_person, prices))
        return [hit for hit in fused if pipeline.matches(hit)][:plan.limit]

    async def _lexical_fallback(self, plan: SearchPlan, pipeline: FilterPipeline,
                                candidates: int, venues: bool) -> list[FusedHit]:
        params = pipeline.lexical_params()
        if venues:
            rows = await self._collector.search_venues_lexical(
                plan.vector_query, params.get("city"), params.get("rubric"),
                candidates)
        else:
            rows = await self._collector.search_lexical(
                plan.vector_query, params.get("city"), params.get("category"),
                candidates)
        lexical_by_id = {str(row["id"]): row for row in rows}
        fused = fuse_search([], list(lexical_by_id), candidates)
        for hit in fused:
            hit.payload.update({k: v for k, v in
                                lexical_by_id[hit.id].items() if v is not None})
        return fused

    def _finish_fallback(self, fused: list[FusedHit], pipeline: FilterPipeline,
                         plan: SearchPlan, venues: bool) -> list[FusedHit]:
        """Old path: backfill payload from lexical rows, then filter."""
        if plan.max_price_per_person is not None and not venues:
            prices = {hit.id: hit.payload.get("price_min") for hit in fused}
            pipeline.add(MaxPriceFilter(plan.max_price_per_person, prices))
        result = [hit for hit in fused if pipeline.matches(hit)]
        return result[:plan.limit]
