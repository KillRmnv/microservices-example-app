"""2GIS Places (catalog.api.2gis.com/3.0/items): venues directory.

Every HTTP call consumes one monthly quota unit BEFORE firing; the run
stops with QuotaExhausted at cap - reserve (demo key: 1000/month).
Rubric/region ids are discovered once and cached in the DB.
"""
from __future__ import annotations

import logging

from .. import db
from ..normalize import VenueRow
from ..quota import QuotaExhausted, current_month, try_consume
from ..store import upsert_venues
from .base import CollectContext, RunStats, SourceAdapter

log = logging.getLogger(__name__)

BASE = "https://catalog.api.2gis.com"
PROVIDER = "twogis"

# Minsk center (lon, lat order for 2GIS params) + radius covering the city.
MINSK_POINT = "27.5618,53.9028"
MINSK_RADIUS = 25000

# Sanity box for our catalog: swapped API coords land far outside it.
MINSK_BBOX = (53.5, 54.3, 27.1, 28.1)


def in_minsk_bbox(lat: float, lon: float) -> bool:
    south, north, west, east = MINSK_BBOX
    return south <= lat <= north and west <= lon <= east


def fix_minsk_coords(lat: float | None, lon: float | None) -> tuple[float | None, float | None]:
    """Recover swapped coordinates when only the swapped variant is in Minsk."""
    if lat is None or lon is None:
        return lat, lon
    if in_minsk_bbox(lat, lon):
        return lat, lon
    if in_minsk_bbox(lon, lat):
        log.warning("2GIS point looks swapped, recovering: (%s, %s)", lat, lon)
        return lon, lat
    log.warning("2GIS point outside Minsk bbox, kept as-is: (%s, %s)", lat, lon)
    return lat, lon

FIELDS = ("items.point,items.address_name,items.full_address_name,"
          "items.rubrics,items.schedule,items.reviews,items.name_ex")


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
        from ..config import settings
        month = current_month()
        allowed = try_consume(conn, PROVIDER, month,
                              settings.twogis_monthly_cap, settings.twogis_reserve)
        conn.commit()
        if not allowed:
            raise QuotaExhausted(
                f"2GIS monthly quota reached "
                f"(cap {settings.twogis_monthly_cap}, reserve {settings.twogis_reserve})")
        params = {**params, "key": settings.twogis_api_key}
        response = await ctx.http.get(self.name, BASE + path, params=params)
        stats.fetched += 1
        if response.status_code != 200:
            raise RuntimeError(f"{path} -> HTTP {response.status_code}: "
                               f"{response.text[:200]}")
        data = response.json()
        if str(data.get("meta", {}).get("code")) != "200":
            raise RuntimeError(f"{path} -> API code {data.get('meta')}")
        return data.get("result", {})

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
        from ..config import settings
        cached = self._kv_get(conn, "twogis:region_id")
        if cached:
            return cached
        result = await self._get(ctx, conn, "/2.0/region/search",
                                 {"q": settings.twogis_region}, stats)
        items = result.get("items", [])
        if not items or "id" not in items[0]:
            raise RuntimeError(f"region not found for {settings.twogis_region!r}")
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
        lat, lon = normalize_point(item.get("point"))
        lat, lon = fix_minsk_coords(lat, lon)
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
        return VenueRow(
            source_id=str(item["id"]),
            name=name[:300],
            rubric=rubric,
            address=(item.get("full_address_name") or item.get("address_name") or "").strip() or None,
            lat=lat,
            lon=lon,
            schedule=item.get("schedule") if isinstance(item.get("schedule"), dict) else None,
            rating=rating,
            review_count=review_count,
            raw=item,
        )

    async def collect(self, ctx: CollectContext) -> RunStats:
        from ..config import settings
        if not settings.twogis_api_key:
            raise RuntimeError("COLLECTOR_TWOGIS_API_KEY is not set")
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
                    log.warning("2GIS quota exhausted, stopping run")
                    break
                except Exception as exc:  # noqa: BLE001 — one rubric must not kill the run
                    stats.parse_errors += 1
                    log.warning("2GIS rubric %r failed: %s", name, exc)
        if stats.fetched == 0:
            raise RuntimeError("2GIS collect fetched nothing (key/quota?)")
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
            result = await self._get(ctx, conn, "/3.0/items", {
                "rubric_id": rubric_id,
                "region_id": region_id,
                "point": MINSK_POINT,
                "radius": MINSK_RADIUS,
                "type": "branch",
                "fields": FIELDS,
                "page": page,
                "page_size": page_size,
                "locale": "ru_RU",
            }, stats)
            items = result.get("items", [])
            if not items:
                break
            venues: list[VenueRow] = []
            for item in items:
                venue = self.parse_item(item, name)
                if venue is None:
                    stats.parse_errors += 1
                    continue
                stats.parsed += 1
                venues.append(venue)
            merged = upsert_venues(conn, venues)
            stats.new_events += merged.new_events
            stats.duplicates += merged.duplicates
            conn.commit()
            log.info("2GIS rubric %r page %d: %d items", name, page, len(items))
            total = result.get("total")
            if len(items) < page_size:
                break
            if isinstance(total, int) and page * page_size >= total:
                break
            page += 1
