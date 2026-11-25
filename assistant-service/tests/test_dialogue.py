from datetime import datetime
from zoneinfo import ZoneInfo

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
        {"id": "aaa", "title": "Джазовый вечер", "price_min": 25.0,
         "start_at": "2026-10-24T19:00:00+00:00"},
        {"id": "7", "title": "Концерт в филармонии", "price_min": 120.0,
         "start_at": "2026-10-24T19:00:00+00:00"},
    ]


class FakeCollector(CollectorClient):
    def __init__(self, rows):
        self._rows = rows

    async def search_lexical(self, query, city, category, limit,
                             *, date_from=None, date_to=None):
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
            "category": ["concert"],
        },
        "semantic_payload": {"vector_query": "тихий джаз"},
        "context_state": {"session_id": "s1"},
    }
    base.update(overrides)
    return StateContract.model_validate(base)


def make_service(store, collector, weather=None,
                 settings=None, now=None) -> DialogueService:
    booking = BookingClient("http://booking:8082",
                            transport=httpx.MockTransport(booking_handler))
    return DialogueService(
        search=SearchService(FakeEmbedder(), store, collector),
        search_venues=SearchService(FakeEmbedder(), store, collector),
        weather=weather or FakeWeather(),
        booking=booking,
        db_url="",
        settings=settings or Settings(),
        now=now,
    )


def two_event_store() -> InMemoryStore:
    """Hybrid payloads carry price_min, like reindexed Qdrant points."""
    return InMemoryStore(
        [
            ("aaa", [1.0, 0.0, 0.0],
             {"title": "Джазовый вечер", "city": "Минск", "price_min": 25.0,
              "category": "concert", "source": "ticketpro",
              "start_at": "2026-10-24T19:00:00+00:00"}),
            ("7", [0.9, 0.1, 0.0],
             {"title": "Концерт в филармонии", "city": "Минск",
              "price_min": 120.0, "category": "concert",
              "start_at": "2026-10-24T19:00:00+00:00"}),
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
    assert "наличие уточняйте у источника" in scraped.meta
    assert scraped.detail_id == "aaa"
    assert scraped.source == "ticketpro"
    booked = next(card for card in cards if card.event_id == "7")
    assert booked.meta == "осталось мало"  # 2 active tickets < 10
    assert booked.price == "от 60 руб."


@pytest.mark.asyncio
async def test_search_turn_keeps_only_requested_day():
    """A named date must filter hits; a January event is not "завтра"."""
    store = InMemoryStore(
        [
            ("aaa", [1.0, 0.0, 0.0],
             {"title": "Джазовый вечер", "city": "Минск",
              "price_min": 25.0, "category": "concert",
              "start_at": "2026-10-24T19:00:00+00:00"}),
            ("jjj", [1.0, 0.0, 0.0],
             {"title": "Январский концерт", "city": "Минск",
              "price_min": 25.0, "category": "concert",
              "start_at": "2027-01-24T19:00:00+00:00"}),
            ("undated", [1.0, 0.0, 0.0],
             {"title": "Пост без даты", "city": "Минск",
              "price_min": 25.0, "category": "concert"}),
        ],
        {doc_id: encode_sparse(title) for doc_id, title in (
            ("aaa", "Джазовый вечер"), ("jjj", "Январский концерт"),
            ("undated", "Пост без даты"))},
    )
    service = make_service(store, FakeCollector([]))
    response = await service.search_turn(make_contract())
    assert {card.event_id for card in response.messages[-1].results} == {"aaa"}


@pytest.mark.asyncio
async def test_search_plan_covers_the_whole_requested_day():
    service = make_service(two_event_store(), FakeCollector(collector_rows()))
    plan = service._search_plan(make_contract())
    assert plan.date_from is not None and plan.date_to is not None
    # No explicit end: the whole 24 October in the contract timezone.
    assert plan.date_from.isoformat().startswith("2026-10-24T00:00:00")
    assert plan.date_to.isoformat().startswith("2026-10-25T00:00:00")


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
              "price_min": None, "booking_event_id": 42,
              "category": "concert",
              "start_at": "2026-10-24T19:00:00+00:00"}),
        ],
        {"8f14e45f-ceea-467a-9c5b-3b1c1e0a1a11": encode_sparse("Симфонический вечер")},
    )


