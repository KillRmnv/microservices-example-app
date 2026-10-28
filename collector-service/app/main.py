"""Collector service entrypoint: wiring only, no business logic."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routers import catalog, collect, embed, ops
from .core import db
from .core.config import settings
from .core.logging import RequestIdMiddleware, setup_logging
from .embeddings import LlamaServerEmbedding
from .errors.handlers import register_exception_handlers
from .http import PoliteClient
from .scheduler import start_scheduler, stop_scheduler
from .services.collect_service import CollectService
from .services.embed_service import EmbedService
from .services.ops_service import OpsService
from .vector import QdrantStore

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_url = settings.require_database_url()
    applied = db.run_migrations(db_url)
    if applied:
        log.info("applied migrations: %s", applied)
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
    app.state.http = http
    app.state.collect = CollectService(http, db_url)
    app.state.embed = EmbedService(db_url, embedder, vector, vector_venues,
                                   settings)
    app.state.ops = OpsService(db_url, settings)
    start_scheduler(app)
    try:
        yield
    finally:
        stop_scheduler(app)
        await http.aclose()


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
