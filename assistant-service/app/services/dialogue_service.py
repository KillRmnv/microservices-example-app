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
from dataclasses import replace
from datetime import datetime, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo

from ..api.schemas.contract import StateContract
from ..api.schemas.dialogue import ChatMessage, DialogResponse, ResultCard
from ..clients.booking import BookingClient
from ..core import db, i18n
from ..core.config import Settings, settings as default_settings
from ..core.dates import parse_iso_date, has_explicit_clock, time_window
from ..core.geo import resolve_location
from ..filters.specs import day_intervals
from ..models.availability import (AVAILABLE, FEW_LEFT, INSUFFICIENT, SOLD_OUT,
                                   UNKNOWN, Availability)
from ..models import intent as intents
from ..models.search import FusedHit, SearchPlan
from ..models.vocabulary import EVENT_CATEGORY_SET
from ..models.weather import Weather
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
# Outdoor seating that rain makes unappealing. Amenities are lowercase tags;
# rain excludes them through `AmenityExcludeFilter` (structured `amenities`
# only), so a venue that merely mentions "терраса" in its description stays.
OUTDOOR_AMENITIES = ("terrace", "веранда", "терраса", "на улице")
RAIN_EXCLUDE_AMENITIES = OUTDOOR_AMENITIES

# A raw category code ("film") is a poor lexical/embedding query: the catalog
# uses Russian words. Expand each code to the words the sources actually use.
CATEGORY_QUERY: dict[str, str] = {
    "film": "кино, фильм, кинопоказ",
    "concert": "концерт, живая музыка",
    "theatre": "театр, спектакль",
    "exhibition": "выставка",
    "sport": "спорт, матч",
    "kids": "для детей",
    "other": "события",
}
# Event categories that have a venue analogue. When a dated event search
# finds nothing, the assistant offers the matching places instead (2GIS
# rubrics). Keep this a map: more categories can be added without branching.
CATEGORY_VENUE_FALLBACK: dict[str, tuple[str, str]] = {
    "film": ("Кинотеатры", "search_empty_cinemas"),
    "theatre": ("Театры", "search_empty_theatres"),
    "exhibition": ("Художественные выставки", "search_empty_exhibitions"),
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
        if contract.dialogue_action == "ask_clarification":
            # Clarification is an explicit opt-in only. A missing slot never
            # blocks a search: the defaults (nearest events, the default city)
            # answer the turn.
            if not contract.clarify_missing:
                contract.dialogue_action = "search"
                contract.clarification_slots = []
                contract.needs_clarification = False
                contract.clarification_prompt = None
            return contract
        # A search turn must never turn into a blocking question just because
        # a slot is absent.
        contract.clarification_slots = []
        contract.needs_clarification = False
        return contract

    def record_run(self, contract: StateContract, duration_ms: int) -> None:
        try:
            with db.get_conn(self._db_url) as conn:
                dialogue_runs.record_run(conn, contract, duration_ms)
        except Exception as exc:  # noqa: BLE001 — metrics must not break dialogue
            log.warning("dialogue_runs insert failed: %s", exc)

    def elapsed_ms(self, started: float) -> int:
        return int((time.monotonic() - started) * 1000)

    # --- filters summary ---------------------------------------------------

    def _filters_summary(self, contract: StateContract,
                         language: str | None) -> str:
        """One deterministic line: every slot, with defaults spelled out."""
        hard = contract.hard_filters
        items: list[str] = []

        def add(label_key: str, value: str) -> None:
            items.append(i18n.t(
                "filters_item", language,
                label=i18n.t(label_key, language), value=value))

        add("filters_label_section", self._section_text(contract, language))
        if hard.event_count is not None:
            add("filters_label_event_count", str(hard.event_count))
        add("filters_label_date", self._date_text(hard.datetime, language))
        add("filters_label_city", self._city_text(hard.location, language))
        add("filters_label_type", self._type_text(hard.category, language))
        add("filters_label_themes", self._list_text(hard.themes, language))
        add("filters_label_company",
            self._company_text(hard.party_size, language))
        add("filters_label_budget", self._budget_text(hard.budget, language))
        add("filters_label_amenities",
            self._list_text(hard.amenities_required, language))
        add("filters_label_rating", self._rating_text(hard.min_rating,
                                                      language))
        add("filters_label_age", self._age_text(hard.age_max, language))
        add("filters_label_exclusions",
            self._exclusions_text(contract.negative_filters, language))
        return i18n.t("filters_sep", language).join(items)

    def _section_text(self, contract: StateContract,
                      language: str | None) -> str:
        scope = (contract.semantic_payload.target_collection
                 or intents.spec(contract.intent).scope)
        key = ("filters_section_venues" if scope == "venues"
               else "filters_section_both" if scope == "both"
               else "filters_section_events")
        return i18n.t(key, language)

    def _date_text(self, value, language: str | None) -> str:
        default = (f"{i18n.t('filters_date_default', language)} "
                   f"{i18n.t('filters_default_suffix', language)}")
        if value is None:
            return default
        if value.any:
            return i18n.t("filters_date_any", language)
        if not value.start:
            return default
        text = str(value.start)
        return (text[:16].replace("T", " ") if len(text) >= 16
                else text[:10])

    def _city_text(self, location, language: str | None) -> str:
        if location.any:
            return i18n.t("filters_city_any", language)
        if location.city:
            return location.city
        default = self._settings.default_city.strip()
        if not default:
            return i18n.t("filters_city_none", language)
        return (f"{default} "
                f"{i18n.t('filters_default_suffix', language)}")

    def _type_text(self, categories: list[str], language: str | None) -> str:
        if not categories:
            return i18n.t("filters_type_any", language)
        return i18n.t("filters_list_sep", language).join(
            i18n.t(f"category_{category}", language)
            if category in EVENT_CATEGORY_SET else str(category)
            for category in categories)

    def _list_text(self, values: list[str], language: str | None) -> str:
        if not values:
            return i18n.t("filters_none", language)
        return i18n.t("filters_list_sep", language).join(
            str(value) for value in values)

    def _company_text(self, party: int | None,
                      language: str | None) -> str:
        if party is None:
            return i18n.t("filters_company_none", language)
        if party <= 0:
            return i18n.t("filters_company_any", language)
        return i18n.t("filters_company_value", language, party=party)

    def _budget_text(self, budget, language: str | None) -> str:
        if budget is None or budget.any:
            return i18n.t("filters_budget_none", language)
        currency = i18n.currency_label(
            budget.currency or self._settings.default_currency, language)
        if budget.basis == "total" and budget.total is not None:
            return i18n.t("filters_budget_total", language,
                          amount=f"{budget.total:g}", currency=currency)
        if budget.max_price_per_person is not None:
            return i18n.t("filters_budget_per_person", language,
                          amount=f"{budget.max_price_per_person:g}",
                          currency=currency)
        return i18n.t("filters_budget_none", language)

    def _rating_text(self, rating: float | None,
                     language: str | None) -> str:
        if rating is None:
            return i18n.t("filters_rating_any", language)
        return i18n.t("filters_rating_value", language, rating=rating)

    def _age_text(self, age: int | None, language: str | None) -> str:
        if age is None:
            return i18n.t("filters_age_any", language)
        return i18n.t("filters_age_value", language, age=age)

    def _exclusions_text(self, negative, language: str | None) -> str:
        parts = [
            i18n.t(f"category_{category}", language)
            if category in EVENT_CATEGORY_SET else str(category)
            for category in negative.exclude_categories
        ]
        parts.extend(str(tag) for tag in negative.exclude_tags)
        parts.extend(str(district) for district in negative.exclude_districts)
        if not parts:
            return i18n.t("filters_none", language)
        return i18n.t("filters_list_sep", language).join(parts)

    def _filters_message(self, contract: StateContract,
                         language: str | None) -> ChatMessage:
        return ChatMessage(kind="filters",
                           text=self._filters_summary(contract, language))

    def _log_search(self, kind: str, contract: StateContract,
                    plan: SearchPlan, stats: dict | None, *,
                    empty: bool) -> None:
        """One INFO line per search call; vector text is bounded."""
        log.info(
            "%s: intent=%s categories=%s vector=%r results=%d excluded=%d "
            "empty=%s",
            kind, contract.intent,
            plan.categories or ([plan.rubric] if plan.rubric else []),
            plan.vector_query[:120],
            int((stats or {}).get("results", 0)),
            int((stats or {}).get("excluded", 0)), empty)

    async def search_turn(self, contract: StateContract) -> DialogResponse:
        spec = intents.spec(contract.intent)
        scope = spec.scope
        hard = contract.hard_filters
        target = contract.semantic_payload.target_collection
        if (target in intents.SEARCH_SCOPES
                and contract.dialogue_action in SEARCH_ACTIONS):
            # An explicit collection from the structure model outranks the
            # intent's default scope. Clarifications keep their own routing.
            scope = target
        # A generic request with no explicit category/theme ("что-нибудь")
        # should not silently exclude venues.
        elif scope == "events" and not hard.category and not hard.themes:
            scope = "both"
        if scope == "venues":
            return await self._venue_turn(contract)
        if scope == "both":
            return await self._both_turn(contract)
        language = i18n.resolve_locale(contract.semantic_payload.language)
        messages: list[ChatMessage] = [
            self._filters_message(contract, language)
        ]
        date_value = hard.datetime.start if hard.datetime else None
        day = parse_iso_date(date_value)
        rain = False
        if day is not None:
            rain = await self._append_weather(
                contract, day, language, messages, announce_outdoor=False)
        plan = self._search_plan(contract, drop_outdoor=rain)
        stats: dict = {}
        fused = await self._search.events(plan, stats=stats)
        self._log_search("search", contract, plan, stats, empty=not fused)
        if not fused:
            # A category with a venue analogue ("фильм") should still answer
            # with the matching places instead of a dead end.
            fallback = await self._category_venue_turn(
                contract, language, messages)
            if fallback is not None:
                return fallback
            messages.append(ChatMessage(
                kind="assistant",
                text=await self._empty_text(
                    plan, language, self._search.events)))
            return DialogResponse(contract=contract, messages=messages)
        cards = await self._cards(fused, language, hard.party_size)
        messages.append(ChatMessage(
            kind="results", text=i18n.t("search_results", language), results=cards))
        return DialogResponse(contract=contract, messages=messages)

    async def _category_venue_turn(self, contract: StateContract,
                                   language: str,
                                   messages: list[ChatMessage]
                                   ) -> DialogResponse | None:
        """Empty event category -> the matching venue rubric, if mapped."""
        for category in contract.hard_filters.category:
            mapped = CATEGORY_VENUE_FALLBACK.get(category)
            if mapped is None:
                continue
            rubric, message_key = mapped
            plan = self._venue_plan(contract)
            plan.rubric = rubric
            plan.vector_query = rubric
            stats: dict = {}
            venues = await self._search_venues.venues(plan, stats=stats)
            self._log_search("venues", contract, plan, stats,
                             empty=not venues)
            if not venues:
                if plan.exclude_ids and await self._search_venues.venues(
                        replace(plan, exclude_ids=[])):
                    messages.append(ChatMessage(
                        kind="assistant",
                        text=i18n.t("search_more_empty", language)))
                    return DialogResponse(contract=contract,
                                          messages=messages)
                return None
            messages.append(ChatMessage(
                kind="assistant", text=i18n.t(message_key, language)))
            messages.append(ChatMessage(
                kind="results", text=i18n.t("venue_results", language),
                results=[self._to_venue_card(hit, language)
                         for hit in venues]))
            return DialogResponse(contract=contract, messages=messages)
        return None

    async def _empty_text(self, plan: SearchPlan, language: str,
                          search) -> str:
        """Distinguish "nothing exists" from "everything was already shown"."""
        if plan.exclude_ids:
            probe = replace(plan, exclude_ids=[])
            if await search(probe):
                return i18n.t("search_more_empty", language)
        return i18n.t("search_empty", language)

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
            self._filters_message(contract, language)
        ]
        hard = contract.hard_filters
        day = parse_iso_date(hard.datetime.start if hard.datetime else None)
        rain = False
        if day is not None:
            rain = await self._append_weather(
                contract, day, language, messages, announce_outdoor=True)
        plan = self._venue_plan(
            contract,
            extra_exclude_amenities=(RAIN_EXCLUDE_AMENITIES if rain else None))
        stats: dict = {}
        fused = await self._search_venues.venues(plan, stats=stats)
        self._log_search("venues", contract, plan, stats, empty=not fused)
        if not fused:
            messages.append(ChatMessage(
                kind="assistant",
                text=await self._empty_text(
                    plan, language, self._search_venues.venues)))
            return DialogResponse(contract=contract, messages=messages)
        messages.append(ChatMessage(
            kind="results", text=i18n.t("venue_results", language),
            results=[self._to_venue_card(hit, language) for hit in fused]))
        return DialogResponse(contract=contract, messages=messages)

    async def _both_turn(self, contract: StateContract) -> DialogResponse:
        language = i18n.resolve_locale(contract.semantic_payload.language)
        messages: list[ChatMessage] = [
            self._filters_message(contract, language)
        ]
        hard = contract.hard_filters
        day = parse_iso_date(hard.datetime.start if hard.datetime else None)
        rain = False
        if day is not None:
            rain = await self._append_weather(
                contract, day, language, messages, announce_outdoor=True)
        event_plan = self._search_plan(contract, drop_outdoor=rain)
        venue_plan = self._venue_plan(
            contract,
            extra_exclude_amenities=(
                RAIN_EXCLUDE_AMENITIES if rain else None))
        event_stats: dict = {}
        venue_stats: dict = {}
        events, venues = await asyncio.gather(
            self._search.events(event_plan, stats=event_stats),
            self._search_venues.venues(venue_plan, stats=venue_stats),
        )
        self._log_search("search", contract, event_plan, event_stats,
                         empty=not events)
        self._log_search("venues", contract, venue_plan, venue_stats,
                         empty=not venues)
        event_cards = (await self._cards(events, language, hard.party_size)
                       if events else [])
        venue_cards = ([self._to_venue_card(hit, language) for hit in venues])
        cards = event_cards + venue_cards
        if not cards:
            more = False
            if event_plan.exclude_ids or venue_plan.exclude_ids:
                probes = await asyncio.gather(
                    self._search.events(replace(event_plan, exclude_ids=[])),
                    self._search_venues.venues(
                        replace(venue_plan, exclude_ids=[])),
                )
                more = any(probes)
            messages.append(ChatMessage(
                kind="assistant",
                text=i18n.t("search_more_empty" if more else "search_empty",
                            language)))
            return DialogResponse(contract=contract, messages=messages)
        messages.append(ChatMessage(
            kind="results", text=i18n.t("search_results", language), results=cards))
        return DialogResponse(contract=contract, messages=messages)

    def _venue_plan(self, contract: StateContract, *,
                    extra_exclude_tags: list[str] | None = None,
                    extra_exclude_amenities: list[str] | None = None,
                    ) -> SearchPlan:
        hard = contract.hard_filters
        spec = intents.spec(contract.intent)
        rubric = spec.rubrics[0] if spec.rubrics else None
        vector = (contract.semantic_payload.vector_query.strip()
                  or rubric or self._settings.default_venue_query)
        budget = hard.budget
        exclude_tags = list(contract.negative_filters.exclude_tags)
        for tag in extra_exclude_tags or []:
            if tag not in exclude_tags:
                exclude_tags.append(tag)
        exclude_amenities = list(extra_exclude_amenities or [])
        date_from, date_to = self._date_window(hard)
        timezone = (hard.datetime.timezone if hard.datetime
                    and hard.datetime.timezone
                    else self._settings.default_timezone)
        return SearchPlan(
            vector_query=vector,
            limit=self._settings.max_results,
            city=(None if hard.location.any
                  else hard.location.city or self._settings.default_city),
            rubric=rubric,
            max_price_per_person=(
                budget.max_price_per_person
                if budget and not budget.any else None),
            exclude_categories=list(contract.negative_filters.exclude_categories),
            exclude_tags=exclude_tags,
            exclude_ids=list(contract.context_state.shown_ids),
            exclude_amenities=exclude_amenities,
            date_from=date_from,
            date_to=date_to,
            timezone=timezone,
            party_size=hard.party_size,
            age_max=hard.age_max,
            min_rating=hard.min_rating,
            dense_only=True,
        )

    def _to_venue_card(self, hit: FusedHit, language: str) -> ResultCard:
        payload = hit.payload
        title = payload.get("name") or i18n.t("card_untitled", language)
        rating = self._as_float(payload.get("rating"))
        review_count = self._as_int(payload.get("review_count"))
        address = str(payload.get("address") or "")
        # The address travels in its own `address` field (the frontend
        # renders it on a separate line) and the rating is a structured
        # field the UI badges, so `meta` keeps only the rubric; the city is
        # the fallback when it is missing.
        meta = payload.get("rubric") or payload.get("city", "")
        return ResultCard(
            event_id=hit.id,
            kind="venue",
            detail_id=hit.id,
            title=title,
            meta=meta,
            price="",
            source=str(payload.get("source") or ""),
            rating=rating,
            review_count=review_count,
            address=address,
            hours=self._venue_hours_text(payload, language),
            status=str(payload.get("status") or ""),
        )

    async def _weather_context(self, contract: StateContract, day,
                               language: str) -> tuple[ChatMessage, Weather]:
        hard = contract.hard_filters
        city = hard.location.city or self._settings.default_city
        center = (self._settings.default_latitude, self._settings.default_longitude)
        landmark = (hard.location.landmarks or [None])[0]
        geo = resolve_location(landmark, city, center, language)
        weather = await self._weather.forecast(day.isoformat(),
                                               geo["lat"], geo["lon"])
        text = weather.advice(language)
        return (ChatMessage(kind="weather", text=text,
                            weather=text if weather.available else None),
                weather)

    async def _weather_message(self, contract: StateContract, day,
                               language: str) -> ChatMessage:
        message, _ = await self._weather_context(contract, day, language)
        return message

    def _is_rainy(self, weather: Weather | None) -> bool:
        """True when the forecast crosses the configured rain threshold."""
        if weather is None or not weather.available:
            return False
        probability = weather.precipitation_probability
        if probability is None:
            return False
        return probability >= self._settings.weather_rain_probability_threshold

    async def _append_weather(self, contract: StateContract, day,
                              language: str, messages: list[ChatMessage],
                              *, announce_outdoor: bool) -> bool:
        """Append the forecast; report whether outdoor options are excluded.

        The "outdoor/terrace excluded" notice is only honest on turns that
        actually search venues; an events-only turn keeps the plain advice.
        """
        message, weather = await self._weather_context(contract, day, language)
        messages.append(message)
        if not self._is_rainy(weather):
            return False
        if announce_outdoor:
            messages.append(ChatMessage(
                kind="assistant",
                text=i18n.t("weather_adjusted_rain", language,
                            date=day.isoformat(),
                            probability=weather.precipitation_probability)))
        return True

    @staticmethod
    def _as_float(value) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_int(value) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return None

    @staticmethod
    def _as_str_list(value) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple)):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    @staticmethod
    def _payload_datetime(value) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    @classmethod
    def _is_film(cls, payload) -> bool:
        """Cinema rows are `category=film`; the extra fields also mark them."""
        categories = {item.casefold()
                      for item in cls._as_str_list(payload.get("category"))}
        return ("film" in categories
                or bool(cls._as_str_list(payload.get("film_genre")))
                or cls._as_int(payload.get("film_duration_min")) is not None)

    @classmethod
    def _film_run_until(cls, start_at, end_at) -> str:
        """DD.MM when the interval is a multi-day cinema run, not one show."""
        start = cls._payload_datetime(start_at)
        end = cls._payload_datetime(end_at)
        if start is None or end is None:
            return ""
        if end - start <= timedelta(days=1):
            return ""
        return end.strftime("%d.%m")

    @classmethod
    def _film_session_text(cls, payload, language: str) -> str:
        session = cls._payload_datetime(payload.get("next_session_at"))
        if session is None:
            return ""
        cinema = str(payload.get("cinema") or "").strip()
        time_text = session.strftime("%H:%M")
        key = "card_film_next_session_cinema" if cinema else \
            "card_film_next_session"
        return i18n.t(key, language, time=time_text, cinema=cinema)

    @classmethod
    def _film_facts_text(cls, payload, language: str) -> str:
        genres = cls._as_str_list(payload.get("film_genre"))[:2]
        minutes = cls._as_int(payload.get("film_duration_min"))
        parts = [", ".join(genres)] if genres else []
        if minutes is not None and minutes > 0:
            parts.append(i18n.t("card_film_duration", language, minutes=minutes))
        return i18n.t("filters_sep", language).join(parts)

    @classmethod
    def _film_meta_parts(cls, payload, start_at, end_at,
                         language: str) -> tuple[str, str]:
        """Film meta: the run/session line and the short genre/duration facts.

        Both parts stay empty when the source sends none of the optional
        fields, so older payloads render exactly as before.
        """
        if not cls._is_film(payload):
            return "", ""
        line = ""
        if cls._payload_datetime(payload.get("next_session_at")) is not None:
            line = cls._film_session_text(payload, language)
        run_until = cls._film_run_until(start_at, end_at)
        if run_until:
            run_text = i18n.t("card_film_run_until", language,
                              date=run_until)
            line = (i18n.t("filters_sep", language).join([line, run_text])
                    if line else run_text)
        return line, cls._film_facts_text(payload, language)

    @classmethod
    def _venue_hours_text(cls, payload, language: str) -> str:
        """Compact opening hours: "до 23:00" / "круглосуточно" / "закрыто"."""
        if payload.get("is_24_7"):
            return i18n.t("card_hours_24_7", language)
        hours = payload.get("hours")
        if not isinstance(hours, dict) or not hours:
            return ""
        latest = None
        for entry in hours.values():
            intervals = day_intervals(entry)
            if intervals is None:
                return i18n.t("card_hours_24_7", language)
            for _, close_time in intervals:
                if latest is None or close_time > latest:
                    latest = close_time
        if latest is None:
            return i18n.t("venue_closed", language)
        return i18n.t("card_hours", language,
                      close=f"{latest.hour:02d}:{latest.minute:02d}")

    @staticmethod
    def _fits_party(party: int | None, seats_left: int | None,
                    capacity: int | None, availability: Availability | None
                    ) -> bool | None:
        if not party or party < 1:
            return None
        if availability is not None and availability.status == INSUFFICIENT:
            return False
        if seats_left is not None:
            return seats_left >= party
        if capacity is not None:
            return capacity >= party
        return None

    def _search_plan(self, contract: StateContract, *,
                     drop_outdoor: bool = False) -> SearchPlan:
        hard = contract.hard_filters
        budget = hard.budget
        spec = intents.spec(contract.intent)
        categories = list(hard.category) or list(spec.categories)
        # Undated posts are announcements: only a category-only search with
        # no explicit date opts into them, so generic queries keep their
        # future floor.
        include_undated = (bool(hard.category)
                           and (hard.datetime is None or hard.datetime.any))
        date_from, date_to = self._date_window(hard)
        if date_from is None:
            # No date (or "any date"): never offer events that already ended.
            # Undated mode keeps this future floor and admits undated posts
            # through DateRangeFilter(allow_undated=True).
            date_from = self._now()
            date_to = None
        vector_query = contract.semantic_payload.vector_query.strip()
        amenities = list(hard.amenities_required)
        if drop_outdoor:
            # Rain turn: outdoor seating is excluded, so it must not drive
            # the fallback query either.
            amenities = [item for item in amenities
                         if item.casefold() not in OUTDOOR_AMENITIES]
        return SearchPlan(
            vector_query=(vector_query
                          or self._fallback_query(hard, amenities, categories)),
            limit=self._settings.max_results,
            city=(None if hard.location.any
                  else hard.location.city or self._settings.default_city),
            categories=categories,
            max_price_per_person=(
                budget.max_price_per_person
                if budget and not budget.any else None),
            exclude_categories=list(contract.negative_filters.exclude_categories),
            exclude_tags=list(contract.negative_filters.exclude_tags),
            exclude_ids=list(contract.context_state.shown_ids),
            date_from=date_from,
            date_to=date_to,
            timezone=(hard.datetime.timezone if hard.datetime
                      and hard.datetime.timezone
                      else self._settings.default_timezone),
            party_size=hard.party_size,
            age_max=hard.age_max,
            min_rating=hard.min_rating,
            # Themes are a lexical (sparse/BM25) signal, not a reason to
            # disable sparse retrieval.
            themes=list(hard.themes),
            include_undated=include_undated,
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

    def _fallback_query(self, hard, amenities: list[str] | None = None,
                        categories: list[str] | None = None) -> str:
        parts: list[str] = []
        for category in (categories if categories is not None
                         else hard.category):
            parts.append(CATEGORY_QUERY.get(category, str(category)))
        parts.extend(list(hard.amenities_required)
                     if amenities is None else amenities)
        return ", ".join(part for part in parts if part) \
            if parts else self._settings.default_search_query

    async def _cards(self, hits: list[FusedHit], language: str,
                     party: int | None = None) -> list[ResultCard]:
        availabilities = await asyncio.gather(
            *(self._availability_for(hit, party) for hit in hits))
        return [self._to_card(hit, availability, language, party)
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

    async def _availability_for(self, hit: FusedHit,
                               party: int | None = None) -> Availability | None:
        event_id = self._booking_event_id(hit)
        if event_id is None:
            return None  # collected (scraped) event: no live inventory
        return await self._booking.check_availability(event_id, party)

    def _to_card(self, hit: FusedHit, availability: Availability | None,
                 language: str, party: int | None = None) -> ResultCard:
        payload = hit.payload
        title = payload.get("title") or i18n.t("card_untitled", language)
        booking_id = self._booking_event_id(hit)
        source = str(payload.get("source") or "")
        start_at = str(payload.get("start_at") or "")
        end_at = str(payload.get("end_at") or start_at)
        currency = str(payload.get("currency")
                       or self._settings.default_currency)
        rating = self._as_float(payload.get("venue_rating"))
        review_count = self._as_int(payload.get("venue_review_count"))
        address = str(payload.get("address") or "")
        event_status = str(payload.get("status") or "")
        seats_left = self._as_int(payload.get("seats_left"))
        capacity = self._as_int(payload.get("capacity"))
        # Optional film extras: absent fields leave the card untouched.
        film_line, film_facts = self._film_meta_parts(
            payload, start_at, end_at, language)
        next_session_at = str(payload.get("next_session_at") or "")
        cinema = str(payload.get("cinema") or "")
        film_genre = self._as_str_list(payload.get("film_genre")) or None
        film_duration_min = self._as_int(payload.get("film_duration_min"))

        def film_meta(meta: str) -> str:
            """Run/showtime replaces the generic line; facts still fit."""
            if film_line:
                meta = film_line
            if film_facts and film_facts.casefold() not in meta.casefold():
                meta = (i18n.t("filters_sep", language).join([meta, film_facts])
                        if meta else film_facts)
            return meta

        if availability is None:
            # Scraped event: no live inventory, but the source price is known
            # often enough that hiding it behind "цена уточняется" is a bug.
            # The rating is a structured field, so `meta` stays status-only.
            price_min = self._as_float(payload.get("price_min"))
            price_max = self._as_float(payload.get("price_max"))
            meta = (i18n.t("card_undated", language) if not start_at
                    else i18n.t("card_scraped", language))
            meta = film_meta(meta)
            return ResultCard(
                event_id=str(booking_id) if booking_id is not None else hit.id,
                detail_id=hit.id,
                title=title,
                meta=meta,
                price=i18n.format_price(price_min, price_max, currency,
                                        language),
                source=source,
                start_at=start_at,
                end_at=end_at,
                rating=rating,
                review_count=review_count,
                address=address,
                seats_left=seats_left,
                fits_party=self._fits_party(party, seats_left, capacity, None),
                status=event_status,
                next_session_at=next_session_at,
                cinema=cinema,
                film_genre=film_genre,
                film_duration_min=film_duration_min,
            )
        if availability.status == INSUFFICIENT:
            meta = (i18n.t("card_no_seats", language, party=party)
                    if party else i18n.t("availability_sold_out", language))
        else:
            status = STATUS_KEYS.get(availability.status, availability.status)
            meta = i18n.t(status, language)
        if not start_at:
            meta = i18n.t("card_undated", language)
        meta = film_meta(meta)
        zone_prices = [self._as_float(zone.get("min_price"))
                       for zone in availability.zones]
        zone_prices = [price for price in zone_prices if price is not None]
        zone_max = max(zone_prices) if zone_prices else None
        if (zone_max is not None and availability.min_price is not None
                and zone_max <= availability.min_price):
            zone_max = None
        # Prefer live inventory when it reports seats; fall back to the
        # source's own `seats_left` payload field.
        live_seats = (availability.seats_left
                      if availability.seats_left is not None else seats_left)
        live_capacity = (availability.capacity
                         if availability.capacity is not None else capacity)
        return ResultCard(
            event_id=str(booking_id) if booking_id is not None else hit.id,
            detail_id=hit.id,
            title=title,
            meta=meta,
            price=i18n.format_price(availability.min_price, zone_max,
                                    currency, language),
            source=source,
            start_at=start_at,
            end_at=end_at,
            rating=rating,
            review_count=review_count,
            address=address,
            seats_left=live_seats,
            fits_party=self._fits_party(party, live_seats, live_capacity,
                                        availability),
            status=(availability.status
                    if availability.status != UNKNOWN else event_status),
            next_session_at=next_session_at,
            cinema=cinema,
            film_genre=film_genre,
            film_duration_min=film_duration_min,
        )
