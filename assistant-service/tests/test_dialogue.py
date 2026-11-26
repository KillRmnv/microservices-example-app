from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.api.schemas.contract import BudgetFilter, StateContract
from app.clients.booking import BookingClient
from app.clients.collector import CollectorClient
from app.clients.vector import InMemoryStore
from app.core.config import Settings
from app.models.search import FusedHit
from app.models.weather import Weather
from app.services.dialogue_service import CATEGORY_VENUE_FALLBACK, DialogueService
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
    # The source price is known, so the card must show it (not "цена
    # уточняется"); scraped rows still carry no live inventory.
    assert scraped.price == "от 25 руб."
    assert scraped.detail_id == "aaa"
    assert scraped.source == "ticketpro"
    booked = next(card for card in cards if card.event_id == "7")
    assert booked.meta == "осталось мало"  # 2 active tickets < 10
    # Zone prices: 60 (BASIC) .. 120 (VIP) is the per-zone range.
    assert booked.price == "60–120 руб."


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


def test_search_plan_passes_negative_tags():
    service = make_service(InMemoryStore(), FakeCollector([]))
    contract = make_contract(
        negative_filters={"exclude_categories": ["sport"],
                          "exclude_tags": ["кальян"]})
    plan = service._search_plan(contract)
    assert plan.exclude_categories == ["sport"]
    assert plan.exclude_tags == ["кальян"]


@pytest.mark.asyncio
async def test_search_turn_excludes_negative_tags():
    store = InMemoryStore(
        [
            ("hookah", [1.0, 0.0, 0.0],
             {"title": "Вечеринка с кальяном", "city": "Минск",
              "price_min": 25.0, "category": "concert",
              "search_text": "вечеринка кальян музыка",
              "start_at": "2026-10-24T19:00:00+00:00"}),
            ("jazz", [1.0, 0.0, 0.0],
             {"title": "Джазовый вечер", "city": "Минск",
              "price_min": 25.0, "category": "concert",
              "search_text": "джазовый вечер",
              "start_at": "2026-10-24T19:00:00+00:00"}),
        ],
        {"hookah": encode_sparse("вечеринка кальян"),
         "jazz": encode_sparse("джазовый вечер")},
    )
    service = make_service(store, FakeCollector([]))
    contract = make_contract(negative_filters={"exclude_tags": ["кальян"]})
    response = await service.search_turn(contract)
    ids = {card.event_id for card in response.messages[-1].results}
    assert ids == {"jazz"}


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
    assert "Section:" in response.messages[0].text
    assert "When:" in response.messages[0].text
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


def test_venue_plan_carries_negative_tags():
    service = make_service(InMemoryStore(), FakeCollector([]))
    contract = StateContract.model_validate({
        "intent": "find_venue_bar",
        "hard_filters": {},
        "negative_filters": {"exclude_tags": ["кальян"]},
    })
    assert service._venue_plan(contract).exclude_tags == ["кальян"]


