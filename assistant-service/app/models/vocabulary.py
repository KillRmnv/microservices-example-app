"""Controlled vocabularies for contract slots.

One source of truth shared by the structure-stage normaliser and the DTO
sanitiser, so a category the model may emit is exactly a category the server
keeps. Venue rubrics are derived from the intent registry: an intent carries
the 2GIS rubrics it targets, never a second hand-written list.
"""
from __future__ import annotations

from . import intent as intents

# Ordered so callers can cap deterministically; the set is for membership.
EVENT_CATEGORIES: tuple[str, ...] = (
    "concert", "theatre", "exhibition", "film", "sport", "kids", "other")
EVENT_CATEGORY_SET: set[str] = set(EVENT_CATEGORIES)

VENUE_RUBRICS: tuple[str, ...] = tuple(dict.fromkeys(
    rubric for rubrics in intents.VENUE_INTENTS.values() for rubric in rubrics))
