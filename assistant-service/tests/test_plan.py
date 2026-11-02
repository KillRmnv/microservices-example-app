import json

import pytest

from app.api.schemas.contract import StateContract
from app.api.schemas.dialogue import ChatMessage, DialogResponse, ResultCard
from app.core.config import Settings
from app.services.plan_service import PlanService


class FakeProvider:
    name = "fake"

    def __init__(self, payload: str):
        self.payload = payload
        self.calls: list[dict] = []

    async def complete(self, *, system, user, json_mode=False, max_tokens=512):
        self.calls.append({"system": system, "user": user,
                           "json_mode": json_mode, "max_tokens": max_tokens})
        return self.payload


class StubDialogue:
    def __init__(self, response: DialogResponse):
        self._response = response

    def apply_rules(self, contract, language=None):
        return contract

    async def search_turn(self, contract):
        return self._response

    def record_run(self, contract, duration_ms):
        pass


def search_response() -> DialogResponse:
    contract = StateContract.model_validate({
        "dialogue_action": "search",
        "hard_filters": {"location": {"city": "Минск"}, "party_size": 2},
        "semantic_payload": {"vector_query": "джаз", "language": "ru"},
        "context_state": {"session_id": "s1"},
    })
    cards = [
        ResultCard(event_id="1", title="Джаз вечером", meta="СБ · Зал", price="от 50 руб."),
        ResultCard(event_id="2", title="Выставка", meta="ВС · Музей", price="от 10 руб."),
    ]
    return DialogResponse(contract=contract, messages=[
        ChatMessage(kind="filters", text="Условия зафиксированы."),
        ChatMessage(kind="results", text="Нашлось:", results=cards),
    ])


def plan_json() -> str:
    return json.dumps({
        "summary": "Вечер джаза и выставки.",
        "steps": [
            {"time": "19:00", "title": "Джаз вечером",
             "detail": "Зал · от 50 руб.", "source": "assistant"},
            {"time": "21:00", "title": "Выставка",
             "detail": "Музей · от 10 руб.", "source": "assistant"},
        ],
    }, ensure_ascii=False)


@pytest.mark.asyncio
async def test_plan_stage_returns_itinerary():
    provider = FakeProvider(plan_json())
    service = PlanService(provider, StubDialogue(search_response()), Settings())
    response = await service.build_plan(search_response().contract)

    kinds = [message.kind for message in response.messages]
    assert kinds == ["filters", "results", "plan"]
    plan = response.messages[-1]
    assert plan.text == "Вечер джаза и выставки."
    assert [step.time for step in plan.plan] == ["19:00", "21:00"]
    assert provider.calls[0]["json_mode"] is True
    assert provider.calls[0]["max_tokens"] == 3072  # plan budget


@pytest.mark.asyncio
async def test_plan_stage_retries_without_thinking():
    primary = FakeProvider("")  # reasoning exhausted the budget
    fallback = FakeProvider(plan_json())
    service = PlanService(primary, StubDialogue(search_response()), Settings(),
                          fallback_provider=fallback)
    response = await service.build_plan(search_response().contract)

    assert [message.kind for message in response.messages][-1] == "plan"
    assert response.messages[-1].text == "Вечер джаза и выставки."
    assert len(fallback.calls) == 1


@pytest.mark.asyncio
async def test_plan_stage_falls_back_to_cards():
    provider = FakeProvider(json.dumps({"summary": "x", "steps": []}))
    service = PlanService(provider, StubDialogue(search_response()), Settings())
    response = await service.build_plan(search_response().contract)

    plan = response.messages[-1]
    assert plan.kind == "plan"
    assert [step.title for step in plan.plan] == ["Джаз вечером", "Выставка"]
    assert "Модель не ответила" in plan.text


@pytest.mark.asyncio
async def test_plan_stage_non_json_falls_back_to_cards():
    provider = FakeProvider("не json")
    service = PlanService(provider, StubDialogue(search_response()), Settings())
    response = await service.build_plan(search_response().contract)
    assert response.messages[-1].kind == "plan"
    assert len(response.messages[-1].plan) == 2


@pytest.mark.asyncio
async def test_plan_stage_without_results_returns_search_response():
    contract = search_response().contract
    empty = DialogResponse(contract=contract, messages=[
        ChatMessage(kind="assistant", text="Ничего не нашлось."),
    ])
    service = PlanService(FakeProvider(plan_json()), StubDialogue(empty),
                          Settings())
    response = await service.build_plan(contract)
    assert [message.kind for message in response.messages] == ["assistant"]


