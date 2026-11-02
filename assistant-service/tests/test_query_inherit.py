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
        "hard_filters": {"location": {"city": "Минск"}, "party_size": None},
        "semantic_payload": {"vector_query": ""},
    })
    merged = _inherit(fresh, previous)
    assert merged.hard_filters.datetime.start.startswith("2026-10-31")
    assert merged.hard_filters.category == ["concert"]
    assert merged.hard_filters.budget.max_price_per_person == 80
    assert merged.hard_filters.party_size == 3
    assert merged.semantic_payload.vector_query == "джаз"
    assert merged.negative_filters.exclude_categories == ["sport"]


def test_follow_up_keeps_explicit_party_size():
    previous = contract()
    fresh = StateContract.model_validate({
        "dialogue_action": "search",
        "hard_filters": {"party_size": 2},
    })
    assert _inherit(fresh, previous).hard_filters.party_size == 2


def test_clarification_answer_keeps_previous_topic():
    previous = contract()
    previous.needs_clarification = True
    previous.intent = "find_venues"
    previous.hard_filters.category = []
    previous.hard_filters.themes = ["food"]
    previous.semantic_payload.vector_query = "пообедать"
    fresh = StateContract.model_validate({
        "dialogue_action": "search",
        "intent": "find_venues",
        "clarify_missing": True,
        "hard_filters": {"location": {"city": "Минск"}, "party_size": 3},
        "semantic_payload": {"vector_query": "бюджет не важен, для 2-3 человек"},
    })
    merged = _inherit(fresh, previous)
    assert merged.semantic_payload.vector_query == "пообедать"
    assert merged.hard_filters.themes == ["food"]
    assert merged.hard_filters.location.city == "Минск"
    assert merged.hard_filters.party_size == 3


def test_clarification_answer_keeps_intent_even_if_llm_flips_it():
    """The LLM sometimes re-labels a slot answer as find_events."""
    previous = contract()
    previous.needs_clarification = True
    previous.intent = "find_venue_restaurant"
    previous.hard_filters.category = []
    previous.hard_filters.themes = ["lunch"]
    previous.semantic_payload.vector_query = "обед, поесть"
    fresh = StateContract.model_validate({
        "dialogue_action": "search",
        "intent": "find_events",
        "hard_filters": {
            "location": {"city": "Минск"},
            "themes": ["lunch"],
            "party_size": 3,
        },
        "semantic_payload": {"vector_query": "бюджет не важен, для 2"},
    })
    merged = _inherit(fresh, previous)
    assert merged.intent == "find_venue_restaurant"
    assert merged.semantic_payload.vector_query == "обед, поесть"
    assert merged.hard_filters.location.city == "Минск"


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
