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
from .sources.base import RunStats

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


@app.get("/actuator/health")
def health():
    return {"status": "UP"}


@app.get("/sources")
def sources():
    # Stage 1 registers: ticketpro, relax, afisha_me, telegram.
    return {"sources": []}


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
