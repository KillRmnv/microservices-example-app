import json

import pytest

from app.core.config import Settings
from app.errors import UpstreamError
from app.services.query_structure import QueryStructureService


class FakeProvider:
    name = "fake"

    def __init__(self, payload: str):
        self.payload = payload
        self.calls: list[dict] = []

    async def complete(self, *, system, user, json_mode=False, max_tokens=512):
        self.calls.append({"system": system, "user": user,
                           "json_mode": json_mode, "max_tokens": max_tokens})
        return self.payload


def contract_json(**overrides) -> str:
    data = {
        "dialogue_action": "search",
        "hard_filters": {
            "datetime": {"start": "2026-10-31T19:00:00",
                         "raw_expression": "в субботу", "is_relative": True},
            "location": {"city": "Минск"},
            "category": ["concert"],
            "party_size": 2,
            "budget": {"max_price_per_person": 50},
        },
        "semantic_payload": {"vector_query": "тихий джаз", "language": "ru"},
        "context_state": {"turn_count": 1, "session_id": ""},
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


@pytest.mark.asyncio
async def test_structure_stage_parses_json_and_sanitises():
    provider = FakeProvider(contract_json())
    service = QueryStructureService(provider, Settings())

    contract = await service.parse("тихий джаз в субботу", session_id="s1")

    assert contract.dialogue_action == "search"
    assert contract.hard_filters.category == ["concert"]
    assert contract.hard_filters.datetime.start.startswith("2026-10-31")
    assert contract.hard_filters.budget.max_price_per_person == 50
    assert contract.semantic_payload.vector_query == "тихий джаз"
    assert contract.context_state.session_id == "s1"
    assert contract.context_state.turn_count == 2  # sanitize advances the turn
    assert contract.hard_filters.location.city == "Минск"
    assert provider.calls[0]["json_mode"] is True


@pytest.mark.asyncio
async def test_structure_stage_accepts_code_fences_and_fills_vectors():
    payload = "```json\n" + contract_json() + "\n```"
    service = QueryStructureService(FakeProvider(payload), Settings())
    contract = await service.parse("что-то интересное")
    # Missing vector query falls back to the raw request, not empty string.
    assert contract.semantic_payload.vector_query == "тихий джаз"


@pytest.mark.asyncio
async def test_structure_stage_rejects_empty_or_non_json():
    with pytest.raises(UpstreamError):
        await QueryStructureService(FakeProvider(""), Settings()).parse("x")
    with pytest.raises(UpstreamError):
        await QueryStructureService(FakeProvider("не json"), Settings()).parse("x")
