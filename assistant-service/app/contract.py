"""StateContract: the dialogue state owned by the client, validated here.

The server never trusts the contract blindly: unknown fields are dropped,
enums are validated, numeric slots are clamped, and the turn counter is
bumped server-side. This is the prompt-injection checkpoint.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


DialogueAction = Literal["search", "update_filters", "confirm_booking", "ask_clarification"]


class DateTimeFilter(StrictModel):
    start: str | None = None
    end: str | None = None
    timezone: str = "Europe/Minsk"
    is_relative: bool = False
    raw_expression: str | None = None


class GeoRadius(StrictModel):
    latitude: float | None = None
    longitude: float | None = None
    radius_meters: int | None = None


class LocationFilter(StrictModel):
    city: str = "Минск"
    districts: list[str] = Field(default_factory=list)
    landmarks: list[str] = Field(default_factory=list)
    geo_radius: GeoRadius | None = None


class BudgetFilter(StrictModel):
    level: str | None = None
    currency: str = "BYN"
    max_price_per_person: float | None = None


class HardFilters(StrictModel):
    datetime: DateTimeFilter | None = None
    location: LocationFilter = Field(default_factory=LocationFilter)
    category: list[str] = Field(default_factory=list)
    party_size: int = 2
    budget: BudgetFilter | None = None
    amenities_required: list[str] = Field(default_factory=list)


class NegativeFilters(StrictModel):
    exclude_categories: list[str] = Field(default_factory=list)
    exclude_tags: list[str] = Field(default_factory=list)
    exclude_districts: list[str] = Field(default_factory=list)


class SemanticPayload(StrictModel):
    vector_query: str = ""
    target_collection: str | None = None
    language: str = "ru"


class ContextState(StrictModel):
    turn_count: int = 1
    active_filters_changed: list[str] = Field(default_factory=list)
    session_id: str = "client_session"


class StateContract(StrictModel):
    dialogue_action: DialogueAction = "search"
    needs_clarification: bool = False
    clarification_prompt: str | None = None
    hard_filters: HardFilters = Field(default_factory=HardFilters)
    negative_filters: NegativeFilters = Field(default_factory=NegativeFilters)
    semantic_payload: SemanticPayload = Field(default_factory=SemanticPayload)
    context_state: ContextState = Field(default_factory=ContextState)


def sanitize(contract: StateContract) -> StateContract:
    """Server-side normalization after validation."""
    data = contract.model_dump()
    hard = data["hard_filters"]
    hard["party_size"] = max(1, min(20, int(hard.get("party_size") or 2)))
    if not (hard.get("location") or {}).get("city"):
        hard["location"]["city"] = "Минск"
    data["context_state"]["turn_count"] = max(1, int(data["context_state"].get("turn_count") or 1)) + 1
    # Server owns the clarification flags; the client suggestion is advisory.
    data["needs_clarification"] = False
    data["clarification_prompt"] = None
    return StateContract.model_validate(data)
