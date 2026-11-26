"""Optional reranking hook for hybrid search results.

The interface is deliberately tiny: a provider receives the user query and
the ranked candidates and returns them in its own order. It runs after the
fused ordering and tie-break boosts, so it can override both. No model is
wired in yet — ``NoopReranker`` keeps the incoming order and is the default,
so ``ASSISTANT_RERANK_ENABLED=false`` costs nothing.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models.search import FusedHit


@runtime_checkable
class Reranker(Protocol):
    """Reorders candidate hits; must return the same ids (may drop some)."""

    async def rerank(self, query: str, hits: list[FusedHit]) -> list[FusedHit]:
        ...


class NoopReranker:
    """Keeps the fused order (the default provider)."""

    async def rerank(self, query: str, hits: list[FusedHit]) -> list[FusedHit]:
        return hits
