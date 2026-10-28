import httpx
import pytest

from app.clients.booking import BookingClient
from app.clients.weather import OpenMeteoClient
from app.core.dates import get_current_datetime
from app.core.geo import resolve_location

CENTER = (53.9056, 27.5539)


def test_get_current_datetime_uses_configured_timezone():
    now = get_current_datetime("Europe/Minsk")
    assert str(now.tzinfo) == "Europe/Minsk"
    assert get_current_datetime("Mars/Olympus").tzinfo is not None  # bad tz falls back


def test_resolve_location_landmark_and_fallback():
    resolved = resolve_location("встречаемся у Немиги", "Минск", CENTER, "ru")
    assert resolved["label"] == "встречаемся у Немиги"
    assert abs(resolved["lat"] - 53.9056) < 0.001
    fallback = resolve_location(None, "Минск", CENTER, "ru")
    assert fallback["label"] == "центр: Минск"
    assert fallback["city"] == "Минск"


def test_resolve_location_localizes_fallback_label():
    fallback = resolve_location(None, "Minsk", CENTER, "en")
    assert fallback["label"] == "center of Minsk"


@pytest.mark.asyncio
async def test_weather_parses_open_meteo():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "open-meteo.com" in str(request.url)
        assert request.url.params["timezone"] == "Europe/Minsk"
        return httpx.Response(200, json={"daily": {
            "temperature_2m_max": [11.0],
            "precipitation_probability_max": [80],
            "weathercode": [61],
        }})

    client = OpenMeteoClient("https://api.open-meteo.com/v1/forecast",
                             "Europe/Minsk", attempts=1,
                             transport=httpx.MockTransport(handler))
    weather = await client.forecast("2026-10-24", 53.9, 27.5)
    assert weather is not None and weather.available is True
    assert weather.is_rainy is True
    assert "дождь" in weather.advice("ru")
    assert "rain" in weather.advice("en")


@pytest.mark.asyncio
async def test_weather_retries_then_returns_none():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        return httpx.Response(500, text="down")

    client = OpenMeteoClient("https://api.open-meteo.com/v1/forecast",
                             "Europe/Minsk", attempts=2, backoff_base_s=0,
                             transport=httpx.MockTransport(handler))
    assert await client.forecast("2026-10-24", 53.9, 27.5) is None
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_weather_does_not_retry_client_errors():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        return httpx.Response(400, text="bad date")

    client = OpenMeteoClient("https://api.open-meteo.com/v1/forecast",
                             "Europe/Minsk", attempts=3, backoff_base_s=0,
                             transport=httpx.MockTransport(handler))
    assert await client.forecast("2026-10-24", 53.9, 27.5) is None
    assert len(calls) == 1


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

    client = BookingClient("http://booking:8082",
                           transport=httpx.MockTransport(handler))
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

    client = BookingClient("http://booking:8082",
                           transport=httpx.MockTransport(handler))
    assert (await client.check_availability(42)).status == "unknown"
