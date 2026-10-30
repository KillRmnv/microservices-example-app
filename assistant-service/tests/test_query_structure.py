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


def make_service(payload: str, reasoning_payload: str | None = None,
                 **overrides) -> tuple[QueryStructureService, FakeProvider,
                                       FakeProvider | None]:
    fast = FakeProvider(payload)
    reasoning = FakeProvider(reasoning_payload if reasoning_payload is not None
                             else payload) if reasoning_payload is not None else None
    service = QueryStructureService(fast, Settings(**overrides),
                                    reasoning_provider=reasoning)
    return service, fast, reasoning


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
    assert provider.calls[0]["max_tokens"] == 512  # fast lane budget


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


@pytest.mark.asyncio
async def test_two_categories_are_preserved():
    # Search supports multi-category filters (classical = concert + theatre).
    payload = contract_json()
    data = json.loads(payload)
    data["hard_filters"]["category"] = ["theatre", "concert"]
    contract = await QueryStructureService(
        FakeProvider(json.dumps(data, ensure_ascii=False)), Settings()).parse(
            "классика завтра")
    assert contract.hard_filters.category == ["theatre", "concert"]


@pytest.mark.asyncio
async def test_classical_theme_is_preserved_and_visible():
    payload = contract_json()
    data = json.loads(payload)
    data["hard_filters"]["category"] = ["concert", "theatre"]
    data["hard_filters"]["themes"] = ["classical"]
    contract = await QueryStructureService(
        FakeProvider(json.dumps(data, ensure_ascii=False)), Settings()).parse(
            "хочу что-нибудь классическое завтра")
    assert contract.hard_filters.themes == ["classical"]
    assert contract.hard_filters.category == ["concert", "theatre"]


@pytest.mark.asyncio
async def test_structure_stage_cleans_slots_out_of_vector_query():
    payload = contract_json()
    data = json.loads(payload)
    data["semantic_payload"]["vector_query"] = (
        "команда из 3 человек для компании, завтра Минск")
    service = QueryStructureService(
        FakeProvider(json.dumps(data, ensure_ascii=False)), Settings())
    contract = await service.parse(
        "найди что-нибудь на компанию из 3 человек на завтра")
    vector = contract.semantic_payload.vector_query
    assert "человек" not in vector
    assert "завтра" not in vector
    assert "Минск" not in vector


@pytest.mark.asyncio
async def test_structure_stage_repairs_null_location_and_string_category():
    payload = json.dumps({
        "dialogue_action": "search",
        "hard_filters": {"location": None, "category": "concert",
                         "party_size": None, "budget": None,
                         "datetime": None},
        "semantic_payload": {"vector_query": "джаз"},
    }, ensure_ascii=False)
    contract = await QueryStructureService(FakeProvider(payload), Settings()).parse("джаз")
    assert contract.hard_filters.location.city == "Минск"
    assert contract.hard_filters.category == ["concert"]
    assert contract.hard_filters.party_size == 2


@pytest.mark.asyncio
async def test_broad_request_does_not_filter_by_every_category():
    # "Какие есть события на завтра?" makes the model list all categories;
    # keeping them would narrow the search to the first one (concerts).
    payload = contract_json()
    data = json.loads(payload)
    data["hard_filters"]["category"] = [
        "concert", "theatre", "exhibition", "film", "sport", "kids", "other"]
    contract = await QueryStructureService(
        FakeProvider(json.dumps(data, ensure_ascii=False)), Settings()).parse(
            "какие есть события на завтра?")
    assert contract.hard_filters.category == []


@pytest.mark.asyncio
async def test_simple_request_uses_fast_provider():
    service, fast, reasoning = make_service(contract_json(), contract_json())
    contract, reasoning_used, complex = await service.parse_meta("джаз завтра")
    assert contract.semantic_payload.vector_query == "тихий джаз"
    assert reasoning_used is False
    assert complex is False
    assert len(fast.calls) == 1
    assert len(reasoning.calls) == 0


@pytest.mark.asyncio
async def test_complex_request_uses_reasoning_provider():
    service, fast, reasoning = make_service(contract_json(), contract_json())
    _, reasoning_used, complex = await service.parse_meta(
        "тихий джаз в субботу до 50 рублей на двоих без фастфуда")
    assert complex is True
    assert reasoning_used is True
    assert len(fast.calls) == 0
    assert len(reasoning.calls) == 1
    assert reasoning.calls[0]["max_tokens"] == 2048  # full reasoning budget


@pytest.mark.asyncio
async def test_force_reasoning_overrides_heuristic():
    service, fast, reasoning = make_service(contract_json(), contract_json())
    _, reasoning_used, _ = await service.parse_meta(
        "джаз", force_reasoning=True)
    assert reasoning_used is True
    assert len(reasoning.calls) == 1
    _, reasoning_used, _ = await service.parse_meta(
        "тихий джаз в субботу до 50 рублей на двоих", force_reasoning=False)
    assert reasoning_used is False
    assert len(fast.calls) == 1


@pytest.mark.asyncio
async def test_reasoning_falls_back_to_fast_without_reasoning_provider():
    service = QueryStructureService(FakeProvider(contract_json()), Settings())
    contract, reasoning_used, complex = await service.parse_meta(
        "тихий джаз в субботу до 50 рублей на двоих без фастфуда")
    assert complex is True
    assert reasoning_used is False
    assert contract.semantic_payload.vector_query == "тихий джаз"
