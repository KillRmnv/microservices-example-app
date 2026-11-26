"""Tolerant 2GIS schedule -> ``{"mon": [["09:00", "22:00"]], ...}``.

2GIS 3.0/items returns

    {"Mon": {"working_hours": [{"from": "09:00", "to": "22:00"}]}}

but exports and cached payloads also hand us JSON strings, "Пн-Вс 09:00-23:00"
style text and "круглосуточно". Anything unrecognised yields ``(None, False)``
so a venue is stored without hours instead of failing the collect run.

Contract: keys are lowercase 3-letter English days ("mon".."sun"), values are a
**list of** ``[opens, closes]`` windows as "HH:MM", e.g.

    {"fri": [["18:00", "02:00"]],
     "mon": [["09:00", "13:00"], ["14:00", "23:00"]]}

A list keeps overnight spans (close < open means the next day) and lunch
breaks; flattening them into one pair silently misreported both. ``is_24_7``
stays a separate boolean.
"""
from __future__ import annotations

import json
import re

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

_DAY_ALIASES = {
    "mon": "mon", "monday": "mon", "пн": "mon", "понедельник": "mon",
    "tue": "tue", "tues": "tue", "tuesday": "tue", "вт": "tue", "вторник": "tue",
    "wed": "wed", "wednesday": "wed", "ср": "wed", "среда": "wed",
    "thu": "thu", "thur": "thu", "thurs": "thu", "thursday": "thu",
    "чт": "thu", "четверг": "thu",
    "fri": "fri", "friday": "fri", "пт": "fri", "пятница": "fri",
    "sat": "sat", "saturday": "sat", "сб": "sat", "суббота": "sat",
    "sun": "sun", "sunday": "sun", "вс": "sun", "воскресенье": "sun",
}

_OPEN_24_RE = re.compile(r"круглосуточ|24\s*[/хx]\s*7|24\s*час", re.I)
_DAILY_RE = re.compile(r"ежедневно|каждый день|daily|без выходных", re.I)
_TIME_RE = re.compile(r"(\d{1,2})\s*[:.]\s*(\d{2})")
_DAY_TOKEN_RE = re.compile(r"[а-яёa-z]+", re.I)
_RANGE_RE = re.compile(r"[-–—]")

Window = list[str]


def _norm_time(value) -> str | None:
    """'9:00' / '09.00' / '24:00' -> 'HH:MM' (24:00 clamps to 23:59)."""
    if isinstance(value, (int, float)):
        value = f"{int(value)}:00"
    if not isinstance(value, str):
        return None
    match = _TIME_RE.search(value)
    if match is None:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour == 24 and minute == 0:
        return "23:59"
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def _day_key(value) -> str | None:
    if not isinstance(value, str):
        return None
    return _DAY_ALIASES.get(value.strip().casefold().replace("ё", "е"))


def _span(start, end) -> Window | None:
    """One validated window; overnight (close < open) is kept as-is."""
    opened, closed = _norm_time(start), _norm_time(end)
    if opened is None or closed is None:
        return None
    if opened == closed:
        return None  # zero-length window is noise, not an appointment
    return [opened, closed]


def _dedupe(windows: list[Window]) -> list[Window]:
    unique: list[Window] = []
    for window in windows:
        if window not in unique:
            unique.append(window)
    return unique


def _windows_from_text(text: str) -> list[Window]:
    """Every "HH:MM[-–]HH:MM" window inside a text fragment."""
    times = [_norm_time(match.group(0)) for match in _TIME_RE.finditer(text)]
    times = [time for time in times if time]
    windows: list[Window] = []
    for index in range(0, len(times) - 1, 2):
        span = _span(times[index], times[index + 1])
        if span is not None:
            windows.append(span)
    return _dedupe(windows)


def _windows_from_entries(entries) -> list[Window]:
    """2GIS `working_hours` list (also accepts bare/JSON-ish pair lists)."""
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, (list, tuple)):
        return []
    windows: list[Window] = []
    for entry in entries:
        if isinstance(entry, dict):
            span = _span(entry.get("from"), entry.get("to"))
            if span is not None:
                windows.append(span)
        elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
            span = _span(entry[0], entry[1])
            if span is not None:
                windows.append(span)
        elif isinstance(entry, str):
            windows.extend(_windows_from_text(entry))
    return _dedupe(windows)


def _day_value(value) -> list[Window] | str | None:
    """Parse one day entry; the "24_7" sentinel marks an around-the-clock day."""
    if isinstance(value, str):
        if _OPEN_24_RE.search(value):
            return "24_7"
        return _windows_from_text(value) or None
    if isinstance(value, (list, tuple)):
        # Already-normalized hours fed back through a JSON round-trip.
        return _windows_from_entries(value) or None
    if not isinstance(value, dict):
        return None
    if value.get("is_24_7") is True:
        return "24_7"
    if value.get("is_closed") is True:
        return None
    entries = (value.get("working_hours") or value.get("hours")
               or value.get("intervals") or [])
    return _windows_from_entries(entries) or None


