"""Required-slot rules shared by the dialogue and the structure stage.

A search turn no longer blocks on a missing date: the default is "nearest
events", so the whole pipeline can answer with what it has. Clarification is
an explicit opt-in (``clarify_required_slots=True``), used only by the legacy
clarification path when the client asked for it. The city is still the one
strict slot when no default city is configured.
"""
from __future__ import annotations

from ..api.schemas.contract import StateContract
from ..core.config import Settings
from ..models import intent as intents

EVENT_SCOPES = ("events", "both")


def required_slots(contract: StateContract, settings: Settings, *,
                   clarify_required_slots: bool = False) -> list[str]:
    """Open slots that block a search, in a stable order.

    By default nothing blocks: an absent date means "nearest events" and an
    absent category means "any". Only the explicit clarification path opts in.
    """
    if not clarify_required_slots:
        return []
    hard = contract.hard_filters
    slots: list[str] = []
    if intents.spec(contract.intent).scope in EVENT_SCOPES:
        date_filter = hard.datetime
        if date_filter is None or (not date_filter.any
                                   and not date_filter.start):
            slots.append("datetime")
    location = hard.location
    if (not settings.default_city.strip() and not location.any
            and not location.city):
        slots.append("city")
    return slots
