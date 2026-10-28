"""Booking hold controllers."""
from __future__ import annotations

from fastapi import APIRouter, status

from ..deps import get_components
from ..schemas.holds import HoldRequest, HoldResponse, SweepResponse

router = APIRouter(prefix="/assistant/holds", tags=["holds"])


@router.post("", status_code=status.HTTP_201_CREATED,
             response_model=HoldResponse)
async def create_hold(req: HoldRequest) -> HoldResponse:
    hold = await get_components().holds.create(
        session_id=req.session_id, event_id=req.event_id, zone=req.zone,
        price=req.price, party_size=req.party_size)
    return HoldResponse.from_hold(hold)


@router.post("/sweep", response_model=SweepResponse)
def sweep_holds() -> SweepResponse:
    return SweepResponse(expired=get_components().holds.sweep())


@router.post("/{hold_id}/confirm", response_model=HoldResponse)
def confirm_hold(hold_id: str) -> HoldResponse:
    return HoldResponse.from_hold(get_components().holds.confirm(hold_id))
