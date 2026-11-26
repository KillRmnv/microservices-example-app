"""Concurrency regressions for local booking holds."""
from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core import db
from app.errors import HoldGone
from app.models.availability import FEW_LEFT, Availability
from app.services.hold_service import HoldService


class BarrierBooking:
    def __init__(self) -> None:
        self.barrier = asyncio.Barrier(2)

    async def check_availability(self, event_id):
        await self.barrier.wait()
        return Availability(event_id=event_id, status=FEW_LEFT, zones=[
            {"zone": "VIP", "count": 2, "min_price": 100.0},
        ])


class FastBooking:
    async def check_availability(self, event_id):
        return Availability(event_id=event_id, status=FEW_LEFT, zones=[
            {"zone": "VIP", "count": 2, "min_price": 100.0},
        ])


@pytest.mark.asyncio
async def test_parallel_hold_create_returns_one_hold(database_url):
    service = HoldService(database_url, BarrierBooking())
    first, second = await asyncio.gather(
        service.create(session_id="race", event_id=7, zone="VIP",
                       price=120.0, party_size=2),
        service.create(session_id="race", event_id=7, zone="VIP",
                       price=120.0, party_size=2),
    )
    assert first.id == second.id
    with db.get_conn(database_url) as conn:
        count = conn.execute(
            "SELECT count(*) AS n FROM booking_holds").fetchone()["n"]
    assert count == 1


@pytest.mark.asyncio
async def test_parallel_confirm_transitions_only_once(database_url):
    service = HoldService(database_url, FastBooking())
    hold = await service.create(session_id="confirm-race", event_id=8,
                                zone="VIP", price=120.0, party_size=1)
    barrier = threading.Barrier(8)

    def confirm():
        barrier.wait(timeout=10)
        try:
            return service.confirm(hold.id)
        except HoldGone:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: confirm(), range(8)))

    confirmed = [item for item in results if item is not None]
    assert len(confirmed) == 1
    with db.get_conn(database_url) as conn:
        row = conn.execute(
            "SELECT status FROM booking_holds WHERE id = %s",
            (hold.id,)).fetchone()
    assert row["status"] == "CONFIRMED"
