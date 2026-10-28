"""Hybrid search engine: dense + lexical -> RRF -> filter pipeline.

The engine performs one dense call, one lexical call, one fusion pass and
one post-filter pass; filters are composable specifications, not branches
inside this module.
"""
from __future__ import annotations

import logging

from ..clients.collector import CollectorClient
from ..clients.embeddings import EmbeddingProvider
from ..clients.vector import ScoredHit, VectorStore
from ..filters import (
    CategoryFilter,
    CityFilter,
    ExcludeCategoriesFilter,
    FilterPipeline,
    MaxPriceFilter,
    RubricFilter,
)
from ..models.search import FusedHit, SearchPlan
from .fusion import fuse_search

log = logging.getLogger(__name__)


class SearchService:
    def __init__(self, embedder: EmbeddingProvider, store: VectorStore,
                 collector: CollectorClient, *,
                 candidate_multiplier: int = 2) -> None:
        self._embedder = embedder
        self._store = store
        self._collector = collector
        self._candidate_multiplier = max(1, candidate_multiplier)

    async def _dense(self, query: str, limit: int,
                     must: dict[str, str]) -> list[ScoredHit]:
        if not query.strip():
            return []
        try:
            vector = (await self._embedder.embed([query]))[0]
            return await self._store.search(vector, limit, must or None)
        except Exception as exc:  # noqa: BLE001 — dense is optional, lexical is not
            log.warning("dense search failed, lexical only: %s", exc)
            return []

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
        params = pipeline.lexical_params()
        dense = await self._dense(plan.vector_query, candidates, must)
        if venues:
            rows = await self._collector.search_venues_lexical(
                plan.vector_query, params.get("city"), params.get("rubric"),
                candidates)
        else:
            rows = await self._collector.search_lexical(
                plan.vector_query, params.get("city"), params.get("category"),
                candidates)
        lexical_by_id = {str(row["id"]): row for row in rows}
        dense_ids = [(hit.id, dict(hit.payload)) for hit in dense]
        fused = fuse_search(dense_ids, list(lexical_by_id), candidates)
        # Price lives only in the lexical row, so the filter is built after it.
        if plan.max_price_per_person is not None:
            prices = {doc_id: row.get("price_min")
                      for doc_id, row in lexical_by_id.items()}
            pipeline.add(MaxPriceFilter(plan.max_price_per_person, prices))
        return self._finish(fused, lexical_by_id, pipeline, plan.limit, venues)

    @staticmethod
    def _finish(fused: list[FusedHit], lexical_by_id: dict[str, dict],
                pipeline: FilterPipeline, limit: int, venues: bool) -> list[FusedHit]:
        """One pass: backfill payload from lexical rows and apply filters."""
        result: list[FusedHit] = []
        for hit in fused:
            row = lexical_by_id.get(hit.id)
            if row is not None:
                keys = ("name", "rubric", "address") if venues else (
                    "title", "category", "city")
                for key in keys:
                    if not hit.payload.get(key) and row.get(key):
                        hit.payload[key] = row[key]
            if pipeline.matches(hit):
                result.append(hit)
                if len(result) >= limit:
                    break
        return result
