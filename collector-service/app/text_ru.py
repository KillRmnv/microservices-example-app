"""Russian date expressions from Telegram posts.

Covers "9 октября (пт), в 19:00", "9 октября в 19:00", "сегодня/завтра в 19:00".
Times are Europe/Minsk local, returned UTC-aware. Past dates -> None.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

MINSK_TZ = ZoneInfo("Europe/Minsk")

MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

DAY_MONTH_RE = re.compile(
    r"(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)"
    r"(?:\s*\([^)]*\))?\s*,?\s*(?:в\s*)?(\d{1,2}:\d{2})?",
    re.I,
)
RELATIVE_RE = re.compile(
    r"(сегодня|завтра)\s*(?:в\s*(\d{1,2}:\d{2}))?", re.I,
)
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")


def _at(day: datetime, time_text: str | None) -> datetime:
    hour, minute = 12, 0
    if time_text:
        match = TIME_RE.search(time_text)
        if match:
            hour, minute = int(match.group(1)), int(match.group(2))
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def parse_ru_datetime(text: str | None, now_utc: datetime) -> datetime | None:
    """Future datetime in UTC, or None when absent/past."""
    if not text:
        return None
    now_minsk = now_utc.astimezone(MINSK_TZ)
    match = DAY_MONTH_RE.search(text)
    if match:
        day, month_name, time_text = int(match.group(1)), match.group(2).lower(), match.group(3)
        candidate = _at(now_minsk.replace(month=MONTHS[month_name], day=day), time_text)
        if candidate < now_minsk - timedelta(hours=12):
            return None  # announcements are for upcoming dates, not next year
        return candidate.astimezone(ZoneInfo("UTC"))
    match = RELATIVE_RE.search(text)
    if match:
        day = now_minsk + timedelta(days=1 if match.group(1).lower() == "завтра" else 0)
        result = _at(day, match.group(2))
        if result < now_minsk:
            return None
        return result.astimezone(ZoneInfo("UTC"))
    return None
