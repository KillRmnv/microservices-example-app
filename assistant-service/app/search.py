"""Hybrid event search: embed query -> Qdrant dense + collector lexical -> RRF."""
from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException
from pydantic import BaseModel

from .config import settings
from .embeddings import LlamaServerEmbedding
from .hybrid import FusedHit, fuse_search
from .vector import QdrantStore

log = logging.getLogger(__name__)


class SearchRequest(BaseModel):
    vector_query: str
    city: str | None = None
    category: str | None = None
    max_price_per_person: float | None = None
    limit: int = 10


class SearchHit(BaseModel):
    event_id: str
    title: str
    score: float
    origins: list[str]


class VenueSearchRequest(BaseModel):
    vector_query: str
    city: str | None = None
    rubric: str | None = None
    limit: int = 10


class VenueHit(BaseModel):
    venue_id: str
    name: str
    rubric: str
    address: str
    score: float
    origins: list[str]


async def hybrid_search_venues(embedder, store, collector: CollectorClient,
                               req: VenueSearchRequest) -> list[FusedHit]:
    must = {}
    if req.city:
        must["city"] = req.city
    if req.rubric:
        must["rubric"] = req.rubric
    dense = []
    if req.vector_query.strip():
        try:
            query_vector = (await embedder.embed([req.vector_query]))[0]
            dense = await store.search(query_vector, req.limit * 2, must or None)
        except Exception as exc:  # noqa: BLE001 — dense optional, lexical is not
            log.warning("venues dense search failed, lexical only: %s", exc)
    try:
        lexical = await collector.search_venues_lexical(
            req.vector_query, req.city, req.rubric, req.limit * 2)
    except Exception as exc:
        log.warning("venues lexical search failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"collector search failed: {exc}") from exc
    dense_ids = [(hit.id, {"name": hit.payload.get("name", "")}) for hit in dense]
    lexical_ids = [str(row["id"]) for row in lexical]
    names = {str(row["id"]): (row.get("name", ""), row.get("rubric", ""),
                              row.get("address", "")) for row in lexical}
    fused = fuse_search(dense_ids, lexical_ids, req.limit)
    for hit in fused:
        if hit.id in names:
            name, rubric, address = names[hit.id]
            if not hit.payload.get("name"):
                hit.payload["name"] = name
            hit.payload.setdefault("rubric", rubric)
            hit.payload.setdefault("address", address)
    return fused


class CollectorClient:
    """Thin wrapper over collector read endpoints (fakeable in tests)."""

    def __init__(self, base_url: str, transport: httpx.BaseTransport | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._transport = transport

    async def search_lexical(self, query: str, city: str | None,
                             category: str | None, limit: int) -> list[dict]:
        params = {"q": query, "limit": limit}
        if city:
            params["city"] = city
        if category:
            params["category"] = category
        async with httpx.AsyncClient(base_url=self._base, timeout=15.0,
                                     transport=self._transport) as client:
            response = await client.get("/events/search", params=params)
            response.raise_for_status()
            return response.json()["events"]

    async def search_venues_lexical(self, query: str, city: str | None,
                                    rubric: str | None, limit: int) -> list[dict]:
        params = {"q": query, "limit": limit}
        if city:
            params["city"] = city
        if rubric:
            params["rubric"] = rubric
        async with httpx.AsyncClient(base_url=self._base, timeout=15.0,
                                     transport=self._transport) as client:
            response = await client.get("/venues/search", params=params)
            response.raise_for_status()
            return response.json()["venues"]


async def hybrid_search(embedder, store, collector: CollectorClient,
                        req: SearchRequest) -> list[FusedHit]:
    must = {}
    if req.city:
        must["city"] = req.city
    if req.category:
        must["category"] = req.category
    dense = []
    if req.vector_query.strip():
        try:
            query_vector = (await embedder.embed([req.vector_query]))[0]
            dense = await store.search(query_vector, req.limit * 2, must or None)
        except Exception as exc:  # noqa: BLE001 — dense is optional, lexical is not
            log.warning("dense search failed, lexical only: %s", exc)
    try:
        lexical = await collector.search_lexical(req.vector_query, req.city,
                                                 req.category, req.limit * 2)
    except Exception as exc:
        log.warning("lexical search failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"collector search failed: {exc}") from exc
    dense_ids = [(hit.id, {"title": hit.payload.get("title", "")}) for hit in dense]
    lexical_ids = [str(row["id"]) for row in lexical]
    titles = {str(row["id"]): row.get("title", "") for row in lexical}
    prices = {str(row["id"]): row.get("price_min") for row in lexical}
    fused = fuse_search(dense_ids, lexical_ids, req.limit * 2)
    if req.max_price_per_person is not None:
        fused = [hit for hit in fused
                 if (price := prices.get(hit.id)) is None
                 or float(price) <= req.max_price_per_person]
    fused = fused[:req.limit]
    for hit in fused:
        if not hit.payload.get("title") and hit.id in titles:
            hit.payload["title"] = titles[hit.id]
    return fused


def build_search_components(transport: httpx.BaseTransport | None = None,
                            venues: bool = False):
    collection = (settings.qdrant_collection_venues
                  if venues else settings.qdrant_collection)
    return (
        LlamaServerEmbedding(settings.llama_embed_url),
        QdrantStore(settings.qdrant_url, collection),
        CollectorClient(settings.collector_base_url, transport=transport),
    )
