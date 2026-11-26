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

Ranking: fused RRF score, then near-zero tie-breaks only — rating (events:
the venue rating; venues: their own), freshness for events, and group-fit
amenities for venues at a large party size. Every boost is a small epsilon,
so the retriever order still decides.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from ..clients.collector import CollectorClient
from ..clients.embeddings import EmbeddingProvider
from ..clients.vector import RETRIEVERS, VectorStore
from ..core.config import settings as default_settings
from ..filters import (
    AgeMaxFilter,
    AmenityExcludeFilter,
    CategoryFilter,
    CityFilter,
    DateRangeFilter,
    ExcludeCategoriesFilter,
    ExcludeIdsFilter,
    ExcludeTagsFilter,
    ExcludeVenueCategoriesFilter,
    FilterPipeline,
    MaxPriceFilter,
    MinRatingFilter,
    PartyFilter,
    RubricFilter,
    StatusFilter,
    VenueBudgetFilter,
    VenueHoursFilter,
)
from ..filters.specs import normalise_tag
from ..models.search import FusedHit, SearchPlan
from ..sparse import SparseVector, encode_sparse
from .fusion import fuse_search
from .rerank import NoopReranker, Reranker

log = logging.getLogger(__name__)

HYBRID_ORIGIN = "hybrid"
HYBRID_MODES = ("bm25", "sparse", "lexical")


def _weight_map(value: Mapping[str, float] | str | None) -> dict[str, float]:
    """Accept a parsed map, the ``dense:1,sparse:1,bm25:1`` string or None."""
    if value is None:
        return dict(default_settings.hybrid_weight_map())
    if isinstance(value, Mapping):
        parsed = {name: 1.0 for name in RETRIEVERS}
        for name, weight in value.items():
            if name in parsed and weight is not None:
                try:
                    parsed[name] = max(0.0, float(weight))
                except (TypeError, ValueError):
                    continue
        return parsed
    parsed = {name: 1.0 for name in RETRIEVERS}
    for chunk in str(value).split(","):
        name, _, raw = chunk.partition(":")
        name = name.strip().casefold()
        if name not in parsed:
            continue
        try:
            weight = float(raw.strip())
        except ValueError:
            continue
        if weight >= 0:
            parsed[name] = weight
    return parsed


