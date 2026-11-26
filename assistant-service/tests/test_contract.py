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
    # Missing location stays unset: the assistant asks or applies "any".
    assert contract.hard_filters.location.city is None
    assert sanitize(contract).hard_filters.location.city is None


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
    assert clean.hard_filters.location.city is None
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


def test_sanitize_keeps_any_filters():
    from app.api.schemas.contract import sanitize

    contract = StateContract.model_validate({
        "hard_filters": {
            "datetime": {"start": "2026-10-31T00:00:00", "any": True},
            "location": {"city": "Минск", "any": True},
            "party_size": 0,
            "budget": {"max_price_per_person": 50, "any": True},
        },
        "context_state": {"session_id": "s1"},
    })
    clean = sanitize(contract)
    assert clean.hard_filters.datetime.any is True
    assert clean.hard_filters.datetime.start is None
    assert clean.hard_filters.location.any is True
    assert clean.hard_filters.location.city is None
    assert clean.hard_filters.party_size == 0
    assert clean.hard_filters.budget.any is True


def test_dialogue_endpoint_accepts_no_date():
    from app.main import app

    client = TestClient(app)
    response = client.post("/assistant/dialogue", json={
        "dialogue_action": "search",
        "hard_filters": {},
        "context_state": {"session_id": "s1"},
    })
    assert response.status_code == 200
    body = response.json()
    assert body["dialogue_action"] == "search"
    assert body["needs_clarification"] is False


def test_dialogue_v2_capabilities_has_visible_message():
    from app.main import app

    client = TestClient(app)
    response = client.post("/assistant/dialogue/v2", json={
        "dialogue_action": "search",
        "intent": "capabilities",
        "hard_filters": {},
        "context_state": {"session_id": "s1"},
    })
    assert response.status_code == 200
    body = response.json()
    assert len(body["messages"]) == 1
    assert body["messages"][0]["kind"] == "assistant"
    assert "события" in body["messages"][0]["text"]


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


def test_sanitize_makes_evening_window_stable():
    contract = StateContract.model_validate({
        "hard_filters": {
            "datetime": {
                "start": "2026-11-27T17:00:00+03:00",
                "raw_expression": "вечер пятницы",
                "timezone": "Europe/Minsk",
            }
        },
    })
    clean = sanitize(contract)
    assert clean.hard_filters.datetime.start == "2026-11-27T18:00:00+03:00"
    assert clean.hard_filters.datetime.end == "2026-11-27T23:59:00+03:00"


def test_sanitize_keeps_explicit_clock_inside_evening():
    contract = StateContract.model_validate({
        "hard_filters": {
            "datetime": {
                "start": "2026-11-27T20:00:00+03:00",
                "raw_expression": "в пятницу вечером в 20:00",
                "timezone": "Europe/Minsk",
            }
        },
    })
    clean = sanitize(contract)
    assert clean.hard_filters.datetime.start == "2026-11-27T20:00:00+03:00"
    assert clean.hard_filters.datetime.end == "2026-11-27T23:59:00+03:00"


def test_sanitize_drops_unknown_categories():
    contract = StateContract.model_validate({
        "hard_filters": {"category": ["Restaurant", " concert ", "concert",
                                      "restaurant"]},
    })
    clean = sanitize(contract)
    assert clean.hard_filters.category == ["concert"]


def test_sanitize_caps_themes_and_negative_filters():
    contract = StateContract.model_validate({
        "hard_filters": {
            "themes": [" Jazz ", "jazz"] + [f"theme-{i}" for i in range(8)],
            "amenities_required": [f" option-{i} " for i in range(15)],
        },
        "negative_filters": {
            "exclude_categories": ["Sport", "sport", "Karaoke"],
            "exclude_tags": [f"tag-{i}" for i in range(15)],
            "exclude_districts": [" Центр ", "центр", "x" * 60],
        },
    })
    clean = sanitize(contract)
    themes = clean.hard_filters.themes
    assert themes[0] == "jazz" and themes.count("jazz") == 1
    assert len(themes) == 5 and all(len(theme) <= 40 for theme in themes)
    amenities = clean.hard_filters.amenities_required
    assert len(amenities) == 10
    assert amenities[0] == "option-0"
    negative = clean.negative_filters
    assert negative.exclude_categories == ["sport", "karaoke"]
    assert len(negative.exclude_tags) == 10
    assert negative.exclude_districts == ["центр", "x" * 40]


