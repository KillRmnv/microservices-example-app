"""Collector service entrypoint: wiring only, no business logic."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from .api.routers import catalog, collect, embed, ops
from .clients.kafka import BookingCatalogConsumer
from .core import db
from .core.config import settings
from .core.logging import RequestIdMiddleware, setup_logging
from .clients.embeddings import LlamaServerEmbedding
from .errors.handlers import register_exception_handlers
from .clients.http import PoliteClient
from .repositories import queries
from .scheduler import start_scheduler, stop_scheduler
from .services.atmosphere_service import AtmosphereService
from .services.catalog_service import CatalogService
from .services.collect_service import CollectService
from .services.embed_service import EmbedService
from .services.film_metadata_service import FilmMetadataService
from .services.ops_service import OpsService
from .services.telegram_service import TelegramService
from .services.ticketpro_details_service import TicketproDetailsService
from .clients.vector import QdrantStore

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_url = settings.require_database_url()
    applied = db.run_migrations(settings.require_migration_database_url())
    if applied:
        log.info("applied migrations: %s", applied)
    with db.get_conn(db_url) as conn:
        linked = queries.link_event_venues(conn)
        if linked:
            log.info("linked %d events to 2GIS venues", linked)
    http = PoliteClient(
        user_agent=settings.user_agent,
        default_min_interval_s=settings.default_min_interval_s,
        max_attempts=settings.max_attempts,
        backoff_base_s=settings.backoff_base_s,
        timeout_s=settings.timeout_s,
        verify=settings.http_verify,
    )
    embedder = LlamaServerEmbedding(settings.llama_embed_url)
    vector = QdrantStore(settings.qdrant_url, settings.qdrant_collection)
    await vector.ensure(settings.qdrant_vector_size)
    vector_venues = QdrantStore(settings.qdrant_url,
                                settings.qdrant_collection_venues)
    await vector_venues.ensure(settings.qdrant_vector_size)
    app.state.db_url = db_url
    app.state.lock_db_url = settings.require_lock_database_url()
    app.state.http = http
    app.state.catalog = CatalogService(db_url)
    app.state.collect = CollectService(http, db_url)
    app.state.embed = EmbedService(db_url, embedder, vector, vector_venues,
                                   settings,
                                   lock_db_url=settings.require_lock_database_url())
    app.state.ops = OpsService(db_url, settings)
    app.state.atmosphere = AtmosphereService(db_url)
    app.state.ticketpro_details = TicketproDetailsService(http, db_url)
    app.state.telegram = TelegramService(http, db_url)
    app.state.film_metadata = FilmMetadataService(http, db_url)
    catalog_consumer = BookingCatalogConsumer(db_url, vector, settings)
    await catalog_consumer.start()
    start_scheduler(app)
    # Non-blocking: a payload-version mismatch triggers one hybrid reindex in
    # the background, so readiness never waits for Qdrant/Postgres scans.
    payload_sync = asyncio.create_task(app.state.embed.ensure_payload_version())
    payload_sync.add_done_callback(_log_payload_sync)
    try:
        yield
    finally:
        if not payload_sync.done():
            payload_sync.cancel()
            with suppress(asyncio.CancelledError):
                await payload_sync
        stop_scheduler(app)
        await catalog_consumer.stop()
        await http.aclose()
        db.close_pools()


def _log_payload_sync(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        log.warning("payload version check crashed: %s", error)
    else:
        log.info("payload version check: %s", task.result())


def create_app() -> FastAPI:
    setup_logging(settings.app_name, settings.log_level, settings.log_format)
    docs = settings.docs_enabled
    application = FastAPI(
        title=settings.app_name, lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    application.add_middleware(RequestIdMiddleware)
    register_exception_handlers(application)
    # Only the catalog reads stay in the public schema; collection,
    # embedding and ops endpoints are internal.
    application.include_router(catalog.router)
    application.include_router(collect.router, include_in_schema=False)
    application.include_router(embed.router, include_in_schema=False)
    application.include_router(ops.router, include_in_schema=False)
    return application


app = create_app()
