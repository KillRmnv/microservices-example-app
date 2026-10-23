"""Assistant service: leisure-planning dialogue (stage 0 skeleton).

POST /assistant/dialogue validates + sanitizes the client-owned
StateContract and applies the no-LLM rules (missing slots -> clarification).
Stages 2-3 plug in hybrid search, tool calling and booking here.
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
from .contract import StateContract, sanitize
from .dialogue import DialogResponse, run_search_turn
from .holds import confirm_hold as _confirm_hold
from .holds import create_hold as _create_hold
from .holds import expire_holds as _expire_holds
from .search import SearchHit, SearchRequest, build_search_components, hybrid_search
from .tools import BookingClient

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    applied = db.run_migrations(settings.database_url)
    if applied:
        log.info("applied migrations: %s", applied)
    if settings.scheduler_enabled:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        from .holds import expire_holds

        async def sweep_job() -> None:
            try:
                with db.get_conn(settings.database_url) as conn:
                    expired = expire_holds(conn)
                if expired:
                    log.info("sweep expired %d holds", expired)
            except Exception as exc:  # noqa: BLE001 — scheduler must survive
                log.warning("holds sweep failed: %s", exc)

        scheduler = AsyncIOScheduler()
        scheduler.add_job(sweep_job, IntervalTrigger(seconds=settings.sweep_interval_s),
                          id="holds-sweep", max_instances=1, coalesce=True,
                          next_run_time=None)
        scheduler.start()
        app.state.scheduler = scheduler
        log.info("scheduled holds sweep every %ss", settings.sweep_interval_s)
    yield
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get("/actuator/health")
def health():
    return {"status": "UP"}


def record_run(contract: StateContract, duration_ms: int) -> None:
    try:
        with db.get_conn(settings.database_url) as conn:
            conn.execute(
                """INSERT INTO dialogue_runs
                   (session_id, turn, action, needs_clarification, duration_ms)
                   VALUES (%s, %s, %s, %s, %s)""",
                (contract.context_state.session_id,
                 contract.context_state.turn_count,
                 contract.dialogue_action,
                 contract.needs_clarification,
                 duration_ms),
            )
            conn.commit()
    except Exception as exc:  # noqa: BLE001 — observability must not break dialogue
        log.warning("dialogue_runs insert failed: %s", exc)


def apply_stage0_rules(contract: StateContract) -> StateContract:
    """Deterministic rules that need no LLM (course.md §10-11)."""
    if contract.dialogue_action == "confirm_booking":
        contract.needs_clarification = True
        contract.clarification_prompt = (
            "Бронирование через ассистента появится на этапе 3. "
            "Пока оформите билет на странице события."
        )
        return contract
    if contract.dialogue_action in ("search", "update_filters"):
        dt = contract.hard_filters.datetime
        if dt is None or not dt.start:
            contract.dialogue_action = "ask_clarification"
            contract.needs_clarification = True
            hint = f" «{dt.raw_expression}»" if dt and dt.raw_expression else ""
            contract.clarification_prompt = (
                f"На какую дату и время ищем?{hint} "
                "Например: «в субботу вечером»."
            )
            return contract
    return contract


@app.post("/assistant/dialogue", response_model=StateContract)
def dialogue(contract: StateContract):
    # Legacy shape (kept for backward compat): contract only.
    started = time.monotonic()
    clean = sanitize(contract)
    result = apply_stage0_rules(clean)
    duration_ms = int((time.monotonic() - started) * 1000)
    record_run(result, duration_ms)
    return result


@app.post("/assistant/dialogue/v2", response_model=DialogResponse)
async def dialogue_v2(contract: StateContract):
    """Full turn: validation + tools + messages (stage 3)."""
    started = time.monotonic()
    clean = sanitize(contract)
    ruled = apply_stage0_rules(clean)
    if ruled.needs_clarification or ruled.dialogue_action not in ("search", "update_filters"):
        record_run(ruled, int((time.monotonic() - started) * 1000))
        return DialogResponse(contract=ruled, messages=[])
    embedder, store, collector = build_search_components()
    booking = BookingClient(settings.booking_base_url)
    response = await run_search_turn(ruled, embedder=embedder, store=store,
                                     collector=collector, booking=booking)
    record_run(response.contract, int((time.monotonic() - started) * 1000))
    return response


@app.post("/assistant/search", response_model=list[SearchHit])
async def search(req: SearchRequest):
    embedder, store, collector = build_search_components()
    fused = await hybrid_search(embedder, store, collector, req)
    return [SearchHit(event_id=hit.id, title=hit.payload.get("title", ""),
                      score=hit.score, origins=hit.origins) for hit in fused]


class HoldRequest(BaseModel):
    session_id: str
    event_id: int
    zone: str = "BASIC"
    price: float = 0.0
    party_size: int = 1


@app.post("/assistant/holds", status_code=201)
def create_hold_endpoint(req: HoldRequest):
    with db.get_conn(settings.database_url) as conn:
        hold = _create_hold(conn, req.session_id, req.event_id,
                            req.zone, req.price, req.party_size)
    return hold.__dict__


@app.post("/assistant/holds/{hold_id}/confirm")
def confirm_hold_endpoint(hold_id: str):
    with db.get_conn(settings.database_url) as conn:
        hold = _confirm_hold(conn, hold_id)
    if hold is None:
        raise HTTPException(status_code=410, detail="hold missing, taken or expired")
    return hold.__dict__


@app.post("/assistant/holds/sweep")
def sweep_holds_endpoint():
    with db.get_conn(settings.database_url) as conn:
        expired = _expire_holds(conn)
    return {"expired": expired}


@app.get("/metrics")
def metrics():
    """Prometheus text (scraped, see prometheus.yml)."""
    with db.get_conn(settings.database_url) as conn:
        text = assistant_metrics(conn)
    return PlainTextResponse(text)


def assistant_metrics(conn) -> str:
    dialogue = conn.execute(
        "SELECT action, count(*) FROM dialogue_runs GROUP BY action").fetchall()
    holds = conn.execute(
        "SELECT status, count(*) FROM booking_holds GROUP BY status").fetchall()
    lines = []
    for row in dialogue:
        lines.append(f'assistant_dialogue_runs_total{{action="{row["action"]}"}} {row["count"]}')
    for row in holds:
        lines.append(f'assistant_holds{{status="{row["status"]}"}} {row["count"]}')
    return "\n".join(lines) + "\n"