@pytest.mark.asyncio
async def test_venue_turn_excludes_negative_tags():
    store = InMemoryStore(
        [
            ("hookah", [1.0, 0.0, 0.0],
             {"name": "Кальян-бар «Дым»", "rubric": "Бары",
              "address": "ул. Немига, 5", "city": "Минск",
              "search_text": "бар кальян дым"}),
            ("clean", [1.0, 0.0, 0.0],
             {"name": "Пивной бар «Кран»", "rubric": "Бары",
              "address": "ул. Октябрьская, 16", "city": "Минск",
              "search_text": "пивной бар кран"}),
        ],
        {"hookah": encode_sparse("бар кальян"),
         "clean": encode_sparse("пивной бар")},
    )
    service = make_service(store, FakeCollector([]))
    contract = StateContract.model_validate({
        "intent": "find_venue_bar",
        "hard_filters": {"location": {"city": "Минск"}},
        "semantic_payload": {"vector_query": "бар без кальяна"},
        "negative_filters": {"exclude_tags": ["кальян"]},
        "context_state": {"session_id": "v2"},
    })
    response = await service.search_turn(contract)
    ids = {card.event_id for card in response.messages[-1].results}
    assert ids == {"clean"}


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
    assert required_slots(venue, Settings(), clarify_required_slots=True) == []

    undated = StateContract.model_validate({
        "intent": "find_events", "hard_filters": {},
    })
    # A search never blocks on a date; only the explicit clarification path
    # can ask for it.
    assert required_slots(undated, Settings()) == []
    assert required_slots(undated, Settings(),
                          clarify_required_slots=True) == ["datetime"]

    dated = StateContract.model_validate({
        "intent": "find_events",
        "hard_filters": {"datetime": {"start": "2026-10-24T19:00:00"}},
    })
    assert required_slots(dated, Settings(), clarify_required_slots=True) == []

    any_date = StateContract.model_validate({
        "intent": "find_events",
        "hard_filters": {"datetime": {"any": True}},
    })
    assert required_slots(any_date, Settings(),
                          clarify_required_slots=True) == []


def test_required_slots_asks_for_city_only_without_a_default():
    from app.services.rules import required_slots

    contract = StateContract.model_validate({
        "intent": "find_venues", "hard_filters": {},
    })
    assert required_slots(contract, Settings(default_city="")) == []
    assert required_slots(contract, Settings(default_city=""),
                          clarify_required_slots=True) == ["city"]
    assert required_slots(contract, Settings(default_city="Минск"),
                          clarify_required_slots=True) == []


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


def test_apply_rules_never_blocks_a_dated_or_undated_search():
    service = make_service(InMemoryStore(), FakeCollector([]))
    undated = StateContract.model_validate({
        "intent": "find_events",
        "clarify_missing": True,
        "hard_filters": {},
    })
    ruled = service.apply_rules(undated)
    assert ruled.dialogue_action == "search"
    assert ruled.needs_clarification is False
    assert ruled.clarification_slots == []

    dated = StateContract.model_validate({
        "intent": "find_events",
        "clarify_missing": True,
        "hard_filters": {"datetime": {"start": "2026-10-24T19:00:00"}},
    })
    assert service.apply_rules(dated).dialogue_action == "search"


def test_apply_rules_downgrades_clarification_without_opt_in():
    service = make_service(InMemoryStore(), FakeCollector([]))
    contract = StateContract.model_validate({
        "intent": "find_events",
        "dialogue_action": "ask_clarification",
        "hard_filters": {},
    })
    ruled = service.apply_rules(contract)
    assert ruled.dialogue_action == "search"
    assert ruled.needs_clarification is False
    assert ruled.clarification_slots == []


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


def test_search_plan_without_a_date_starts_now_for_generic_queries():
    service = make_service(InMemoryStore(), FakeCollector([]), now=fixed_now)
    contract = make_contract(hard_filters={
        "location": {"city": "Минск"}})
    plan = service._search_plan(contract)
    assert plan.date_from == FIXED_NOW
    assert plan.date_to is None
    assert plan.include_undated is False

    any_date = make_contract(hard_filters={
        "datetime": {"any": True},
        "location": {"city": "Минск"},
    })
    assert service._search_plan(any_date).date_from == FIXED_NOW


def test_category_search_without_a_date_includes_undated_posts():
    service = make_service(InMemoryStore(), FakeCollector([]), now=fixed_now)
    contract = make_contract(hard_filters={
        "location": {"city": "Минск"}, "category": ["film"]})
    plan = service._search_plan(contract)
    assert plan.include_undated is True
    # The future floor is kept; undated posts pass through the filter's
    # allow_undated mode, past dated events still do not.
    assert plan.date_from == FIXED_NOW
    assert plan.date_to is None


