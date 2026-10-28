"""Scheduled collection: interval jobs + advisory locks + alerting.

Manual POST /collect stays for debugging; the scheduler calls the same
services and records source_runs identically.
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager

import httpx
import psycopg
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI

from .core.config import settings
from .services.collect_service import CollectService
from .services.embed_service import EmbedService
from .services.ops_service import OpsService
from .sources.base import RunStats

log = logging.getLogger(__name__)

EMBED_CATCHUP_CAP = 2000


@contextmanager
def advisory_lock(db_url: str, key: str):
    """Yields True when the lock was acquired, False when a run overlaps."""
    with psycopg.connect(db_url) as conn:
        locked = conn.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", (key,)).fetchone()[0]
        try:
            yield bool(locked)
        finally:
            if locked:
                conn.execute("SELECT pg_advisory_unlock(hashtext(%s))", (key,))
                conn.commit()


async def run_source_job(app: FastAPI, source: str) -> None:
    """One scheduled pass: collect -> embed catch-up -> alert check."""
    collect: CollectService = app.state.collect
    embed: EmbedService = app.state.embed
    ops: OpsService = app.state.ops
    with advisory_lock(app.state.db_url, f"collect:{source}") as locked:
        if not locked:
            log.warning("collect %s skipped: previous run still holds the lock",
                        source)
            collect.record_run(source, "skipped", RunStats(), None, 0.0)
            return
        try:
            await collect.collect(source)
        except Exception as exc:  # noqa: BLE001 — already recorded; keep going
            log.warning("scheduled collect %s failed: %s", source, exc)
    try:
        embedded, _ = await embed.embed_events(cap=EMBED_CATCHUP_CAP)
        log.info("scheduled embed catch-up for %s: %d", source, embedded)
    except Exception as exc:  # noqa: BLE001
        log.warning("scheduled embed catch-up failed: %s", exc)
    try:
        await ops.alert_check()
    except Exception as exc:  # noqa: BLE001
        log.warning("scheduled alert check failed: %s", exc)


async def embed_catchup_job(app: FastAPI) -> None:
    """Embed rows that arrived outside a collect run (booking catalog)."""
    embed: EmbedService = app.state.embed
    with advisory_lock(app.state.db_url, "embed:catchup") as locked:
        if not locked:
            return
        try:
            embedded, _ = await embed.embed_events(cap=EMBED_CATCHUP_CAP)
            if embedded:
                log.info("periodic embed catch-up: %d", embedded)
        except Exception as exc:  # noqa: BLE001
            log.warning("periodic embed catch-up failed: %s", exc)


def start_scheduler(app: FastAPI) -> None:
    if not settings.scheduler_enabled:
        log.info("scheduler disabled")
        return
    scheduler = AsyncIOScheduler()
    for source, seconds in settings.schedule_map().items():
        scheduler.add_job(
            run_source_job, IntervalTrigger(seconds=seconds), args=[app, source],
            id=f"collect-{source}", max_instances=1, coalesce=True,
            next_run_time=None,  # first run after one full interval, not at boot
        )
        log.info("scheduled collect %s every %ss", source, seconds)
    if settings.embed_catchup_interval_s > 0:
        scheduler.add_job(
            embed_catchup_job,
            IntervalTrigger(seconds=settings.embed_catchup_interval_s),
            args=[app], id="embed-catchup", max_instances=1, coalesce=True,
            next_run_time=None,
        )
        log.info("embed catch-up every %ss", settings.embed_catchup_interval_s)
    scheduler.start()
    app.state.scheduler = scheduler


def stop_scheduler(app: FastAPI) -> None:
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is not None:
        scheduler.shutdown(wait=False)
