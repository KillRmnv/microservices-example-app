import httpx
import pytest

from app.clients.booking import BookingClient, availability_key


class FakeAvailabilityCache:
    """In-memory stand-in for the Redis availability cache."""

    def __init__(self) -> None:
        self.data: dict[str, dict] = {}
        self.sets = 0

    async def get(self, key: str) -> dict | None:
        return self.data.get(key)

    async def set(self, key: str, value: dict, ttl_s: int) -> None:
        self.sets += 1
        self.data[key] = value

    async def close(self) -> None:
        self.data.clear()


def make_client(status: str = "available"):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={
            "status": status,
            "capacity": 100,
            "zones": [{"zone": "BASIC", "seatsLeft": 5, "minPrice": 30.0}],
        })

    cache = FakeAvailabilityCache()
    client = BookingClient(
        "http://booking:8082", transport=httpx.MockTransport(handler),
        availability_cache=cache, availability_ttl_s=30)
    return client, cache, calls


def test_availability_key_uses_party_or_zero():
    assert availability_key(7, 2) == "availability:7:2"
    assert availability_key(7, None) == "availability:7:0"


@pytest.mark.asyncio
async def test_second_identical_call_makes_no_http():
    client, cache, calls = make_client()
    first = await client.check_availability(7, 2)
    second = await client.check_availability(7, 2)
    assert len(calls) == 1
    assert cache.sets == 1
    assert second.status == "available"
    assert second.seats_left == 5
    assert second.zones[0]["min_price"] == 30.0
    assert first.status == second.status


@pytest.mark.asyncio
async def test_different_party_size_misses_the_cache():
    client, cache, calls = make_client()
    await client.check_availability(7, 2)
    await client.check_availability(7, 4)
    assert len(calls) == 2
    assert cache.sets == 2


@pytest.mark.asyncio
async def test_unknown_status_is_never_cached():
    client, cache, calls = make_client(status="unknown")
    assert (await client.check_availability(7, 2)).status == "unknown"
    assert (await client.check_availability(7, 2)).status == "unknown"
    assert len(calls) == 2
    assert cache.sets == 0


@pytest.mark.asyncio
async def test_cache_hits_return_fresh_copies():
    client, _cache, calls = make_client()
    first = await client.check_availability(7, 2)
    first.zones[0]["seats_left"] = 999
    first.status = "sold_out"
    second = await client.check_availability(7, 2)
    assert len(calls) == 1
    assert second.status == "available"
    assert second.zones[0]["seats_left"] == 5


@pytest.mark.asyncio
async def test_client_without_cache_still_works():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"status": "available"})

    client = BookingClient("http://booking:8082",
                           transport=httpx.MockTransport(handler))
    assert (await client.check_availability(7)).status == "available"
    assert (await client.check_availability(7)).status == "available"
    assert len(calls) == 2