@pytest.mark.asyncio
async def test_search_turn_drops_past_events_without_a_date():
    """The future floor applies only when the user named no date."""
    store = InMemoryStore(
        [
            ("past", [1.0, 0.0, 0.0],
             {"title": "Прошлый концерт", "city": "Минск",
              "price_min": 25.0,
              "start_at": "2026-11-01T19:00:00+00:00"}),
            ("future", [1.0, 0.0, 0.0],
             {"title": "Будущий концерт", "city": "Минск",
              "price_min": 25.0,
              "start_at": "2026-12-05T19:00:00+00:00"}),
        ],
        {"past": encode_sparse("прошлый концерт"),
         "future": encode_sparse("будущий концерт")},
    )
    service = make_service(store, FakeCollector([]), now=fixed_now)
    # No category: generic queries keep the future floor. A theme keeps the
    # intent's event scope without turning the turn into "events + venues".
    contract = make_contract(hard_filters={
        "location": {"city": "Минск"}, "themes": ["concert"]})
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


# --- rain adjustment / party availability / venue card fields -----------


@pytest.mark.asyncio
async def test_rain_excludes_terrace_venues_and_explains():
    store = InMemoryStore(
        [
            ("11111111-1111-4111-8111-111111111111", [1.0, 0.0, 0.0],
             {"name": "Летняя терраса", "rubric": "Кафе", "city": "Минск",
              "amenities": ["terrace", "wifi"]}),
            ("22222222-2222-4222-8222-222222222222", [1.0, 0.0, 0.0],
             {"name": "Кафе в помещении", "rubric": "Кафе", "city": "Минск",
              "amenities": ["wifi"]}),
        ],
        {"11111111-1111-4111-8111-111111111111": encode_sparse("кафе"),
         "22222222-2222-4222-8222-222222222222": encode_sparse("кафе")},
    )
    rainy = Weather(date="2026-10-24", temp_max=9.0,
                    precipitation_probability=85, weathercode=61)
    service = make_service(store, FakeCollector([]),
                           weather=FakeWeather(rainy))
    contract = StateContract.model_validate({
        "intent": "find_venue_cafe",
        "hard_filters": {
            "datetime": {"start": "2026-10-24T19:00:00+03:00"},
            "location": {"city": "Минск"},
            "amenities_required": ["terrace"],
        },
        "semantic_payload": {"vector_query": "кафе"},
        "context_state": {"session_id": "rain"},
    })
    response = await service.search_turn(contract)
    kinds = [message.kind for message in response.messages]
    assert kinds == ["filters", "weather", "assistant", "results"]
    assert "террас" in response.messages[2].text
    assert "85" in response.messages[2].text
    cards = response.messages[-1].results
    assert [card.title for card in cards] == ["Кафе в помещении"]


@pytest.mark.asyncio
async def test_events_only_rain_turn_keeps_plain_advice():
    rainy = Weather(date="2026-10-24", temp_max=9.0,
                    precipitation_probability=85, weathercode=61)
    service = make_service(two_event_store(),
                           FakeCollector(collector_rows()),
                           weather=FakeWeather(rainy))
    response = await service.search_turn(make_contract())
    kinds = [message.kind for message in response.messages]
    # Nothing outdoor was filtered on an events-only turn, so no "excluded"
    # claim is allowed.
    assert kinds == ["filters", "weather", "results"]
    assert all("исключены" not in (message.text or "")
               for message in response.messages)


@pytest.mark.asyncio
async def test_party_availability_marks_the_card():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/booking/events/7/availability":
            assert request.url.params["party"] == "6"
            return httpx.Response(200, json={
                "eventId": 7,
                "status": "insufficient",
                "capacity": 20,
                "zones": [{"zone": "VIP", "seatsLeft": 2, "minPrice": 120.0}],
            })
        return booking_handler(request)

    booking = BookingClient("http://booking:8082",
                            transport=httpx.MockTransport(handler))
    service = DialogueService(
        search=SearchService(FakeEmbedder(), two_event_store(),
                             FakeCollector(collector_rows())),
        search_venues=SearchService(FakeEmbedder(), two_event_store(),
                                    FakeCollector(collector_rows())),
        weather=FakeWeather(), booking=booking, db_url="",
        settings=Settings(),
    )
    contract = make_contract(hard_filters={
        "datetime": {"start": "2026-10-24T12:00:00"},
        "location": {"city": "Минск"},
        "category": ["concert"],
        "party_size": 6,
    })
    response = await service.search_turn(contract)
    card = next(card for card in response.messages[-1].results
                if card.event_id == "7")
    assert card.status == "insufficient"
    assert card.meta == "на 6 человек нет мест"
    assert card.fits_party is False
    assert card.seats_left == 2
    assert card.price == "от 120 руб."


