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
    def __init__(self, categories: str | list[str]) -> None:
        self._categories = ([categories] if isinstance(categories, str)
                            else list(categories))

    def qdrant_must(self):
        return {"category": self._categories}

    def lexical_params(self):
        return {"categories": self._categories}

    def matches(self, hit: FusedHit) -> bool:
        value = hit.payload.get("category")
        return value is None or value in self._categories


class DateRangeFilter(Filter):
    """Only events overlapping [from, to).

    Multi-day events (a dolphinarium running for a month) must match a query
    for any day inside their period, not only the start date. Events without
    `start_at` are dropped when the user named a date: a scraped post without
    a date cannot be promised for that evening.

    `end` is optional: the future floor only needs "not finished before now",
    so a query without an explicit date keeps every event still running.
    """

    def __init__(self, start: datetime, end: datetime | None = None) -> None:
        self._start = start
        self._end = end

    def qdrant_must(self) -> dict[str, PayloadDateRange]:
        # start_at < query_end (only with an end) AND end_at >= query_start.
        # Payload stores end_at = start_at for single-day events.
        must: dict[str, PayloadDateRange] = {
            "end_at": PayloadDateRange(gte=self._start.isoformat()),
        }
        if self._end is not None:
            must["start_at"] = PayloadDateRange(lt=self._end.isoformat())
        return must

    def lexical_params(self) -> dict[str, str]:
        params = {"date_from": self._start.isoformat()}
        if self._end is not None:
            params["date_to"] = self._end.isoformat()
        return params

    def matches(self, hit: FusedHit) -> bool:
        start = _parse_datetime(hit.payload.get("start_at"))
        if start is None:
            return False
        if self._end is not None and start >= self._end:
            return False
        end = _parse_datetime(hit.payload.get("end_at")) or start
        return end >= self._start


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
        self._categories = [str(category) for category in categories]
        self._folded = {category.casefold() for category in self._categories}

    def qdrant_must_not(self) -> dict[str, list[str]]:
        return {"category": self._categories}

    def matches(self, hit: FusedHit) -> bool:
        category = str(hit.payload.get("category") or "").casefold()
        return category not in self._folded


# Payload fields that carry free text the user may want excluded. Scraped
# events put the whole embedding text into `search_text`; venue rows use
# `name`/`rubric`/`address` instead.
_TAG_TEXT_FIELDS = ("search_text", "title", "description", "venue", "name",
                    "rubric", "address")
# "кальяна" must match "кальян": compare a short prefix as well as the
# whole normalised tag. Six characters covers RU noun endings for words of
# that length; shorter tags are matched verbatim only.
_TAG_STEM_CHARS = 6


def _normalise_tag(tag: str) -> str:
    """`loud_music`/`loud-music` -> `loud music`; lowercase and trim."""
    text = str(tag or "").casefold().replace("_", " ").replace("-", " ")
    return " ".join(text.split())


def _tag_haystack(payload: Mapping) -> str:
    parts = [str(payload.get(field) or "") for field in _TAG_TEXT_FIELDS]
    return " ".join(part for part in parts if part).casefold()


class ExcludeTagsFilter(Filter):
    """Post-filter: drop hits mentioning a forbidden tag.

    Qdrant cannot exclude a token inside free text, so this stays in Python.
    Payload text is searched case-insensitively for the whole tag and for a
    short stem, which absorbs RU inflections ("без кальяна" -> "кальян").
    """

    def __init__(self, tags: list[str]) -> None:
        self._tags: list[tuple[str, str | None]] = []
        for tag in tags:
            normalised = _normalise_tag(tag)
            if not normalised:
                continue
            stem = (normalised[:_TAG_STEM_CHARS]
                    if len(normalised) > _TAG_STEM_CHARS else None)
            self._tags.append((normalised, stem))

    def matches(self, hit: FusedHit) -> bool:
        if not self._tags:
            return True
        haystack = _tag_haystack(hit.payload)
        for tag, stem in self._tags:
            if tag in haystack or (stem is not None and stem in haystack):
                return False
        return True
