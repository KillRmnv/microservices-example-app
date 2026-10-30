"""Intent vocabulary shared by DTOs and services.

Classification itself belongs to the structure LLM; this module only defines
the allowed values and how the dialogue/router interprets them.
"""
from __future__ import annotations

EVENT_SEARCH = "find_events"
VENUE_SEARCH = "find_venues"
BOTH = "both"
PLAN = "plan"
BOOKING = "booking"
WEATHER = "weather"
CAPABILITIES = "capabilities"
UNSUPPORTED = "unsupported"

ALL = {
    EVENT_SEARCH, VENUE_SEARCH, BOTH, PLAN, BOOKING, WEATHER,
    CAPABILITIES, UNSUPPORTED,
}

SEARCH_INTENTS = {EVENT_SEARCH, VENUE_SEARCH, BOTH}
DIALOGUE_INTENTS = {EVENT_SEARCH, VENUE_SEARCH, BOTH, PLAN, WEATHER, BOOKING}


def normalize(value: str | None) -> str:
    text = (value or "").strip().lower()
    return text if text in ALL else EVENT_SEARCH
