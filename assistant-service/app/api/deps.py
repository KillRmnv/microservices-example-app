"""Composition root: builds clients/services once per process.

Routers never construct HTTP clients or repositories themselves; they take
ready services from here. This keeps controllers thin and testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..clients.booking import BookingClient
from ..clients.cache import WeatherCache, build_weather_cache
from ..clients.collector import CollectorClient
from ..clients.embeddings import LlamaServerEmbedding
from ..clients.vector import QdrantStore
from ..clients.llm.registry import provider_for
from ..clients.weather import OpenMeteoClient
from ..core.config import Settings, settings
from ..services.dialogue_service import DialogueService
from ..services.hold_service import HoldService
from ..services.metrics_service import MetricsService
from ..services.plan_service import PlanService
from ..services.query_structure import QueryStructureService
from ..services.search_service import SearchService
from ..services.weather_service import WeatherService


@dataclass
class Components:
    dialogue: DialogueService
    search_events: SearchService
    search_venues: SearchService
    structure: QueryStructureService
    plan: PlanService
    holds: HoldService
    metrics: MetricsService
    cache: WeatherCache


def _embedder(config: Settings) -> LlamaServerEmbedding:
    return LlamaServerEmbedding(config.llama_embed_url, dim=config.embedding_dim,
                                timeout_s=config.embedding_timeout_s)


def _search_service(config: Settings, *, venues: bool) -> SearchService:
    collection = (config.qdrant_collection_venues if venues
                  else config.qdrant_collection)
    return SearchService(
        _embedder(config),
        QdrantStore(config.qdrant_url, collection,
                    dense_min_score=(config.search_venue_min_score if venues
                                     else config.search_dense_min_score)),
        CollectorClient(config.collector_base_url),
        candidate_multiplier=config.search_candidate_multiplier,
        query_timeout_s=config.query_embedding_timeout_s,
    )


def build_components(config: Settings | None = None) -> Components:
    config = config or settings
    booking = BookingClient(config.booking_base_url)
    cache = build_weather_cache(config.redis_url)
    weather = WeatherService(
        OpenMeteoClient(config.weather_base_url, config.default_timezone,
                        attempts=config.weather_attempts,
                        backoff_base_s=config.weather_backoff_base_s,
                        timeout_s=config.weather_timeout_s),
        cache,
        ttl_s=config.weather_cache_ttl_s,
        timezone=config.default_timezone,
    )
    search_events = _search_service(config, venues=False)
    search_venues = _search_service(config, venues=True)
    dialogue = DialogueService(search=search_events, search_venues=search_venues,
                               weather=weather,
                               booking=booking, db_url=config.database_url,
                               settings=config)
    return Components(
        dialogue=dialogue,
        search_events=search_events,
        search_venues=search_venues,
        structure=QueryStructureService(
            provider_for("structure", config, thinking=False), config,
            max_tokens=config.llm_structure_max_tokens,
            reasoning_provider=provider_for("structure", config,
                                            thinking=True)),
        plan=PlanService(provider_for("plan", config), dialogue, config,
                         fallback_provider=provider_for("plan", config,
                                                        thinking=False)),
        holds=HoldService(config.database_url, booking),
        metrics=MetricsService(config.database_url),
        cache=cache,
    )


@lru_cache(maxsize=1)
def get_components() -> Components:
    return build_components()


async def close_components() -> None:
    components = get_components()
    await components.cache.close()
    get_components.cache_clear()
