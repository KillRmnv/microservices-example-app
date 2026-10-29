"""Ordered filter pipeline: one backend pass, one post-filter pass."""
from __future__ import annotations

from typing import Any

from ..models.search import FusedHit
from .base import Filter


class FilterPipeline:
    def __init__(self, filters: list[Filter] | None = None) -> None:
        self._filters = filters or []

    def add(self, specification: Filter) -> "FilterPipeline":
        self._filters.append(specification)
        return self

    def qdrant_must(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for specification in self._filters:
            merged.update(specification.qdrant_must())
        return merged

    def lexical_params(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for specification in self._filters:
            merged.update(specification.lexical_params())
        return merged

    def matches(self, hit: FusedHit) -> bool:
        return all(specification.matches(hit) for specification in self._filters)

    def apply(self, hits: list[FusedHit]) -> list[FusedHit]:
        """Single pass over the fused candidates."""
        return [hit for hit in hits if self.matches(hit)]
