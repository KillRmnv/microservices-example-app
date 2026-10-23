"""Assistant service: leisure-planning dialogue (stage 0 skeleton).

POST /assistant/dialogue validates + sanitizes the client-owned
StateContract and applies the no-LLM rules (missing slots -> clarification).
Stages 2-3 plug in hybrid search, tool calling and booking here.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import db
from .config import settings
from .contract import StateContract, sanitize

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    applied = db.run_migrations(settings.database_url)
    if applied:
        log.info("applied migrations: %s", applied)
    yield


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
    started = time.monotonic()
    clean = sanitize(contract)
    result = apply_stage0_rules(clean)
    duration_ms = int((time.monotonic() - started) * 1000)
    record_run(result, duration_ms)
    return result
