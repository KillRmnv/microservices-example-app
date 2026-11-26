"""Concrete filter specifications."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from ..core.config import settings as default_settings
from ..models.search import FusedHit, PayloadDateRange
from .base import Filter


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _is_fresh(value, ttl_hours: int | float, *,
              now: datetime | None = None) -> bool:
    """True when a collector timestamp is inside the availability TTL.

    A missing, unparsable or tz-naive stamp is not fresh: scraped inventory
    without a proven fetch time counts as unknown, never as a reason to hide.
    """
    parsed = _parse_datetime(value)
    if parsed is None:
        return False
    moment = now or datetime.now(timezone.utc)
    return moment - parsed <= timedelta(hours=ttl_hours)


def _as_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


class CityFilter(Filter):
    def __init__(self, city: str) -> None:
        self._city = city

    def qdrant_must(self) -> dict[str, str]:
        return {"city": self._city}

    def lexical_params(self) -> dict[str, str]:
        return {"city": self._city}

    def matches(self, hit: FusedHit) -> bool:
        value = hit.payload.get("city")
        return value is None or value == self._city


class CategoryFilter(Filter):
    def __init__(self, categories: str | list[str]) -> None:
        self._categories = ([categories] if isinstance(categories, str)
                            else list(categories))

    def qdrant_must(self):
        return {"category": self._categories}

    def lexical_params(self):
        return {"categories": self._categories}

    def matches(self, hit: FusedHit) -> bool:
        value = hit.payload.get("category")
        return value is None or value in self._categories


class DateRangeFilter(Filter):
    """Only events overlapping [from, to).

    Multi-day events (a dolphinarium running for a month) must match a query
    for any day inside their period, not only the start date. Events without
    `start_at` are dropped when the user named a date: a scraped post without
    a date cannot be promised for that evening. In category-only "undated"
    mode they pass instead, but dated events still have to be in the future:
    an announcement must never resurrect a performance that already ended.

    `end` is optional: the future floor only needs "not finished before now",
    so a query without an explicit date keeps every event still running.
    """

    def __init__(self, start: datetime, end: datetime | None = None,
                 allow_undated: bool = False) -> None:
        self._start = start
        self._end = end
        self._allow_undated = allow_undated

    def qdrant_must(self) -> dict[str, PayloadDateRange]:
        # Undated points cannot satisfy a date range; the condition is applied
        # in Python instead so they can pass in undated mode.
        if self._allow_undated:
            return {}
        # start_at < query_end (only with an end) AND end_at >= query_start.
        # Payload stores end_at = start_at for single-day events.
        must: dict[str, PayloadDateRange] = {
            "end_at": PayloadDateRange(gte=self._start.isoformat()),
        }
        if self._end is not None:
            must["start_at"] = PayloadDateRange(lt=self._end.isoformat())
        return must

    def lexical_params(self) -> dict[str, str]:
        if self._allow_undated:
            return {}
        params = {"date_from": self._start.isoformat()}
        if self._end is not None:
            params["date_to"] = self._end.isoformat()
        return params

    def matches(self, hit: FusedHit) -> bool:
        start = _parse_datetime(hit.payload.get("start_at"))
        if start is None:
            return self._allow_undated
        if self._end is not None and start >= self._end:
            return False
        end = _parse_datetime(hit.payload.get("end_at")) or start
        return end >= self._start


class RubricFilter(Filter):
    def __init__(self, rubric: str) -> None:
        self._rubric = rubric

    def qdrant_must(self) -> dict[str, str]:
        return {"rubric": self._rubric}

    def lexical_params(self) -> dict[str, str]:
        return {"rubric": self._rubric}

    def matches(self, hit: FusedHit) -> bool:
        value = hit.payload.get("rubric")
        return value is None or value == self._rubric


class MaxPriceFilter(Filter):
    """Post-filter using prices from the lexical rows (dense has no price)."""

    def __init__(self, max_price: float, prices: Mapping[str, float | None]) -> None:
        self._max = float(max_price)
        self._prices = prices

    def matches(self, hit: FusedHit) -> bool:
        price = self._prices.get(hit.id)
        return price is None or float(price) <= self._max


class ExcludeCategoriesFilter(Filter):
    def __init__(self, categories: list[str]) -> None:
        self._categories = [str(category) for category in categories]
        self._folded = {category.casefold() for category in self._categories}

    def qdrant_must_not(self) -> dict[str, list[str]]:
        return {"category": self._categories}

    def matches(self, hit: FusedHit) -> bool:
        category = str(hit.payload.get("category") or "").casefold()
        return category not in self._folded


# Payload fields that carry free text the user may want excluded. Scraped
# events put the whole embedding text into `search_text`; venue rows use
# `name`/`rubric`/`address`/`amenities` instead. `atmosphere` is the collector
# venue tag list ("шумно", "толпа"), so "без громко" keeps working there.
_TAG_TEXT_FIELDS = ("search_text", "title", "description", "venue", "name",
                    "rubric", "address", "amenities", "atmosphere")
# "кальяна" must match "кальян": compare a short prefix as well as the
# whole normalised tag. Six characters covers RU noun endings for words of
# that length; shorter tags are matched verbatim only.
_TAG_STEM_CHARS = 6


def normalise_tag(tag: str) -> str:
    """`loud_music`/`loud-music` -> `loud music`; lowercase and trim."""
    text = str(tag or "").casefold().replace("_", " ").replace("-", " ")
    return " ".join(text.split())


def _tag_haystack(payload: Mapping) -> str:
    parts: list[str] = []
    for field in _TAG_TEXT_FIELDS:
        value = payload.get(field)
        if isinstance(value, (list, tuple, set)):
            parts.extend(str(item) for item in value if item)
        elif value:
            parts.append(str(value))
    return " ".join(parts).casefold()


class ExcludeTagsFilter(Filter):
    """Post-filter: drop hits mentioning a forbidden tag.

    Qdrant cannot exclude a token inside free text, so this stays in Python.
    Payload text is searched case-insensitively for the whole tag and for a
    short stem, which absorbs RU inflections ("без кальяна" -> "кальян").
    """

    def __init__(self, tags: list[str]) -> None:
        self._tags: list[tuple[str, str | None]] = []
        for tag in tags:
            normalised = normalise_tag(tag)
            if not normalised:
                continue
            stem = (normalised[:_TAG_STEM_CHARS]
                    if len(normalised) > _TAG_STEM_CHARS else None)
            self._tags.append((normalised, stem))

    def matches(self, hit: FusedHit) -> bool:
        if not self._tags:
            return True
        haystack = _tag_haystack(hit.payload)
        for tag, stem in self._tags:
            if tag in haystack or (stem is not None and stem in haystack):
                return False
        return True


class ExcludeIdsFilter(Filter):
    """Post-filter: drop cards already shown in this dialogue ("ещё")."""

    def __init__(self, ids: list[str]) -> None:
        self._ids = {str(value).strip() for value in ids if str(value).strip()}

    def matches(self, hit: FusedHit) -> bool:
        if not self._ids:
            return True
        if str(hit.id) in self._ids:
            return False
        booking_id = hit.payload.get("booking_event_id")
        return booking_id is None or str(booking_id) not in self._ids


class AmenityExcludeFilter(Filter):
    """Post-filter: drop hits whose ``amenities`` contain a tag.

    Live 2GIS payloads do not carry ``attribute_groups``/``attributes`` (the
    adapter requests them, the API answers without them), so real venues
    arrive with ``amenities: []`` and text is the only outdoor signal left.
    Semantics:

    - non-empty ``amenities`` -> match ONLY that structured list (a venue
      that merely mentions "терраса" in its description is kept);
    - missing/empty ``amenities`` -> fall back to the free-text haystack of
      :class:`ExcludeTagsFilter` (search_text/title/description/venue/name/
      rubric/address), so a venue named "Веранда" is still excluded on a
      rainy turn.

    Tags and amenities are normalised the same way (``_``/``-`` -> space).
    """

    def __init__(self, tags: list[str]) -> None:
        self._tags = {normalised for normalised in
                      (normalise_tag(tag) for tag in tags) if normalised}
        self._text_fallback = ExcludeTagsFilter(tags)

    def matches(self, hit: FusedHit) -> bool:
        if not self._tags:
            return True
        amenities = hit.payload.get("amenities")
        values = ({normalise_tag(item) for item in amenities if item}
                  if isinstance(amenities, (list, tuple, set)) else set())
        if values:
            return not (values & self._tags)
        # No structured amenities: degrade to text matching, the only signal
        # the live 2GIS API leaves us.
        return self._text_fallback.matches(hit)


class PartyFilter(Filter):
    """Post-filter: can the hit host the requested party?

    Both ``seats_left`` and ``capacity`` may be unknown (scraped rows carry
    neither), in which case the hit passes: the assistant must not hide an
    event just because the source did not publish inventory. Explicit
    constructor values win; otherwise the hit payload is read, so the search
    service can instantiate one filter for the whole pipeline.

    Payload inventory is only trustworthy while the collector fetched it
    within ``availability_ttl_h`` of ``availability_at``. A stale or missing
    stamp (legacy points) makes those numbers unknown, so the hit passes.
    """

    def __init__(self, party: int | None,
                 seats_left: int | None = None,
                 capacity: int | None = None,
                 availability_ttl_h: int | float | None = None) -> None:
        self._party = max(0, int(party or 0))
        self._seats_left = _as_int(seats_left)
        self._capacity = _as_int(capacity)
        self._ttl_h = (default_settings.availability_ttl_h
                       if availability_ttl_h is None else availability_ttl_h)

    def matches(self, hit: FusedHit) -> bool:
        if self._party < 1:
            return True
        fresh = _is_fresh(hit.payload.get("availability_at"), self._ttl_h)
        seats_left = self._seats_left
        if seats_left is None and fresh:
            seats_left = _as_int(hit.payload.get("seats_left"))
        capacity = self._capacity
        if capacity is None and fresh:
            capacity = _as_int(hit.payload.get("capacity"))
        if seats_left is None and capacity is None:
            return True
        if seats_left is not None and seats_left < self._party:
            return False
        if capacity is not None:
            return capacity >= self._party
        return True


class StatusFilter(Filter):
    """Post-filter: cancelled events never show; sold out only with a party.

    A sold-out event is still a valid answer to "what's on tonight" when no
    party size was given (the user may just want to know about it), but it
    must not be offered as a bookable option for a specific group.

    ``sold_out`` is scraped inventory too: it is only trusted while
    ``availability_at`` is fresh. A stale/absent stamp (legacy points) means
    the status may no longer hold, so the hit is not hidden. ``cancelled``
    is editorial and always dropped.
    """

    def __init__(self, party: int | None = None,
                 availability_ttl_h: int | float | None = None) -> None:
        self._party = max(0, int(party or 0))
        self._ttl_h = (default_settings.availability_ttl_h
                       if availability_ttl_h is None else availability_ttl_h)

    def matches(self, hit: FusedHit) -> bool:
        status = str(hit.payload.get("status") or "").strip().casefold()
        if status == "cancelled":
            return False
        if (status == "sold_out" and self._party >= 1
                and _is_fresh(hit.payload.get("availability_at"), self._ttl_h)):
            return False
        return True


class AgeMaxFilter(Filter):
    """Drop hits whose age limit is above the requested maximum."""

    def __init__(self, age_max: int | None) -> None:
        self._age_max = _as_int(age_max)

    def matches(self, hit: FusedHit) -> bool:
        if self._age_max is None:
            return True
        limit = _as_int(hit.payload.get("age_limit"))
        return limit is None or limit <= self._age_max


class MinRatingFilter(Filter):
    """Drop hits rated below the floor; unknown ratings always pass.

    ``key`` selects the payload field: venues carry ``rating``, events carry
    the venue's ``venue_rating``.
    """

    def __init__(self, min_rating: float | None, key: str = "rating") -> None:
        self._min = _as_float(min_rating)
        self._key = key

    def matches(self, hit: FusedHit) -> bool:
        if self._min is None:
            return True
        rating = _as_float(hit.payload.get(self._key))
        return rating is None or rating >= self._min


_DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_ALL_DAY_TOKENS = ("24", "круглосуточн", "all day", "весь день")


def parse_clock(value) -> time | None:
    """``"09:00"``/``"9:30"``/``"24:00"`` -> ``time``; ``None`` when unknown."""
    if isinstance(value, time):
        return value
    text = str(value or "").strip()
    if ":" not in text:
        return None
    hour_text, _, minute_text = text.partition(":")
    try:
        hour = int(hour_text)
        minute = int(minute_text[:2] or 0)
    except ValueError:
        return None
    if hour == 24 and minute == 0:
        # "24:00" is the end of the day: reuse midnight and let the caller
        # roll the close over to the next day.
        return time(0, 0)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None
    return time(hour, minute)


def day_intervals(entry) -> list[tuple[time, time]] | None:
    """One hours entry -> intervals, or ``None`` for a whole-day opening.

    Accepts the collector shape ``["09:00", "23:00"]`` (a flat pair or a list
    of pairs), a ``"09:00-23:00"`` string, a ``{open, close}`` mapping, and
    the textual ``"24 hours"``/``"круглосуточно"`` whole-day entry. Closed
    days return an empty list.
    """
    if not entry:
        return []
    if isinstance(entry, dict):
        open_time = parse_clock(entry.get("open") or entry.get("from"))
        close_time = parse_clock(entry.get("close") or entry.get("to"))
        return [(open_time, close_time)] if open_time and close_time else []
    if isinstance(entry, str):
        if ":" not in entry:
            return None if any(token in entry.casefold()
                               for token in _ALL_DAY_TOKENS) else []
        pairs: list[tuple[time, time]] = []
        for part in entry.replace("–", "-").replace("—", "-").split(","):
            bits = [bit.strip() for bit in part.split("-") if bit.strip()]
            if len(bits) < 2:
                continue
            open_time, close_time = parse_clock(bits[0]), parse_clock(bits[1])
            if open_time is not None and close_time is not None:
                pairs.append((open_time, close_time))
        return pairs
    if isinstance(entry, (list, tuple)):
        items = list(entry)
        if items and all(not isinstance(item, (list, tuple, dict))
                         for item in items):
            if len(items) < 2:
                return []
            open_time, close_time = parse_clock(items[0]), parse_clock(items[1])
            return ([(open_time, close_time)]
                    if open_time is not None and close_time is not None else [])
        pairs = []
        for item in items:
            nested = day_intervals(item)
            if nested is None:
                return None
            pairs.extend(nested)
        return pairs
    return []


def _local(value: datetime, tz: ZoneInfo) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=tz)


class VenueHoursFilter(Filter):
    """Keep venues open during at least part of the requested window.

    Venues without opening hours (or marked 24/7) always pass: missing data
    is not a closed venue. That includes the collector's live shape where a
    day is ``None``/``[]`` when the schedule is unknown — an unknown day is
    never treated as "closed".

    Each day entry is a list of pairs (``[["09:00","13:00"],
    ["14:00","23:00"]]``: lunch breaks work) or the legacy flat pair
    ``["09:00","22:00"]``. Overnight closes (``18:00``–``02:00``) roll into
    the next day, and textual whole-day entries count as open all day.
    """

    def __init__(self, start: datetime, end: datetime | None = None,
                 tz_name: str | None = None) -> None:
        self._start = start
        self._end = end
        self._tz_name = tz_name

    @staticmethod
    def _entry(hours: Mapping, day: date):
        return (hours.get(_DAY_KEYS[day.weekday()])
                or hours.get(_DAY_KEYS[day.weekday()].upper())
                or hours.get(day.strftime("%A").casefold()))

    def _covers(self, entry, day: date, start: datetime, end: datetime,
                tz) -> bool | None:
        """``True``/``False`` when the day is known, ``None`` when unknown."""
        if not entry:
            return None
        intervals = day_intervals(entry)
        if intervals is None:  # textual "24 hours"/"круглосуточно"
            return True
        for open_time, close_time in intervals:
            opens = datetime.combine(day, open_time, tzinfo=tz)
            closes = datetime.combine(day, close_time, tzinfo=tz)
            if closes <= opens:
                closes += timedelta(days=1)
            if opens < end and closes > start:
                return True
        return False

    def matches(self, hit: FusedHit) -> bool:
        if hit.payload.get("is_24_7"):
            return True
        hours = hit.payload.get("hours")
        if not isinstance(hours, dict) or not hours:
            return True
        try:
            tz = ZoneInfo(self._tz_name or "UTC")
        except Exception:  # noqa: BLE001 — bad client timezone
            from datetime import timezone as _timezone
            tz = _timezone.utc  # type: ignore[assignment]
        start = _local(self._start, tz)
        end = _local(self._end or self._start, tz)
        if end <= start:
            end = start + timedelta(days=1)
        day: date = start.date()
        last_day: date = end.date()
        while day <= last_day:
            # The previous day's overnight interval may still be running
            # (18:00-02:00 covers 01:00 today); it is only a bonus, so an
            # unknown previous day changes nothing.
            previous = self._covers(self._entry(hours, day - timedelta(days=1)),
                                    day - timedelta(days=1), start, end, tz)
            if previous:
                return True
            covered = self._covers(self._entry(hours, day), day, start, end, tz)
            if covered is None:
                # Unknown schedule for a requested day: do not hide.
                return True
            if covered:
                return True
            day += timedelta(days=1)
        return False


class VenueBudgetFilter(Filter):
    """Post-filter on the per-person check.

    ``avg_check`` is authoritative when the source publishes it; otherwise
    the coarse 2GIS ``price_level`` is mapped through configuration. Unknown
    prices always pass, mirroring ``MaxPriceFilter``.
    """

    def __init__(self, max_per_person: float,
                 price_levels: Mapping[str, float] | None = None) -> None:
        self._max = float(max_per_person)
        self._levels = {str(key).casefold(): float(value)
                        for key, value in (price_levels or {}).items()}

    def matches(self, hit: FusedHit) -> bool:
        avg_check = _as_float(hit.payload.get("avg_check"))
        if avg_check is not None:
            return avg_check <= self._max
        level = str(hit.payload.get("price_level") or "").strip().casefold()
        mapped = self._levels.get(level)
        return mapped is None or mapped <= self._max


# Event categories that have a matching 2GIS venue rubric. Categories with no
# mapping (concert/sport/kids/other) are ignored: a bar is not excluded just
# because the user said "no sport".
CATEGORY_TO_VENUE_RUBRICS: dict[str, tuple[str, ...]] = {
    "theatre": ("театры",),
    "film": ("кинотеатры",),
    "exhibition": ("художественные выставки", "библиотеки"),
}


class ExcludeVenueCategoriesFilter(Filter):
    """Exclude venues whose rubric corresponds to a forbidden event category."""

    def __init__(self, categories: list[str]) -> None:
        rubrics: list[str] = []
        for category in categories:
            for rubric in CATEGORY_TO_VENUE_RUBRICS.get(
                    str(category).strip().casefold(), ()):
                if rubric not in rubrics:
                    rubrics.append(rubric)
        self._rubrics = rubrics

    def matches(self, hit: FusedHit) -> bool:
        if not self._rubrics:
            return True
        rubric = str(hit.payload.get("rubric") or "").strip().casefold()
        if not rubric:
            return True
        return not any(rubric in mapped or mapped in rubric
                       for mapped in self._rubrics)
