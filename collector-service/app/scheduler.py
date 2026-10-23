"""Scheduled collection: interval jobs + advisory locks + alerting.

Manual POST /collect stays for debugging; the scheduler calls the same
adapters and records source_runs identically.
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager

import httpx

log = logging.getLogger(__name__)


@contextmanager
def advisory_lock(db_url: str, key: str):
    """Yields True when the lock was acquired, False when a run overlaps."""
    import psycopg
    with psycopg.connect(db_url) as conn:
        locked = conn.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", (key,)).fetchone()[0]
        try:
            yield bool(locked)
        finally:
            if locked:
                conn.execute("SELECT pg_advisory_unlock(hashtext(%s))", (key,))
                conn.commit()


def source_health(conn, window: int = 2) -> list[dict]:
    """Last `window` runs per source for /collect/health and alerting."""
    rows = conn.execute(
        """SELECT DISTINCT ON (source) source FROM source_runs ORDER BY source""",
    ).fetchall()
    health = []
    for row in rows:
        runs = conn.execute(
            """SELECT status, new_events, parse_errors, started_at, error
               FROM source_runs WHERE source = %s
               ORDER BY started_at DESC LIMIT %s""",
            (row["source"], window),
        ).fetchall()
        runs = [dict(run) for run in runs]
        degraded = (
            len(runs) == 0
            or any(run["status"] == "error" for run in runs)
            or (len(runs) == window and all(run["new_events"] == 0 for run in runs))
        )
        health.append({"source": row["source"], "runs": runs, "degraded": degraded})
    return health


def degraded_sources(health: list[dict]) -> list[str]:
    return [entry["source"] for entry in health if entry["degraded"]]


async def post_alert(webhook_url: str, degraded: list[str],
                     transport: httpx.BaseTransport | None = None) -> bool:
    if not webhook_url or not degraded:
        return False
    text = ("dosug collector degraded: "
            + ", ".join(sorted(degraded))
            + " (0 new events twice in a row or run errors)")
    try:
        async with httpx.AsyncClient(timeout=15.0, transport=transport) as client:
            response = await client.post(webhook_url, json={"text": text})
            response.raise_for_status()
        log.warning("ops alert sent: %s", text)
        return True
    except Exception as exc:  # noqa: BLE001 — alerting must not break collection
        log.warning("ops alert failed: %s", exc)
        return False


async def run_source_job(app, source: str) -> None:
    """One scheduled pass: collect -> embed catch-up -> alert check."""
    from . import db
    from .config import settings
    from .main import ADAPTERS, embed_pending, record_run
    from .sources.base import CollectContext, RunStats

    with advisory_lock(settings.database_url, f"collect:{source}") as locked:
        if not locked:
            log.warning("collect %s skipped: previous run still holds the lock", source)
            return
    adapter = ADAPTERS.get(source)
    if adapter is None:
        log.warning("no adapter for scheduled source %r", source)
        return
    started = time.monotonic()
    stats = RunStats()
    try:
        ctx = CollectContext(http=app.state.http, db_url=settings.database_url)
        stats = await adapter.collect(ctx)
        record_run(source, "ok", stats, None, started, time.monotonic() - started)
    except Exception as exc:  # noqa: BLE001 — recorded, then alert check
        record_run(source, "error", stats, str(exc), started, time.monotonic() - started)
        log.warning("scheduled collect %s failed: %s", source, exc)
    try:
        embedded, _ = await embed_pending(app, cap=2000)
        log.info("scheduled embed catch-up for %s: %d", source, embedded)
    except Exception as exc:  # noqa: BLE001
        log.warning("scheduled embed catch-up failed: %s", exc)
    try:
        with db.get_conn(settings.database_url) as conn:
            health = source_health(conn, settings.ops_alert_window)
        await post_alert(settings.ops_webhook_url, degraded_sources(health))
    except Exception as exc:  # noqa: BLE001
        log.warning("scheduled alert check failed: %s", exc)


def start_scheduler(app) -> None:
    """Attach AsyncIOScheduler to the app (call from lifespan)."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    from .config import settings

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
    scheduler.start()
    app.state.scheduler = scheduler


def stop_scheduler(app) -> None:
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is not None:
        scheduler.shutdown(wait=False)
