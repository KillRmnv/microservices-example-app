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
from collections.abc import Callable
from datetime import datetime, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo

from ..api.schemas.contract import StateContract
from ..api.schemas.dialogue import ChatMessage, DialogResponse, ResultCard
from ..clients.booking import BookingClient
from ..core import db, i18n
from ..core.config import Settings, settings as default_settings
from ..core.dates import parse_iso_date, has_explicit_clock, time_window
from ..core.geo import resolve_location
from ..models.availability import AVAILABLE, FEW_LEFT, SOLD_OUT, UNKNOWN, Availability
from ..models import intent as intents
from ..models.search import FusedHit, SearchPlan
from ..repositories import dialogue_runs
from .rules import required_slots
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
    def __init__(self, *, search: SearchService, search_venues: SearchService,
                 weather: WeatherService, booking: BookingClient, db_url: str,
                 settings: Settings = default_settings,
                 now: Callable[[], datetime] | None = None) -> None:
        self._search = search
        self._search_venues = search_venues
        self._weather = weather
        self._booking = booking
        self._db_url = db_url
        self._settings = settings
        # Injectable clock: tests need a stable "today" for the future floor.
        self._now = now or (
            lambda: datetime.now(ZoneInfo(settings.default_timezone)))

    def apply_rules(self, contract: StateContract,
                    language: str | None = None) -> StateContract:
        """Deterministic rules that need no LLM."""
        if contract.dialogue_action == "confirm_booking":
            contract.needs_clarification = True
            contract.clarification_prompt = i18n.t("clarify_booking", language)
            return contract
        if contract.dialogue_action in SEARCH_ACTIONS and contract.clarify_missing:
            missing = required_slots(contract, self._settings)
            if missing:
                contract.dialogue_action = "ask_clarification"
                contract.needs_clarification = True
                contract.clarification_slots = list(missing)
                contract.clarification_prompt = i18n.t(
                    "clarify_missing", language,
                    missing=", ".join(i18n.t(f"slot_{slot}", language)
                                      for slot in missing))
            else:
                contract.clarification_slots = []
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
        spec = intents.spec(contract.intent)
        scope = spec.scope
        hard = contract.hard_filters
        # A generic request with no explicit category/theme ("что-нибудь")
        # should not silently exclude venues.
        if scope == "events" and not hard.category and not hard.themes:
            scope = "both"
        if scope == "venues":
            return await self._venue_turn(contract)
        if scope == "both":
            return await self._both_turn(contract)
        language = i18n.resolve_locale(contract.semantic_payload.language)
        messages: list[ChatMessage] = [
            ChatMessage(kind="filters", text=i18n.t("filters_locked", language))
        ]
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

    async def weather_turn(self, contract: StateContract) -> DialogResponse:
        """Weather-only turn: no search, no cards, just the forecast advice."""
        language = i18n.resolve_locale(contract.semantic_payload.language)
        hard = contract.hard_filters
        day = None
        if hard.datetime is not None and not hard.datetime.any:
            day = parse_iso_date(hard.datetime.start)
        if day is None:
            # "Какая погода?" without a date means today.
            day = self._now().date()
        message = await self._weather_message(contract, day, language)
        return DialogResponse(contract=contract, messages=[message])

    async def _venue_turn(self, contract: StateContract) -> DialogResponse:
        language = i18n.resolve_locale(contract.semantic_payload.language)
        messages: list[ChatMessage] = [
            ChatMessage(kind="filters", text=i18n.t("filters_locked", language))
        ]
        hard = contract.hard_filters
        day = parse_iso_date(hard.datetime.start if hard.datetime else None)
        if day is not None:
            messages.append(await self._weather_message(contract, day, language))
        fused = await self._search_venues.venues(self._venue_plan(contract))
        if not fused:
            messages.append(ChatMessage(
                kind="assistant", text=i18n.t("venue_empty", language)))
            return DialogResponse(contract=contract, messages=messages)
        messages.append(ChatMessage(
            kind="results", text=i18n.t("venue_results", language),
            results=[self._to_venue_card(hit, language) for hit in fused]))
        return DialogResponse(contract=contract, messages=messages)

    async def _both_turn(self, contract: StateContract) -> DialogResponse:
        language = i18n.resolve_locale(contract.semantic_payload.language)
        messages: list[ChatMessage] = [
            ChatMessage(kind="filters", text=i18n.t("filters_locked", language))
        ]
        hard = contract.hard_filters
        day = parse_iso_date(hard.datetime.start if hard.datetime else None)
        if day is not None:
            messages.append(await self._weather_message(contract, day, language))
        events, venues = await asyncio.gather(
            self._search.events(self._search_plan(contract)),
            self._search_venues.venues(self._venue_plan(contract)),
        )
        event_cards = await self._cards(events, language) if events else []
        venue_cards = ([self._to_venue_card(hit, language) for hit in venues])
        cards = event_cards + venue_cards
        if not cards:
            messages.append(ChatMessage(
                kind="assistant", text=i18n.t("search_empty", language)))
            return DialogResponse(contract=contract, messages=messages)
        messages.append(ChatMessage(
            kind="results", text=i18n.t("search_results", language), results=cards))
        return DialogResponse(contract=contract, messages=messages)

    def _venue_plan(self, contract: StateContract) -> SearchPlan:
        hard = contract.hard_filters
        spec = intents.spec(contract.intent)
        rubric = spec.rubrics[0] if spec.rubrics else None
        vector = (contract.semantic_payload.vector_query.strip()
                  or rubric or self._settings.default_venue_query)
        return SearchPlan(
            vector_query=vector,
            limit=self._settings.max_results,
            city=(None if hard.location.any
                  else hard.location.city or self._settings.default_city),
            rubric=rubric,
            dense_only=True,
        )

    def _to_venue_card(self, hit: FusedHit, language: str) -> ResultCard:
        payload = hit.payload
        title = payload.get("name") or i18n.t("card_untitled", language)
        meta = " · ".join(part for part in
                          (payload.get("rubric"), payload.get("address"))
                          if part) or payload.get("city", "")
        return ResultCard(
            event_id=hit.id,
            kind="venue",
            detail_id=hit.id,
            title=title,
            meta=meta,
            price="",
            source=str(payload.get("source") or ""),
        )

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
        date_from, date_to = self._date_window(hard)
        if date_from is None:
            # No date (or "any date"): never offer events that already ended.
            date_from = self._now()
            date_to = None
        spec = intents.spec(contract.intent)
        return SearchPlan(
            vector_query=vector_query or self._fallback_query(hard),
            limit=self._settings.max_results,
            city=(None if hard.location.any
                  else hard.location.city or self._settings.default_city),
            categories=list(hard.category) or list(spec.categories),
            max_price_per_person=(
                budget.max_price_per_person
                if budget and not budget.any else None),
            exclude_categories=list(contract.negative_filters.exclude_categories),
            date_from=date_from,
            date_to=date_to,
            dense_only=bool(hard.themes),
        )

    def _date_window(self, hard) -> tuple[datetime | None, datetime | None]:
        """Respect the requested time-of-day, not just the calendar date."""
        date_filter = hard.datetime
        if date_filter is None or date_filter.any:
            return None, None
        start_day = parse_iso_date(date_filter.start)
        if start_day is None:
            return None, None
        end_day = parse_iso_date(date_filter.end) or start_day
        if end_day < start_day:
            end_day = start_day
        tz_name = date_filter.timezone or self._settings.default_timezone
        try:
            tz = ZoneInfo(tz_name)
        except Exception:  # noqa: BLE001 — bad client timezone
            tz = timezone.utc
        raw = date_filter.raw_expression or ""
        window = time_window(raw)
        explicit = has_explicit_clock(raw)
        # No time-of-day and no clock: the whole calendar day(s).
        if window is None and not explicit:
            start = datetime.combine(start_day, dt_time.min, tzinfo=tz)
            end = datetime.combine(end_day + timedelta(days=1),
                                   dt_time.min, tzinfo=tz)
            return start, end

        def parsed_time(value, fallback: dt_time) -> dt_time:
            if not value:
                return fallback
            try:
                parsed = datetime.fromisoformat(
                    str(value).replace("Z", "+00:00"))
                return parsed.timetz().replace(tzinfo=None)
            except ValueError:
                return fallback

        if window is not None and not explicit:
            start_time = dt_time(window[0], window[1])
            end_time = dt_time(window[2], window[3])
        else:
            fallback_start = (dt_time(window[0], window[1])
                              if window else dt_time.min)
            fallback_end = (dt_time(window[2], window[3])
                            if window else dt_time(23, 59))
            start_time = parsed_time(date_filter.start, fallback_start)
            end_time = parsed_time(date_filter.end, fallback_end)
        start = datetime.combine(start_day, start_time, tzinfo=tz)
        end = datetime.combine(end_day, end_time, tzinfo=tz)
        if end <= start:
            end += timedelta(days=1)
        return start, end

    def _fallback_query(self, hard) -> str:
        parts = list(hard.category) + hard.amenities_required
        return " ".join(parts) if parts else self._settings.default_search_query

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
        source = str(hit.payload.get("source") or "")
        start_at = str(hit.payload.get("start_at") or "")
        end_at = str(hit.payload.get("end_at") or start_at)
        if availability is None:
            return ResultCard(
                event_id=str(booking_id) if booking_id is not None else hit.id,
                detail_id=hit.id,
                title=title,
                meta=i18n.t("card_scraped", language),
                price=i18n.format_price(None, None,
                                        self._settings.default_currency, language),
                source=source,
                start_at=start_at,
                end_at=end_at,
            )
        status = STATUS_KEYS.get(availability.status, availability.status)
        return ResultCard(
            event_id=str(booking_id) if booking_id is not None else hit.id,
            detail_id=hit.id,
            title=title,
            meta=i18n.t(status, language),
            price=i18n.format_price(availability.min_price, None,
                                    self._settings.default_currency, language),
            source=source,
            start_at=start_at,
            end_at=end_at,
        )
