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
