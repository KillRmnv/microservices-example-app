"""StateContract DTO: the dialogue state owned by the client.

The server never trusts it blindly: unknown fields are dropped, enums and
vocabularies are validated, free-form slots are clamped/truncated, and domain
defaults (timezone, currency, language) come from configuration, not hardcoded
values. The city is *not* filled here: the default is applied at search time.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core import i18n
from ...core.config import settings
from ...core.dates import has_explicit_clock, time_window
from ...models.vocabulary import EVENT_CATEGORIES, EVENT_CATEGORY_SET

PARTY_SIZE_MIN = 1
PARTY_SIZE_MAX = 20
# Adult content is 18+; 21 is a generous upper clamp for the requested max.
MAX_AGE_MAX = 21
MAX_RATING = 5.0
ANONYMOUS_SESSION = "anonymous"

MAX_CATEGORIES = len(EVENT_CATEGORIES)
MAX_THEMES = 5
MAX_NEGATIVE_FILTERS = 10
MAX_AMENITIES = 10
MAX_SLOT_TEXT = 40
MAX_VECTOR_QUERY = 300
MAX_SESSION_ID = 128
# "Ещё" pagination: ids already shown to this chat. Ids are opaque strings
# (Qdrant UUIDs or numeric booking ids), so they keep their case.
MAX_SHOWN_IDS = 100
MAX_SHOWN_ID = 64

# The structure model names a collection with several synonyms; the search
# scope only understands three values, so aliases are folded here (not in the
# DTO type, which stays a plain string for client compatibility).
TARGET_COLLECTION_ALIASES = {
    "events": "events",
    "venues": "venues",
    "venues_atmosphere": "venues",
    "places": "venues",
    "both": "both",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


DialogueAction = Literal["search", "update_filters", "confirm_booking", "ask_clarification"]


class DateTimeFilter(StrictModel):
    start: str | None = None
    end: str | None = None
    timezone: str | None = None
    is_relative: bool = False
    raw_expression: str | None = None
    any: bool = False


class GeoRadius(StrictModel):
    latitude: float | None = None
    longitude: float | None = None
    radius_meters: int | None = None


class LocationFilter(StrictModel):
    city: str | None = None
    districts: list[str] = Field(default_factory=list)
    landmarks: list[str] = Field(default_factory=list)
    geo_radius: GeoRadius | None = None
    any: bool = False


class BudgetFilter(StrictModel):
    level: str | None = None
    currency: str | None = None
    # Derived, always per-person: this is what the search compares against.
    max_price_per_person: float | None = None
    # The sum the user named for the whole party ("40 рублей на двоих").
    # Kept as-is so the contract can be re-sanitized (every turn) and still
    # display "до 40 на всех".
    total: float | None = None
    basis: Literal["per_person", "total"] = "per_person"
    any: bool = False


class HardFilters(StrictModel):
    datetime: DateTimeFilter | None = None
    location: LocationFilter = Field(default_factory=LocationFilter)
    category: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    party_size: int | None = None
    budget: BudgetFilter | None = None
    amenities_required: list[str] = Field(default_factory=list)
    # Drop hits whose age_limit is above this (12 = "для детей",
    # 17 = "без 18+" ). None means "no age constraint".
    age_max: int | None = None
    # Minimum venue/venue-of-event rating on a 0..5 scale.
    min_rating: float | None = None
    # How many events the user explicitly wants in one plan iteration.
    # None means "not stated" (the plan keeps one event by default).
    event_count: int | None = None


class NegativeFilters(StrictModel):
    exclude_categories: list[str] = Field(default_factory=list)
    exclude_tags: list[str] = Field(default_factory=list)
    exclude_districts: list[str] = Field(default_factory=list)


class SemanticPayload(StrictModel):
    vector_query: str = ""
    target_collection: str | None = None
    language: str | None = None


class ContextState(StrictModel):
    turn_count: int = 1
    active_filters_changed: list[str] = Field(default_factory=list)
    session_id: str = ""
    # Card ids already rendered in this dialogue ("ещё" excludes them).
    shown_ids: list[str] = Field(default_factory=list)

    @field_validator("shown_ids", mode="before")
    @classmethod
    def _coerce_shown_ids(cls, value):
        """Accept a single id or loose JSON values; sanitize bounds them."""
        if isinstance(value, str):
            return [value]
        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value if item is not None]
        return []


class StateContract(StrictModel):
    dialogue_action: DialogueAction = "search"
    intent: str = "find_events"
    clarify_missing: bool = False
    needs_clarification: bool = False
    clarification_prompt: str | None = None
    clarification_slots: list[str] = Field(default_factory=list)
    hard_filters: HardFilters = Field(default_factory=HardFilters)
    negative_filters: NegativeFilters = Field(default_factory=NegativeFilters)
    semantic_payload: SemanticPayload = Field(default_factory=SemanticPayload)
    context_state: ContextState = Field(default_factory=ContextState)


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _aware(value: datetime | None, tz_name: str) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    try:
        return value.replace(tzinfo=ZoneInfo(tz_name))
    except Exception:  # noqa: BLE001 — bad client timezone
        return value.replace(tzinfo=timezone.utc)


def _normalize_time_of_day(dt: dict) -> None:
    """Make "вечер пятницы" a stable 18:00–23:59 window.

    The structure model is free-form and sometimes returns 17:00 for
    "вечер"; the search then silently expanded it to the whole day anyway.
    """
    if not isinstance(dt, dict) or dt.get("any"):
        return
    raw = str(dt.get("raw_expression") or "")
    window = time_window(raw)
    if window is None:
        return
    tz_name = dt.get("timezone") or settings.default_timezone
    start = _aware(_parse_datetime(dt.get("start")), tz_name)
    if start is None:
        return
    end = _aware(_parse_datetime(dt.get("end")), tz_name)
    start_h, start_m, end_h, end_m = window
    if not has_explicit_clock(raw):
        start = start.replace(hour=start_h, minute=start_m,
                              second=0, microsecond=0)
    end = (end or start).replace(hour=end_h, minute=end_m,
                                 second=0, microsecond=0)
    if end <= start and end.date() == start.date():
        end += timedelta(days=1)
    dt["start"] = start.isoformat()
    dt["end"] = end.isoformat()


def _clean_category(value) -> list[str]:
    """Keep known categories only, deduplicated and capped.

    "All seven categories" is a broad request, not a filter: drop it.
    """
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    kept: list[str] = []
    for item in value:
        text = str(item).strip().lower()
        if text in EVENT_CATEGORY_SET and text not in kept:
            kept.append(text)
    if set(kept) >= EVENT_CATEGORY_SET:
        return []
    return kept[:MAX_CATEGORIES]


def _clean_text_list(value, *, limit: int, max_len: int = MAX_SLOT_TEXT
                     ) -> list[str]:
    """Lowercase/strip, dedupe, truncate and cap free-form slot lists.

    Unknown values are kept: the search layer decides what to do with them.
    """
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        text = str(item).strip().lower()[:max_len].strip()
        if text and text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _clean_ids(value, *, limit: int, max_len: int) -> list[str]:
    """Strip, truncate and dedupe opaque ids without changing their case."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        text = str(item).strip()[:max_len].strip()
        if text and text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _clean_price(value) -> float | None:
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None


