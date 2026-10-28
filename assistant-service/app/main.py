"""Assistant service entrypoint: wiring only, no business logic."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import deps
from .api.routers import dialogue, holds, ops, search
from .core import db
from .core.config import settings
from .core.logging import RequestIdMiddleware, setup_logging
from .errors.handlers import register_exception_handlers
from .scheduler import start_scheduler, stop_scheduler

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    applied = db.run_migrations(settings.require_database_url())
    if applied:
        log.info("applied migrations: %s", applied)
    get_components = deps.get_components()
    start_scheduler(app)
    try:
        yield
    finally:
        stop_scheduler(app)
        await get_components.cache.close()


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
    application.include_router(dialogue.router)
    application.include_router(search.router)
    application.include_router(holds.router)
    # Ops endpoints stay out of the public schema.
    application.include_router(ops.router, include_in_schema=False)
    return application


app = create_app()