@pytest.mark.asyncio
async def test_venue_card_exposes_rating_and_hours():
    store = InMemoryStore(
        [("33333333-3333-4333-8333-333333333333", [1.0, 0.0, 0.0],
          {"name": "Кофейня", "rubric": "Кафе", "city": "Минск",
           "address": "ул. Немига, 5", "rating": 4.6, "review_count": 123,
           "hours": {"wed": ["10:00", "23:00"]}})],
        {"33333333-3333-4333-8333-333333333333": encode_sparse("кофейня")},
    )
    service = make_service(store, FakeCollector([]))
    contract = StateContract.model_validate({
        "intent": "find_venue_cafe",
        "hard_filters": {"location": {"city": "Минск"}},
        "semantic_payload": {"vector_query": "кофейня"},
        "context_state": {"session_id": "v3"},
    })
    response = await service.search_turn(contract)
    card = response.messages[-1].results[0]
    assert card.rating == 4.6
    assert card.review_count == 123
    assert card.address == "ул. Немига, 5"
    assert card.hours == "до 23:00"
    # The rating is structured (the UI renders its own badge): meta stays
    # rubric-only, so the rating is not shown twice.
    assert card.meta == "Кафе"
    assert "★" not in card.meta


@pytest.mark.asyncio
async def test_booking_party_endpoint_is_preferred():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/booking/events/7/availability"
        assert request.url.params["party"] == "6"
        return httpx.Response(200, json={
            "eventId": 7, "status": "few_left", "capacity": 20,
            "zones": [
                {"zone": "VIP", "seatsLeft": 3, "minPrice": 120.0},
                {"zone": "BASIC", "seatsLeft": 0, "minPrice": 60.0},
            ]})

    from app.models.availability import FEW_LEFT

    client = BookingClient("http://booking:8082",
                           transport=httpx.MockTransport(handler))
    availability = await client.check_availability(7, party=6)
    assert availability.status == FEW_LEFT
    assert availability.min_price == 60.0
    assert availability.capacity == 20
    assert availability.seats_left == 3


@pytest.mark.asyncio
async def test_booking_fallback_paginates_ticket_search():
    from app.clients.booking import TICKET_PAGE_SIZE
    from app.models.availability import AVAILABLE

    requests: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/availability"):
            return httpx.Response(404, json={"error": "not found"})
        if "seatable" in request.url.path:
            return httpx.Response(200, json=[])
        page = int(request.url.params.get("page", "1"))
        requests.append(page)
        if page == 1:
            return httpx.Response(200, json=[
                {"id": i, "active": True, "zone": "BASIC", "price": 50.0}
                for i in range(TICKET_PAGE_SIZE)])
        if page == 2:
            return httpx.Response(200, json=[
                {"id": 999, "active": True, "zone": "BASIC", "price": 50.0}])
        return httpx.Response(200, json=[])

    client = BookingClient("http://booking:8082",
                           transport=httpx.MockTransport(handler))
    availability = await client.check_availability(7, party=2)
    assert availability.status == AVAILABLE
    assert availability.seats_left == TICKET_PAGE_SIZE + 1
    assert requests == [1, 2]