@pytest.mark.asyncio
async def test_catalog_hit_uses_booking_event_id():
    rows = [{"id": "8f14e45f-ceea-467a-9c5b-3b1c1e0a1a11",
             "title": "Симфонический вечер", "price_min": None,
             "start_at": "2026-10-24T19:00:00+00:00"}]
    service = make_service(catalog_store(), FakeCollector(rows))
    response = await service.search_turn(make_contract())
    card = response.messages[-1].results[0]
    # The card carries the numeric booking id, so the frontend can book it.
    assert card.event_id == "42"
    # ...and the Qdrant UUID, so the card links to the event page.
    assert card.detail_id == "8f14e45f-ceea-467a-9c5b-3b1c1e0a1a11"
    assert card.meta == "осталось мало"
    assert card.price == "от 90 руб."


@pytest.mark.asyncio
async def test_venue_intent_searches_places_without_asking_for_date():
    from app.api.schemas.contract import StateContract

    store = InMemoryStore(
        [("11111111-1111-4111-8111-111111111111", [1.0, 0.0, 0.0],
          {"name": "Пивной бар «Кран»", "rubric": "Бары",
           "address": "ул. Немига, 5", "city": "Минск",
           "source": "twogis_places"})],
        {"11111111-1111-4111-8111-111111111111": encode_sparse("пивной бар")},
    )
    contract = StateContract.model_validate({
        "dialogue_action": "search",
        "intent": "find_venues",
        "hard_filters": {"location": {"city": "Минск"}},
        "semantic_payload": {"vector_query": "пиво с друзьями"},
        "context_state": {"session_id": "v1"},
    })
    service = make_service(store, FakeCollector([]))
    response = await service.search_turn(contract)
    card = response.messages[-1].results[0]
    assert card.kind == "venue"
    assert card.title == "Пивной бар «Кран»"
    assert card.detail_id == "11111111-1111-4111-8111-111111111111"
    assert "Бары" in card.meta


@pytest.mark.asyncio
async def test_empty_vector_index_falls_back_to_lexical():
    service = make_service(InMemoryStore(), FakeCollector(collector_rows()))
    response = await service.search_turn(make_contract())
    assert response.messages[-1].kind == "results"
    assert {card.event_id for card in response.messages[-1].results} == {"aaa", "7"}


def test_date_window_uses_evening_hours():
    service = make_service(two_event_store(), FakeCollector([]))
    contract = StateContract.model_validate({
        "hard_filters": {
            "datetime": {
                "start": "2026-11-27T18:00:00+03:00",
                "end": "2026-11-27T23:59:00+03:00",
                "raw_expression": "вечер пятницы",
                "timezone": "Europe/Minsk",
            }
        },
    })
    start, end = service._date_window(contract.hard_filters)
    assert start is not None and end is not None
    assert (start.hour, start.minute) == (18, 0)
    assert (end.hour, end.minute) == (23, 59)
    assert start.date().isoformat() == "2026-11-27"


def test_date_window_without_time_of_day_is_whole_day():
    service = make_service(two_event_store(), FakeCollector([]))
    contract = StateContract.model_validate({
        "hard_filters": {
            "datetime": {
                "start": "2026-11-27T12:00:00+03:00",
                "raw_expression": "пятница",
                "timezone": "Europe/Minsk",
            }
        },
    })
    start, end = service._date_window(contract.hard_filters)
    assert start is not None and end is not None
    assert (start.hour, start.minute) == (0, 0)
    assert start.date().isoformat() == "2026-11-27"
    assert end.date().isoformat() == "2026-11-28"


