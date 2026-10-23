"""Collector service: playbill ingestion (stage 0 skeleton).

Stage 1 adds real source adapters (ticketpro/relax/afisha_me/telegram).
Until then POST /collect/probe exercises the fetch + source_runs path.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import db
from .config import settings
from .http import PoliteClient
from .sources.afisha_me import AfishaMeAdapter
from .sources.base import CollectContext, RunStats, SourceAdapter
from .sources.relax import RelaxAdapter
from .sources.ticketpro import TicketproAdapter

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    applied = db.run_migrations(settings.database_url)
    if applied:
        log.info("applied migrations: %s", applied)
    app.state.http = PoliteClient(
        user_agent=settings.user_agent,
        default_min_interval_s=settings.default_min_interval_s,
        max_attempts=settings.max_attempts,
        backoff_base_s=settings.backoff_base_s,
        timeout_s=settings.timeout_s,
    )
    yield
    await app.state.http.aclose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)


ADAPTERS: dict[str, SourceAdapter] = {
    TicketproAdapter.name: TicketproAdapter(),
    RelaxAdapter.name: RelaxAdapter(),
    AfishaMeAdapter.name: AfishaMeAdapter(),
}


@app.get("/actuator/health")
def health():
    return {"status": "UP"}


@app.get("/sources")
def sources():
    return {"sources": sorted(ADAPTERS)}


@app.post("/collect/{source}")
async def collect_source(source: str, limit: int | None = None):
    """Run one adapter end-to-end and record the source_runs row."""
    adapter = ADAPTERS.get(source)
    if adapter is None:
        raise HTTPException(status_code=404, detail=f"unknown source: {source}")
    started = time.monotonic()
    stats = RunStats()
    try:
        ctx = CollectContext(http=app.state.http, db_url=settings.database_url,
                             max_urls=limit)
        stats = await adapter.collect(ctx)
        record_run(source, "ok", stats, None, started, time.monotonic() - started)
        return {"source": source, "status": "ok", **stats.__dict__}
    except Exception as exc:  # noqa: BLE001 — must be recorded, not crash
        record_run(source, "error", stats, str(exc), started, time.monotonic() - started)
        raise HTTPException(status_code=502, detail=f"collect failed: {exc}") from exc


@app.get("/events")
def events(source: str | None = None, city: str | None = None, limit: int = 50):
    """Read model for the collected catalog (used by assistant at stage 3)."""
    limit = max(1, min(500, limit))
    query = ("SELECT id, source, source_url, title, category, start_at, end_at,"
             " venue_name, address, city, price_min, price_max, currency"
             " FROM collected_events WHERE (%s::TEXT IS NULL OR source = %s)"
             " AND (%s::TEXT IS NULL OR city = %s)"
             " ORDER BY start_at NULLS LAST LIMIT %s")
    with db.get_conn(settings.database_url) as conn:
        rows = conn.execute(query, (source, source, city, city, limit)).fetchall()
    return {"events": [dict(row) for row in rows]}


def record_run(source: str, status: str, stats: RunStats, error: str | None,
               started: float, duration: float) -> None:
    with db.get_conn(settings.database_url) as conn:
        conn.execute(
            """INSERT INTO source_runs
               (source, status, started_at, finished_at, duration_s,
                fetched, parsed, parse_errors, duplicates, new_events, error)
               VALUES (%s, %s, now() - make_interval(secs => %s), now(), %s,
                       %s, %s, %s, %s, %s, %s)""",
            (source, status, duration, duration,
             stats.fetched, stats.parsed, stats.parse_errors,
             stats.duplicates, stats.new_events, error),
        )
        conn.commit()


class ProbeRequest(BaseModel):
    source: str = "probe"
    url: str


@app.post("/collect/probe")
async def collect_probe(req: ProbeRequest):
    """Fetch one URL politely and record a source_run. Smoke-test for stage 0."""
    started = time.monotonic()
    stats = RunStats()
    try:
        response = await app.state.http.get(req.source, str(req.url))
        stats.fetched = 1
        stats.parsed = 1 if response.status_code == 200 else 0
        record_run(req.source, "ok", stats, None, started, time.monotonic() - started)
        return {
            "source": req.source,
            "status_code": response.status_code,
            "bytes": len(response.content),
            "final_url": str(response.url),
        }
    except Exception as exc:  # noqa: BLE001 — must be recorded, not crash
        stats.parse_errors = 1
        record_run(req.source, "error", stats, str(exc), started, time.monotonic() - started)
        raise HTTPException(status_code=502, detail=f"fetch failed: {exc}") from exc
