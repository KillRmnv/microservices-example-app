"""Search domain models shared by services and the API layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FusedHit:
    id: str
    score: float
    origins: list[str] = field(default_factory=list)
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PayloadDateRange:
    """Backend-neutral date range pushed into the payload condition."""

    gte: str | None = None
    lt: str | None = None


@dataclass
class SearchPlan:
    """One search request after the contract has been mapped to filters."""

    vector_query: str
    limit: int
    city: str | None = None
    categories: list[str] = field(default_factory=list)
    rubric: str | None = None
    max_price_per_person: float | None = None
    exclude_categories: list[str] = field(default_factory=list)
    exclude_tags: list[str] = field(default_factory=list)
    # Card ids already shown in the dialogue ("ещё" pagination).
    exclude_ids: list[str] = field(default_factory=list)
    date_from: datetime | None = None
    date_to: datetime | None = None
    # Venue-hours filtering needs the requested window in the user's zone.
    timezone: str | None = None
    # Hard constraints from the contract (0/None = "any").
    party_size: int | None = None
    age_max: int | None = None
    min_rating: float | None = None
    # Structured exclusion (payload `amenities` only) — weather-driven.
    exclude_amenities: list[str] = field(default_factory=list)
    # Theme expansions are a sparse/BM25 signal, not a dense-only hint.
    themes: list[str] = field(default_factory=list)
    # Long theme expansions are noisy in sparse search; use dense+threshold.
    dense_only: bool = False
    # Category-only, undated search: announcements without `start_at` are
    # allowed and ranked after dated hits. Only set when the user named no
    # date and the category is explicit (see DialogueService._search_plan).
    include_undated: bool = False
