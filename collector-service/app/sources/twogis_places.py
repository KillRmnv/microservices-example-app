"""2GIS Places (catalog.api.2gis.com/3.0/items): venues directory.

Every HTTP attempt consumes one monthly quota unit BEFORE firing; the run
stops with QuotaExhausted at cap - reserve (demo key: 1000/month).
Rubric/region ids are discovered once and cached in the DB.
"""
from __future__ import annotations

import logging
import re

from ..core import db
from ..core.config import settings
from ..errors.domain import (QuotaExhausted, SourceConfigError,
                             SourceFetchError, SourceParseError)
from ..parsing.normalize import VenueRow
from ..parsing.schedule import normalize_schedule, schedule_for_storage
from ..repositories.quota import current_month, try_consume
from ..repositories.store import upsert_venues
from .base import CollectContext, RunStats, SourceAdapter

log = logging.getLogger(__name__)

PROVIDER = "twogis"


def bbox() -> tuple[float, float, float, float]:
    """Configured (south, north, west, east) sanity box for catalog coords."""
    values = [float(part) for part in settings.twogis_bbox.split(",")]
    if len(values) != 4:
        raise SourceConfigError("COLLECTOR_TWOGIS_BBOX must be 'south,north,west,east'")
    return values[0], values[1], values[2], values[3]


def in_bbox(latitude: float, longitude: float, box: tuple[float, float, float, float] | None = None) -> bool:
    south, north, west, east = box or bbox()
    return south <= latitude <= north and west <= longitude <= east


def fix_coords(latitude: float | None, longitude: float | None) -> tuple[float | None, float | None]:
    """Recover swapped coordinates when only the swapped variant is in bounds."""
    if latitude is None or longitude is None:
        return latitude, longitude
    box = bbox()
    if in_bbox(latitude, longitude, box):
        return latitude, longitude
    if in_bbox(longitude, latitude, box):
        log.warning("2GIS point looks swapped, recovering: (%s, %s)", latitude, longitude)
        return longitude, latitude
    log.warning("2GIS point outside catalog bbox, kept as-is: (%s, %s)", latitude, longitude)
    return latitude, longitude

FIELDS = ("items.point,items.address_name,items.full_address_name,"
          "items.rubrics,items.schedule,items.reviews,items.name_ex,items.name,"
          # Enrichment groups. Live-verified against 3.0 /3.0/items
          # (2026-11-26): requesting them is accepted (HTTP 200) but the
          # items carry no attribute_groups/attributes/adm_div, so parsing
          # below stays defensive and the venue keeps NULL enrichment values.
          "items.attribute_groups,items.attributes,items.adm_div")

# RU attribute names -> lowercase ASCII tags (contract vocabulary).
AMENITY_TAGS = {
    "веранда": "terrace",
    "терраса": "terrace",
    "wi-fi": "wifi",
    "wifi": "wifi",
    "вай-фай": "wifi",
    "парковка": "parking",
    "депозит": "deposit",
    "доставка": "delivery",
    "детская комната": "kids_room",
    "детская": "kids_room",
}

# 2GIS attribute values are free text: "есть"/"нет", "500 Br", a list, ...
# A known amenity name only becomes a tag when the value is affirmative.
NEGATIVE_VALUES = {"нет", "no", "отсутствует", "недоступно", "не доступно",
                   "false", "0"}

_AVG_CHECK_RE = re.compile(r"(\d+(?:[.,]\d+)?)")
_AVG_CHECK_NAME = "средний чек"
MAX_AVG_CHECK = 100_000.0


def _normalize_name(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold().replace("ё", "е")).strip()


def _attr_text(value) -> str:
    if isinstance(value, dict):
        value = value.get("name") or value.get("value") or value.get("text") or ""
    if isinstance(value, (list, tuple)):
        return " ".join(filter(None, (_attr_text(item) for item in value)))
    if isinstance(value, bool):
        return "да" if value else ""
    return str(value).strip()


