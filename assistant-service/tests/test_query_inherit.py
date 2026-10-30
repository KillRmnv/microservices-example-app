from app.api.routers.query import _inherit
from app.api.schemas.contract import StateContract


def contract(**overrides) -> StateContract:
    data = {
        "dialogue_action": "search",
        "hard_filters": {
            "datetime": {"start": "2026-10-31T00:00:00+03:00"},
            "location": {"city": "Минск"},
            "category": ["concert"],
            "party_size": 3,
            "budget": {"max_price_per_person": 80},
        },
        "negative_filters": {"exclude_categories": ["sport"]},
        "semantic_payload": {"vector_query": "джаз"},
        "context_state": {"session_id": "s1"},
    }
    data.update(overrides)
    return StateContract.model_validate(data)


def test_follow_up_inherits_missing_slots():
    previous = contract()
    fresh = StateContract.model_validate({
        "dialogue_action": "search",
        "hard_filters": {"location": {"city": "Минск"}, "party_size": 2},
        "semantic_payload": {"vector_query": ""},
    })
    merged = _inherit(fresh, previous)
    assert merged.hard_filters.datetime.start.startswith("2026-10-31")
    assert merged.hard_filters.category == ["concert"]
    assert merged.hard_filters.budget.max_price_per_person == 80
    assert merged.hard_filters.party_size == 3
    assert merged.semantic_payload.vector_query == "джаз"
    assert merged.negative_filters.exclude_categories == ["sport"]


def test_explicit_values_win_over_previous():
    previous = contract()
    fresh = contract()
    fresh.hard_filters.datetime.start = "2026-11-07T00:00:00+03:00"
    fresh.hard_filters.category = ["theatre"]
    fresh.semantic_payload.vector_query = "балет"
    merged = _inherit(fresh, previous)
    assert merged.hard_filters.datetime.start.startswith("2026-11-07")
    assert merged.hard_filters.category == ["theatre"]
    assert merged.semantic_payload.vector_query == "балет"
