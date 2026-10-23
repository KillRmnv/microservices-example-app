"""Service configuration. Env vars documented in .env.example."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COLLECTOR_", case_sensitive=False)

    app_name: str = "collector-service"
    port: int = 8085

    database_url: str = "postgresql://postgres:1234@localhost:5432/collector_db"

    user_agent: str = "dosug-collector/0.1"
    default_min_interval_s: float = 1.0
    max_attempts: int = 4
    backoff_base_s: float = 2.0
    timeout_s: float = 20.0
    # "relax:10,afisha_me:10" — minimum seconds between requests per source.
    source_intervals: str = ""

    def min_interval_for(self, source: str) -> float:
        for chunk in self.source_intervals.split(","):
            if ":" not in chunk:
                continue
            name, _, value = chunk.partition(":")
            if name.strip() == source:
                try:
                    return float(value)
                except ValueError:
                    break
        return self.default_min_interval_s


settings = Settings()