def test_sanitize_caps_vector_query_and_session_id():
    contract = StateContract.model_validate({
        "semantic_payload": {"vector_query": "  " + "джаз " * 100 + "  "},
        "context_state": {"session_id": "  " + "s" * 200 + "  "},
    })
    clean = sanitize(contract)
    assert len(clean.semantic_payload.vector_query) == 300
    assert clean.semantic_payload.vector_query.startswith("джаз")
    assert len(clean.context_state.session_id) == 128
    assert sanitize(StateContract.model_validate(
        {"context_state": {"session_id": "   "}})
    ).context_state.session_id == "anonymous"


def test_sanitize_clears_non_positive_or_any_budget():
    contract = StateContract.model_validate({
        "hard_filters": {"budget": {"max_price_per_person": 50, "any": True}},
    })
    assert sanitize(contract).hard_filters.budget.max_price_per_person is None
    zero = StateContract.model_validate({
        "hard_filters": {"budget": {"max_price_per_person": 0}},
    })
    assert sanitize(zero).hard_filters.budget.max_price_per_person is None
    negative = StateContract.model_validate({
        "hard_filters": {"budget": {"max_price_per_person": -5}},
    })
    assert sanitize(negative).hard_filters.budget.max_price_per_person is None


def test_sanitize_does_not_fill_default_city():
    clean = sanitize(StateContract.model_validate({
        "hard_filters": {"category": ["concert"]},
    }))
    assert clean.hard_filters.location.city is None


# --- budget basis / age / rating ---------------------------------------


def test_sanitize_total_budget_is_derived_and_idempotent():
    contract = StateContract.model_validate({
        "hard_filters": {"party_size": 2,
                         "budget": {"basis": "total", "total": 40}},
    })
    once = sanitize(contract)
    budget = once.hard_filters.budget
    assert budget.basis == "total"          # keeps the user's basis
    assert budget.total == 40.0             # keeps the user's sum
    assert budget.max_price_per_person == 20.0

    twice = sanitize(once)
    assert twice.hard_filters.budget.max_price_per_person == 20.0
    assert twice.hard_filters.budget.total == 40.0
    assert twice.hard_filters.budget.basis == "total"


def test_sanitize_recomputes_total_budget_when_party_changes():
    contract = StateContract.model_validate({
        "hard_filters": {"party_size": 2,
                         "budget": {"basis": "total", "total": 40}},
    })
    clean = sanitize(contract)
    clean.hard_filters.party_size = 4
    updated = sanitize(clean)
    # 40 on everyone at 4 people is 10 each, not 20 / 4.
    assert updated.hard_filters.budget.max_price_per_person == 10.0
    assert updated.hard_filters.budget.total == 40.0


def test_sanitize_reads_legacy_total_as_a_total():
    clean = sanitize(StateContract.model_validate({
        "hard_filters": {
            "party_size": 2,
            "budget": {"basis": "total", "max_price_per_person": 40},
        },
    }))
    budget = clean.hard_filters.budget
    assert budget.total == 40.0
    assert budget.max_price_per_person == 20.0


def test_sanitize_keeps_per_person_budget_as_per_person():
    clean = sanitize(StateContract.model_validate({
        "hard_filters": {
            "party_size": 2,
            "budget": {"basis": "per_person", "max_price_per_person": 40},
        },
    }))
    budget = clean.hard_filters.budget
    assert budget.max_price_per_person == 40.0
    assert budget.total is None
    assert budget.basis == "per_person"


