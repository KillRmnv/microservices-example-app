"""Date/time helpers shared by the dialogue layer."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

# Canonical Russian time-of-day windows: (start hour, start minute,
# end hour, end minute). The end is inclusive and may cross midnight.
TIME_WINDOWS: dict[str, tuple[int, int, int, int]] = {
    "morning": (9, 0, 11, 59),
    "day": (12, 0, 17, 59),
    "evening": (18, 0, 23, 59),
    "night": (22, 0, 5, 59),
}

_TIME_WINDOW_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("morning", re.compile(r"\bутр|morning", re.IGNORECASE)),
    ("evening", re.compile(r"\bвечер|evening", re.IGNORECASE)),
    ("night", re.compile(r"\bноч|night", re.IGNORECASE)),
    ("day", re.compile(r"\bдн[её]м\b|\bдень\b|\bдневн|afternoon",
                       re.IGNORECASE)),
)
_CLOCK_RE = re.compile(r"\d{1,2}[:.]\d{2}|\bв\s+\d{1,2}\b", re.IGNORECASE)


def time_window(expression: str | None) -> tuple[int, int, int, int] | None:
    """Return the canonical window for "утро/день/вечер/ночь", if present."""
    text = (expression or "").strip()
    if not text:
        return None
    for name, pattern in _TIME_WINDOW_PATTERNS:
        if pattern.search(text):
            return TIME_WINDOWS[name]
    return None


def has_explicit_clock(expression: str | None) -> bool:
    """True when the user named a concrete time ("в 20:00", "к 19")."""
    return bool(_CLOCK_RE.search(expression or ""))



def parse_iso_date(value: str | None) -> date | None:
    """Parse a date from an ISO date or datetime string, None when invalid.

    Accepts "2026-11-01", "2026-11-01T19:00:00+03:00" and the "Z" suffix
    instead of slicing the string (which silently broke on short inputs).
    """
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            log.debug("unparseable date %r", value)
            return None


def get_current_datetime(tz_name: str) -> datetime:
    """Timezone-aware "now"; invalid zone names fall back to UTC."""
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:  # noqa: BLE001 — bad tz name from a client
        log.warning("bad timezone %r, falling back to UTC", tz_name)
        return datetime.now(timezone.utc)
