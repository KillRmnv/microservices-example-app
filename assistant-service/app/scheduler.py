"""In-process scheduler for the hold expiry sweep."""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI

from .api.deps import get_components
from .core.config import settings

log = logging.getLogger(__name__)


async def sweep_job() -> None:
    try:
        expired = get_components().holds.sweep()
        if expired:
            log.info("sweep expired %d holds", expired)
    except Exception as exc:  # noqa: BLE001 — scheduler must survive
        log.warning("holds sweep failed: %s", exc)


def start_scheduler(app: FastAPI) -> None:
    if not settings.scheduler_enabled:
        log.info("scheduler disabled")
        return
    scheduler = AsyncIOScheduler()
    scheduler.add_job(sweep_job, IntervalTrigger(seconds=settings.sweep_interval_s),
                      id="holds-sweep", max_instances=1, coalesce=True,
                      next_run_time=None)
    scheduler.start()
    app.state.scheduler = scheduler
    log.info("scheduled holds sweep every %ss", settings.sweep_interval_s)


def stop_scheduler(app: FastAPI) -> None:
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is not None:
        scheduler.shutdown(wait=False)
