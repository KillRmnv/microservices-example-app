"""LLM structure endpoint: raw query -> dialogue contract + intent."""
from __future__ import annotations

import logging

from fastapi import APIRouter

from ..deps import get_components
from ..schemas.plan import QueryResponse
from ..schemas.query import QueryRequest
from ...core import i18n
from ...core.config import settings
from ...models import intent as intents

log = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["dialogue"])


def _inherit(contract, previous):
    """Carry missing follow-up slots; the LLM owns intent classification."""
    if previous is None:
        return contract
    hard = contract.hard_filters
    before = previous.hard_filters
    if (hard.datetime is None or not hard.datetime.start) \
            and before.datetime is not None and before.datetime.start:
        hard.datetime = before.datetime
    if not hard.category and before.category:
        hard.category = list(before.category)
    if not hard.themes and before.themes:
        hard.themes = list(before.themes)
    if hard.budget is None and before.budget is not None:
        hard.budget = before.budget
    if hard.party_size in (0, settings.default_party_size) \
            and before.party_size not in (0, settings.default_party_size):
        hard.party_size = before.party_size
    if not contract.semantic_payload.vector_query.strip():
        contract.semantic_payload.vector_query = \
            previous.semantic_payload.vector_query
    contract.negative_filters.exclude_tags = list(dict.fromkeys(
        [*previous.negative_filters.exclude_tags,
         *contract.negative_filters.exclude_tags]))
    contract.negative_filters.exclude_categories = list(dict.fromkeys(
        [*previous.negative_filters.exclude_categories,
         *contract.negative_filters.exclude_categories]))
    return contract


@router.post("/query", response_model=QueryResponse)
async def parse_query(request: QueryRequest) -> QueryResponse:
    contract, reasoning_used, complex = await get_components().structure.parse_meta(
        request.query,
        language=request.language,
        session_id=request.session_id,
        force_reasoning=request.force_reasoning,
        previous=request.contract,
    )
    contract = _inherit(contract, request.contract)
    supported = contract.intent in intents.DIALOGUE_INTENTS
    return QueryResponse(
        contract=contract,
        reasoning_used=reasoning_used,
        complex=complex,
        intent=contract.intent,
        supported=supported,
        reply=None if supported else i18n.t(
            "assistant_capabilities", i18n.resolve_locale(request.language)),
    )
