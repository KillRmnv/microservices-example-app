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

    collector_base_url: str = "http://collector-service:8080"
    booking_base_url: str = "http://booking-service:8082"

    # Domain defaults live here, never inside DTOs or business logic.
    default_city: str = "Минск"
    default_timezone: str = "Europe/Minsk"
    default_currency: str = "BYN"
    default_language: str = "ru"
    default_latitude: float = 53.9056
    default_longitude: float = 27.5539
    default_party_size: int = 2

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
    llm_stages: str = "structure:mock,plan:mock,telegram:mock"
    llm_default_backend: str = "local"
    llm_fallback_enabled: bool = False
    llm_timeout_s: float = 60.0

    scheduler_enabled: bool = True
    sweep_interval_s: int = 300

    search_candidate_multiplier: int = 2
    max_results: int = 5

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


def _normalize_backend(name: str) -> str:
    # "ollama" was the old name for the local llama.cpp server.
    return "local" if name in ("", "ollama") else name


settings = Settings()
