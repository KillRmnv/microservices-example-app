"""Intent vocabulary and declarative routing specs.

Classification belongs to the structure LLM. This module maps each chosen
intent to a search scope and optional default category/rubric slots. No
keyword matching lives here.
"""
from __future__ import annotations

from dataclasses import dataclass

EVENT_SEARCH = "find_events"
VENUE_SEARCH = "find_venues"
BOTH = "both"
PLAN = "plan"
BOOKING = "booking"
WEATHER = "weather"
CAPABILITIES = "capabilities"
UNSUPPORTED = "unsupported"

# Category-specific intents let the model state the user's goal directly;
# the registry derives search slots from that decision.
EVENT_INTENTS = {
    "find_event_concert": ("concert",),
    "find_event_theatre": ("theatre",),
    "find_event_exhibition": ("exhibition",),
    "find_event_film": ("film",),
    "find_event_sport": ("sport",),
    "find_event_kids": ("kids",),
    "find_event_other": ("other",),
}

VENUE_INTENTS = {
    "find_venue_bar": ("Бары",),
    "find_venue_cafe": ("Кафе",),
    "find_venue_restaurant": ("Рестораны",),
    "find_venue_cinema": ("Кинотеатры",),
    "find_venue_theatre": ("Театры",),
    "find_venue_exhibition": ("Художественные выставки",),
    "find_venue_gym": ("Фитнес-клубы", "Спортзалы"),
    "find_venue_library": ("Библиотеки", "Книжные магазины"),
}


@dataclass(frozen=True)
class IntentSpec:
    scope: str
    categories: tuple[str, ...] = ()
    rubrics: tuple[str, ...] = ()


SPECS: dict[str, IntentSpec] = {
    EVENT_SEARCH: IntentSpec("events"),
    VENUE_SEARCH: IntentSpec("venues"),
    BOTH: IntentSpec("both"),
    PLAN: IntentSpec("plan"),
    BOOKING: IntentSpec("booking"),
    WEATHER: IntentSpec("weather"),
    CAPABILITIES: IntentSpec("capabilities"),
    UNSUPPORTED: IntentSpec("unsupported"),
    **{name: IntentSpec("events", categories=categories)
       for name, categories in EVENT_INTENTS.items()},
    **{name: IntentSpec("venues", rubrics=rubrics)
       for name, rubrics in VENUE_INTENTS.items()},
}

ALL = set(SPECS)
SEARCH_SCOPES = {"events", "venues", "both"}
SEARCH_INTENTS = {name for name, spec in SPECS.items()
                  if spec.scope in SEARCH_SCOPES}
DIALOGUE_INTENTS = {name for name, spec in SPECS.items()
                    if spec.scope not in {"capabilities", "unsupported"}}


def normalize(value: str | None) -> str:
    text = (value or "").strip().lower()
    return text if text in ALL else EVENT_SEARCH


def spec(value: str | None) -> IntentSpec:
    return SPECS[normalize(value)]


def is_venue(value: str | None) -> bool:
    return spec(value).scope == "venues"
