"""Rule-based dialogue turn: tools first, LLM only where rules give up.

Flow for search/update_filters (course.md scenario):
  current datetime -> weather -> resolve landmarks -> hybrid search
  (dense + lexical RRF) -> availability for booking-service events
  -> filters/weather/results messages.
Collected (scraped) events have no live inventory: availability unknown
+ source link. Booking-service events (integer ids) get a real check.
"""
from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel

from .contract import StateContract
from .hybrid import FusedHit
from .search import CollectorClient, SearchRequest, hybrid_search
from .tools import (
    Availability,
    BookingClient,
    get_current_datetime,
    get_weather_forecast,
    resolve_location,
)

log = logging.getLogger(__name__)

MessageKind = Literal["assistant", "filters", "results", "plan", "weather"]


class ResultCard(BaseModel):
    event_id: str
    title: str
    meta: str
    price: str
    source: str = ""


class ChatMessage(BaseModel):
    kind: MessageKind
    text: str
    results: list[ResultCard] | None = None
    weather: str | None = None


class DialogResponse(BaseModel):
    contract: StateContract
    messages: list[ChatMessage]


def _price_text(price_min, price_max) -> str:
    if price_min is None:
        return "цена уточняется"
    if price_max is not None and price_max != price_min:
        return f"{price_min:g}–{price_max:g} руб."
    return f"от {price_min:g} руб."


async def run_search_turn(contract: StateContract, *, embedder, store,
                          collector: CollectorClient, booking: BookingClient,
                          weather_transport=None) -> DialogResponse:
    messages: list[ChatMessage] = [
        ChatMessage(kind="filters", text="Условия поиска зафиксированы.")
    ]
    hard = contract.hard_filters
    # Weather on the requested date (advisory, never fatal).
    start = (hard.datetime.start if hard.datetime else None) or ""
    date_part = start[:10] if len(start) >= 10 else ""
    if date_part:
        geo = resolve_location(
            (hard.location.landmarks or [None])[0], hard.location.city)
        weather = await get_weather_forecast(
            date_part, geo["lat"], geo["lon"], transport=weather_transport)
        messages.append(ChatMessage(
            kind="weather",
            text=weather.advice_ru() if weather.available else "Прогноз недоступен.",
            weather=weather.advice_ru() if weather.available else None,
        ))
    # Hybrid search: vector_query carries atmosphere, filters stay out of it.
    vector_query = contract.semantic_payload.vector_query.strip()
    budget = hard.budget
    fused = await hybrid_search(
        embedder, store, collector,
        SearchRequest(
            vector_query=vector_query or _fallback_query(hard),
            city=hard.location.city or None,
            category=(hard.category or [None])[0],
            max_price_per_person=(budget.max_price_per_person if budget else None),
            limit=5,
        ),
    )
    if not fused:
        messages.append(ChatMessage(
            kind="assistant",
            text="По этим условиям ничего не нашлось. Смягчите фильтры или уточните дату."))
        return DialogResponse(contract=contract, messages=messages)
    # Availability for booking-service events (integer ids); scraped ones link out.
    cards: list[ResultCard] = []
    for hit in fused[:5]:
        availability = await _availability_for(hit, booking)
        cards.append(_to_card(hit, availability))
    messages.append(ChatMessage(
        kind="results", text="Вот что нашлось:", results=cards))
    return DialogResponse(contract=contract, messages=messages)


def _fallback_query(hard) -> str:
    parts = list(hard.category) + hard.amenities_required
    return " ".join(parts) if parts else "события и места"


async def _availability_for(hit: FusedHit, booking: BookingClient) -> Availability | None:
    try:
        event_id = int(hit.id)
    except (TypeError, ValueError):
        return None  # collected (scraped) event: no live inventory
    return await booking.check_availability(event_id)


def _to_card(hit: FusedHit, availability: Availability | None) -> ResultCard:
    title = hit.payload.get("title", "") or "Без названия"
    if availability is None:
        return ResultCard(event_id=hit.id, title=title,
                          meta="Внешняя афиша — наличие уточняйте у источника",
                          price="цена уточняется")
    status_ru = {"available": "места есть", "few_left": "осталось мало",
                 "sold_out": "распродано", "unknown": "наличие неизвестно"}
    return ResultCard(
        event_id=hit.id, title=title,
        meta=status_ru.get(availability.status, availability.status),
        price=_price_text(availability.min_price, None),
    )
