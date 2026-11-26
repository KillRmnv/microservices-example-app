"""Assistant service configuration.

Every value is overridable through an ``ASSISTANT_*`` environment variable.
Secrets have no defaults: an empty value means "not configured" and the
service refuses to start when a required one is missing.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ASSISTANT_", case_sensitive=False, extra="ignore")

    app_name: str = "assistant-service"
    port: int = 8084

    # No default: credentials must come from the environment.
    database_url: str = ""
    # Direct Postgres URL for migrations (PgBouncer transaction mode is not
    # safe for the session advisory lock used by the migration runner).
    migration_database_url: str = ""

    collector_base_url: str = "http://collector-service:8080"
    booking_base_url: str = "http://booking-service:8082"

    # Domain defaults live here, never inside DTOs or business logic.
    default_city: str = "Минск"
    default_timezone: str = "Europe/Minsk"
    default_currency: str = "BYN"
    default_language: str = "ru"
    default_latitude: float = 53.9056
    default_longitude: float = 27.5539
    # A party is unknown until the user names it; one person is the neutral
    # assumption for deriving a per-person budget, not a guess about company.
    default_party_size: int = 1
    # Semantic query used for broad "что-нибудь" requests without a topic.
    default_search_query: str = "события"
    # Same for places: a venue search with no topic/rubric must not embed the
    # city name (it is an exact filter, not a theme).
    default_venue_query: str = "места"

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "events"
    qdrant_collection_venues: str = "venues"
    llama_embed_url: str = "http://localhost:8088"
    embedding_dim: int = 1024
    embedding_timeout_s: float = 120.0
    # Query-time embed budget: the sparse half must answer without the model.
    query_embedding_timeout_s: float = 2.0

    # Weather: Redis cache + retry policy.
    redis_url: str = "redis://localhost:6379/0"
    weather_base_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_attempts: int = 3
    weather_backoff_base_s: float = 0.5
    weather_timeout_s: float = 15.0
    weather_cache_ttl_s: int = 21600

    # LLM backends: "local" (llama.cpp server), "external" (OpenAI-compatible)
    # or "mock". Stages are mapped by name, e.g. "structure:local,plan:external".
    llm_local_base_url: str = "http://localhost:11434"
    llm_local_model: str = "qwen3:8b"
    llm_external_base_url: str = "https://api.openai.com/v1"
    llm_external_api_key: str = ""
    llm_external_model: str = "gpt-4o-mini"
    # OpenRouter: hosted OpenAI-compatible API used by the assistant stages.
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_key: str = ""
    openrouter_model: str = ""
    openrouter_referer: str = "http://localhost:3000"
    openrouter_title: str = "Dosug Assistant"
    llm_stages: str = "structure:mock,plan:mock,telegram:mock"
    llm_default_backend: str = "local"
    llm_fallback_enabled: bool = False
    # LFM/Qwen reasoning templates emit reasoning_content instead of the
    # answer unless thinking is disabled (json contracts need the answer).
    # Thinking defaults to ON (reasoning stages); the fast structure lane
    # forces it OFF explicitly.
    llm_disable_thinking: bool = False
    llm_max_tokens: int = 2048
    # Fast structure lane: no-think extraction, small budget, seconds.
    llm_structure_max_tokens: int = 512
    # The structure stage must never stall a chat turn: cap every provider
    # call, and stop hammering a dead model after a few failures.
    llm_structure_timeout_s: float = 20.0
    llm_breaker_failures: int = 3
    llm_breaker_cooldown_s: float = 60.0
    # Plan stage: reasoning can eat the whole budget before the JSON answer.
    llm_plan_max_tokens: int = 3072
    # Complexity heuristic: reasoning kicks in on long/multi-constraint
    # requests only.
    llm_complex_min_chars: int = 140
    llm_complex_min_signals: int = 2
    llm_temperature: float = 0.2
    llm_top_p: float = 0.95
    llm_top_k: int = 20
    llm_timeout_s: float = 300.0

    scheduler_enabled: bool = True
    sweep_interval_s: int = 300

    search_candidate_multiplier: int = 2
    # bm25 (dense+sparse+full-text, compose default) | sparse | lexical.
    # Code default stays `sparse` so unit tests never need the text index.
    hybrid_mode: str = "sparse"
    # Per-retriever RRF weights (dense:1,sparse:1,bm25:1 = plain RRF, fused
    # server-side). Unequal weights make the store fuse client-side.
    hybrid_weights: str = "dense:1,sparse:1,bm25:1"
    # Dense hits below this cosine score are noise ("jazz" -> random pop).
    search_dense_min_score: float = 0.45
    # Places are sparse and semantically broad; keep a lower relevance floor.
    search_venue_min_score: float = 0.30
    max_results: int = 5
    # Rating is a TIE-BREAK only: `score + boost * (rating / 5)` with a
    # near-zero epsilon, so the fused ranking still decides and an unrated
    # hit is never lifted above a scored one (no rating -> no boost).
    search_rating_boost: float = 0.002
    # Freshness is another near-zero tie-break for events: closer start_at
    # gets a larger share of the boost (1.0 today -> 0 at the horizon).
    # 0.0 keeps the fused order untouched.
    search_freshness_boost: float = 0.0
    search_freshness_horizon_days: int = 30
    # Optional reranker hook (no model wired in); off by default.
    rerank_enabled: bool = False
    # Group relevance for venues: no capacity math, only a better query and
    # a near-zero amenity tie-break at/above this party size.
    venue_group_party_min: int = 6
    venue_group_query_terms: str = (
        "большая компания, просторный зал, длинный стол, банкет")
    venue_group_amenities: str = "banquet,deposit,long_tables,kids_room"
    venue_group_boost: float = 0.002
    # Venue budget mapping when a venue has no `avg_check`: low/medium/high
    # are the 2GIS price tiers, rendered as an approximate per-person check.
    venue_price_levels: str = "low:25,medium:60,high:150"
    # A party at or above this many free seats is "available", below it
    # "few left" (mirrors the booking-service availability statuses).
    availability_few_left: int = 10
    # Scraped inventory (`seats_left`/`capacity`/`sold_out`) is only trusted
    # while the collector fetched it within this window; older or missing
    # `availability_at` counts as unknown and never hides a hit.
    availability_ttl_h: int = 48
    # Rain probability (%) from which terrace/outdoor options are excluded.
    weather_rain_probability_threshold: int = 60

    # Rate limiting for the LLM endpoints (Redis fixed window, fail-open).
    # Identity is the request's session_id (falling back to the client IP).
    rate_limit_enabled: bool = True
    rate_limit_query_per_min: int = 30
    rate_limit_plan_per_min: int = 10
    # booking-service availability answers change slowly; a short cache keeps
    # a chat turn from probing the same event once per card render.
    availability_cache_ttl_s: int = 30

    # OpenAPI/Swagger: disable in production (docs_enabled=false hides
    # /docs, /redoc and /openapi.json entirely).
    docs_enabled: bool = True

    # Structured logging: "json" for containers, "text" for local runs.
    log_format: str = "json"
    log_level: str = "INFO"

    def backend_for(self, stage: str) -> str:
        """Backend name for a pipeline stage; "ollama" is a legacy alias."""
        for chunk in self.llm_stages.split(","):
            name, _, backend = chunk.partition(":")
            if name.strip() == stage:
                return _normalize_backend(backend.strip() or self.llm_default_backend)
        return _normalize_backend(self.llm_default_backend)

    def require_database_url(self) -> str:
        if not self.database_url.strip():
            raise RuntimeError(
                "ASSISTANT_DATABASE_URL is not set; refusing to start without a database")
        return self.database_url

    def require_migration_database_url(self) -> str:
        return self.migration_database_url.strip() or self.require_database_url()

    def venue_price_level_map(self) -> dict[str, float]:
        """Parse ``low:25,medium:60,high:150`` into a price-level map."""
        parsed: dict[str, float] = {}
        for chunk in self.venue_price_levels.split(","):
            name, _, value = chunk.partition(":")
            name = name.strip().casefold()
            try:
                price = float(value.strip())
            except ValueError:
                continue
            if name and price > 0:
                parsed[name] = price
        return parsed

    def hybrid_weight_map(self) -> dict[str, float]:
        """Parse ``dense:1,sparse:1,bm25:1`` into per-retriever weights.

        Names outside dense/sparse/bm25 are ignored; a missing or malformed
        weight keeps the neutral 1.0, so a typo can never silence a retriever.
        """
        parsed = {"dense": 1.0, "sparse": 1.0, "bm25": 1.0}
        for chunk in self.hybrid_weights.split(","):
            name, _, value = chunk.partition(":")
            name = name.strip().casefold()
            if name not in parsed:
                continue
            try:
                weight = float(value.strip())
            except ValueError:
                continue
            if weight >= 0:
                parsed[name] = weight
        return parsed

    def venue_group_term_list(self) -> list[str]:
        """Comma-separated group phrases for the venue semantic query."""
        return [part.strip() for part in self.venue_group_query_terms.split(",")
                if part.strip()]

    def venue_group_amenity_list(self) -> list[str]:
        """Comma-separated amenity tags that suit a big company."""
        return [part.strip().casefold()
                for part in self.venue_group_amenities.split(",")
                if part.strip()]


def _normalize_backend(name: str) -> str:
    # "ollama" was the old name for the local llama.cpp server.
    return "local" if name in ("", "ollama") else name


settings = Settings()
