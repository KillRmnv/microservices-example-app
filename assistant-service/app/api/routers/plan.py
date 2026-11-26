"""Plan controller: explicit evening-itinerary generation (reasoning LLM)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_components
from ..schemas.dialogue import DialogResponse
from ..schemas.plan import PlanRequest
from ...core.rate_limit import rate_limit

router = APIRouter(prefix="/assistant", tags=["dialogue"])


@router.post("/plan", response_model=DialogResponse,
             dependencies=[Depends(rate_limit("plan"))])
async def build_plan(request: PlanRequest) -> DialogResponse:
    return await get_components().plan.build_plan(request.contract,
                                                  request.contexts)
