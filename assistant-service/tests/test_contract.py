import pytest
from fastapi.testclient import TestClient

from app.api.schemas.contract import StateContract, sanitize


def test_valid_contract_passes():
    contract = StateContract.model_validate({
        "dialogue_action": "search",
        "hard_filters": {"datetime": {"start": "2026-10-24T19:00:00"}},
        "context_state": {"turn_count": 3, "session_id": "s1"},
    })
    assert contract.dialogue_action == "search"
    # Defaults are filled from settings by sanitize, not by the DTO.
    assert contract.hard_filters.location.city is None
    assert sanitize(contract).hard_filters.location.city == "Минск"


def test_unknown_action_rejected():
    with pytest.raises(Exception):
        StateContract.model_validate({"dialogue_action": "hack_the_planet"})


def test_sanitize_clamps_and_bumps_turn():
    contract = StateContract.model_validate({
        "hard_filters": {"party_size": 99, "location": {"city": ""}},
        "needs_clarification": True,
        "clarification_prompt": "client says hi",
        "context_state": {"turn_count": 1},
    })
    clean = sanitize(contract)
    assert clean.hard_filters.party_size == 20
    assert clean.hard_filters.location.city == "Минск"
    assert clean.context_state.turn_count == 2
    assert clean.semantic_payload.language == "ru"
    assert clean.hard_filters.datetime is None
    # Server owns clarification flags.
    assert clean.needs_clarification is False
    assert clean.clarification_prompt is None


def test_sanitize_drops_unknown_fields():
    contract = StateContract.model_validate({
        "hard_filters": {"datetime": {"start": "2026-10-24T19:00:00"}},
        "injected": "drop me",
    })
    assert not hasattr(contract, "injected")


def test_dialogue_endpoint_asks_for_date():
    from app.main import app

    client = TestClient(app)
    response = client.post("/assistant/dialogue", json={
        "dialogue_action": "search",
        "hard_filters": {},
        "context_state": {"session_id": "s1"},
    })
    assert response.status_code == 200
    body = response.json()
    assert body["dialogue_action"] == "ask_clarification"
    assert body["needs_clarification"] is True
    assert "дату" in body["clarification_prompt"]


def test_dialogue_endpoint_accepts_dated_search():
    from app.main import app

    client = TestClient(app)
    response = client.post("/assistant/dialogue", json={
        "dialogue_action": "search",
        "hard_filters": {"datetime": {"start": "2026-10-24T19:00:00"}},
        "context_state": {"session_id": "s1"},
    })
    assert response.status_code == 200
    body = response.json()
    assert body["dialogue_action"] == "search"
    assert body["needs_clarification"] is False


def test_unknown_dialogue_action_returns_422():
    from app.main import app

    client = TestClient(app)
    response = client.post("/assistant/dialogue", json={
        "dialogue_action": "drop_tables"})
    assert response.status_code == 422
