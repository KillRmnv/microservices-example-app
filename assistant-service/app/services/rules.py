"""Required-slot rules shared by the dialogue and the structure stage.

Only a date is genuinely required, and only when the intent searches events.
The city is required only when no default city is configured. Budget and party
size are never asked about: they are optional refinements.
"""
from __future__ import annotations

from ..api.schemas.contract import StateContract
from ..core.config import Settings
from ..models import intent as intents

EVENT_SCOPES = ("events", "both")


def required_slots(contract: StateContract, settings: Settings) -> list[str]:
    """Open slots that block a search, in a stable order."""
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
