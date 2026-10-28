import httpx
import pytest

from app.api.schemas.contract import BudgetFilter, StateContract
from app.clients.booking import BookingClient
from app.clients.collector import CollectorClient
from app.clients.vector import InMemoryStore
from app.core.config import Settings
from app.models.weather import Weather
from app.services.dialogue_service import DialogueService
from app.services.search_service import SearchService
from app.sparse import encode_sparse


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


class FakeWeather:
    def __init__(self, weather=None):
        self.weather = weather or Weather(
            date="2026-10-24", temp_max=11.0,
            precipitation_probability=10, weathercode=1)

    async def forecast(self, date, lat, lon):
        return self.weather


def booking_handler(request: httpx.Request) -> httpx.Response:
    if "eventId=7" in str(request.url):
        return httpx.Response(200, json=[
            {"id": 1, "active": True, "zone": "VIP", "price": 120.0},
            {"id": 2, "active": True, "zone": "BASIC", "price": 60.0},
        ])
    if "eventId=42" in str(request.url):
        return httpx.Response(200, json=[
            {"id": 3, "active": True, "zone": "BASIC", "price": 90.0},
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


def make_service(store, collector, weather=None) -> DialogueService:
    booking = BookingClient("http://booking:8082",
                            transport=httpx.MockTransport(booking_handler))
    return DialogueService(
        search=SearchService(FakeEmbedder(), store, collector),
        weather=weather or FakeWeather(),
        booking=booking,
        db_url="",
        settings=Settings(),
    )


def two_event_store() -> InMemoryStore:
    """Hybrid payloads carry price_min, like reindexed Qdrant points."""
    return InMemoryStore(
        [
            ("aaa", [1.0, 0.0, 0.0],
             {"title": "Джазовый вечер", "city": "Минск", "price_min": 25.0}),
            ("7", [0.9, 0.1, 0.0],
             {"title": "Концерт в филармонии", "city": "Минск",
              "price_min": 120.0}),
        ],
        {
            "aaa": encode_sparse("Джазовый вечер"),
            "7": encode_sparse("Концерт в филармонии"),
        },
    )


@pytest.mark.asyncio
async def test_search_turn_returns_messages():
    service = make_service(two_event_store(), FakeCollector(collector_rows()))
    response = await service.search_turn(make_contract())
    kinds = [message.kind for message in response.messages]
    assert kinds == ["filters", "weather", "results"]
    cards = response.messages[-1].results
    assert {card.event_id for card in cards} == {"aaa", "7"}
    scraped = next(card for card in cards if card.event_id == "aaa")
    assert "Внешняя афиша" in scraped.meta
    booked = next(card for card in cards if card.event_id == "7")
    assert booked.meta == "осталось мало"  # 2 active tickets < 10
    assert booked.price == "от 60 руб."


@pytest.mark.asyncio
async def test_search_turn_budget_filters_expensive():
    contract = make_contract()
    contract.hard_filters.budget = BudgetFilter(max_price_per_person=30.0)
    service = make_service(two_event_store(), FakeCollector(collector_rows()))
    response = await service.search_turn(contract)
    ids = {card.event_id for card in response.messages[-1].results}
    assert ids == {"aaa"}  # 120 > 30 dropped, 25 kept


@pytest.mark.asyncio
async def test_search_turn_empty_results_message():
    service = make_service(InMemoryStore(), FakeCollector([]))
    response = await service.search_turn(make_contract())
    assert response.messages[-1].kind == "assistant"
    assert "ничего не нашлось" in response.messages[-1].text


@pytest.mark.asyncio
async def test_search_turn_uses_english_catalog():
    contract = make_contract()
    contract.semantic_payload.language = "en"
    service = make_service(two_event_store(), FakeCollector(collector_rows()))
    response = await service.search_turn(contract)
    assert response.messages[0].text == "Search conditions are locked in."
    assert response.messages[-1].text == "Here is what we found:"


def catalog_store() -> InMemoryStore:
    """A mirrored booking event: UUID point id, bookable id in the payload."""
    return InMemoryStore(
        [
            ("8f14e45f-ceea-467a-9c5b-3b1c1e0a1a11", [1.0, 0.0, 0.0],
             {"title": "Симфонический вечер", "city": "Минск",
              "price_min": None, "booking_event_id": 42}),
        ],
        {"8f14e45f-ceea-467a-9c5b-3b1c1e0a1a11": encode_sparse("Симфонический вечер")},
    )


@pytest.mark.asyncio
async def test_catalog_hit_uses_booking_event_id():
    rows = [{"id": "8f14e45f-ceea-467a-9c5b-3b1c1e0a1a11",
             "title": "Симфонический вечер", "price_min": None}]
    service = make_service(catalog_store(), FakeCollector(rows))
    response = await service.search_turn(make_contract())
    card = response.messages[-1].results[0]
    # The card carries the numeric booking id, so the frontend can book it.
    assert card.event_id == "42"
    assert card.meta == "осталось мало"
    assert card.price == "от 90 руб."


@pytest.mark.asyncio
async def test_empty_vector_index_falls_back_to_lexical():
    service = make_service(InMemoryStore(), FakeCollector(collector_rows()))
    response = await service.search_turn(make_contract())
    assert response.messages[-1].kind == "results"
    assert {card.event_id for card in response.messages[-1].results} == {"aaa", "7"}
