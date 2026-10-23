"""Service configuration. Env vars documented in .env.example."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASSISTANT_", case_sensitive=False)

    app_name: str = "assistant-service"
    port: int = 8084

    database_url: str = "postgresql://postgres:1234@localhost:5432/assistant_db"
    booking_base_url: str = "http://localhost:8082"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    llm_external_base_url: str = "https://api.openai.com/v1"
    llm_external_api_key: str = ""
    llm_external_model: str = "gpt-4o-mini"
    # "structure:ollama,plan:external,telegram:external"
    llm_stages: str = "structure:mock,plan:mock,telegram:mock"
    llm_timeout_s: float = 60.0

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "events"
    llama_embed_url: str = "http://localhost:8088"
    collector_base_url: str = "http://localhost:8085"

    def backend_for(self, stage: str) -> str:
        for chunk in self.llm_stages.split(","):
            name, _, backend = chunk.partition(":")
            if name.strip() == stage:
                return backend.strip() or "ollama"
        return "ollama"


settings = Settings()
