"""Hybrid search engine: Qdrant dense+sparse (+BM25) fused server-side (RRF).

One Qdrant hybrid call carries exact-match filters; price stays a Python
post-filter because unknown prices must pass. Modes:

- ``bm25`` (compose default): dense + sparse + full-text BM25 prefetch. If the
  BM25 index is missing the call is retried as dense+sparse.
- ``sparse`` (code default): dense + sparse only.
- ``lexical``: skip Qdrant entirely and use the collector lexical endpoint.

When every vector path fails (missing sparse config, outage), the engine falls
back to the collector lexical endpoint fused in Python — the old path, kept
for resilience.
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
    DateRangeFilter,
    ExcludeCategoriesFilter,
    ExcludeTagsFilter,
    FilterPipeline,
    MaxPriceFilter,
    RubricFilter,
)
from ..models.search import FusedHit, SearchPlan
from ..sparse import SparseVector, encode_sparse
from .fusion import fuse_search

log = logging.getLogger(__name__)

HYBRID_ORIGIN = "hybrid"
HYBRID_MODES = ("bm25", "sparse", "lexical")


class SearchService:
    def __init__(self, embedder: EmbeddingProvider, store: VectorStore,
                 collector: CollectorClient, *,
                 candidate_multiplier: int = 2,
                 query_timeout_s: float = 2.0,
                 hybrid_mode: str = "sparse") -> None:
        mode = (hybrid_mode or "sparse").strip().lower()
        if mode not in HYBRID_MODES:
            raise ValueError(
                f"unknown hybrid_mode {hybrid_mode!r}; expected one of "
                f"{', '.join(HYBRID_MODES)}")
        self._embedder = embedder
        self._store = store
        self._collector = collector
        self._candidate_multiplier = max(1, candidate_multiplier)
        self._query_timeout_s = query_timeout_s
        self._hybrid_mode = mode

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
        if plan.categories:
            pipeline.add(CategoryFilter(plan.categories))
        if plan.exclude_categories:
            pipeline.add(ExcludeCategoriesFilter(plan.exclude_categories))
        if plan.exclude_tags:
            pipeline.add(ExcludeTagsFilter(plan.exclude_tags))
        if plan.date_from is not None:
            pipeline.add(DateRangeFilter(plan.date_from, plan.date_to))
        return await self._search(plan, pipeline, venues=False)

    async def venues(self, plan: SearchPlan) -> list[FusedHit]:
        pipeline = FilterPipeline()
        if plan.city:
            pipeline.add(CityFilter(plan.city))
        if plan.rubric:
            pipeline.add(RubricFilter(plan.rubric))
        if plan.exclude_tags:
            pipeline.add(ExcludeTagsFilter(plan.exclude_tags))
        return await self._search(plan, pipeline, venues=True)

    async def _search(self, plan: SearchPlan, pipeline: FilterPipeline,
                      *, venues: bool) -> list[FusedHit]:
        candidates = plan.limit * self._candidate_multiplier
        must = pipeline.qdrant_must()
        must_not = pipeline.must_not()
        if must_not or plan.exclude_tags:
            # Tag exclusion is a Python post-filter over free text: fetch a
            # wider window or the survivors may not fill `limit`.
            candidates = plan.limit * max(self._candidate_multiplier, 3)
        if self._hybrid_mode == "lexical":
            # Operator escape hatch: Postgres tsvector only, no Qdrant.
            log.info("hybrid_mode=lexical, skipping the vector store")
            fused = await self._lexical_fallback(plan, pipeline, candidates,
                                                 venues)
            return self._finish_fallback(fused, pipeline, plan, venues)
        dense, sparse = await self._encode_query(plan.vector_query)
        if plan.dense_only:
            sparse = None
        text_query = (plan.vector_query.strip()
                      if self._hybrid_mode == "bm25" else None) or None
        try:
            if dense is None and sparse is None and not text_query:
                raise ValueError("empty query")
            if text_query:
                try:
                    hits = await self._store.hybrid_search(
                        dense, sparse, candidates, must or None,
                        must_not or None, text_query=text_query)
                except Exception as exc:  # noqa: BLE001 — missing BM25 index
                    log.warning("BM25 search failed, retrying dense+sparse: %s",
                                exc)
                    if dense is None and sparse is None:
                        raise
                    hits = await self._store.hybrid_search(
                        dense, sparse, candidates, must or None,
                        must_not or None)
            else:
                hits = await self._store.hybrid_search(dense, sparse,
                                                       candidates, must or None,
                                                       must_not or None)
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
                plan.vector_query, params.get("city"), params.get("categories"),
                candidates, date_from=params.get("date_from"),
                date_to=params.get("date_to"))
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
