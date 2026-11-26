"""Hold DTOs."""
from __future__ import annotations

from pydantic import BaseModel, Field


class HoldRequest(BaseModel):
    session_id: str = Field(min_length=1)
    event_id: int = Field(gt=0)
    zone: str = "BASIC"
    price: float = Field(default=0.0, ge=0)
    party_size: int = Field(default=1, ge=1, le=20)


class HoldResponse(BaseModel):
    id: str
    session_id: str
    event_id: int
    zone: str
    price: float
    party_size: int
    status: str

    @classmethod
    def from_hold(cls, hold) -> "HoldResponse":
        return cls(
            id=hold.id, session_id=hold.session_id, event_id=hold.event_id,
            zone=hold.zone, price=hold.price,
            party_size=hold.party_size, status=hold.status,
        )


class SweepResponse(BaseModel):
    expired: int
