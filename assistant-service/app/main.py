"""Assistant service entrypoint: wiring only, no business logic."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import deps
from .api.routers import dialogue, holds, ops, search
from .core import db
from .core.config import settings
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
    application = FastAPI(title=settings.app_name, lifespan=lifespan)
    register_exception_handlers(application)
    application.include_router(dialogue.router)
    application.include_router(search.router)
    application.include_router(holds.router)
    application.include_router(ops.router)
    return application


app = create_app()
