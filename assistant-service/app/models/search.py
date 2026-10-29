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

    gte: str
    lt: str


@dataclass
class SearchPlan:
    """One search request after the contract has been mapped to filters."""

    vector_query: str
    limit: int
    city: str | None = None
    category: str | None = None
    rubric: str | None = None
    max_price_per_person: float | None = None
    exclude_categories: list[str] = field(default_factory=list)
    date_from: datetime | None = None
    date_to: datetime | None = None