def _clean_age_max(value) -> int | None:
    try:
        age = int(value)
    except (TypeError, ValueError):
        return None
    return min(MAX_AGE_MAX, max(0, age))


def _clean_rating(value) -> float | None:
    try:
        rating = float(value)
    except (TypeError, ValueError):
        return None
    return min(MAX_RATING, max(0.0, rating))


def _clean_event_count(value) -> int | None:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    return min(5, max(1, count))


def _clean_target_collection(value) -> str | None:
    """Fold collection synonyms; unknown collections mean "no override"."""
    if not isinstance(value, str):
        return None
    return TARGET_COLLECTION_ALIASES.get(value.strip().lower())


def _clean_language(value) -> str:
    """Clamp the presentation locale to a catalog (ru/en).

    Only message selection uses this value; retrieval stays Russian-only.
    An unknown tag falls back to the configured default language.
    """
    if isinstance(value, str):
        text = value.strip().lower()
        base = text.split("-", 1)[0].split("_", 1)[0]
        resolved = i18n.resolve_locale(text)
        if base and resolved == base:
            return resolved
    return i18n.resolve_locale(settings.default_language)


def sanitize(contract: StateContract) -> StateContract:
    """Server-side normalization: clamp slots and fill configured defaults."""
    from ...models import intent as intents

    data = contract.model_dump()
    data["intent"] = intents.normalize(data.get("intent"))
    data["clarify_missing"] = bool(data.get("clarify_missing"))
    hard = data["hard_filters"]
    raw_party = hard.get("party_size")
    if raw_party is None:
        hard["party_size"] = None
    else:
        value = int(raw_party)
        # 0 is an explicit "any party size"; None means "not specified".
        hard["party_size"] = (0 if value == 0 else
                              min(PARTY_SIZE_MAX, max(PARTY_SIZE_MIN, value)))
    location = hard.get("location") or {}
    city = location.get("city")
    if location.get("any") or not (isinstance(city, str) and city.strip()):
        # Never invent a city here: the default is applied at search time.
        location["city"] = None
    else:
        location["city"] = city.strip()
    hard["location"] = location
    hard["category"] = _clean_category(hard.get("category"))
    hard["themes"] = _clean_text_list(hard.get("themes"), limit=MAX_THEMES)
    hard["amenities_required"] = _clean_text_list(
        hard.get("amenities_required"), limit=MAX_AMENITIES)
    hard["age_max"] = _clean_age_max(hard.get("age_max"))
    hard["min_rating"] = _clean_rating(hard.get("min_rating"))
    hard["event_count"] = _clean_event_count(hard.get("event_count"))
    negative = data.get("negative_filters") or {}
    for key in ("exclude_categories", "exclude_tags", "exclude_districts"):
        negative[key] = _clean_text_list(
            negative.get(key), limit=MAX_NEGATIVE_FILTERS)
    data["negative_filters"] = negative
    if hard.get("datetime") is not None and not hard["datetime"].get("timezone"):
        hard["datetime"]["timezone"] = settings.default_timezone
    if hard.get("datetime") is not None and hard["datetime"].get("any"):
        hard["datetime"]["start"] = None
        hard["datetime"]["end"] = None
    if hard.get("datetime") is not None:
        _normalize_time_of_day(hard["datetime"])
    budget = hard.get("budget")
    if budget is not None:
        if not budget.get("currency"):
            budget["currency"] = settings.default_currency
        basis = str(budget.get("basis") or "per_person").strip().lower()
        budget["basis"] = (basis if basis in ("per_person", "total")
                           else "per_person")
        if budget.get("any"):
            budget["max_price_per_person"] = None
            budget["total"] = None
            budget["basis"] = "per_person"
        elif budget["basis"] == "total":
            # "40 рублей на двоих" is a total for the group. Keep the total
            # (the frontend shows "до 40 на всех") and derive the per-person
            # ceiling. Always recompute from `total`, never from the already
            # divided value: sanitize runs on every turn and must be
            # idempotent. Legacy clients that send only
            # `max_price_per_person` with basis=total are read as a total.
            total = _clean_price(budget.get("total"))
            if total is None:
                total = _clean_price(budget.get("max_price_per_person"))
            budget["total"] = total
            party = hard.get("party_size")
            if not (isinstance(party, int)
                    and PARTY_SIZE_MIN <= party <= PARTY_SIZE_MAX):
                # No named party: split by the configured default (1), not
                # by a guessed party. Banner text still shows the true total.
                party = settings.default_party_size
            budget["max_price_per_person"] = (
                round(total / party, 2) if total is not None else None)
        else:
            budget["total"] = None
            budget["max_price_per_person"] = _clean_price(
                budget.get("max_price_per_person"))
    payload = data["semantic_payload"]
    # Presentation locale only: retrieval text and Qdrant stay Russian.
    payload["language"] = _clean_language(payload.get("language"))
    payload["target_collection"] = _clean_target_collection(
        payload.get("target_collection"))
    raw_vector = payload.get("vector_query")
    payload["vector_query"] = (
        raw_vector.strip()[:MAX_VECTOR_QUERY]
        if isinstance(raw_vector, str) else "")
    context = data["context_state"]
    session_id = context.get("session_id")
    session_id = (session_id.strip()[:MAX_SESSION_ID]
                  if isinstance(session_id, str) else "")
    context["session_id"] = session_id or ANONYMOUS_SESSION
    context["shown_ids"] = _clean_ids(context.get("shown_ids"),
                                      limit=MAX_SHOWN_IDS,
                                      max_len=MAX_SHOWN_ID)
    context["turn_count"] = max(1, int(context.get("turn_count") or 1)) + 1
    # Server owns the clarification flags; the client suggestion is advisory.
    data["needs_clarification"] = False
    data["clarification_prompt"] = None
    return StateContract.model_validate(data)