def test_sanitize_total_without_party_uses_the_configured_default():
    clean = sanitize(StateContract.model_validate({
        "hard_filters": {"budget": {"basis": "total", "total": 40}},
    }))
    budget = clean.hard_filters.budget
    assert budget.total == 40.0
    # No named party: use settings.default_party_size (1), not a guess.
    assert budget.max_price_per_person == 40.0
    assert budget.basis == "total"


def test_sanitize_any_budget_clears_total_and_per_person():
    clean = sanitize(StateContract.model_validate({
        "hard_filters": {
            "budget": {"basis": "total", "total": 40, "any": True},
        },
    }))
    budget = clean.hard_filters.budget
    assert budget.total is None
    assert budget.max_price_per_person is None
    assert budget.basis == "per_person"


def test_sanitize_clamps_age_max_and_min_rating():
    clean = sanitize(StateContract.model_validate({
        "hard_filters": {"age_max": 99, "min_rating": 9},
    }))
    assert clean.hard_filters.age_max == 21
    assert clean.hard_filters.min_rating == 5.0
    low = sanitize(StateContract.model_validate({
        "hard_filters": {"age_max": -3, "min_rating": -1},
    }))
    assert low.hard_filters.age_max == 0
    assert low.hard_filters.min_rating == 0.0


# --- target collection / presentation language -------------------------


def test_sanitize_normalizes_target_collection_aliases():
    for raw, expected in (
        ("venues", "venues"),
        ("venues_atmosphere", "venues"),
        ("places", "venues"),
        (" Events ", "events"),
        ("both", "both"),
        ("spaceship", None),
        (None, None),
    ):
        clean = sanitize(StateContract.model_validate({
            "semantic_payload": {"target_collection": raw},
        }))
        assert clean.semantic_payload.target_collection == expected


def test_sanitize_clamps_language_to_presentation_locales():
    assert sanitize(StateContract.model_validate(
        {"semantic_payload": {"language": "en"}})
    ).semantic_payload.language == "en"
    assert sanitize(StateContract.model_validate(
        {"semantic_payload": {"language": "en-US"}})
    ).semantic_payload.language == "en"
    # Retrieval stays Russian; an unsupported presentation locale is dropped.
    assert sanitize(StateContract.model_validate(
        {"semantic_payload": {"language": "de"}})
    ).semantic_payload.language == "ru"


def test_sanitize_unknown_language_uses_the_configured_default(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "default_language", "en")
    clean = sanitize(StateContract.model_validate(
        {"semantic_payload": {"language": "de"}}))
    assert clean.semantic_payload.language == "en"


# --- shown_ids / plan event_count ---------------------------------------


def test_sanitize_cleans_shown_ids():
    clean = sanitize(StateContract.model_validate({
        "context_state": {"shown_ids": [
            "  abc  ", "abc", 42, "", "x" * 80,
            *[f"id-{i}" for i in range(120)],
        ]},
    }))
    ids = clean.context_state.shown_ids
    assert ids[0] == "abc"
    assert ids.count("abc") == 1
    assert "42" in ids
    assert "" not in ids
    assert all(len(value) <= 64 for value in ids)
    assert len(ids) == 100


def test_sanitize_ignores_non_list_shown_ids():
    clean = sanitize(StateContract.model_validate({
        "context_state": {"shown_ids": {"a": 1}},
    }))
    assert clean.context_state.shown_ids == []


def test_sanitize_clamps_event_count_to_one_through_five():
    for raw, expected in ((0, 1), (1, 1), (3, 3), (9, 5), ("2", 2), (None, None)):
        clean = sanitize(StateContract.model_validate({
            "hard_filters": {"event_count": raw},
        }))
        assert clean.hard_filters.event_count == expected