def test_required_slots_only_asks_events_for_a_date():
    from app.services.rules import required_slots

    venue = StateContract.model_validate({
        "intent": "find_venue_bar", "hard_filters": {},
    })
    assert required_slots(venue, Settings()) == []

    undated = StateContract.model_validate({
        "intent": "find_events", "hard_filters": {},
    })
    assert required_slots(undated, Settings()) == ["datetime"]

    dated = StateContract.model_validate({
        "intent": "find_events",
        "hard_filters": {"datetime": {"start": "2026-10-24T19:00:00"}},
    })
    assert required_slots(dated, Settings()) == []

    any_date = StateContract.model_validate({
        "intent": "find_events",
        "hard_filters": {"datetime": {"any": True}},
    })
    assert required_slots(any_date, Settings()) == []


def test_required_slots_asks_for_city_only_without_a_default():
    from app.services.rules import required_slots

    contract = StateContract.model_validate({
        "intent": "find_venues", "hard_filters": {},
    })
    assert required_slots(contract, Settings(default_city="")) == ["city"]
    assert required_slots(contract, Settings(default_city="Минск")) == []


def test_apply_rules_venue_needs_no_budget_or_party():
    contract = StateContract.model_validate({
        "intent": "find_venues",
        "clarify_missing": True,
        "hard_filters": {},
    })
    service = make_service(InMemoryStore(), FakeCollector([]))
    ruled = service.apply_rules(contract)
    assert ruled.needs_clarification is False
    assert ruled.dialogue_action == "search"
    assert ruled.clarification_slots == []


def test_apply_rules_asks_only_for_the_event_date():
    contract = StateContract.model_validate({
        "intent": "find_events",
        "clarify_missing": True,
        "hard_filters": {},
    })
    service = make_service(InMemoryStore(), FakeCollector([]))
    ruled = service.apply_rules(contract)
    assert ruled.dialogue_action == "ask_clarification"
    assert ruled.clarification_slots == ["datetime"]
    assert "дата" in ruled.clarification_prompt
    assert "бюджет" not in ruled.clarification_prompt
    assert "человек" not in ruled.clarification_prompt


def test_apply_rules_clears_stale_slots_when_nothing_is_missing():
    contract = StateContract.model_validate({
        "intent": "find_events",
        "clarify_missing": True,
        "clarification_slots": ["datetime", "budget"],
        "hard_filters": {"datetime": {"start": "2026-10-24T19:00:00"}},
    })
    service = make_service(InMemoryStore(), FakeCollector([]))
    ruled = service.apply_rules(contract)
    assert ruled.clarification_slots == []
    assert ruled.dialogue_action == "search"


def test_search_plan_applies_the_default_city():
    service = make_service(InMemoryStore(), FakeCollector([]))
    contract = make_contract(hard_filters={
        "datetime": {"start": "2026-10-24T12:00:00"},
        "category": ["concert"],
    })
    assert service._search_plan(contract).city == "Минск"

    any_city = make_contract(hard_filters={
        "datetime": {"start": "2026-10-24T12:00:00"},
        "location": {"any": True},
    })
    assert service._search_plan(any_city).city is None


def test_venue_plan_uses_rubric_and_never_the_city_as_query():
    service = make_service(InMemoryStore(), FakeCollector([]))
    contract = StateContract.model_validate({
        "intent": "find_venue_bar",
        "hard_filters": {},
    })
    plan = service._venue_plan(contract)
    assert plan.rubric == "Бары"
    assert plan.vector_query == "Бары"
    assert plan.city == "Минск"

    any_city = StateContract.model_validate({
        "intent": "find_venues",
        "hard_filters": {"location": {"any": True}},
    })
    fallback = service._venue_plan(any_city)
    assert fallback.city is None
    assert fallback.rubric is None
    assert fallback.vector_query == "места"


FIXED_NOW = datetime(2026, 11, 25, 12, 0, tzinfo=ZoneInfo("Europe/Minsk"))


def fixed_now() -> datetime:
    return FIXED_NOW


