"""Catalog search controllers."""
from __future__ import annotations

from fastapi import APIRouter

from ..deps import get_components
from ..schemas.search import (
    SearchHit,
    SearchRequest,
    VenueHit,
    VenueSearchRequest,
)
from ...models.search import SearchPlan

router = APIRouter(prefix="/assistant", tags=["search"])


@router.post("/search", response_model=list[SearchHit])
async def search(req: SearchRequest) -> list[SearchHit]:
    categories = list(req.categories)
    if req.category and req.category not in categories:
        categories.append(req.category)
    plan = SearchPlan(vector_query=req.vector_query, limit=req.limit,
                      city=req.city, categories=categories,
                      max_price_per_person=req.max_price_per_person)
    fused = await get_components().search_events.events(plan)
    return [SearchHit(event_id=hit.id, title=hit.payload.get("title", ""),
                      score=hit.score, origins=hit.origins)
            for hit in fused]


@router.post("/search_venues", response_model=list[VenueHit])
async def search_venues(req: VenueSearchRequest) -> list[VenueHit]:
    plan = SearchPlan(vector_query=req.vector_query, limit=req.limit,
                      city=req.city, rubric=req.rubric)
    fused = await get_components().search_venues.venues(plan)
    return [VenueHit(venue_id=hit.id, name=hit.payload.get("name", ""),
                     rubric=hit.payload.get("rubric", ""),
                     address=hit.payload.get("address", ""),
                     score=hit.score, origins=hit.origins)
            for hit in fused]
