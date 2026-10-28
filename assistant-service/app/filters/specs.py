"""Concrete filter specifications."""
from __future__ import annotations

from collections.abc import Mapping

from ..models.search import FusedHit
from .base import Filter


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
