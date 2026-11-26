"""Deterministic relevance classifier for Telegram afisha posts.

No LLM: hard-exclude lexicons (housing/jobs/ads/resale), event-type signals,
date/venue/price context and a few per-channel policy flags. The classifier
runs before normalization so junk never reaches `collected_events`.

The legal caveat from ``sources/telegram.py`` still applies: the owner checks
every channel against the Mininform list; this module only measures content
quality/accessibility.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TAG_ORDER = ("housing", "jobs", "ad", "resale", "companion")

HARD_EXCLUDES = {
    "housing": re.compile(
        r"(?:сдам|снять|аренд|квартир|жиль|коттедж|апартамент|посуточн|"
        r"комнат|риэлтор)", re.I),
    "jobs": re.compile(
        r"(?:ваканс|стажиров|резюме|зарплат|трудоустро|собеседован|найм|"
        r"работа в)", re.I),
    "ad": re.compile(
        r"(?:розыгрыш|конкурс|промокод|купон|подпишись|переходи по ссылке|"
        r"реклама|спонсор)", re.I),
    "resale": re.compile(r"(?:продам билет|перепрода|перекуп)", re.I),
}

EVENT_RE = re.compile(
    r"(?:концерт|спектакл|выставк|кинопоказ|\bпоказ\b|\bсеанс|\bпремьер[а-я]*|"
    r"\bфильм[а-я]*|фестивал|стендап|квиз|"
    r"лекци|экскурси|мастер[-\s]?класс|\bвстреч|\bигр(?:а|ы|е|у|ой|ов|ах|ами)?\b|"
    r"турнир|вечеринк|\bвечер(?:а|ы|ов)?\b|ярмарк|\bмаркет(?!инг)|\bшоу|"
    r"перформанс)", re.I)

_MONTHS = (r"(?:январ[а-я]*|феврал[а-я]*|март[а-я]*|апрел[а-я]*|ма[йя]|"
           r"июн[а-я]*|июл[а-я]*|август[а-я]*|сентябр[а-я]*|октябр[а-я]*|"
           r"ноябр[а-я]*|декабр[а-я]*)")
DATE_RE = re.compile(
    r"(?:\b\d{1,2}\s+" + _MONTHS + r"\b|"
    r"\b\d{1,2}\s*[./]\s*\d{1,2}(?:\s*[./]\s*\d{2,4})?\b|"
    r"\b(?:сегодня|завтра|послезавтра|выходн[а-я]*)\b|"
    r"\b(?:понедельник|вторник|сред[ауы]|четверг|пятниц[ауы]|суббот[ауы]|"
    r"воскресень[ея])\b)", re.I)

VENUE_RE = re.compile(
    r"(?:\bул\.|\bпр\.|просп\.?|проспект|\bклуб|\bтеатр|\bгалере|"
    r"\bбар(?:а|е|у|ы|ов)?\b|\bкафе|\bпарк|\bзал[ае]?\b|\bплощадк|"
    r"\bмузе[йя]|\bбиблиотек|\bтц\b|\bтрц\b)", re.I)

PRICE_RE = re.compile(r"(?:билет|вход|бесплатн|руб|byn|р\.)", re.I)

COMPANION_RE = re.compile(
    r"(?:ищу компани|ищу напарник|кто ид[её]т|кто со мной|"
    r"кто хочет пойти|пойд[её]м вместе|составлю компани)", re.I)

NUMBERED_RE = re.compile(r"(?m)^\s*\d{1,2}[.)]\s+")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class ChannelRules:
    no_housing: bool = False
    no_jobs: bool = False
    no_ad: bool = False
    strict_event: bool = False
    no_companion_search: bool = False
    undated_ok: bool = False


@dataclass
class Decision:
    keep: bool
    reason: str
    signals: list[str] = field(default_factory=list)
    has_date: bool = False
    has_venue: bool = False

    def as_dict(self) -> dict:
        return {"keep": self.keep, "reason": self.reason,
                "signals": list(self.signals), "has_date": self.has_date,
                "has_venue": self.has_venue}


def _norm(text: str | None) -> str:
    return _WHITESPACE_RE.sub(" ", str(text or "")).strip()


def _drop(reason: str, signals: list[str], has_date: bool,
          has_venue: bool) -> Decision:
    return Decision(False, reason, signals, has_date, has_venue)


def _digest(text: str, dates: list[str], venues: list[str]) -> bool:
    unique_dates = set(dates)
    bells = text.count("⏰")
    numbered = len(NUMBERED_RE.findall(text))
    # Count venue *lines*, not regex hits: one address line often mentions a
    # club and a street ("Клуб «X», ул. Ленина 1").
    venue_lines = {line.strip().casefold() for line in text.splitlines()
                   if VENUE_RE.search(line)}
    # A date range ("с 14 ноября по 14 декабря") or an opening date is still
    # one event: only repeated ⏰ markers or several venue+date pairs are a
    # digest. Numbered lists need at least one date marker as well.
    return (bells >= 2
            or (numbered >= 3 and bells >= 1)
            or (len(unique_dates) >= 2 and len(venue_lines) >= 2))


def classify(text: str | None, channel: str = "",
             rules: ChannelRules | None = None) -> Decision:
    """Classify one post. `rules` carries per-channel policy flags."""
    rules = rules or ChannelRules()
    normalized = _norm(text)
    signals: list[str] = []
    has_event = bool(EVENT_RE.search(normalized))
    dates = DATE_RE.findall(normalized)
    venues = VENUE_RE.findall(normalized)
    has_date = bool(dates)
    has_venue = bool(venues)
    if has_event:
        signals.append("event")
    if has_date:
        signals.append("date")
    if has_venue:
        signals.append("venue")
    if PRICE_RE.search(normalized):
        signals.append("price")

    if _digest(str(text or ""), dates, venues):
        signals.append("digest")
        return _drop("digest", signals, has_date, has_venue)

    matched = [name for name, pattern in HARD_EXCLUDES.items()
               if pattern.search(normalized)]
    signals.extend(name for name in matched if name not in signals)

    companion = bool(COMPANION_RE.search(normalized))
    if companion:
        signals.append("companion")

    if "resale" in matched:
        return _drop("resale", signals, has_date, has_venue)

    for category in ("housing", "jobs", "ad"):
        if category not in matched:
            continue
        disabled = getattr(rules, f"no_{category}")
        if disabled:
            return _drop(category, signals, has_date, has_venue)
        if not (has_event and has_date):
            return _drop(category, signals, has_date, has_venue)
        break  # a discount/announcement with an event + date is a real event

    if companion and (rules.no_companion_search
                      or not (has_event and has_date and has_venue)):
        return _drop("companion", signals, has_date, has_venue)

    if not has_event:
        return _drop("no_event", signals, has_date, has_venue)
    if rules.strict_event and not has_date:
        return _drop("strict_event", signals, has_date, has_venue)
    if not has_date:
        if has_venue and rules.undated_ok:
            signals.append("undated_ok")
        else:
            return _drop("undated", signals, has_date, has_venue)
    return Decision(True, "keep", signals, has_date, has_venue)