@pytest.mark.asyncio
async def test_rain_drops_terrace_amenity_but_keeps_a_text_mention():
    """Amenity-only exclusion: a description is not a terrace."""

    def venue_store() -> InMemoryStore:
        return InMemoryStore(
            [
                ("11111111-1111-4111-8111-111111111111", [1.0, 0.0, 0.0],
                 {"name": "Летняя терраса", "rubric": "Кафе", "city": "Минск",
                  "amenities": ["terrace", "wifi"]}),
                ("22222222-2222-4222-8222-222222222222", [1.0, 0.0, 0.0],
                 {"name": "Кофейня «Уют»", "rubric": "Кафе", "city": "Минск",
                  "description": "есть уютная терраса", "amenities": ["wifi"]}),
                ("33333333-3333-4333-8333-333333333333", [1.0, 0.0, 0.0],
                 {"name": "Кафе в помещении", "rubric": "Кафе", "city": "Минск",
                  "amenities": ["wifi"]}),
            ],
            {doc_id: encode_sparse("кафе") for doc_id in (
                "11111111-1111-4111-8111-111111111111",
                "22222222-2222-4222-8222-222222222222",
                "33333333-3333-4333-8333-333333333333")},
        )

    contract = StateContract.model_validate({
        "intent": "find_venue_cafe",
        "hard_filters": {
            "datetime": {"start": "2026-10-24T19:00:00+03:00"},
            "location": {"city": "Минск"},
        },
        "semantic_payload": {"vector_query": "кафе"},
        "context_state": {"session_id": "rain-amenity"},
    })

    rainy = Weather(date="2026-10-24", temp_max=9.0,
                    precipitation_probability=85, weathercode=61)
    wet = make_service(venue_store(), FakeCollector([]),
                       weather=FakeWeather(rainy))
    wet_cards = (await wet.search_turn(contract)).messages[-1].results
    titles = {card.title for card in wet_cards}
    assert "Летняя терраса" not in titles
    # The description mentions a terrace, but the amenity list does not.
    assert "Кофейня «Уют»" in titles
    assert "Кафе в помещении" in titles

    dry = make_service(venue_store(), FakeCollector([]),
                       weather=FakeWeather())
    dry_cards = (await dry.search_turn(contract)).messages[-1].results
    assert "Летняя терраса" in {card.title for card in dry_cards}


def test_rain_keeps_user_exclude_tags_as_text_filters():
    service = make_service(InMemoryStore(), FakeCollector([]))
    contract = StateContract.model_validate({
        "intent": "find_venue_bar",
        "hard_filters": {"location": {"city": "Минск"}},
        "negative_filters": {"exclude_tags": ["кальян"]},
    })
    plan = service._venue_plan(contract)
    assert plan.exclude_tags == ["кальян"]
    # No weather exclusion unless a rainy venue turn asks for it.
    assert plan.exclude_amenities == []
    rainy = service._venue_plan(
        contract, extra_exclude_amenities=["terrace"])
    assert rainy.exclude_amenities == ["terrace"]
    assert rainy.exclude_tags == ["кальян"]


def test_search_plan_keeps_sparse_retrieval_for_themes():
    service = make_service(InMemoryStore(), FakeCollector([]))
    contract = make_contract(
        hard_filters={
            "datetime": {"start": "2026-10-24T12:00:00"},
            "location": {"city": "Минск"},
            "themes": ["джаз"],
        },
        semantic_payload={"vector_query": ""},
    )
    plan = service._search_plan(contract)
    assert plan.themes == ["джаз"]
    # Themes are a lexical signal now: dense-only is no longer implied.
    assert plan.dense_only is False


# --- explicit target collection ----------------------------------------


def venue_store() -> InMemoryStore:
    return InMemoryStore(
        [("11111111-1111-4111-8111-111111111111", [1.0, 0.0, 0.0],
          {"name": "Пивной бар «Кран»", "rubric": "Бары",
           "address": "ул. Немига, 5", "city": "Минск",
           "source": "twogis_places"})],
        {"11111111-1111-4111-8111-111111111111": encode_sparse("пивной бар")},
    )


