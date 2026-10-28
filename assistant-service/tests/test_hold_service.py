import pytest

from app.errors import ConflictError, HoldGone, PriceMismatch, ValidationError
from app.models.availability import FEW_LEFT, SOLD_OUT, Availability
from app.services.hold_service import HoldService


class FakeBooking:
    def __init__(self, status=FEW_LEFT, zones=None):
        self.status = status
        self.zones = zones if zones is not None else [
            {"zone": "VIP", "count": 2, "min_price": 100.0},
            {"zone": "BASIC", "count": 5, "min_price": 50.0},
        ]

    async def check_availability(self, event_id):
        return Availability(event_id=event_id, status=self.status,
                            zones=self.zones)


@pytest.mark.asyncio
async def test_create_validates_and_is_idempotent(database_url):
    service = HoldService(database_url, FakeBooking())
    first = await service.create(session_id="s1", event_id=7, zone="VIP",
                                 price=120.0, party_size=2)
    assert first.status == "PENDING"
    second = await service.create(session_id="s1", event_id=7, zone="VIP",
                                  price=120.0, party_size=2)
    assert second.id == first.id


@pytest.mark.asyncio
async def test_price_below_zone_minimum_is_rejected(database_url):
    service = HoldService(database_url, FakeBooking())
    with pytest.raises(PriceMismatch):
        await service.create(session_id="s2", event_id=7, zone="VIP",
                             price=10.0, party_size=1)


@pytest.mark.asyncio
async def test_unknown_zone_is_rejected(database_url):
    service = HoldService(database_url, FakeBooking())
    with pytest.raises(ValidationError):
        await service.create(session_id="s3", event_id=7, zone="BALCONY",
                             price=120.0, party_size=1)


@pytest.mark.asyncio
async def test_sold_out_event_is_rejected(database_url):
    service = HoldService(database_url, FakeBooking(status=SOLD_OUT, zones=[]))
    with pytest.raises(ConflictError):
        await service.create(session_id="s4", event_id=7, zone="VIP",
                             price=120.0, party_size=1)


def test_confirm_missing_hold_raises_gone(database_url):
    service = HoldService(database_url, FakeBooking())
    with pytest.raises(HoldGone):
        service.confirm("00000000-0000-0000-0000-000000000000")
