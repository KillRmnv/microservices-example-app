"""Dialogue DTOs (response shape consumed by the frontend)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .contract import StateContract

MessageKind = Literal["assistant", "filters", "results", "plan", "weather"]


class ResultCard(BaseModel):
    event_id: str
    kind: Literal["event", "venue"] = "event"
    # Catalog UUID: the id of the event/place page, distinct from the numeric
    # booking id (which is what "Выбрать" needs).
    detail_id: str = ""
    title: str
    meta: str
    price: str
    source: str = ""
    start_at: str = ""
    end_at: str = ""
    # Structured extras (added for party/rating/hours aware cards); `meta`
    # stays the human-readable fallback so older clients keep working.
    rating: float | None = None
    review_count: int | None = None
    address: str = ""
    hours: str = ""
    seats_left: int | None = None
    fits_party: bool | None = None
    status: str = ""
    # Film-only extras (optional: scraped cinema rows may omit them, and
    # older sources never send them). `meta` stays the short human fallback.
    next_session_at: str = ""
    cinema: str = ""
    film_genre: list[str] | None = None
    film_duration_min: int | None = None


class PlanStep(BaseModel):
    time: str = "—"
    title: str = ""
    detail: str = ""
    source: str = "assistant"
    kind: Literal["event", "venue"] = "event"
    detail_id: str = ""
    event_id: str = ""
    bookable: bool = False


class ChatMessage(BaseModel):
    kind: MessageKind
    text: str
    results: list[ResultCard] | None = None
    weather: str | None = None
    plan: list[PlanStep] | None = None


class DialogResponse(BaseModel):
    contract: StateContract
    messages: list[ChatMessage]