def target_contract(target: str, **overrides) -> StateContract:
    base = {
        "dialogue_action": "search",
        "intent": "find_events",
        "hard_filters": {
            "datetime": {"start": "2026-10-24T12:00:00"},
            "location": {"city": "Минск"},
            "category": ["concert"],
        },
        "semantic_payload": {"vector_query": "пивной бар",
                             "target_collection": target},
        "context_state": {"session_id": "t1"},
    }
    base.update(overrides)
    return StateContract.model_validate(base)


@pytest.mark.asyncio
async def test_target_collection_venues_overrides_event_intent():
    service = make_service(venue_store(), FakeCollector([]))
    response = await service.search_turn(target_contract("venues"))
    cards = response.messages[-1].results
    assert [card.kind for card in cards] == ["venue"]
    assert cards[0].title == "Пивной бар «Кран»"


@pytest.mark.asyncio
async def test_target_collection_alias_searches_venues():
    from app.api.schemas.contract import sanitize

    service = make_service(venue_store(), FakeCollector([]))
    contract = sanitize(target_contract("venues_atmosphere"))
    assert contract.semantic_payload.target_collection == "venues"
    response = await service.search_turn(contract)
    assert [card.kind for card in response.messages[-1].results] == ["venue"]


@pytest.mark.asyncio
async def test_target_collection_events_overrides_venue_intent():
    service = make_service(two_event_store(), FakeCollector([]))
    contract = target_contract(
        "events", intent="find_venue_bar",
        hard_filters={"datetime": {"start": "2026-10-24T12:00:00"},
                      "location": {"city": "Минск"}})
    response = await service.search_turn(contract)
    cards = response.messages[-1].results
    assert cards and all(card.kind == "event" for card in cards)


@pytest.mark.asyncio
async def test_unknown_target_collection_keeps_the_intent_scope():
    from app.api.schemas.contract import sanitize

    service = make_service(two_event_store(), FakeCollector([]))
    contract = sanitize(target_contract("spaceship"))
    assert contract.semantic_payload.target_collection is None
    response = await service.search_turn(contract)
    cards = response.messages[-1].results
    assert cards and all(card.kind == "event" for card in cards)


@pytest.mark.asyncio
async def test_target_collection_does_not_reroute_a_clarification():
    service = make_service(two_event_store(), FakeCollector([]))
    contract = target_contract("venues",
                               dialogue_action="ask_clarification")
    response = await service.search_turn(contract)
    cards = response.messages[-1].results
    # A clarification/search phase keeps the intent scope: events, not venues.
    assert cards and all(card.kind == "event" for card in cards)


# --- filters summary / category fallback / undated / "ещё" ---------------


def test_filters_summary_lists_defaults_for_an_empty_contract():
    service = make_service(InMemoryStore(), FakeCollector([]))
    contract = StateContract.model_validate({"hard_filters": {}})
    text = service._filters_summary(contract, "ru")
    assert "Раздел: события" in text
    assert "Когда: ближайшие (по умолчанию)" in text
    assert "Где: Минск (по умолчанию)" in text
    assert "Тип: любые" in text
    assert "Темы: нет" in text
    assert "Компания: не указана" in text
    assert "Бюджет: без ограничений" in text
    assert "Удобства: нет" in text
    assert "Рейтинг: любой" in text
    assert "Возраст: любой" in text
    assert "Исключения: нет" in text


