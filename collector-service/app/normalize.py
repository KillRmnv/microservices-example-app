"""JSON-LD Event -> RawEvent normalization.

Dates: naive values use the configured timezone, stored as UTC-aware.
Prices: numbers in the configured currency; "Уточняйте" -> None.
Cities: only the configured target city passes (MVP catalog scope).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from .core.config import settings
from .models.catalog import RawEvent, VenueRow  # re-exported for adapters

log = logging.getLogger(__name__)

CATEGORIES = {"concert", "theatre", "exhibition", "film", "sport", "kids", "other"}

PRICE_RE = re.compile(r"(\d[\d\s]*(?:[.,]\d+)?)")
AGE_RE = re.compile(r"(\d+)\s*\+")
NON_PRICE = re.compile(r"уточняйте|договорная|бесплатно|free", re.I)


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(settings.default_timezone))
    return parsed.astimezone(ZoneInfo("UTC"))


def parse_price(text: str | None) -> tuple[float | None, float | None]:
    """Returns (min, max). 'Уточняйте'/free -> (None, None); single -> (v, v)."""
    if not text or NON_PRICE.search(text):
        return None, None
    numbers = []
    for match in PRICE_RE.findall(text):
        try:
            numbers.append(float(match.replace(" ", "").replace(",", ".")))
        except ValueError:
            continue
    if not numbers:
        return None, None
    return min(numbers), max(numbers)


def parse_age(text: str | None) -> int | None:
    if not text:
        return None
    match = AGE_RE.search(text)
    return int(match.group(1)) if match else None


def _location_strings(location) -> str:
    """Flatten schema.org location into one searchable string."""
    if isinstance(location, str):
        return location
    if not isinstance(location, dict):
        return ""
    parts = [str(location.get("name", ""))]
    address = location.get("address", "")
    if isinstance(address, dict):
        parts += [str(address.get(k, "")) for k in
                  ("streetAddress", "addressLocality", "addressRegion", "addressCountry")]
    else:
        parts.append(str(address))
    return " ".join(parts)


def is_target_city(location, city: str | None = None) -> bool:
    target = (city or settings.default_city).casefold()
    text = _location_strings(location).casefold()
    if target in text:
        return True
    return target == "минск" and "minsk" in text


def _first_image(image) -> str | None:
    if isinstance(image, str):
        return image
    if isinstance(image, list) and image:
        first = image[0]
        return first if isinstance(first, str) else None
    return None


def _offers(offers) -> dict:
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    return offers if isinstance(offers, dict) else {}


def normalize_jsonld(source: str, source_id: str, source_url: str, category: str,
                     data: dict, now_utc: datetime) -> RawEvent | None:
    """Returns None when the card must be skipped (past, non-Minsk, ...)."""
    location = data.get("location", "")
    if not is_target_city(location):
        return None
    end_at = parse_datetime(data.get("endDate"))
    if end_at is not None and end_at < now_utc:
        return None  # stale repertoire entry (Relax keeps years-old shows)
    offers = _offers(data.get("offers"))
    price_min, price_max = parse_price(str(offers.get("price", "") or ""))
    if price_min is None:
        low, _ = parse_price(str(offers.get("lowPrice", "") or ""))
        _, high = parse_price(str(offers.get("highPrice", "") or ""))
        price_min, price_max = low, high
    geo = (location.get("geo", {}) if isinstance(location, dict) else {}) or {}
    title = (data.get("name") or "").strip()
    if not title:
        return None
    return RawEvent(
        source=source,
        source_id=source_id,
        source_url=data.get("url") or source_url,
        title=title,
        description=(data.get("description") or "").strip() or None,
        category=category if category in CATEGORIES else "other",
        start_at=parse_datetime(data.get("startDate")),
        end_at=end_at,
        venue_name=(location.get("name") if isinstance(location, dict) else None),
        address=_location_strings(location) or None,
        city=settings.default_city,
        price_min=price_min,
        price_max=price_max,
        currency=str(offers.get("priceCurrency") or settings.default_currency),
        age_limit=parse_age(str(data.get("typicalAgeRange", "") or "")),
        ticket_url=offers.get("url") if isinstance(offers.get("url"), str) else None,
        image_url=_first_image(data.get("image")),
        organizer=(data.get("organizer") or {}).get("name")
        if isinstance(data.get("organizer"), dict) else None,
        raw=data,
    )
