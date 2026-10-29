"""Filter specification contract.

A spec knows how to express itself in every execution backend (Qdrant payload,
collector SQL parameters) and how to post-filter a fused hit. New filters are
added as small classes instead of growing conditionals in the search service.
"""
from __future__ import annotations

from abc import ABC
from typing import Any

from ..models.search import FusedHit


class Filter(ABC):
    def qdrant_must(self) -> dict[str, Any]:
        return {}

    def lexical_params(self) -> dict[str, Any]:
        return {}

    def matches(self, hit: FusedHit) -> bool:
        return True