def test_filters_summary_reflects_a_fully_specified_contract():
    service = make_service(InMemoryStore(), FakeCollector([]))
    contract = StateContract.model_validate({
        "intent": "find_venues",
        "hard_filters": {
            "datetime": {"start": "2026-10-24T19:00:00+03:00"},
            "location": {"city": "Гомель"},
            "party_size": 4,
            "budget": {"max_price_per_person": 50},
            "min_rating": 4.5,
            "age_max": 12,
            "event_count": 2,
            "amenities_required": ["terrace"],
            "themes": ["jazz"],
        },
        "negative_filters": {
            "exclude_categories": ["sport"],
            "exclude_tags": ["кальян"],
            "exclude_districts": ["центр"],
        },
    })
    text = service._filters_summary(contract, "ru")
    assert "Раздел: места" in text
    assert "Событий в плане: 2" in text
    assert "Когда: 2026-10-24 19:00" in text
    assert "Где: Гомель" in text
    assert "Компания: 4 чел." in text
    assert "Бюджет: до 50 руб. на человека" in text
    assert "Удобства: terrace" in text
    assert "Рейтинг: от 4.5" in text
    assert "Возраст: до 12 лет" in text
    assert "Исключения: спорт, кальян, центр" in text


def test_fallback_query_expands_raw_category_codes():
    service = make_service(InMemoryStore(), FakeCollector([]))
    film = make_contract(
        hard_filters={"location": {"city": "Минск"}, "category": ["film"]},
        semantic_payload={"vector_query": ""})
    assert service._search_plan(film).vector_query == "кино, фильм, кинопоказ"

    concert = make_contract(
        hard_filters={"location": {"city": "Минск"},
                      "category": ["concert"]},
        semantic_payload={"vector_query": ""})
    assert service._search_plan(concert).vector_query == \
        "концерт, живая музыка"


@pytest.mark.asyncio
async def test_empty_film_events_fall_back_to_cinemas():
    store = InMemoryStore(
        [("cinema-uuid", [1.0, 0.0, 0.0],
          {"name": "Кинотеатр «Победа»", "rubric": "Кинотеатры",
           "city": "Минск", "source": "twogis_places"})],
        {"cinema-uuid": encode_sparse("кинотеатр победа")},
    )
    service = make_service(store, FakeCollector([]))
    contract = StateContract.model_validate({
        "dialogue_action": "search",
        "intent": "find_event_film",
        "hard_filters": {
            "datetime": {"start": "2026-10-24T12:00:00"},
            "location": {"city": "Минск"},
            "category": ["film"],
        },
        "semantic_payload": {"vector_query": "фильм"},
        "context_state": {"session_id": "film-fallback"},
    })
    response = await service.search_turn(contract)
    assert [message.kind for message in response.messages] == [
        "filters", "weather", "assistant", "results"]
    assert response.messages[2].text == "Событий с датой нет — вот кинотеатры"
    cards = response.messages[-1].results
    assert [card.kind for card in cards] == ["venue"]
    assert cards[0].title == "Кинотеатр «Победа»"


def test_film_intent_owns_the_film_category_and_cinema_fallback():
    service = make_service(InMemoryStore(), FakeCollector([]))
    contract = make_contract(
        intent="find_event_film",
        hard_filters={"location": {"city": "Минск"}},
        semantic_payload={"vector_query": ""})
    plan = service._search_plan(contract)
    assert plan.categories == ["film"]
    assert plan.vector_query == "кино, фильм, кинопоказ"
    assert CATEGORY_VENUE_FALLBACK["film"] == (
        "Кинотеатры", "search_empty_cinemas")


def film_hit(**payload) -> FusedHit:
    base = {
        "title": "Дюна",
        "category": "film",
        "start_at": "2026-11-26T10:00:00+03:00",
        "end_at": "2026-11-26T12:00:00+03:00",
    }
    base.update(payload)
    return FusedHit(id="film-point", score=1.0, payload=base)


def test_film_run_card_shows_the_run_end_instead_of_availability():
    service = make_service(InMemoryStore(), FakeCollector([]))
    card = service._to_card(
        film_hit(end_at="2026-12-05T23:00:00+03:00"), None, "ru")
    assert card.meta == "прокат до 05.12"
    assert card.next_session_at == ""
    assert card.cinema == ""
    assert card.film_genre is None
    assert card.film_duration_min is None

    english = service._to_card(
        film_hit(end_at="2026-12-05T23:00:00+03:00"), None, "en")
    assert english.meta == "in cinemas until 05.12"