def _attr_pair(entry) -> tuple[str, str]:
    if isinstance(entry, dict):
        name = entry.get("name") or entry.get("title") or entry.get("key") or ""
        raw = entry.get("value", entry.get("values", entry.get("text", "")))
        return str(name), _attr_text(raw)
    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
        return str(entry[0]), _attr_text(entry[1])
    return _attr_text(entry), ""


def attribute_pairs(item: dict) -> list[tuple[str, str]]:
    """Flatten the plausible 2GIS attribute shapes into (name, value) pairs.

    Covered: grouped list ``[{"name": ..., "attributes": [{...}]}]`` (also
    ``items`` inside a group), flat ``[{"name","value"}]``, and a mapping
    ``{"Wi-Fi": "есть"}``. Unknown shapes simply contribute nothing.
    """
    pairs: list[tuple[str, str]] = []
    groups = item.get("attribute_groups")
    if isinstance(groups, list):
        for group in groups:
            if not isinstance(group, dict):
                pairs.append(_attr_pair(group))
                continue
            entries = group.get("attributes")
            if entries is None:
                entries = group.get("items")
            if isinstance(entries, dict):
                pairs.extend((str(key), _attr_text(value))
                             for key, value in entries.items())
            elif isinstance(entries, list):
                pairs.extend(_attr_pair(entry) for entry in entries)
            elif group.get("name"):
                pairs.append(_attr_pair(group))
    attributes = item.get("attributes")
    if isinstance(attributes, dict):
        pairs.extend((str(key), _attr_text(value))
                     for key, value in attributes.items())
    elif isinstance(attributes, list):
        pairs.extend(_attr_pair(entry) for entry in attributes)
    return [(name, value) for name, value in pairs if name]


def parse_amenities(item: dict) -> list[str] | None:
    """Map known RU attribute names onto the ASCII tag vocabulary."""
    tags: list[str] = []
    for name, value in attribute_pairs(item):
        normalized = _normalize_name(name)
        if _normalize_name(value) in NEGATIVE_VALUES:
            continue
        for needle, tag in AMENITY_TAGS.items():
            if needle in normalized and tag not in tags:
                tags.append(tag)
    return tags or None


def parse_avg_check(item: dict) -> float | None:
    """'Средний чек' -> midpoint of its range ('30–50 Br' -> 40.0)."""
    text = ""
    for name, value in attribute_pairs(item):
        if _AVG_CHECK_NAME in _normalize_name(name):
            text = value
            break
    if not text:
        return None
    numbers = []
    for match in _AVG_CHECK_RE.findall(text):
        try:
            number = float(match.replace(",", "."))
        except ValueError:
            continue
        if 0 < number <= MAX_AVG_CHECK:
            numbers.append(number)
    if not numbers:
        return None
    sample = numbers[:2]  # a "30–50" range contributes exactly two bounds
    return round(sum(sample) / len(sample), 2)


def price_level_for(avg_check: float | None) -> str | None:
    """low < 25 BYN, medium < 60 BYN, high otherwise."""
    if avg_check is None:
        return None
    if avg_check < 25:
        return "low"
    if avg_check < 60:
        return "medium"
    return "high"


def parse_district(item: dict) -> str | None:
    """adm_div district name (entries carry {"type": "district"|"city"|...})."""
    entries = item.get("adm_div")
    if not isinstance(entries, list):
        return None
    fallback = None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        if str(entry.get("type") or "").casefold() == "district":
            return name
        fallback = name
    return fallback


def normalize_point(point: dict | None) -> tuple[float | None, float | None]:
    """2GIS point is {lat, lon} — but docs show swapped examples, so guard
    by range: latitude must fit [-90, 90]. Returns (lat, lon)."""
    import math
    if not isinstance(point, dict):
        return None, None
    try:
        first = float(point.get("lat"))
        second = float(point.get("lon"))
    except (TypeError, ValueError):
        return None, None
    if not math.isfinite(first) or not math.isfinite(second):
        return None, None
    if abs(first) > 90 >= abs(second):
        first, second = second, first
    if abs(first) > 90:
        return None, None
    return first, second


