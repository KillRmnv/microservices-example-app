"""StateContract DTO: the dialogue state owned by the client.

The server never trusts it blindly: unknown fields are dropped, enums are
validated, numeric slots are clamped, and domain defaults (city, timezone,
currency, language) are filled from configuration, not from hardcoded values.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ...core.config import settings

PARTY_SIZE_MIN = 1
PARTY_SIZE_MAX = 20
ANONYMOUS_SESSION = "anonymous"


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
    max_price_per_person: float | None = None
    any: bool = False


class HardFilters(StrictModel):
    datetime: DateTimeFilter | None = None
    location: LocationFilter = Field(default_factory=LocationFilter)
    category: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    party_size: int | None = None
    budget: BudgetFilter | None = None
    amenities_required: list[str] = Field(default_factory=list)


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
    if location.get("any"):
        location["city"] = None
    elif not location.get("city"):
        location["city"] = None
    hard["location"] = location
    themes = hard.get("themes")
    hard["themes"] = ([str(theme).strip().lower() for theme in themes
                       if str(theme).strip()][:5]
                      if isinstance(themes, list) else [])
    if hard.get("datetime") is not None and not hard["datetime"].get("timezone"):
        hard["datetime"]["timezone"] = settings.default_timezone
    if hard.get("datetime") is not None and hard["datetime"].get("any"):
        hard["datetime"]["start"] = None
        hard["datetime"]["end"] = None
    budget = hard.get("budget")
    if budget is not None and not budget.get("currency"):
        budget["currency"] = settings.default_currency
    payload = data["semantic_payload"]
    if not payload.get("language"):
        payload["language"] = settings.default_language
    context = data["context_state"]
    if not context.get("session_id"):
        context["session_id"] = ANONYMOUS_SESSION
    context["turn_count"] = max(1, int(context.get("turn_count") or 1)) + 1
    # Server owns the clarification flags; the client suggestion is advisory.
    data["needs_clarification"] = False
    data["clarification_prompt"] = None
    return StateContract.model_validate(data)
