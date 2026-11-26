"""LLM structure endpoint: raw query -> dialogue contract + intent."""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends

from ..deps import get_components
from ..schemas.plan import QueryResponse
from ..schemas.query import QueryRequest
from ..schemas.contract import (PARTY_SIZE_MAX, PARTY_SIZE_MIN,
                                StateContract, sanitize)
from ...core import i18n
from ...core.rate_limit import rate_limit
from ...models import intent as intents

log = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["dialogue"])

# "Ещё", "а подешевле?", "другие варианты" are pagination intents, not new
# topics. The model used to drift to an unrelated category on these, so they
# are answered deterministically from the previous contract and skip the LLM.
FOLLOW_UP_RE = re.compile(
    r"^(?:а\s+)?(?:ещё|еще|другие|другой|варианты|подешевле|дешевле|"
    r"подороже|дороже|что-нибудь|что-то)[\s?.!]*$",
    re.IGNORECASE)


def _is_follow_up(query: str) -> bool:
    return bool(FOLLOW_UP_RE.match((query or "").strip()))


def _follow_up_contract(previous: StateContract) -> StateContract:
    """Copy the previous turn for pagination, resetting clarification flags.

    Intent, category, themes, datetime, budget, party, negatives, vector
    query and `shown_ids` all survive: the search then excludes already shown
    cards and returns the next page. Sanitize keeps the contract within the
    server-side bounds.
    """
    contract = previous.model_copy(deep=True)
    contract.dialogue_action = "search"
    contract.clarify_missing = False
    contract.needs_clarification = False
    contract.clarification_slots = []
    contract.clarification_prompt = None
    return sanitize(contract)


def _downgrade_clarification(contract: StateContract,
                             previous: StateContract | None) -> StateContract:
    """Clarification is opt-in and never repeats on the same topic.

    The structure model no longer asks questions for search intents, but an
    old client or a disobedient model may still return `ask_clarification`.
    Honor it only when the client explicitly set `clarify_missing=true` and
    this topic has not already been clarified once.
    """
    if contract.dialogue_action != "ask_clarification":
        return contract
    # One-shot rule: never ask the same topic twice. Proceed with defaults.
    repeated = previous is not None and previous.needs_clarification
    if repeated or not contract.clarify_missing:
        contract.dialogue_action = "search"
        contract.needs_clarification = False
        contract.clarification_slots = []
        contract.clarification_prompt = None
    return contract


def _inherit(contract, previous):
    """Carry missing follow-up slots; the LLM owns intent classification."""
    if previous is None:
        return contract
    if previous.clarify_missing:
        contract.clarify_missing = True
    hard = contract.hard_filters
    before = previous.hard_filters
    new_topic = (bool(hard.category or hard.themes)
                 and (set(hard.category) != set(before.category)
                      or set(hard.themes) != set(before.themes)))
    if (hard.datetime is None
            or (not hard.datetime.any and not hard.datetime.start)):
        if before.datetime is not None:
            hard.datetime = before.datetime
    if not hard.location.any and not hard.location.city \
            and (before.location.city or before.location.any):
        hard.location = before.location
    if not hard.category and before.category:
        hard.category = list(before.category)
    if not hard.themes and before.themes:
        hard.themes = list(before.themes)
    if hard.budget is None and before.budget is not None:
        # Copy: a total budget may be re-derived below and must not mutate
        # the previous turn's contract.
        hard.budget = before.budget.model_copy(deep=True)
    if hard.party_size is None and before.party_size is not None:
        hard.party_size = before.party_size
    if not hard.amenities_required and before.amenities_required:
        hard.amenities_required = list(before.amenities_required)
    if hard.age_max is None and before.age_max is not None:
        hard.age_max = before.age_max
    if hard.min_rating is None and before.min_rating is not None:
        hard.min_rating = before.min_rating
    if hard.event_count is None and before.event_count is not None:
        hard.event_count = before.event_count
    # A total budget keeps its total: the per-person value is derived in
    # sanitize. When the party only becomes known here (inherited from the
    # previous turn), recompute the derived ceiling from the total.
    budget = hard.budget
    if (budget is not None and budget.basis == "total"
            and budget.total is not None
            and isinstance(hard.party_size, int)
            and PARTY_SIZE_MIN <= hard.party_size <= PARTY_SIZE_MAX):
        budget.max_price_per_person = round(
            budget.total / hard.party_size, 2)
    if previous.needs_clarification:
        # The answer fills slots; it must not replace the topic with
        # "Минск, бюджет не важен". Keep the previous search meaning.
        if not new_topic:
            contract.intent = previous.intent
            contract.semantic_payload.vector_query = \
                previous.semantic_payload.vector_query
    if not contract.semantic_payload.vector_query.strip():
        contract.semantic_payload.vector_query = \
            previous.semantic_payload.vector_query
    contract.negative_filters.exclude_tags = list(dict.fromkeys(
        [*previous.negative_filters.exclude_tags,
         *contract.negative_filters.exclude_tags]))
    contract.negative_filters.exclude_categories = list(dict.fromkeys(
        [*previous.negative_filters.exclude_categories,
         *contract.negative_filters.exclude_categories]))
    # "Ещё" needs the previous page even when the model produced a fresh
    # contract. A genuinely new topic keeps its own (empty) list.
    if (previous.context_state.shown_ids
            and not contract.context_state.shown_ids and not new_topic):
        contract.context_state.shown_ids = list(
            previous.context_state.shown_ids)
    return contract


@router.post("/query", response_model=QueryResponse,
             dependencies=[Depends(rate_limit("query"))])
async def parse_query(request: QueryRequest) -> QueryResponse:
    if request.contract is not None and _is_follow_up(request.query):
        # Deterministic pagination: no model call, no category drift.
        contract = _follow_up_contract(request.contract)
        reasoning_used = False
        complex_ = False
    else:
        contract, reasoning_used, complex_ = \
            await get_components().structure.parse_meta(
                request.query,
                language=request.language,
                session_id=request.session_id,
                force_reasoning=request.force_reasoning,
                previous=request.contract,
            )
        contract = _inherit(contract, request.contract)
        contract = _downgrade_clarification(contract, request.contract)
    supported = contract.intent in intents.DIALOGUE_INTENTS
    return QueryResponse(
        contract=contract,
        reasoning_used=reasoning_used,
        complex=complex_,
        intent=contract.intent,
        supported=supported,
        reply=None if supported else i18n.t(
            "assistant_capabilities", i18n.resolve_locale(request.language)),
    )
