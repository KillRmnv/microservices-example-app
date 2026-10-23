import httpx
import pytest

from app.contract import StateContract
from app.dialogue import run_search_turn
from app.search import CollectorClient, SearchRequest
from app.tools import BookingClient
from app.vector import InMemoryStore


class FakeEmbedder:
    dim = 3

    async def embed(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]


def collector_rows():
    return [
        {"id": "aaa", "title": "Джазовый вечер", "price_min": 25.0},
        {"id": "7", "title": "Концерт в филармонии", "price_min": 120.0},
    ]


class FakeCollector(CollectorClient):
    def __init__(self, rows):
        self._rows = rows

    async def search_lexical(self, query, city, category, limit):
        return self._rows[:limit]


def booking_handler(request: httpx.Request) -> httpx.Response:
    if "eventId=7" in str(request.url):
        return httpx.Response(200, json=[
            {"id": 1, "active": True, "zone": "VIP", "price": 120.0},
            {"id": 2, "active": True, "zone": "BASIC", "price": 60.0},
        ])
    return httpx.Response(200, json=[])


def make_contract(**overrides) -> StateContract:
    base = {
        "dialogue_action": "search",
        "hard_filters": {
            "datetime": {"start": "2026-10-24T12:00:00"},
            "location": {"city": "Минск"},
        },
        "semantic_payload": {"vector_query": "тихий джаз"},
        "context_state": {"session_id": "s1"},
    }
    base.update(overrides)
    return StateContract.model_validate(base)


def weather_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"daily": {
        "temperature_2m_max": [11.0],
        "precipitation_probability_max": [10],
        "weathercode": [1],
    }})


@pytest.mark.asyncio
async def test_search_turn_returns_messages():
    store = InMemoryStore([
        ("aaa", [1.0, 0.0, 0.0], {"title": "Джазовый вечер"}),
        ("7", [0.9, 0.1, 0.0], {"title": "Концерт в филармонии"}),
    ])
    booking = BookingClient("http://booking:8082",
                            transport=httpx.MockTransport(booking_handler))
    response = await run_search_turn(
        make_contract(), embedder=FakeEmbedder(), store=store,
        collector=FakeCollector(collector_rows()), booking=booking,
        weather_transport=httpx.MockTransport(weather_handler))
    kinds = [message.kind for message in response.messages]
    assert kinds == ["filters", "weather", "results"]
    cards = response.messages[-1].results
    assert {card.event_id for card in cards} == {"aaa", "7"}
    scraped = next(card for card in cards if card.event_id == "aaa")
    assert "Внешняя афиша" in scraped.meta
    booked = next(card for card in cards if card.event_id == "7")
    assert booked.meta == "осталось мало"  # 2 active tickets < 10


@pytest.mark.asyncio
async def test_search_turn_budget_filters_expensive():
    store = InMemoryStore([
        ("aaa", [1.0, 0.0, 0.0], {"title": "Джазовый вечер"}),
        ("7", [0.9, 0.1, 0.0], {"title": "Концерт в филармонии"}),
    ])
    contract = make_contract()
    from app.contract import BudgetFilter
    contract.hard_filters.budget = BudgetFilter(max_price_per_person=30.0)
    booking = BookingClient("http://booking:8082",
                            transport=httpx.MockTransport(booking_handler))
    response = await run_search_turn(
        contract, embedder=FakeEmbedder(), store=store,
        collector=FakeCollector(collector_rows()), booking=booking,
        weather_transport=httpx.MockTransport(weather_handler))
    ids = {card.event_id for card in response.messages[-1].results}
    assert ids == {"aaa"}  # 120 > 30 dropped, 25 kept


@pytest.mark.asyncio
async def test_search_turn_empty_results_message():
    store = InMemoryStore()
    booking = BookingClient("http://booking:8082",
                            transport=httpx.MockTransport(booking_handler))
    response = await run_search_turn(
        make_contract(), embedder=FakeEmbedder(), store=store,
        collector=FakeCollector([]), booking=booking,
        weather_transport=httpx.MockTransport(weather_handler))
    assert response.messages[-1].kind == "assistant"
    assert "ничего не нашлось" in response.messages[-1].text
