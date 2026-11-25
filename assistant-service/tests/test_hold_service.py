import types

import pytest

from app.core import db
from app.errors import (
    ConflictError,
    HoldGone,
    NotEnoughSeats,
    PriceMismatch,
    ValidationError,
)
from app.models.availability import FEW_LEFT, SOLD_OUT, Availability
from app.models.hold import EXPIRED
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


@pytest.mark.asyncio
async def test_party_larger_than_zone_count_is_rejected(database_url):
    service = HoldService(database_url, FakeBooking())
    with pytest.raises(NotEnoughSeats) as exc:
        await service.create(session_id="s5", event_id=7, zone="VIP",
                             price=120.0, party_size=3)
    assert exc.value.code == "not_enough_seats"


@pytest.mark.asyncio
async def test_party_equal_to_zone_count_is_allowed(database_url):
    service = HoldService(database_url, FakeBooking())
    hold = await service.create(session_id="s6", event_id=7, zone="VIP",
                                price=120.0, party_size=2)
    assert hold.party_size == 2


@pytest.mark.asyncio
async def test_expired_pending_hold_is_replaced(database_url):
    service = HoldService(database_url, FakeBooking())
    stale = await service.create(session_id="renew", event_id=11, zone="VIP",
                                 price=120.0, party_size=1)
    with db.get_conn(database_url) as conn:
        conn.execute(
            "UPDATE booking_holds SET created_at = now() - make_interval(mins => 20),"
            " expires_at = now() - make_interval(mins => 10)"
            " WHERE id = %s",
            (stale.id,),
        )
        conn.commit()
    fresh = await service.create(session_id="renew", event_id=11, zone="VIP",
                                 price=120.0, party_size=1)
    assert fresh.id != stale.id
    assert fresh.status == "PENDING"
    with db.get_conn(database_url) as conn:
        rows = conn.execute(
            "SELECT id, status FROM booking_holds WHERE session_id = 'renew'"
        ).fetchall()
    statuses = {str(row["id"]): row["status"] for row in rows}
    assert statuses[str(stale.id)] == EXPIRED
    assert statuses[str(fresh.id)] == "PENDING"
    assert list(statuses.values()).count("PENDING") == 1


def test_sweep_job_is_scheduled_to_run_on_boot(monkeypatch):
    from app import scheduler as scheduler_module
    from app.core.config import settings

    class FakeScheduler:
        def __init__(self):
            self.jobs = []

        def add_job(self, func, trigger, **kwargs):
            self.jobs.append(kwargs)

        def start(self):
            pass

    monkeypatch.setattr(scheduler_module, "AsyncIOScheduler", FakeScheduler)
    monkeypatch.setattr(settings, "scheduler_enabled", True)
    fake_app = types.SimpleNamespace(state=types.SimpleNamespace())
    scheduler_module.start_scheduler(fake_app)
    (job,) = fake_app.state.scheduler.jobs
    assert job["next_run_time"] is not None
    assert job["max_instances"] == 1
    assert job["coalesce"] is True