def test_film_session_and_facts_are_rendered_and_structured():
    service = make_service(InMemoryStore(), FakeCollector([]))
    card = service._to_card(film_hit(
        end_at="2026-12-05T23:00:00+03:00",
        next_session_at="2026-11-26T19:30:00+03:00",
        cinema="Silver Screen",
        film_genre=["Фантастика"],
        film_duration_min=155,
    ), None, "ru")
    assert "ближайший сеанс 19:30 · Silver Screen" in card.meta
    assert "прокат до 05.12" in card.meta
    assert "Фантастика · 155 мин" in card.meta
    assert card.next_session_at == "2026-11-26T19:30:00+03:00"
    assert card.cinema == "Silver Screen"
    assert card.film_genre == ["Фантастика"]
    assert card.film_duration_min == 155


def test_film_card_without_new_fields_keeps_the_old_meta():
    service = make_service(InMemoryStore(), FakeCollector([]))
    card = service._to_card(film_hit(), None, "ru")
    # No run, session, genre or duration: exactly the previous fallback.
    assert card.meta == "наличие уточняйте у источника"
    assert card.film_genre is None
    assert card.film_duration_min is None


def film_store() -> InMemoryStore:
    return InMemoryStore(
        [
            ("dated-film", [1.0, 0.0, 0.0],
             {"title": "Премьера фильма", "city": "Минск",
              "category": "film", "price_min": 20.0,
              "start_at": "2026-11-25T19:00:00+00:00"}),
            ("undated-film", [1.0, 0.0, 0.0],
             {"title": "Анонс кинопоказа", "city": "Минск",
              "category": "film", "price_min": 15.0}),
            ("past-film", [1.0, 0.0, 0.0],
             {"title": "Прошлый кинопоказ", "city": "Минск",
              "category": "film", "price_min": 10.0,
              "start_at": "2026-11-01T19:00:00+00:00"}),
        ],
        {"dated-film": encode_sparse("премьера фильма"),
         "undated-film": encode_sparse("анонс кинопоказа"),
         "past-film": encode_sparse("прошлый кинопоказ")},
    )


@pytest.mark.asyncio
async def test_undated_posts_are_allowed_only_without_an_explicit_date():
    service = make_service(film_store(), FakeCollector([]), now=fixed_now)
    undated_contract = make_contract(hard_filters={
        "location": {"city": "Минск"}, "category": ["film"]})
    cards = (await service.search_turn(undated_contract)).messages[-1].results
    assert [card.event_id for card in cards] == ["dated-film", "undated-film"]
    by_id = {card.event_id: card for card in cards}
    assert by_id["undated-film"].meta == "дата уточняется"
    assert by_id["dated-film"].meta != "дата уточняется"
    # Undated mode must not resurrect a past dated event.
    assert "past-film" not in by_id

    dated_contract = make_contract(hard_filters={
        "datetime": {"start": "2026-11-25T00:00:00+03:00"},
        "location": {"city": "Минск"},
        "category": ["film"],
    })
    dated_cards = (await service.search_turn(dated_contract)).messages[-1].results
    assert [card.event_id for card in dated_cards] == ["dated-film"]


@pytest.mark.asyncio
async def test_search_more_empty_when_everything_was_shown():
    store = InMemoryStore(
        [("only", [1.0, 0.0, 0.0],
          {"title": "Единственный концерт", "city": "Минск",
           "price_min": 25.0,
           "start_at": "2026-12-05T19:00:00+00:00"})],
        {"only": encode_sparse("единственный концерт")},
    )
    service = make_service(store, FakeCollector([]), now=fixed_now)
    contract = make_contract(
        hard_filters={"location": {"city": "Минск"}},
        context_state={"session_id": "more", "shown_ids": ["only"]})
    response = await service.search_turn(contract)
    assert response.messages[-1].kind == "assistant"
    assert response.messages[-1].text == (
        "Больше вариантов нет — уточните фильтры")
