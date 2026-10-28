"""Dialogue controllers."""
from __future__ import annotations

import time

from fastapi import APIRouter

from ..deps import get_components
from ..schemas.contract import StateContract, sanitize
from ..schemas.dialogue import DialogResponse
from ...core import i18n

router = APIRouter(prefix="/assistant", tags=["dialogue"])


@router.post("/dialogue", response_model=StateContract)
def dialogue(contract: StateContract) -> StateContract:
    """Legacy contract-only turn (kept for backward compatibility)."""
    started = time.monotonic()
    components = get_components()
    clean = sanitize(contract)
    language = i18n.resolve_locale(clean.semantic_payload.language)
    result = components.dialogue.apply_rules(clean, language)
    components.dialogue.record_run(result, components.dialogue.elapsed_ms(started))
    return result


@router.post("/dialogue/v2", response_model=DialogResponse)
async def dialogue_v2(contract: StateContract) -> DialogResponse:
    """Full turn: validation + tools + messages."""
    started = time.monotonic()
    components = get_components()
    clean = sanitize(contract)
    language = i18n.resolve_locale(clean.semantic_payload.language)
    ruled = components.dialogue.apply_rules(clean, language)
    if ruled.needs_clarification or ruled.dialogue_action not in ("search", "update_filters"):
        components.dialogue.record_run(ruled, components.dialogue.elapsed_ms(started))
        return DialogResponse(contract=ruled, messages=[])
    response = await components.dialogue.search_turn(ruled)
    components.dialogue.record_run(
        response.contract, components.dialogue.elapsed_ms(started))
    return response
