"""Dialogue use case: rules first, tools next, LLM only where rules give up.

Flow for search/update_filters:
  sanitize -> rules -> weather (Redis-cached) -> hybrid search
  -> availability for booking-service events -> filters/weather/results.
Collected (scraped) events have no live inventory: availability is unknown
and the card links out. Booking-service event ids get a real check.
"""
from __future__ import annotations

import asyncio
import logging
import time

from ..api.schemas.contract import StateContract
from ..api.schemas.dialogue import ChatMessage, DialogResponse, ResultCard
from ..clients.booking import BookingClient
from ..core import db, i18n
from ..core.config import Settings, settings as default_settings
from ..core.dates import parse_iso_date
from ..core.geo import resolve_location
from ..models.availability import AVAILABLE, FEW_LEFT, SOLD_OUT, UNKNOWN, Availability
from ..models.search import FusedHit, SearchPlan
from ..repositories import dialogue_runs
from .search_service import SearchService
from .weather_service import WeatherService

log = logging.getLogger(__name__)

SEARCH_ACTIONS = ("search", "update_filters")
STATUS_KEYS = {
    AVAILABLE: "availability_available",
    FEW_LEFT: "availability_few_left",
    SOLD_OUT: "availability_sold_out",
    UNKNOWN: "availability_unknown",
}


class DialogueService:
    def __init__(self, *, search: SearchService, weather: WeatherService,
                 booking: BookingClient, db_url: str,
                 settings: Settings = default_settings) -> None:
        self._search = search
        self._weather = weather
        self._booking = booking
        self._db_url = db_url
        self._settings = settings

    def apply_rules(self, contract: StateContract,
                    language: str | None = None) -> StateContract:
        """Deterministic rules that need no LLM."""
        if contract.dialogue_action == "confirm_booking":
            contract.needs_clarification = True
            contract.clarification_prompt = i18n.t("clarify_booking", language)
            return contract
        if contract.dialogue_action in SEARCH_ACTIONS:
            date_filter = contract.hard_filters.datetime
            if date_filter is None or not date_filter.start:
                contract.dialogue_action = "ask_clarification"
                contract.needs_clarification = True
                hint = (f" «{date_filter.raw_expression}»"
                        if date_filter and date_filter.raw_expression else "")
                contract.clarification_prompt = i18n.t(
                    "clarify_date", language, hint=hint)
        return contract

    def record_run(self, contract: StateContract, duration_ms: int) -> None:
        try:
            with db.get_conn(self._db_url) as conn:
                dialogue_runs.record_run(conn, contract, duration_ms)
        except Exception as exc:  # noqa: BLE001 — metrics must not break dialogue
            log.warning("dialogue_runs insert failed: %s", exc)

    def elapsed_ms(self, started: float) -> int:
        return int((time.monotonic() - started) * 1000)

    async def search_turn(self, contract: StateContract) -> DialogResponse:
        language = i18n.resolve_locale(contract.semantic_payload.language)
        messages: list[ChatMessage] = [
            ChatMessage(kind="filters", text=i18n.t("filters_locked", language))
        ]
        hard = contract.hard_filters
        date_value = hard.datetime.start if hard.datetime else None
        day = parse_iso_date(date_value)
        if day is not None:
            messages.append(await self._weather_message(contract, day, language))
        plan = self._search_plan(contract)
        fused = await self._search.events(plan)
        if not fused:
            messages.append(ChatMessage(
                kind="assistant", text=i18n.t("search_empty", language)))
            return DialogResponse(contract=contract, messages=messages)
        cards = await self._cards(fused, language)
        messages.append(ChatMessage(
            kind="results", text=i18n.t("search_results", language), results=cards))
        return DialogResponse(contract=contract, messages=messages)

    async def _weather_message(self, contract: StateContract, day,
                               language: str) -> ChatMessage:
        hard = contract.hard_filters
        city = hard.location.city or self._settings.default_city
        center = (self._settings.default_latitude, self._settings.default_longitude)
        landmark = (hard.location.landmarks or [None])[0]
        geo = resolve_location(landmark, city, center, language)
        weather = await self._weather.forecast(day.isoformat(),
                                               geo["lat"], geo["lon"])
        text = weather.advice(language)
        return ChatMessage(kind="weather", text=text,
                           weather=text if weather.available else None)

    def _search_plan(self, contract: StateContract) -> SearchPlan:
        hard = contract.hard_filters
        budget = hard.budget
        vector_query = contract.semantic_payload.vector_query.strip()
        return SearchPlan(
            vector_query=vector_query or self._fallback_query(hard),
            limit=self._settings.max_results,
            city=hard.location.city or None,
            category=(hard.category or [None])[0],
            max_price_per_person=(
                budget.max_price_per_person if budget else None),
            exclude_categories=list(contract.negative_filters.exclude_categories),
        )

    @staticmethod
    def _fallback_query(hard) -> str:
        parts = list(hard.category) + hard.amenities_required
        return " ".join(parts) if parts else "events"

    async def _cards(self, hits: list[FusedHit], language: str) -> list[ResultCard]:
        availabilities = await asyncio.gather(
            *(self._availability_for(hit) for hit in hits))
        return [self._to_card(hit, availability, language)
                for hit, availability in zip(hits, availabilities)]

    @staticmethod
    def _booking_event_id(hit: FusedHit) -> int | None:
        """booking-service event id carried in the payload, if any.

        Scraped events have UUID point ids and no live inventory; catalog
        events mirrored from booking-service carry `booking_event_id`.
        """
        raw = hit.payload.get("booking_event_id")
        if raw is None:
            raw = hit.id  # legacy points whose id already was the event id
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    async def _availability_for(self, hit: FusedHit) -> Availability | None:
        event_id = self._booking_event_id(hit)
        if event_id is None:
            return None  # collected (scraped) event: no live inventory
        return await self._booking.check_availability(event_id)

    def _to_card(self, hit: FusedHit, availability: Availability | None,
                 language: str) -> ResultCard:
        title = hit.payload.get("title") or i18n.t("card_untitled", language)
        booking_id = self._booking_event_id(hit)
        if availability is None:
            return ResultCard(
                event_id=str(booking_id) if booking_id is not None else hit.id,
                title=title,
                meta=i18n.t("card_scraped", language),
                price=i18n.format_price(None, None,
                                        self._settings.default_currency, language),
            )
        status = STATUS_KEYS.get(availability.status, availability.status)
        return ResultCard(
            event_id=str(booking_id) if booking_id is not None else hit.id,
            title=title,
            meta=i18n.t(status, language),
            price=i18n.format_price(availability.min_price, None,
                                    self._settings.default_currency, language),
        )
