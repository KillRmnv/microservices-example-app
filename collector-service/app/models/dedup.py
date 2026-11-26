"""Cross-source event matching without extra DB extensions.

Exact source ids and dedup keys are handled in the repository. This module
only scores a few nearby candidates: title similarity, venue and start time.
No I/O, no LLM, so the result is reproducible and cheap to test.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from .catalog import CATEGORIES, RawEvent

_QUOTES = re.compile(r"[\"'«»“”„‟`]+")
_NON_WORD = re.compile(r"[^0-9a-zа-я]+")
_SPACE = re.compile(r"\s+")


def normalize(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold()
    text = _QUOTES.sub(" ", text).replace("ё", "е")
    text = _NON_WORD.sub(" ", text)
    return _SPACE.sub(" ", text).strip()


def title_similarity(left: str | None, right: str | None) -> float:
    first, second = normalize(left), normalize(right)
    if not first or not second:
        return 0.0
    if first == second:
        return 1.0
    ratio = SequenceMatcher(None, first, second).ratio()
    # "Концерт X" vs "X" and similar source prefixes.
    if len(first) >= 6 and first in second:
        ratio = max(ratio, 0.95)
    elif len(second) >= 6 and second in first:
        ratio = max(ratio, 0.95)
    first_tokens, second_tokens = set(first.split()), set(second.split())
    if first_tokens and second_tokens:
        overlap = len(first_tokens & second_tokens) / len(first_tokens | second_tokens)
        ratio = max(ratio, 0.55 + 0.45 * overlap)
    return ratio


def venue_similarity(left: str | None, right: str | None) -> float | None:
    first, second = normalize(left), normalize(right)
    if not first and not second:
        return None
    if not first or not second:
        return 0.5
    if first == second:
        return 1.0
    if len(first) >= 5 and first in second:
        return 0.95
    if len(second) >= 5 and second in first:
        return 0.95
    return SequenceMatcher(None, first, second).ratio()


def _time_component(first: datetime | None, second: datetime | None) -> float | None:
    if first is None and second is None:
        return 0.4
    if first is None or second is None:
        return 0.5
    delta = abs((first - second).total_seconds())
    if first.date() == second.date():
        return 1.0 if delta <= 6 * 3600 else 0.75
    # Different calendar days are separate performances unless the clocks are
    # within a timezone-sized tolerance across midnight.
    return 0.85 if delta <= 6 * 3600 else None


def _versus_guard(first: str | None, second: str | None) -> bool:
    """Reject "Team A vs X" and "Team A vs Y" as different matches."""
    left, right = normalize(first), normalize(second)
    if " vs " not in left or " vs " not in right:
        return True
    head_left, tail_left = left.split(" vs ", 1)
    head_right, tail_right = right.split(" vs ", 1)
    head = SequenceMatcher(None, head_left, head_right).ratio()
    tail = SequenceMatcher(None, tail_left, tail_right).ratio()
    return not (head >= 0.75 and tail < 0.65)


@dataclass(frozen=True)
class DedupDecision:
    merge: bool
    score: float
    reason: str


def compare(event: RawEvent, candidate: dict) -> DedupDecision:
    """Decide whether a candidate row is the same logical event."""
    title = title_similarity(event.title, candidate.get("title"))
    if title < 0.55:
        return DedupDecision(False, title, "title")
    if not _versus_guard(event.title, candidate.get("title")):
        return DedupDecision(False, title, "versus")
    venue = venue_similarity(event.venue_name, candidate.get("venue_name"))
    if event.venue_id and candidate.get("venue_id"):
        venue = 1.0 if str(event.venue_id) == str(candidate["venue_id"]) else venue
    if venue is not None and venue < 0.55:
        return DedupDecision(False, title, "venue")
    category = (event.category or "").casefold()
    other = (candidate.get("category") or "").casefold()
    if (category in CATEGORIES and other in CATEGORIES
            and category != "other" and other != "other"
            and category != other):
        return DedupDecision(False, title, "category")
    start = event.start_at
    candidate_start = candidate.get("start_at")
    if start is None or candidate_start is None:
        # Two undated posts (or one dated + one undated) can be different
        # occurrences of the same series. Keep both; a human/review job may
        # merge them later.
        return DedupDecision(False, title, "undated")
    time_score = None
    if start is not None and event.end_at is not None \
            and candidate.get("start_at") is not None \
            and start <= candidate["start_at"] <= event.end_at:
        time_score = 1.0  # the new event's period covers the candidate
    elif start is not None and candidate.get("start_at") is not None \
            and candidate.get("end_at") is not None \
            and candidate["start_at"] <= start <= candidate["end_at"]:
        time_score = 1.0  # the candidate's period covers the new event
    else:
        time_score = _time_component(start, candidate.get("start_at"))
    if time_score is None:
        return DedupDecision(False, title, "time")
    venue_score = 0.5 if venue is None else venue
    score = title * 0.65 + venue_score * 0.2 + time_score * 0.15
    if venue is None and title < 0.90:
        return DedupDecision(False, score, "no-venue")
    threshold = 0.84
    if venue is not None and venue >= 0.95 and title >= 0.90:
        threshold = 0.82
    return DedupDecision(score >= threshold, score,
                         "match" if score >= threshold else "score")
