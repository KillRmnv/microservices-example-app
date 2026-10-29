"""Plan controller: explicit evening-itinerary generation (reasoning LLM)."""
from __future__ import annotations

from fastapi import APIRouter

from ..deps import get_components
from ..schemas.dialogue import DialogResponse
from ..schemas.plan import PlanRequest

router = APIRouter(prefix="/assistant", tags=["dialogue"])


@router.post("/plan", response_model=DialogResponse)
async def build_plan(request: PlanRequest) -> DialogResponse:
    return await get_components().plan.build_plan(request.contract)
