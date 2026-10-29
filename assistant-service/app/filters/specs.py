"""Concrete filter specifications."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from ..models.search import FusedHit, PayloadDateRange
from .base import Filter


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


class CityFilter(Filter):
    def __init__(self, city: str) -> None:
        self._city = city

    def qdrant_must(self) -> dict[str, str]:
        return {"city": self._city}

    def lexical_params(self) -> dict[str, str]:
        return {"city": self._city}

    def matches(self, hit: FusedHit) -> bool:
        value = hit.payload.get("city")
        return value is None or value == self._city


class CategoryFilter(Filter):
    def __init__(self, category: str) -> None:
        self._category = category

    def qdrant_must(self) -> dict[str, str]:
        return {"category": self._category}

    def lexical_params(self) -> dict[str, str]:
        return {"category": self._category}

    def matches(self, hit: FusedHit) -> bool:
        value = hit.payload.get("category")
        return value is None or value == self._category


class DateRangeFilter(Filter):
    """Only events inside [from, to) — requested dates must be respected.

    Events without `start_at` are dropped when the user named a date: a
    scraped post without a date cannot be promised for that evening.
    """

    def __init__(self, start: datetime, end: datetime) -> None:
        self._start = start
        self._end = end

    def qdrant_must(self) -> dict[str, PayloadDateRange]:
        return {"start_at": PayloadDateRange(
            gte=self._start.isoformat(), lt=self._end.isoformat())}

    def lexical_params(self) -> dict[str, str]:
        return {"date_from": self._start.isoformat(),
                "date_to": self._end.isoformat()}

    def matches(self, hit: FusedHit) -> bool:
        value = _parse_datetime(hit.payload.get("start_at"))
        return value is not None and self._start <= value < self._end


class RubricFilter(Filter):
    def __init__(self, rubric: str) -> None:
        self._rubric = rubric

    def qdrant_must(self) -> dict[str, str]:
        return {"rubric": self._rubric}

    def lexical_params(self) -> dict[str, str]:
        return {"rubric": self._rubric}

    def matches(self, hit: FusedHit) -> bool:
        value = hit.payload.get("rubric")
        return value is None or value == self._rubric


class MaxPriceFilter(Filter):
    """Post-filter using prices from the lexical rows (dense has no price)."""

    def __init__(self, max_price: float, prices: Mapping[str, float | None]) -> None:
        self._max = float(max_price)
        self._prices = prices

    def matches(self, hit: FusedHit) -> bool:
        price = self._prices.get(hit.id)
        return price is None or float(price) <= self._max


class ExcludeCategoriesFilter(Filter):
    def __init__(self, categories: list[str]) -> None:
        self._categories = {category.casefold() for category in categories}

    def matches(self, hit: FusedHit) -> bool:
        category = str(hit.payload.get("category") or "").casefold()
        return category not in self._categories
