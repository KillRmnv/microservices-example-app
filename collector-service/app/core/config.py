"""Service configuration. Env vars documented in .env.example."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COLLECTOR_", case_sensitive=False)

    app_name: str = "collector-service"
    port: int = 8085

    database_url: str = ""

    # Domain defaults (also used by normalization when a source omits them).
    default_city: str = "Минск"
    default_timezone: str = "Europe/Minsk"
    default_currency: str = "BYN"

    user_agent: str = "dosug-collector/0.1"
    default_min_interval_s: float = 1.0
    max_attempts: int = 4
    backoff_base_s: float = 2.0
    timeout_s: float = 20.0
    # "relax:10,afisha_me:10" — minimum seconds between requests per source.
    source_intervals: str = ""

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "events"
    qdrant_collection_venues: str = "venues"
    qdrant_vector_size: int = 1024  # bge-m3
    llama_embed_url: str = "http://localhost:8088"
    embed_batch_size: int = 32
    # Periodic embed catch-up for rows that arrive outside a collect run
    # (booking catalog, manual SQL). 0 disables the job.
    embed_catchup_interval_s: int = 600

    # Telegram: verify channels against the Mininform list before adding!
    telegram_channels: str = "minsk_kuda,kuda_shodit_by"
    telegram_max_pages: int = 5
    telegram_llm_fallback: bool = False

    # Scheduler (APScheduler, intervals in seconds: "source:seconds,...").
    scheduler_enabled: bool = True
    schedules: str = ("ticketpro:21600,relax:86400,afisha_me:86400,"
                      "telegram:1200")

    # Booking catalog stream (Kafka). Empty bootstrap disables the consumer.
    booking_catalog_enabled: bool = False
    kafka_bootstrap_servers: str = "kafka:9092"
    booking_catalog_topic: str = "booking.catalog"
    booking_catalog_group: str = "collector-catalog"
    # booking-service town names are English in the demo seed; map them onto
    # the default catalog city vocabulary (configurable, not hardcoded).
    booking_city_map: str = "Minsk:Минск,Grodno:Гродно,Brest:Брест"

    # Ops alerting: POST degraded sources here (ntfy/Slack/healthchecks).
    ops_webhook_url: str = ""
    ops_alert_window: int = 2
    http_verify: bool = True

    # 2GIS Places (demo key: 1000 req/month — quota guard stops at cap-reserve).
    twogis_api_key: str = ""
    twogis_base_url: str = "https://catalog.api.2gis.com"
    twogis_monthly_cap: int = 1000
    twogis_reserve: int = 100
    twogis_region: str = ""
    twogis_page_size: int = 10  # 2GIS 3.0/items allows max 10
    # 2GIS rejects unsupported locales with an empty item list, so keep this
    # empty to use the API default. Set only when the endpoint supports it.
    twogis_locale: str = ""
    # Sanity box for our catalog: south,north,west,east (swapped coords land
    # far outside it).
    twogis_bbox: str = "53.5,54.3,27.1,28.1"
    # Test set first; expand after the trial ("кафе,рестораны,бары,кинотеатры,
    # театры,музеи,клубы,выставки,караоке,парки,библиотеки,спортзалы,...").
    twogis_rubrics: str = "кафе,кинотеатры,театры,музеи"

    def city_alias(self, name: str) -> str:
        for chunk in self.booking_city_map.split(","):
            source, _, target = chunk.partition(":")
            if source.strip() == name.strip() and target.strip():
                return target.strip()
        return name

    def schedule_map(self) -> dict[str, int]:
        result = {}
        for chunk in self.schedules.split(","):
            name, _, seconds = chunk.partition(":")
            name, seconds = name.strip(), seconds.strip()
            if name and seconds.isdigit():
                result[name] = int(seconds)
        return result

    def require_database_url(self) -> str:
        if not self.database_url.strip():
            raise RuntimeError(
                "COLLECTOR_DATABASE_URL is not set; refusing to start without a database")
        return self.database_url

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

    # OpenAPI/Swagger: disable in production (docs_enabled=false hides
    # /docs, /redoc and /openapi.json entirely).
    docs_enabled: bool = True

    # Structured logging: "json" for containers, "text" for local runs.
    log_format: str = "json"
    log_level: str = "INFO"


settings = Settings()
