"""Collector service: playbill ingestion (stage 0 skeleton).

Stage 1 adds real source adapters (ticketpro/relax/afisha_me/telegram).
Until then POST /collect/probe exercises the fetch + source_runs path.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from . import db
from .config import settings
from .embeddings import LlamaServerEmbedding, embeddable_text
from .http import PoliteClient
from .scheduler import degraded_sources, post_alert, source_health
from .sources.afisha_me import AfishaMeAdapter
from .sources.base import CollectContext, RunStats, SourceAdapter
from .sources.relax import RelaxAdapter
from .sources.telegram import TelegramAdapter
from .sources.ticketpro import TicketproAdapter
from .sources.twogis_places import TwogisPlacesAdapter
from .vector import QdrantStore, VectorPoint

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    applied = db.run_migrations(settings.require_database_url())
    if applied:
        log.info("applied migrations: %s", applied)
    app.state.http = PoliteClient(
        user_agent=settings.user_agent,
        default_min_interval_s=settings.default_min_interval_s,
        max_attempts=settings.max_attempts,
        backoff_base_s=settings.backoff_base_s,
        timeout_s=settings.timeout_s,
        verify=settings.http_verify,
    )
    app.state.embedder = LlamaServerEmbedding(settings.llama_embed_url)
    app.state.vector = QdrantStore(settings.qdrant_url, settings.qdrant_collection)
    await app.state.vector.ensure(settings.qdrant_vector_size)
    app.state.vector_venues = QdrantStore(settings.qdrant_url,
                                          settings.qdrant_collection_venues)
    await app.state.vector_venues.ensure(settings.qdrant_vector_size)
    from .scheduler import start_scheduler, stop_scheduler
    start_scheduler(app)
    yield
    stop_scheduler(app)
    await app.state.http.aclose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)


ADAPTERS: dict[str, SourceAdapter] = {
    TicketproAdapter.name: TicketproAdapter(),
    RelaxAdapter.name: RelaxAdapter(),
    AfishaMeAdapter.name: AfishaMeAdapter(),
    TelegramAdapter.name: TelegramAdapter(),
    TwogisPlacesAdapter.name: TwogisPlacesAdapter(),
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


@app.get("/events/search")
def events_search(q: str, city: str | None = None, category: str | None = None,
                  limit: int = 20):
    """Lexical half of hybrid search: russian tsvector rank + filters."""
    limit = max(1, min(100, limit))
    query = ("""SELECT id, source, source_url, title, category, start_at,
                       venue_name, city, price_min, price_max,
                       ts_rank_cd(search_vector, plainto_tsquery('russian', %s)) AS rank
                FROM collected_events
                WHERE search_vector @@ plainto_tsquery('russian', %s)
                AND (%s::TEXT IS NULL OR city = %s)
                AND (%s::TEXT IS NULL OR category = %s)
                ORDER BY rank DESC LIMIT %s""")
    with db.get_conn(settings.database_url) as conn:
        rows = conn.execute(query, (q, q, city, city, category, category, limit)).fetchall()
    return {"events": [dict(row) for row in rows]}


@app.post("/embed/{source}")
async def embed_source(source: str, limit: int | None = None):
    """Backfill Qdrant vectors for collected events (stage 2)."""
    if source != "all" and source not in ADAPTERS and source != "telegram":
        raise HTTPException(status_code=404, detail=f"unknown source: {source}")
    started = time.monotonic()
    embedded, pending = await embed_pending(app, source, limit)
    duration = time.monotonic() - started
    return {"source": source, "embedded": embedded,
            "pending": pending, "duration_s": round(duration, 1)}


async def embed_pending(app, source: str = "all", limit: int | None = None,
                        cap: int | None = None) -> tuple[int, int]:
    """Embed unembedded rows in batches; shared by endpoint and scheduler."""
    from .config import settings as collector_settings
    embedded = 0
    with db.get_conn(collector_settings.database_url) as conn:
        params: list = []
        query = ("SELECT id, title, venue_name, description, city, category,"
                 " start_at FROM collected_events WHERE embedded_at IS NULL")
        if source != "all":
            query += " AND source = %s"
            params.append(source)
        query += " ORDER BY fetched_at"
        fetch_limit = limit
        if cap is not None:
            fetch_limit = min(limit or cap, cap)
        if fetch_limit:
            query += " LIMIT %s"
            params.append(max(1, fetch_limit))
        rows = conn.execute(query, params).fetchall()
        batch_size = collector_settings.embed_batch_size
        for offset in range(0, len(rows), batch_size):
            batch = rows[offset:offset + batch_size]
            texts = [embeddable_text(row["title"], row["venue_name"],
                                     row["description"]) for row in batch]
            try:
                vectors = await app.state.embedder.embed(texts)
                await app.state.vector.upsert([
                    VectorPoint(
                        id=str(row["id"]),
                        vector=vector,
                        payload={"title": row["title"], "city": row["city"],
                                 "category": row["category"],
                                 "venue": row["venue_name"] or "",
                                 "start_at": row["start_at"].isoformat()
                                 if row["start_at"] else ""},
                    )
                    for row, vector in zip(batch, vectors)
                ])
            except Exception as exc:  # noqa: BLE001 — keep already stored batches
                log.warning("embed batch failed: %s", exc)
                break
            conn.execute(
                "UPDATE collected_events SET embedded_at = now() WHERE id = ANY(%s)",
                ([row["id"] for row in batch],),
            )
            conn.commit()
            embedded += len(batch)
    return embedded, len(rows) - embedded


@app.get("/venues/search")
def venues_search(q: str, city: str | None = None, rubric: str | None = None,
                  limit: int = 20):
    """Lexical half of venue hybrid search."""
    limit = max(1, min(100, limit))
    query = ("""SELECT id, source, name, rubric, address, city, lat, lon,
                       rating, review_count,
                       ts_rank_cd(search_vector, plainto_tsquery('russian', %s)) AS rank
                FROM collected_venues
                WHERE search_vector @@ plainto_tsquery('russian', %s)
                AND (%s::TEXT IS NULL OR city = %s)
                AND (%s::TEXT IS NULL OR rubric = %s)
                ORDER BY rank DESC LIMIT %s""")
    with db.get_conn(settings.database_url) as conn:
        rows = conn.execute(query, (q, q, city, city, rubric, rubric, limit)).fetchall()
    return {"venues": [dict(row) for row in rows]}


@app.post("/embed/venues")
async def embed_venues(limit: int | None = None):
    """Backfill Qdrant `venues` collection (2GIS catalog)."""
    started = time.monotonic()
    embedded = 0
    with db.get_conn(settings.database_url) as conn:
        query = ("SELECT id, name, rubric, address, city FROM collected_venues"
                 " WHERE embedded_at IS NULL ORDER BY fetched_at")
        params: list = []
        if limit:
            query += " LIMIT %s"
            params.append(max(1, limit))
        rows = conn.execute(query, params).fetchall()
        batch_size = settings.embed_batch_size
        for offset in range(0, len(rows), batch_size):
            batch = rows[offset:offset + batch_size]
            texts = ["\n".join(part for part in
                               [row["name"], row["rubric"], row["address"]]
                               if part) for row in batch]
            try:
                vectors = await app.state.embedder.embed(texts)
                await app.state.vector_venues.upsert([
                    VectorPoint(
                        id=str(row["id"]),
                        vector=vector,
                        payload={"name": row["name"], "city": row["city"],
                                 "rubric": row["rubric"] or "",
                                 "address": row["address"] or ""},
                    )
                    for row, vector in zip(batch, vectors)
                ])
            except Exception as exc:  # noqa: BLE001 — keep already stored batches
                log.warning("venues embed batch failed: %s", exc)
                break
            conn.execute(
                "UPDATE collected_venues SET embedded_at = now() WHERE id = ANY(%s)",
                ([row["id"] for row in batch],),
            )
            conn.commit()
            embedded += len(batch)
    duration = time.monotonic() - started
    return {"embedded": embedded, "pending": len(rows) - embedded,
            "duration_s": round(duration, 1)}


@app.get("/collect/health")
def collect_health():
    """Per-source freshness for alerting (stage 5): degraded when the last
    `ops_alert_window` runs brought 0 new events or any run errored."""
    with db.get_conn(settings.database_url) as conn:
        health = source_health(conn, settings.ops_alert_window)
    return {"sources": health, "degraded": degraded_sources(health)}


@app.post("/collect/alert-check")
async def alert_check():
    """Evaluate health now and POST the degraded list to the webhook."""
    with db.get_conn(settings.database_url) as conn:
        health = source_health(conn, settings.ops_alert_window)
    degraded = degraded_sources(health)
    sent = await post_alert(settings.ops_webhook_url, degraded)
    return {"degraded": degraded, "alert_sent": sent}


@app.get("/metrics")
def metrics():
    """Prometheus text (scraped, see prometheus.yml)."""
    with db.get_conn(settings.database_url) as conn:
        text = collect_metrics(conn)
    return PlainTextResponse(text)


def collect_metrics(conn) -> str:
    totals = conn.execute(
        "SELECT source, count(*) FROM collected_events GROUP BY source").fetchall()
    runs = conn.execute(
        "SELECT source, status, count(*) FROM source_runs GROUP BY source, status"
    ).fetchall()
    errors = conn.execute(
        "SELECT source, sum(parse_errors) FROM source_runs GROUP BY source").fetchall()
    last = conn.execute(
        "SELECT source, extract(epoch FROM max(started_at)) AS ts"
        " FROM source_runs GROUP BY source").fetchall()
    lines = []
    for row in totals:
        lines.append(f'collector_events_total{{source="{row["source"]}"}} {row["count"]}')
    for row in runs:
        lines.append(f'collector_runs_total{{source="{row["source"]}",status="{row["status"]}"}} {row["count"]}')
    for row in errors:
        lines.append(f'collector_parse_errors_total{{source="{row["source"]}"}} {row["sum"] or 0}')
    for row in last:
        lines.append(f'collector_last_run_unixtime{{source="{row["source"]}"}} {int(row["ts"] or 0)}')
    return "\n".join(lines) + "\n"


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