def _term_list(value: list[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(part).strip() for part in value if str(part).strip()]


def _parse_iso(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _amenity_tags(payload: Mapping) -> set[str]:
    amenities = payload.get("amenities")
    if not isinstance(amenities, (list, tuple, set)):
        return set()
    return {normalise_tag(item) for item in amenities if item}


class SearchService:
    def __init__(self, embedder: EmbeddingProvider, store: VectorStore,
                 collector: CollectorClient, *,
                 candidate_multiplier: int = 2,
                 query_timeout_s: float = 2.0,
                 hybrid_mode: str = "sparse",
                 rating_boost: float | None = None,
                 price_levels: dict[str, float] | None = None,
                 hybrid_weights: Mapping[str, float] | str | None = None,
                 freshness_boost: float | None = None,
                 freshness_horizon_days: int | None = None,
                 rerank_enabled: bool | None = None,
                 reranker: Reranker | None = None,
                 venue_group_party_min: int | None = None,
                 venue_group_query_terms: list[str] | str | None = None,
                 venue_group_amenities: list[str] | str | None = None,
                 venue_group_boost: float | None = None,
                 now: Callable[[], datetime] | None = None) -> None:
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
        self._rating_boost = (default_settings.search_rating_boost
                              if rating_boost is None else rating_boost)
        self._price_levels = (default_settings.venue_price_level_map()
                              if price_levels is None else price_levels)

        self._weights = _weight_map(hybrid_weights)
        # Uniform weights keep the plain server-side RRF path untouched.
        self._weighted = (len({round(value, 9)
                              for value in self._weights.values()}) > 1)

        self._freshness_boost = (default_settings.search_freshness_boost
                                 if freshness_boost is None else freshness_boost)
        self._freshness_horizon_days = (
            default_settings.search_freshness_horizon_days
            if freshness_horizon_days is None else freshness_horizon_days)

        self._rerank_enabled = (default_settings.rerank_enabled
                                if rerank_enabled is None else rerank_enabled)
        self._reranker: Reranker = reranker or NoopReranker()

        self._group_party_min = (
            default_settings.venue_group_party_min
            if venue_group_party_min is None else venue_group_party_min)
        self._group_terms = _term_list(
            default_settings.venue_group_query_terms
            if venue_group_query_terms is None else venue_group_query_terms)
        self._group_amenities = {
            tag for tag in (normalise_tag(item) for item in _term_list(
                default_settings.venue_group_amenities
                if venue_group_amenities is None else venue_group_amenities))
            if tag}
        self._group_boost = (default_settings.venue_group_boost
                             if venue_group_boost is None else venue_group_boost)
        self._now = now or (lambda: datetime.now(timezone.utc))

    # --- query building ----------------------------------------------------

    @staticmethod
    def _lexical_query(plan: SearchPlan) -> str:
        """Vector query plus themes: themes must reach sparse and BM25.

        The model often leaves ``vector_query`` empty when the user only
        named a theme ("джаз", "выставки"), so the themes themselves are the
        fallback lexical query.
        """
        themes = " ".join(str(theme).strip() for theme in plan.themes
                          if str(theme).strip())
        base = plan.vector_query.strip()
        if themes:
            return f"{base} {themes}".strip()
        return plan.vector_query

    async def _encode_query(self, query: str,
                            lexical_query: str | None = None,
                            ) -> tuple[list[float] | None, SparseVector | None]:
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
        return dense, encode_sparse(lexical_query if lexical_query is not None
                                    else query)

    # --- public entry points ----------------------------------------------

    async def events(self, plan: SearchPlan, *,
                     stats: dict | None = None) -> list[FusedHit]:
        pipeline = FilterPipeline()
        if plan.city:
            pipeline.add(CityFilter(plan.city))
        if plan.categories:
            pipeline.add(CategoryFilter(plan.categories))
        if plan.exclude_categories:
            pipeline.add(ExcludeCategoriesFilter(plan.exclude_categories))
        if plan.exclude_tags:
            pipeline.add(ExcludeTagsFilter(plan.exclude_tags))
        if plan.exclude_amenities:
            pipeline.add(AmenityExcludeFilter(plan.exclude_amenities))
        if plan.exclude_ids:
            pipeline.add(ExcludeIdsFilter(plan.exclude_ids))
        # Undated announcements are a category-only mode: undated points pass,
        # but past dated events are still dropped by the same filter.
        date_from = plan.date_from
        if plan.include_undated and date_from is None:
            date_from = self._now()
        if date_from is not None:
            pipeline.add(DateRangeFilter(date_from, plan.date_to,
                                         allow_undated=plan.include_undated))
        pipeline.add(PartyFilter(plan.party_size))
        pipeline.add(StatusFilter(plan.party_size))
        if plan.age_max is not None:
            pipeline.add(AgeMaxFilter(plan.age_max))
        if plan.min_rating is not None:
            pipeline.add(MinRatingFilter(plan.min_rating, key="venue_rating"))
        return await self._search(plan, pipeline, venues=False, stats=stats)

    async def venues(self, plan: SearchPlan, *,
                     stats: dict | None = None) -> list[FusedHit]:
        """Venue search; a rubric that matches nothing falls back to none.

        Live 2GIS rubrics are sparse and intent rubrics ("Бары", "Рестораны")
        often do not exist in the data, yet the dense+BM25 text match is still
        good. One retry without the rubric filter, never a loop.

        A large party enriches the semantic query once, before the retry, so
        both attempts search for a group-friendly place.
        """
        plan = self._group_plan(plan)
        hits = await self._venue_search(plan, stats=stats)
        if hits or not plan.rubric:
            return hits
        log.info("no venues for rubric %r, retrying without it", plan.rubric)
        return await self._venue_search(replace(plan, rubric=None), stats=stats)

    def _group_plan(self, plan: SearchPlan) -> SearchPlan:
        """Append group terms to the venue query for a big party.

        Capacity is deliberately not part of this: the product goal is a
        relevant place for a company, not a seat count. Never drops a venue.
        """
        if (plan.party_size or 0) < self._group_party_min or not self._group_terms:
            return plan
        terms = " ".join(self._group_terms)
        base = plan.vector_query.strip()
        return replace(plan, vector_query=f"{base} {terms}".strip())

    async def _venue_search(self, plan: SearchPlan, *,
                            stats: dict | None = None) -> list[FusedHit]:
        pipeline = FilterPipeline()
        if plan.city:
            pipeline.add(CityFilter(plan.city))
        if plan.rubric:
            pipeline.add(RubricFilter(plan.rubric))
        if plan.exclude_tags:
            pipeline.add(ExcludeTagsFilter(plan.exclude_tags))
        if plan.exclude_amenities:
            pipeline.add(AmenityExcludeFilter(plan.exclude_amenities))
        if plan.exclude_categories:
            pipeline.add(ExcludeVenueCategoriesFilter(plan.exclude_categories))
        if plan.exclude_ids:
            pipeline.add(ExcludeIdsFilter(plan.exclude_ids))
        pipeline.add(PartyFilter(plan.party_size))
        pipeline.add(StatusFilter(plan.party_size))
        if plan.min_rating is not None:
            pipeline.add(MinRatingFilter(plan.min_rating, key="rating"))
        if plan.date_from is not None:
            pipeline.add(VenueHoursFilter(
                plan.date_from, plan.date_to, plan.timezone))
        if plan.max_price_per_person is not None:
            pipeline.add(VenueBudgetFilter(plan.max_price_per_person,
                                           self._price_levels))
        return await self._search(plan, pipeline, venues=True, stats=stats)

    # --- the pipeline ------------------------------------------------------

    async def _search(self, plan: SearchPlan, pipeline: FilterPipeline,
                      *, venues: bool, stats: dict | None = None
                      ) -> list[FusedHit]:
        candidates = plan.limit * self._candidate_multiplier
        must = pipeline.qdrant_must()
        must_not = pipeline.must_not()
        if self._needs_wide_window(plan, must_not, venues):
            # Python post-filters (tags, price, party, rating, hours) run after
            # fusion: fetch a wider window or the survivors may not fill
            # `limit`.
            candidates = plan.limit * max(self._candidate_multiplier, 3)
        if self._hybrid_mode == "lexical":
            # Operator escape hatch: Postgres tsvector only, no Qdrant.
            log.info("hybrid_mode=lexical, skipping the vector store")
            fused = await self._lexical_fallback(plan, pipeline, candidates,
                                                 venues)
            return await self._finish_fallback(fused, pipeline, plan, venues,
                                               stats=stats)
        lexical_query = self._lexical_query(plan)
        dense, sparse = await self._encode_query(plan.vector_query,
                                                 lexical_query)
        if plan.dense_only:
            sparse = None
        text_query = (lexical_query.strip()
                      if self._hybrid_mode == "bm25" else None) or None
        try:
            if dense is None and sparse is None and not text_query:
                raise ValueError("empty query")
            if text_query:
                try:
                    hits = await self._store_search(
                        dense, sparse, candidates, must or None,
                        must_not or None, text_query=text_query)
                except Exception as exc:  # noqa: BLE001 — missing BM25 index
                    log.warning("BM25 search failed, retrying dense+sparse: %s",
                                exc)
                    if dense is None and sparse is None:
                        raise
                    hits = await self._store_search(
                        dense, sparse, candidates, must or None,
                        must_not or None)
            else:
                hits = await self._store_search(dense, sparse, candidates,
                                                must or None, must_not or None)
            fused = [FusedHit(id=hit.id, score=hit.score, origins=[HYBRID_ORIGIN],
                              payload=dict(hit.payload)) for hit in hits]
        except Exception as exc:  # noqa: BLE001 — lexical fallback
            log.warning("qdrant hybrid failed, lexical fallback: %s", exc)
            fused = await self._lexical_fallback(plan, pipeline, candidates,
                                                 venues)
            return await self._finish_fallback(fused, pipeline, plan, venues,
                                               stats=stats)
        if not fused:
            # Empty vector index (fresh volume, embeddings not backfilled yet)
            # must not hide rows that the lexical half can still find.
            log.info("hybrid returned no hits, lexical fallback")
            fused = await self._lexical_fallback(plan, pipeline, candidates,
                                                 venues)
            return await self._finish_fallback(fused, pipeline, plan, venues,
                                               stats=stats)
        if plan.max_price_per_person is not None and not venues:
            prices = {hit.id: hit.payload.get("price_min") for hit in fused}
            pipeline.add(MaxPriceFilter(plan.max_price_per_person, prices))
        filtered = [hit for hit in fused if pipeline.matches(hit)]
        ranked = self._rank(filtered, venues=venues, party=plan.party_size,
                            include_undated=plan.include_undated)
        ranked = await self._rerank(plan, ranked)
        final = ranked[:plan.limit]
        self._record_stats(stats, results=len(final),
                           excluded=len(fused) - len(filtered), mode="hybrid")
        return final

    async def _store_search(self, dense, sparse, candidates, must, must_not,
                            *, text_query: str | None = None):
        """One store call; weights only travel when they are not uniform."""
        extra: dict = {}
        if text_query:
            extra["text_query"] = text_query
        if self._weighted:
            extra["weights"] = self._weights
        return await self._store.hybrid_search(dense, sparse, candidates,
                                               must, must_not, **extra)

    async def _rerank(self, plan: SearchPlan,
                      hits: list[FusedHit]) -> list[FusedHit]:
        if not self._rerank_enabled or not hits:
            return hits
        try:
            reranked = await self._reranker.rerank(plan.vector_query, hits)
        except Exception as exc:  # noqa: BLE001 — ranking must not 500
            log.warning("reranker failed, keeping the fused order: %s", exc)
            return hits
        return list(reranked) if reranked is not None else hits

    @staticmethod
    def _record_stats(stats: dict | None, *, results: int, excluded: int,
                      mode: str) -> None:
        if stats is not None:
            stats.update(results=results, excluded=excluded, mode=mode)

    @staticmethod
    def _needs_wide_window(plan: SearchPlan, must_not: dict,
                           venues: bool) -> bool:
        return bool(
            must_not
            or plan.exclude_tags
            or plan.exclude_amenities
            or plan.exclude_ids
            or plan.include_undated
            or plan.max_price_per_person is not None
            or (plan.party_size or 0) >= 1
            or plan.age_max is not None
            or plan.min_rating is not None
            # Venue opening hours are a Python filter on the requested window.
            or (venues and plan.date_from is not None)
        )

    def _rank(self, hits: list[FusedHit], *, venues: bool,
              party: int | None = None,
              include_undated: bool = False) -> list[FusedHit]:
        """Order by fused score; every boost is a near-zero tie-break.

        - rating: `search_rating_boost * (rating / 5)`, at most 0.002, well
          below an RRF score (~0.016–0.049); an unrated hit gets nothing.
        - group fit (venues, big party): `venue_group_boost` when the
          amenities intersect the configured group tags. No capacity math.
        - freshness (events): `search_freshness_boost * decay`, decay 1.0 for
          a start today and 0 at the horizon. Default boost 0.0 = no effect.
        - undated mode: posts without `start_at` keep their own order but
          always come after dated hits, so an announcement never outranks a
          confirmed performance.
        """
        key = "rating" if venues else "venue_rating"
        group = (venues and (party or 0) >= self._group_party_min
                 and self._group_boost > 0 and bool(self._group_amenities))

        def value(hit: FusedHit) -> float:
            total = hit.score
            rating = hit.payload.get(key)
            if rating is not None:
                try:
                    normalised = min(5.0, max(0.0, float(rating))) / 5.0
                    total += self._rating_boost * normalised
                except (TypeError, ValueError):
                    pass
            if group and _amenity_tags(hit.payload) & self._group_amenities:
                total += self._group_boost
            if not venues:
                total += self._freshness(hit.payload)
            return total

        if not include_undated:
            return sorted(hits, key=value, reverse=True)
        return sorted(hits,
                      key=lambda hit: (not bool(hit.payload.get("start_at")),
                                       -value(hit)))

    def _freshness(self, payload: Mapping) -> float:
        """Linear proximity decay over the configured horizon (0 = disabled)."""
        if self._freshness_boost <= 0 or self._freshness_horizon_days <= 0:
            return 0.0
        start = _parse_iso(payload.get("start_at"))
        if start is None:
            return 0.0
        remaining = (start - self._now()) / timedelta(days=1)
        if remaining <= 0 or remaining >= self._freshness_horizon_days:
            return 0.0
        decay = 1.0 - remaining / self._freshness_horizon_days
        return self._freshness_boost * decay

    async def _lexical_fallback(self, plan: SearchPlan, pipeline: FilterPipeline,
                                candidates: int, venues: bool) -> list[FusedHit]:
        params = pipeline.lexical_params()
        query = self._lexical_query(plan)
        if venues:
            rows = await self._collector.search_venues_lexical(
                query, params.get("city"), params.get("rubric"),
                candidates)
        else:
            rows = await self._collector.search_lexical(
                query, params.get("city"), params.get("categories"),
                candidates, date_from=params.get("date_from"),
                date_to=params.get("date_to"))
        lexical_by_id = {str(row["id"]): row for row in rows}
        fused = fuse_search([], list(lexical_by_id), candidates)
        for hit in fused:
            hit.payload.update({k: v for k, v in
                                lexical_by_id[hit.id].items() if v is not None})
        log.info("lexical fallback: query=%r venues=%s results=%d",
                 query[:120], venues, len(fused))
        return fused

    async def _finish_fallback(self, fused: list[FusedHit],
                               pipeline: FilterPipeline,
                               plan: SearchPlan, venues: bool, *,
                               stats: dict | None = None) -> list[FusedHit]:
        """Old path: backfill payload from lexical rows, then filter."""
        if plan.max_price_per_person is not None and not venues:
            prices = {hit.id: hit.payload.get("price_min") for hit in fused}
            pipeline.add(MaxPriceFilter(plan.max_price_per_person, prices))
        result = [hit for hit in fused if pipeline.matches(hit)]
        ranked = self._rank(result, venues=venues, party=plan.party_size,
                            include_undated=plan.include_undated)
        ranked = await self._rerank(plan, ranked)
        final = ranked[:plan.limit]
        self._record_stats(stats, results=len(final),
                           excluded=len(fused) - len(result), mode="lexical")
        return final