class RecordingWeather(FakeWeather):
    def __init__(self):
        super().__init__()
        self.dates: list[str] = []

    async def forecast(self, date, lat, lon):
        self.dates.append(date)
        return Weather(date=date, temp_max=11.0,
                       precipitation_probability=10, weathercode=1)


@pytest.mark.asyncio
async def test_weather_turn_returns_only_the_forecast():
    weather = RecordingWeather()
    service = make_service(InMemoryStore(), FakeCollector([]),
                           weather=weather, now=fixed_now)
    contract = make_contract(intent="weather",
                             hard_filters={"location": {"city": "Минск"}})
    response = await service.weather_turn(contract)
    assert [message.kind for message in response.messages] == ["weather"]
    assert response.messages[0].results is None
    # No date in the contract: the injected clock decides "today".
    assert weather.dates == ["2026-11-25"]
    assert "2026-11-25" in response.messages[0].text

    dated = await service.weather_turn(make_contract(
        intent="weather",
        hard_filters={"datetime": {"start": "2026-12-01T19:00:00+03:00"}}))
    assert dated.messages[0].results is None
    assert weather.dates[-1] == "2026-12-01"


def test_search_plan_without_a_date_starts_now():
    service = make_service(InMemoryStore(), FakeCollector([]), now=fixed_now)
    contract = make_contract(hard_filters={
        "location": {"city": "Минск"}, "category": ["concert"]})
    plan = service._search_plan(contract)
    assert plan.date_from == FIXED_NOW
    assert plan.date_to is None

    any_date = make_contract(hard_filters={
        "datetime": {"any": True},
        "location": {"city": "Минск"},
    })
    assert service._search_plan(any_date).date_from == FIXED_NOW


@pytest.mark.asyncio
async def test_search_turn_drops_past_events_without_a_date():
    """The future floor applies only when the user named no date."""
    store = InMemoryStore(
        [
            ("past", [1.0, 0.0, 0.0],
             {"title": "Прошлый концерт", "city": "Минск",
              "price_min": 25.0, "category": "concert",
              "start_at": "2026-11-01T19:00:00+00:00"}),
            ("future", [1.0, 0.0, 0.0],
             {"title": "Будущий концерт", "city": "Минск",
              "price_min": 25.0, "category": "concert",
              "start_at": "2026-12-05T19:00:00+00:00"}),
        ],
        {"past": encode_sparse("прошлый концерт"),
         "future": encode_sparse("будущий концерт")},
    )
    service = make_service(store, FakeCollector([]), now=fixed_now)
    contract = make_contract(hard_filters={
        "location": {"city": "Минск"}, "category": ["concert"]})
    response = await service.search_turn(contract)
    assert [message.kind for message in response.messages] == ["filters",
                                                                "results"]
    ids = {card.event_id for card in response.messages[-1].results}
    assert ids == {"future"}


def test_dialogue_router_dispatches_weather(monkeypatch):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    import app.api.routers.dialogue as dialogue_router
    from app.api.schemas.dialogue import ChatMessage, DialogResponse
    from app.main import create_app

    calls: list[str] = []

    class FakeDialogue:
        async def weather_turn(self, contract):
            calls.append(contract.intent)
            return DialogResponse(
                contract=contract,
                messages=[ChatMessage(kind="weather", text="погода")])

        def record_run(self, contract, duration_ms):
            calls.append("recorded")

        def elapsed_ms(self, started):
            return 1

    monkeypatch.setattr(dialogue_router, "get_components",
                        lambda: SimpleNamespace(dialogue=FakeDialogue()))
    client = TestClient(create_app())
    response = client.post("/assistant/dialogue/v2", json={
        "dialogue_action": "search",
        "intent": "weather",
        "hard_filters": {},
        "context_state": {"session_id": "weather-1"},
    })
    assert response.status_code == 200
    body = response.json()
    assert [message["kind"] for message in body["messages"]] == ["weather"]
    assert calls == ["weather", "recorded"]