class TwogisPlacesAdapter(SourceAdapter):
    name = "twogis_places"

    def __init__(self, rubrics: list[str] | None = None) -> None:
        self._rubrics = rubrics

    async def _get(self, ctx: CollectContext, conn, path: str,
                   params: dict, stats: RunStats) -> dict:
        def consume_attempt() -> None:
            month = current_month()
            allowed = try_consume(conn, PROVIDER, month,
                                  settings.twogis_monthly_cap,
                                  settings.twogis_reserve)
            conn.commit()
            if not allowed:
                raise QuotaExhausted(
                    f"2GIS monthly quota reached "
                    f"(cap {settings.twogis_monthly_cap}, "
                    f"reserve {settings.twogis_reserve})")

        request_params = {**params, "key": settings.twogis_api_key}
        response = await ctx.http.get(
            self.name, settings.twogis_base_url + path,
            params=request_params, before_attempt=consume_attempt)
        stats.fetched += 1
        if response.status_code == 404:
            return {}
        if response.status_code != 200:
            raise SourceFetchError(f"{path} -> HTTP {response.status_code}: "
                                   f"{response.text[:200]}")
        try:
            data = response.json()
        except Exception as exc:
            raise SourceParseError(
                f"{path} -> invalid JSON: {exc}: {response.text[:200]}") from exc
        meta = data.get("meta") or {}
        code = str(meta.get("code", ""))
        if code in ("404", "204"):
            return {}
        if code != "200":
            raise SourceFetchError(f"{path} -> API code {meta}")
        result = data.get("result") or {}
        return result

    def _kv_get(self, conn, key: str) -> str | None:
        row = conn.execute(
            "SELECT value FROM collector_kv WHERE key = %s", (key,)).fetchone()
        return row["value"] if row else None

    def _kv_set(self, conn, key: str, value: str) -> None:
        conn.execute(
            """INSERT INTO collector_kv (key, value) VALUES (%s, %s)
               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value""",
            (key, value),
        )
        conn.commit()

    async def _region_id(self, ctx, conn, stats: RunStats) -> str:
        cached = self._kv_get(conn, "twogis:region_id")
        if cached:
            return cached
        result = await self._get(ctx, conn, "/2.0/region/search",
                                 {"q": settings.twogis_region or settings.default_city}, stats)
        items = result.get("items", [])
        if not items or "id" not in items[0]:
            raise SourceConfigError(
                f"region not found for {settings.twogis_region or settings.default_city!r}")
        region_id = str(items[0]["id"])
        self._kv_set(conn, "twogis:region_id", region_id)
        return region_id

    async def _rubric_id(self, ctx, conn, stats: RunStats,
                         region_id: str, name: str) -> str | None:
        row = conn.execute(
            "SELECT rubric_id FROM twogis_rubrics WHERE name = %s", (name,)).fetchone()
        if row:
            return row["rubric_id"]
        result = await self._get(ctx, conn, "/2.0/catalog/rubric/search",
                                 {"region_id": region_id, "q": name}, stats)
        items = result.get("items", [])
        if not items or "id" not in items[0]:
            log.warning("2GIS rubric not found: %r", name)
            return None
        rubric_id = str(items[0]["id"])
        conn.execute(
            """INSERT INTO twogis_rubrics (name, rubric_id) VALUES (%s, %s)
               ON CONFLICT (name) DO UPDATE SET rubric_id = EXCLUDED.rubric_id,
               fetched_at = now()""",
            (name, rubric_id),
        )
        conn.commit()
        return rubric_id

    @staticmethod
    def parse_item(item: dict, rubric_name: str) -> VenueRow | None:
        if not isinstance(item, dict) or "id" not in item:
            return None
        name = item.get("name") or ""
        if not name and isinstance(item.get("name_ex"), dict):
            name = item["name_ex"].get("primary") or item["name_ex"].get("short_name") or ""
        name = name.strip()
        if not name:
            return None
        latitude, longitude = normalize_point(item.get("point"))
        latitude, longitude = fix_coords(latitude, longitude)
        rubrics = item.get("rubrics") or []
        rubric = rubric_name
        if rubrics and isinstance(rubrics[0], dict) and rubrics[0].get("name"):
            rubric = str(rubrics[0]["name"])
        reviews = item.get("reviews") or {}
        rating = reviews.get("rating") or reviews.get("general_rating")
        try:
            rating = float(rating) if rating is not None else None
        except (TypeError, ValueError):
            rating = None
        review_count = reviews.get("review_count") or reviews.get("general_review_count")
        try:
            review_count = int(review_count) if review_count is not None else None
        except (TypeError, ValueError):
            review_count = None
        address = item.get("full_address_name") or item.get("address_name")
        if not address and item.get("address"):
            if isinstance(item["address"], dict):
                address = item["address"].get("name") or item["address"].get("full_name")
            elif isinstance(item["address"], str):
                address = item["address"]
        address = str(address).strip() if address else None
        hours, is_24_7 = normalize_schedule(item.get("schedule"))
        avg_check = parse_avg_check(item)
        return VenueRow(
            source_id=str(item["id"]),
            name=name[:300],
            rubric=rubric,
            address=address,
            city=settings.twogis_region or settings.default_city,
            latitude=latitude,
            longitude=longitude,
            schedule=schedule_for_storage(item.get("schedule"), hours, is_24_7),
            rating=rating,
            review_count=review_count,
            hours=hours,
            is_24_7=is_24_7,
            amenities=parse_amenities(item),
            avg_check=avg_check,
            price_level=price_level_for(avg_check),
            district=parse_district(item),
            raw=item,
        )

    async def collect(self, ctx: CollectContext) -> RunStats:
        if not settings.twogis_api_key:
            raise SourceConfigError("COLLECTOR_TWOGIS_API_KEY is not set")
        stats = RunStats()
        rubrics = self._rubrics or [
            name.strip() for name in settings.twogis_rubrics.split(",") if name.strip()]
        max_pages = ctx.max_urls  # canary: cap pages per rubric
        with db.get_conn(ctx.db_url) as conn:
            region_id = await self._region_id(ctx, conn, stats)
            for name in rubrics:
                try:
                    await self._collect_rubric(ctx, conn, stats, region_id, name,
                                              settings.twogis_page_size, max_pages)
                except QuotaExhausted:
                    stats.quota_stopped = True
                    log.warning("2GIS quota exhausted, stopping run")
                    break
                except Exception as exc:  # noqa: BLE001 — one rubric must not kill the run
                    stats.fetch_errors += 1
                    conn.rollback()
                    log.warning("2GIS rubric %r failed: %s", name, exc)
        if stats.fetched == 0:
            raise SourceFetchError("2GIS collect fetched nothing (key/quota?)")
        return stats

    async def _collect_rubric(self, ctx, conn, stats, region_id: str,
                              name: str, page_size: int, max_pages: int | None) -> None:
        rubric_id = await self._rubric_id(ctx, conn, stats, region_id, name)
        if rubric_id is None:
            stats.parse_errors += 1
            return
        page = 1
        while True:
            if max_pages is not None and page > max_pages:
                break
            params = {
                "rubric_id": rubric_id,
                "region_id": region_id,
                "fields": FIELDS,
                "page": page,
                "page_size": page_size,
            }
            # 2GIS returns an empty list for unsupported locales, so only
            # send it when explicitly configured.
            if settings.twogis_locale:
                params["locale"] = settings.twogis_locale
            result = await self._get(ctx, conn, "/3.0/items", params, stats)
            items = result.get("items", []) if isinstance(result, dict) else []
            if not items:
                break
            venues: list[VenueRow] = []
            for item in items:
                venue = self.parse_item(item, name)
                if venue is None:
                    stats.parse_errors += 1
                    continue
                venues.append(venue)
            if venues:
                merged = upsert_venues(conn, venues)
                stats.parsed += merged.parsed
                stats.rows_inserted += merged.rows_inserted
                stats.rows_updated += merged.rows_updated
                stats.duplicates += merged.duplicates
            conn.commit()
            log.info("2GIS rubric %r page %d: %d items", name, page, len(items))
            total = result.get("total") if isinstance(result, dict) else None
            if len(items) < page_size:
                break
            if isinstance(total, int) and page * page_size >= total:
                break
            page += 1
