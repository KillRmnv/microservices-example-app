"""Hybrid search fusion: dense (Qdrant) + lexical (collector tsvector).

Reciprocal Rank Fusion over id lists; hard filters never enter the vector
query — they are Qdrant payload filters and SQL WHERE clauses (course.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FusedHit:
    id: str
    score: float
    origins: list[str] = field(default_factory=list)
    payload: dict = field(default_factory=dict)


def rrf_fuse(rank_lists: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    """[(id, fused_score)] sorted desc. Each list is best-first."""
    fused: dict[str, float] = {}
    for ranking in rank_lists:
        for rank, doc_id in enumerate(ranking, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda item: item[1], reverse=True)


def fuse_search(dense_ids: list[tuple[str, dict]], lexical_ids: list[str],
                limit: int = 10) -> list[FusedHit]:
    """Merge dense hits (id, payload) with lexical id ranking."""
    dense_ranking = [doc_id for doc_id, _ in dense_ids]
    payloads = {doc_id: payload for doc_id, payload in dense_ids}
    fused = rrf_fuse([dense_ranking, lexical_ids])[:limit]
    hits = []
    for doc_id, score in fused:
        origins = []
        if doc_id in payloads:
            origins.append("dense")
        if doc_id in lexical_ids:
            origins.append("lexical")
        hits.append(FusedHit(id=doc_id, score=round(score, 4),
                             origins=origins, payload=payloads.get(doc_id, {})))
    return hits
