import httpx
import pytest

from app.tools import (
    BookingClient,
    get_current_datetime,
    get_weather_forecast,
    resolve_location,
)


def test_get_current_datetime_defaults_to_minsk():
    now = get_current_datetime()
    assert str(now.tzinfo) == "Europe/Minsk"
    assert get_current_datetime("Mars/Olympus").tzinfo is not None  # bad tz falls back


def test_resolve_location_landmark_and_fallback():
    resolved = resolve_location("встречаемся у Немиги", "Минск")
    assert resolved["label"] == "встречаемся у Немиги"
    assert abs(resolved["lat"] - 53.9056) < 0.001
    fallback = resolve_location(None)
    assert fallback["label"] == "центр Минска"
    assert fallback["city"] == "Минск"


@pytest.mark.asyncio
async def test_weather_parses_open_meteo():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "open-meteo.com" in str(request.url)
        return httpx.Response(200, json={"daily": {
            "temperature_2m_max": [11.0],
            "precipitation_probability_max": [80],
            "weathercode": [61],
        }})

    weather = await get_weather_forecast("2026-10-24", 53.9, 27.5,
                                         transport=httpx.MockTransport(handler))
    assert weather.available is True
    assert weather.is_rainy is True
    assert "дождь" in weather.advice_ru()


@pytest.mark.asyncio
async def test_weather_outage_is_advisory():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="down")

    weather = await get_weather_forecast("2026-10-24", 53.9, 27.5,
                                         transport=httpx.MockTransport(handler))
    assert weather.available is False
    assert weather.is_rainy is False


@pytest.mark.asyncio
async def test_booking_availability_statuses():
    def handler(request: httpx.Request) -> httpx.Response:
        path = str(request.url)
        if path.endswith("/booking/events/3"):
            return httpx.Response(200, json={"id": 3, "title": "Пустой зал"})
        if "eventId=1" in path:
            tickets = [{"id": i, "active": True, "zone": "BASIC", "price": 50.0}
                       for i in range(12)]
        elif "eventId=2" in path:
            tickets = [{"id": 1, "active": True, "zone": "VIP", "price": 90.0}]
        elif "eventId=3" in path:
            tickets = []
        else:
            return httpx.Response(500, text="boom")
        return httpx.Response(200, json=tickets)

    client = BookingClient("http://booking:8082", transport=httpx.MockTransport(handler))
    many = await client.check_availability(1)
    assert many.status == "available" and many.min_price == 50.0
    assert many.zones == [{"zone": "BASIC", "count": 12, "min_price": 50.0}]
    few = await client.check_availability(2)
    assert few.status == "few_left"
    assert (await client.check_availability(3)).status == "sold_out"
    assert (await client.check_availability(9)).status == "unknown"
    assert await client.get_event(9) is None


@pytest.mark.asyncio
async def test_booking_unknown_event_is_not_sold_out():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/booking/events/42"):
            return httpx.Response(404, text="nope")
        return httpx.Response(200, json=[])

    client = BookingClient("http://booking:8082", transport=httpx.MockTransport(handler))
    assert (await client.check_availability(42)).status == "unknown"
