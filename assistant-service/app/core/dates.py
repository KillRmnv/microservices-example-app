"""Date/time helpers shared by the dialogue layer."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)


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
