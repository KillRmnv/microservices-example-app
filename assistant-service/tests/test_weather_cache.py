import pytest

from app.clients.cache import NullWeatherCache
from app.models.weather import Weather
from app.services.weather_service import WeatherService


class FakeCache:
    def __init__(self):
        self.fresh = {}
        self.stale = {}

    async def get(self, key):
        return self.fresh.get(key)

    async def get_stale(self, key):
        return self.stale.get(key)

    async def set(self, key, value, ttl_s):
        self.fresh[key] = value
        self.stale[key] = value

    async def close(self):
        pass


class FakeClient:
    def __init__(self, weather=None, down=False):
        self.calls = 0
        self.down = down
        self.weather = weather or Weather(date="2026-10-24", temp_max=10,
                                          precipitation_probability=5,
                                          weathercode=1)

    async def forecast(self, date, lat, lon):
        self.calls += 1
        return None if self.down else self.weather


def make_service(client, cache) -> WeatherService:
    return WeatherService(client, cache, ttl_s=600, timezone="Europe/Minsk")


@pytest.mark.asyncio
async def test_second_call_is_served_from_cache():
    client, cache = FakeClient(), FakeCache()
    service = make_service(client, cache)
    first = await service.forecast("2026-10-24", 53.9, 27.5)
    second = await service.forecast("2026-10-24", 53.9, 27.5)
    assert first.temp_max == second.temp_max == 10
    assert client.calls == 1
    assert cache.fresh


@pytest.mark.asyncio
async def test_failed_refresh_serves_stale_forecast():
    client, cache = FakeClient(), FakeCache()
    service = make_service(client, cache)
    await service.forecast("2026-10-24", 53.9, 27.5)
    cache.fresh.clear()  # simulate an expired fresh entry
    client.down = True
    stale = await service.forecast("2026-10-24", 53.9, 27.5)
    assert stale.available is True and stale.stale is True
    assert client.calls == 2


@pytest.mark.asyncio
async def test_no_cache_no_provider_is_unavailable():
    service = make_service(FakeClient(down=True), NullWeatherCache())
    weather = await service.forecast("2026-10-24", 53.9, 27.5)
    assert weather.available is False
