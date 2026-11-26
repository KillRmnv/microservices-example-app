"""Deterministic "doesn't matter" answers for clarification turns.

The structure model is unreliable on short vague replies ("как хочешь",
"без разницы") and often returns no `any` flag, which makes the assistant repeat
the same question. These phrases are unambiguous, so they are resolved here
without a model call. Partial answers ("дата не важна, город Минск") fill only
the slots they name; the rest still goes through the normal parser.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

# Punctuation is spacing, not a separator: "что-нибудь" normalises to
# "что нибудь", so the phrase tables below are stored in normalised form too.
_NON_WORD = re.compile(r"[^\w\s]+", re.UNICODE)
_SPACES = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Casefold, fold ё, turn punctuation into spaces and collapse runs."""
    cleaned = str(text or "").casefold().replace("ё", "е")
    cleaned = _NON_WORD.sub(" ", cleaned)
    return _SPACES.sub(" ", cleaned).strip()


def _phrases(*items: str) -> frozenset[str]:
    return frozenset(normalise(item) for item in items)


# A bare answer means "any" for every slot the server just asked about.
BARE_ANY: frozenset[str] = _phrases(
    "не важно", "неважно", "не важен", "мне не важно",
    "всё равно", "все равно", "мне всё равно", "мне все равно",
    "любой", "любая", "любое", "любые",
    "без разницы", "как хочешь", "как скажешь", "на твой вкус",
    "на ваше усмотрение", "пофиг", "не принципиально",
    "не имеет значения", "не критично", "необязательно",
    "что угодно", "что-нибудь", "сам реши", "сам решай", "решай сам",
    "на выбор", "без предпочтений", "не суть", "как угодно",
)

# Per-slot phrases. They are matched as substrings, so a partial answer fills
# only its own slot and leaves the rest to the normal parser.
SLOT_PHRASES: dict[str, frozenset[str]] = {
    "datetime": _phrases(
        "когда угодно", "в любой день", "дата не важна", "не важно когда",
        "без даты",
    ),
    "city": _phrases(
        "где угодно", "в любом городе", "город не важен", "не важно где",
    ),
    "budget": _phrases(
        "без ограничений", "не важно сколько", "любой бюджет",
        "деньги не важны",
    ),
    "party": _phrases(
        "сколько угодно", "любая компания", "компания не важна",
        "сколько человек не важно",
    ),
}


def is_bare_any(text: str) -> bool:
    """True when the whole answer is a phrase covering every asked slot."""
    return normalise(text) in BARE_ANY


def any_slots(text: str, asked: Iterable[str]) -> set[str]:
    """Slots the answer deterministically marks as "any"."""
    asked_set = set(asked)
    if not asked_set:
        return set()
    if is_bare_any(text):
        return asked_set
    normalised = normalise(text)
    covered: set[str] = set()
    for slot, phrases in SLOT_PHRASES.items():
        if slot in asked_set and any(phrase in normalised
                                     for phrase in phrases):
            covered.add(slot)
    return covered


def apply(hard: dict, slots: Iterable[str]) -> None:
    """Set the "any" representation of each slot on a hard-filters dict."""
    for slot in slots:
        if slot == "datetime":
            hard["datetime"] = {"any": True, "start": None, "end": None}
        elif slot == "city":
            hard["location"] = {**(hard.get("location") or {}),
                                "city": None, "any": True}
        elif slot == "budget":
            hard["budget"] = {"any": True, "max_price_per_person": None,
                              "total": None, "basis": "per_person"}
        elif slot == "party":
            hard["party_size"] = 0
