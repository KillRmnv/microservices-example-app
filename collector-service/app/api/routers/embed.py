"""Embedding backfill controllers.

Declare ``/embed/venues`` before ``/embed/{source}``: otherwise the literal
path is swallowed by the path parameter.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from ..deps import get_collect_service, get_embed_service
from ..schemas import EmbedResponse, ReindexResponse
from ...errors import UnknownSource, ValidationError
from ...services.collect_service import CollectService
from ...services.embed_service import EmbedService

router = APIRouter(tags=["embed"])


@router.post("/embed/venues", response_model=EmbedResponse)
async def embed_venues(limit: int | None = None,
                       service: EmbedService = Depends(get_embed_service)) -> dict:
    started = time.monotonic()
    embedded, pending = await service.embed_venues(limit)
    return {"embedded": embedded, "pending": pending,
            "duration_s": round(time.monotonic() - started, 1)}


@router.post("/embed/reindex-hybrid", response_model=ReindexResponse)
async def reindex_hybrid(confirm: bool = False,
                         service: EmbedService = Depends(get_embed_service)) -> dict:
    """Backfill sparse vectors + payload into existing Qdrant points.

    Required once per collection created before hybrid search: Qdrant
    cannot add a sparse config to an existing collection in place.
    Dense vectors are preserved; only sparse/payload are merged.
    """
    if not confirm:
        raise ValidationError("reindex-hybrid requires ?confirm=true")
    started = time.monotonic()
    result = await service.reindex_hybrid()
    result["duration_s"] = round(time.monotonic() - started, 1)
    return result


@router.post("/embed/{source}", response_model=EmbedResponse)
async def embed_source(source: str, limit: int | None = None,
                       service: EmbedService = Depends(get_embed_service),
                       collect: CollectService = Depends(get_collect_service)) -> dict:
    if source != "all" and source not in collect.sources:
        raise UnknownSource(f"unknown source: {source}")
    started = time.monotonic()
    embedded, pending = await service.embed_events(source, limit)
    return {"source": source, "embedded": embedded, "pending": pending,
            "duration_s": round(time.monotonic() - started, 1)}