def _mentions_days(text: str) -> bool:
    if _DAILY_RE.search(text):
        return True
    return any(_day_key(match.group(0))
               for match in _DAY_TOKEN_RE.finditer(text))


def _days_in_segment(segment: str) -> list[str] | None:
    """Days named in a fragment; 'Пн-Вс' expands to the whole week."""
    found = []
    for match in _DAY_TOKEN_RE.finditer(segment):
        key = _day_key(match.group(0))
        if key is not None:
            found.append((key, match.start(), match.end()))
    if not found:
        if _DAILY_RE.search(segment):
            return list(DAYS)
        return None
    if len(found) >= 2 and _RANGE_RE.search(segment[found[0][2]:found[1][1] + 1]):
        start, end = DAYS.index(found[0][0]), DAYS.index(found[1][0])
        if start <= end:
            return list(DAYS[start:end + 1])
        return list(DAYS[start:]) + list(DAYS[:end + 1])
    return [key for key, _, _ in found]


def _assign(hours: dict[str, list[Window]], days: list[str] | None,
            windows: list[Window]) -> None:
    """Attach windows to days; an open day never gets an empty window list."""
    if not days or not windows:
        return
    for day in days:
        merged = hours.setdefault(day, [])
        for window in windows:
            if window not in merged:
                merged.append(window)


def _from_dict(schedule: dict) -> tuple[dict, bool]:
    hours: dict[str, list[Window]] = {}
    is_24_7 = schedule.get("is_24_7") is True
    for day, value in schedule.items():
        key = _day_key(day)
        if key is None:
            continue
        parsed = _day_value(value)
        if parsed == "24_7":
            is_24_7 = True
            continue
        if parsed:
            hours[key] = parsed
    return hours, is_24_7


def _from_string(schedule: str) -> tuple[dict, bool]:
    text = schedule.strip()
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
        except ValueError:
            return {}, False
        return _from_dict(parsed) if isinstance(parsed, dict) else ({}, False)
    if _OPEN_24_RE.search(text):
        return {}, True
    hours: dict[str, list[Window]] = {}
    for block in re.split(r"[;\n]+", text):
        days: list[str] | None = None
        windows: list[Window] = []
        for chunk in re.split(r",", block):
            chunk = chunk.strip()
            if not chunk:
                continue
            spans = _windows_from_text(chunk)
            if _mentions_days(chunk):
                # A new day group starts; the previous one is complete.
                _assign(hours, days, windows)
                days = _days_in_segment(chunk) or list(DAYS)
                windows = list(spans)
            else:
                # "Пн-Пт 09:00-13:00, 14:00-23:00": a continuation window of
                # the current (or, with no day names at all, every) day group.
                if days is None:
                    days = list(DAYS)
                windows.extend(spans)
        _assign(hours, days, windows)
    return hours, False


def normalize_schedule(schedule) -> tuple[dict | None, bool]:
    """Return (hours, is_24_7); (None, False) when nothing usable is found."""
    hours: dict[str, list[Window]] = {}
    is_24_7 = False
    if isinstance(schedule, dict):
        hours, is_24_7 = _from_dict(schedule)
    elif isinstance(schedule, str):
        hours, is_24_7 = _from_string(schedule)
    ordered = {day: hours[day] for day in DAYS if hours.get(day)}
    if not ordered:
        return None, is_24_7
    if len(ordered) == 7 and all(windows == [["00:00", "23:59"]]
                                 for windows in ordered.values()):
        is_24_7 = True
    return ordered, is_24_7


_DAY_TITLES = {"mon": "Mon", "tue": "Tue", "wed": "Wed", "thu": "Thu",
               "fri": "Fri", "sat": "Sat", "sun": "Sun"}


def schedule_for_storage(schedule, hours: dict | None,
                         is_24_7: bool) -> dict | None:
    """Canonical 2GIS-shaped schedule for `collected_venues.schedule`.

    A dict payload is stored verbatim (it is the source of truth). A text
    schedule has no dict to keep, so the parsed hours are re-encoded in the
    same shape (every window, not one widened span); otherwise a later
    `/embed/reindex-hybrid` would lose hours derived from the string.
    """
    if isinstance(schedule, dict):
        return schedule
    if hours:
        return {_DAY_TITLES[day]: {"working_hours": [
                    {"from": opened, "to": closed} for opened, closed in windows]}
                for day, windows in hours.items()}
    if is_24_7:
        return {"is_24_7": True}
    return None