class ContextDialogue:
    """Returns different cards for the animal and restaurant contracts."""

    def apply_rules(self, contract, language=None):
        return contract

    async def search_turn(self, contract):
        if "animals" in contract.hard_filters.themes:
            cards = [ResultCard(
                event_id="10", detail_id="ev-10", kind="event",
                title="Дельфинарий", meta="наличие уточняйте у источника",
                price="55 руб.", start_at="2026-11-03T18:00:00+03:00")]
        else:
            cards = [ResultCard(
                event_id="20", detail_id="v-20", kind="venue",
                title="Benedict Bistro", meta="Бистро · Минск",
                price="", start_at="")]
        return DialogResponse(contract=contract, messages=[
            ChatMessage(kind="filters", text="Условия зафиксированы."),
            ChatMessage(kind="results", text="Нашлось:", results=cards),
        ])

    def record_run(self, contract, duration_ms):
        pass


@pytest.mark.asyncio
async def test_plan_combines_earlier_topic_with_current_food_request():
    animal = StateContract.model_validate({
        "intent": "find_events",
        "hard_filters": {
            "datetime": {"start": "2026-11-03T18:00:00+03:00",
                         "end": "2026-11-03T23:59:00+03:00"},
            "location": {"city": "Минск"},
            "themes": ["animals"],
            "party_size": 2,
        },
        "semantic_payload": {"vector_query": "животные, дельфинарий"},
    })
    food = StateContract.model_validate({
        "intent": "find_venue_restaurant",
        "hard_filters": {
            "datetime": {"start": "2026-11-03T18:00:00+03:00",
                         "end": "2026-11-03T23:59:00+03:00"},
            "location": {"city": "Минск"},
            "themes": ["food"],
            "party_size": 2,
        },
        "semantic_payload": {"vector_query": "поужинать"},
    })
    provider = FakeProvider(json.dumps({
        "summary": "Животные и ужин.",
        "steps": [
            {"candidate": 1, "title": "Дельфинарий", "time": "18:00"},
            {"candidate": 2, "title": "Benedict Bistro", "time": "20:00"},
        ],
    }, ensure_ascii=False))
    service = PlanService(provider, ContextDialogue(), Settings())
    response = await service.build_plan(food, [animal])

    plan = response.messages[-1]
    assert [step.title for step in plan.plan] == ["Дельфинарий", "Benedict Bistro"]
    assert [step.kind for step in plan.plan] == ["event", "venue"]
    system = provider.calls[0]["system"]
    assert "Дельфинарий" in provider.calls[0]["user"]
    assert "Benedict Bistro" in provider.calls[0]["user"]
    assert "2026-11-03T18:00:00+03:00" in provider.calls[0]["user"]
    assert "2026-11-03T18:00:00+03:00" in system  # window
    assert "2026-11-03T23:59:00+03:00" in system


@pytest.mark.asyncio
async def test_plan_deduplicates_repeated_contexts():
    contract = search_response().contract
    provider = FakeProvider(plan_json())
    service = PlanService(provider, StubDialogue(search_response()), Settings())
    response = await service.build_plan(contract, [contract, contract])
    assert [message.kind for message in response.messages][-1] == "plan"
    # Three identical cards would otherwise produce duplicate candidates.
    assert provider.calls[0]["user"].count("Джаз вечером") == 1


@pytest.mark.asyncio
async def test_plan_injects_event_when_model_follows_only_latest_request():
    animal = StateContract.model_validate({
        "intent": "find_events",
        "hard_filters": {"themes": ["animals"], "party_size": 2,
                         "location": {"city": "Минск"}},
        "semantic_payload": {"vector_query": "животные"},
    })
    food = StateContract.model_validate({
        "intent": "find_venue_restaurant",
        "hard_filters": {"themes": ["food"], "party_size": 2,
                         "location": {"city": "Минск"}},
        "semantic_payload": {"vector_query": "ужин"},
    })
    provider = FakeProvider(json.dumps({
        "summary": "Ужин.",
        "steps": [{"candidate": 2, "title": "Benedict Bistro",
                   "time": "20:00"}],
    }, ensure_ascii=False))
    service = PlanService(provider, ContextDialogue(), Settings())
    response = await service.build_plan(food, [animal])

    plan = response.messages[-1]
    assert [step.kind for step in plan.plan] == ["event", "venue"]
    assert plan.plan[0].title == "Дельфинарий"
    assert plan.plan[0].time == "18:00"
