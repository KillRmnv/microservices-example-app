"""Complexity heuristic: which requests deserve LLM reasoning.

Reasoning costs minutes on CPU, so it must be opt-in per request. A request
is "complex" when it is long or carries several independent constraints
(date + budget + party + negations, ...). Everything else goes through the
fast no-think structure lane.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..core.config import Settings

DATE_RE = re.compile(
    r"завтра|послезавтра|сегодня|выходн|понедельник|вторник|сред[ау]|"
    r"четверг|пятниц|суббот|воскресень|\d{1,2}\s+(января|февраля|марта|"
    r"апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)|"
    r"\d{1,2}[:.]\d{2}")
BUDGET_RE = re.compile(r"до\s+\d|бюджет|не дороже|дешев|дорог")
PARTY_RE = re.compile(r"нас\s+\d|вдво[её]м|втро[её]м|на\s+двоих|на\s+двух|"
                        r"на\s+троих|двоих|двух|троих|человек|дет[яь]ми|"
                        r"с детьми|компани")
CATEGORY_RES = (
    re.compile(r"концерт|музык|джаз|рок"),
    re.compile(r"спектакл|театр|балет|опера"),
    re.compile(r"выставк|музей|галере"),
    re.compile(r"кино|фильм"),
    re.compile(r"спорт|матч|стадион"),
    re.compile(r"детск|для детей"),
)
NEGATION_RE = re.compile(r"без\s+\S|кроме\s+\S|исключить|не хочу|не надо|только не")
ATMOSPHERE_RE = re.compile(
    r"тих|уют|шумн|романти|весел|спокойн|атмосфер|настроени|живая музыка")


@dataclass
class Complexity:
    complex: bool
    reasons: list[str] = field(default_factory=list)


def classify(query: str, settings: Settings | None = None) -> Complexity:
    """Decide whether the request justifies the reasoning lane."""
    from ..core.config import settings as default_settings
    settings = settings or default_settings
    text = (query or "").strip()
    lowered = text.casefold()
    signals: list[str] = []
    if DATE_RE.search(lowered):
        signals.append("date")
    if BUDGET_RE.search(lowered):
        signals.append("budget")
    if PARTY_RE.search(lowered):
        signals.append("party")
    if sum(1 for pattern in CATEGORY_RES if pattern.search(lowered)) >= 2:
        signals.append("multi_category")
    if NEGATION_RE.search(lowered):
        signals.append("negation")
    if ATMOSPHERE_RE.search(lowered):
        signals.append("atmosphere")
    reasons = list(signals)
    if len(text) >= settings.llm_complex_min_chars:
        reasons.append("long")
    complex_ = (len(text) >= settings.llm_complex_min_chars
                or len(signals) >= settings.llm_complex_min_signals)
    return Complexity(complex=complex_, reasons=reasons)
