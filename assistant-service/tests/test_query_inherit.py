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


def test_follow_up_inherits_amenities_age_rating_and_total_budget():
    from app.api.schemas.contract import BudgetFilter

    previous = contract()
    previous.hard_filters.party_size = 2
    previous.hard_filters.amenities_required = ["terrace"]
    previous.hard_filters.age_max = 12
    previous.hard_filters.min_rating = 4.5
    previous.hard_filters.budget = BudgetFilter(
        basis="total", total=40, max_price_per_person=20)
    fresh = StateContract.model_validate({
        "dialogue_action": "search",
        "hard_filters": {"party_size": None},
    })
    merged = _inherit(fresh, previous)
    assert merged.hard_filters.amenities_required == ["terrace"]
    assert merged.hard_filters.age_max == 12
    assert merged.hard_filters.min_rating == 4.5
    # The whole budget object (total + basis) is carried, not just the
    # derived per-person value.
    assert merged.hard_filters.budget.total == 40
    assert merged.hard_filters.budget.basis == "total"
    assert merged.hard_filters.budget.max_price_per_person == 20


def test_inherited_party_recalculates_a_total_budget():
    previous = contract()
    previous.hard_filters.party_size = 4
    fresh = StateContract.model_validate({
        "dialogue_action": "search",
        "hard_filters": {
            "party_size": None,
            "budget": {"basis": "total", "total": 80},
        },
    })
    merged = _inherit(fresh, previous)
    assert merged.hard_filters.party_size == 4
    assert merged.hard_filters.budget.total == 80
    # 80 for four people, not 80 each or 40 inherited from the old party.
    assert merged.hard_filters.budget.max_price_per_person == 20.0


# --- deterministic follow-up / clarification opt-in ---------------------


def test_follow_up_queries_are_recognised():
    from app.api.routers.query import _is_follow_up

    for query in ("ещё", "еще", "а ещё?", "другие", "другой", "варианты",
                  "подешевле", "дешевле", "подороже", "дороже",
                  "что-нибудь", "что-то", "А ещё!"):
        assert _is_follow_up(query) is True
    for query in ("ещё концерты", "джаз", "что-то интересное"):
        assert _is_follow_up(query) is False


def test_follow_up_contract_keeps_the_previous_topic_and_page():
    from app.api.routers.query import _follow_up_contract

    previous = contract()
    previous.context_state.shown_ids = ["aaa", "7"]
    previous.hard_filters.themes = ["jazz"]
    previous.hard_filters.event_count = 2
    copy = _follow_up_contract(previous)
    assert copy.dialogue_action == "search"
    assert copy.clarify_missing is False
    assert copy.needs_clarification is False
    assert copy.clarification_slots == []
    assert copy.intent == previous.intent
    assert copy.hard_filters.category == ["concert"]
    assert copy.hard_filters.themes == ["jazz"]
    assert copy.hard_filters.datetime.start == \
        previous.hard_filters.datetime.start
    assert copy.hard_filters.budget.max_price_per_person == 80
    assert copy.hard_filters.party_size == 3
    assert copy.hard_filters.event_count == 2
    assert copy.negative_filters.exclude_categories == ["sport"]
    assert copy.semantic_payload.vector_query == "джаз"
    assert copy.context_state.shown_ids == ["aaa", "7"]


def test_follow_up_endpoint_does_not_call_the_llm(monkeypatch):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    import app.api.routers.query as query_router
    from app.main import create_app

    class ExplodingStructure:
        async def parse_meta(self, *args, **kwargs):
            raise AssertionError("the model must not run for «ещё»")

    monkeypatch.setattr(query_router, "get_components",
                        lambda: SimpleNamespace(structure=ExplodingStructure()))
    previous = contract()
    previous.context_state.shown_ids = ["aaa", "7"]
    client = TestClient(create_app())
    response = client.post("/assistant/query", json={
        "query": "ещё",
        "contract": previous.model_dump(),
    })
    assert response.status_code == 200
    body = response.json()
    assert body["reasoning_used"] is False
    assert body["complex"] is False
    result = body["contract"]
    assert result["dialogue_action"] == "search"
    assert result["clarify_missing"] is False
    assert result["needs_clarification"] is False
    assert result["hard_filters"]["category"] == ["concert"]
    assert result["context_state"]["shown_ids"] == ["aaa", "7"]


def test_clarification_is_downgraded_without_opt_in():
    from app.api.routers.query import _downgrade_clarification

    request = StateContract.model_validate({
        "dialogue_action": "ask_clarification",
        "clarify_missing": False,
        "clarification_slots": ["datetime"],
        "hard_filters": {"category": ["film"]},
    })
    result = _downgrade_clarification(request, None)
    assert result.dialogue_action == "search"
    assert result.needs_clarification is False
    assert result.clarification_slots == []
    assert result.hard_filters.category == ["film"]


def test_clarification_is_honoured_with_explicit_opt_in():
    from app.api.routers.query import _downgrade_clarification

    request = StateContract.model_validate({
        "dialogue_action": "ask_clarification",
        "clarify_missing": True,
        "hard_filters": {},
    })
    assert _downgrade_clarification(
        request, None).dialogue_action == "ask_clarification"


def test_clarification_is_not_repeated_on_the_same_topic():
    from app.api.routers.query import _downgrade_clarification

    previous = contract()
    previous.needs_clarification = True
    request = StateContract.model_validate({
        "dialogue_action": "ask_clarification",
        "clarify_missing": True,
        "hard_filters": {},
    })
    result = _downgrade_clarification(request, previous)
    assert result.dialogue_action == "search"
    assert result.clarification_slots == []


def test_follow_up_inherits_the_plan_event_count():
    previous = contract()
    previous.hard_filters.event_count = 2
    fresh = StateContract.model_validate({
        "dialogue_action": "search",
        "hard_filters": {"themes": ["jazz"]},
    })
    merged = _inherit(fresh, previous)
    assert merged.hard_filters.event_count == 2
