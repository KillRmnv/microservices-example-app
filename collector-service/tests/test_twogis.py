import asyncio

import httpx
import pytest

from app.parsing.normalize import VenueRow
from app.errors import QuotaExhausted
from app.repositories.quota import try_consume, used
from app.sources.twogis_places import TwogisPlacesAdapter, normalize_point
from app.repositories.store import upsert_venues
from conftest import pg_url
from pathlib import Path
import json

FIXTURES = Path(__file__).parent / "fixtures"


def test_normalize_point_range_guard():
    assert normalize_point({"lat": 53.9, "lon": 27.5}) == (53.9, 27.5)
    # Impossible latitude + valid longitude: labels were swapped.
    assert normalize_point({"lat": 120.0, "lon": 27.5}) == (27.5, 120.0)
    assert normalize_point({"lat": 200.0, "lon": 300.0}) == (None, None)
    assert normalize_point(None) == (None, None)
    assert normalize_point({"lat": "nan", "lon": 1}) == (None, None)


def test_fix_coords_recovers_swapped():
    from app.sources.twogis_places import fix_coords
    assert fix_coords(53.9, 27.5) == (53.9, 27.5)
    assert fix_coords(27.5, 53.9) == (53.9, 27.5)  # swapped docs example
    assert fix_coords(None, 27.5) == (None, 27.5)


def test_parse_item_from_documented_shape():
    data = json.loads((FIXTURES / "twogis_items.json").read_text())
    venue = TwogisPlacesAdapter.parse_item(data["result"]["items"][0], "кафе")
    assert venue is not None
    assert venue.source_id == "70000001000000001"
    assert venue.name == "Тестовая кофейня"
    assert venue.rubric == "Кофейни"
    assert venue.address == "Минск, улица Тестовая, 1"
    assert (venue.latitude, venue.longitude) == (53.9056, 27.5539)
    assert venue.rating == 4.7
    assert venue.review_count == 32
    assert venue.schedule["Mon"]["working_hours"][0]["from"] == "09:00"
    assert venue.hours == {"mon": [["09:00", "22:00"]]}
    assert venue.is_24_7 is False
    # Enrichment groups are absent in this payload: values stay empty.
    assert venue.amenities is None
    assert venue.avg_check is None
    assert venue.price_level is None
    assert venue.district is None


def test_parse_item_live_sample_keeps_enrichment_null():
    """Live 2GIS sample: attribute_groups/attributes/adm_div arrive as null."""
    data = json.loads((FIXTURES / "twogis_item_enriched.json").read_text())
    venue = TwogisPlacesAdapter.parse_item(data["result"]["items"][0], "кафе")
    assert venue is not None
    assert venue.rating == 4.9 and venue.review_count == 81
    assert venue.rubric == "Кафе"  # first rubric wins over the requested name
    assert venue.address == "Минск, улица Примерная, 1"
    assert venue.hours == {"mon": [["11:00", "22:00"]],
                           "tue": [["11:00", "22:00"]],
                           "wed": [["11:00", "22:00"]],
                           "thu": [["11:00", "22:00"]],
                           "fri": [["11:00", "22:00"]],
                           "sat": [["11:00", "22:00"]],
                           "sun": [["11:00", "22:00"]]}
    assert venue.is_24_7 is False
    # Still defensively parsed, but the live API returned none of them.
    assert venue.amenities is None
    assert venue.avg_check is None
    assert venue.price_level is None
    assert venue.district is None


def test_parse_item_attribute_groups_synthetic_shape():
    """Documented-but-not-live shapes stay covered by a synthetic payload."""
    venue = TwogisPlacesAdapter.parse_item({
        "id": "70000001000000003",
        "name": "Обогащённое кафе",
        "schedule": {
            "Mon": {"working_hours": [{"from": "09:00", "to": "13:00"},
                                      {"from": "14:00", "to": "23:00"}]},
            "Tue": {"working_hours": [{"from": "09:00", "to": "23:00"}]},
        },
        "attribute_groups": [
            {"name": "Особенности", "attributes": [
                {"name": "Wi-Fi", "value": "есть"},
                {"name": "Веранда", "value": "есть"},
                {"name": "Парковка", "value": "нет"},
                {"name": "Средний чек", "value": "30–50 Br"}]},
            {"name": "Услуги", "attributes": [
                {"name": "Доставка", "value": "есть"},
                {"name": "Детская комната", "value": "есть"}]},
        ],
        "adm_div": [
            {"type": "city", "name": "Минск"},
            {"type": "district", "name": "Центральный район"},
        ],
    }, "кафе")
    assert venue is not None
    assert venue.amenities == ["wifi", "terrace", "delivery", "kids_room"]
    assert venue.avg_check == 40.0  # "30–50 Br" -> midpoint
    assert venue.price_level == "medium"
    assert venue.district == "Центральный район"
    # A lunch break survives: two windows, not one widened span.
    assert venue.hours == {"mon": [["09:00", "13:00"], ["14:00", "23:00"]],
                           "tue": [["09:00", "23:00"]]}
    assert venue.is_24_7 is False


def test_parse_item_flat_attributes_and_string_schedule():
    venue = TwogisPlacesAdapter.parse_item({
        "id": "9", "name": "Бар",
        "attributes": [{"name": "Wi-Fi", "value": "есть"},
                       {"name": "Средний чек", "value": "от 60 Br"}],
        "schedule": "Пн-Вс 10:00-02:00",
    }, "бар")
    assert venue is not None
    assert venue.amenities == ["wifi"]
    assert venue.avg_check == 60.0
    assert venue.price_level == "high"
    # An overnight bar keeps every day's window instead of losing its hours.
    assert venue.hours == {day: [["10:00", "02:00"]] for day in
                           ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    assert venue.district is None


def test_string_schedule_is_reencoded_for_storage():
    from app.parsing.schedule import normalize_schedule

    venue = TwogisPlacesAdapter.parse_item({
        "id": "10", "name": "Кинотеатр", "schedule": "Пн-Пт 09:00-23:00",
    }, "кинотеатры")
    assert venue is not None
    assert venue.hours == {day: [["09:00", "23:00"]] for day in
                           ("mon", "tue", "wed", "thu", "fri")}
    # Stored schedule round-trips through the normalizer (reindex safety).
    assert normalize_schedule(venue.schedule)[0] == venue.hours
    assert venue.schedule["Mon"]["working_hours"][0]["from"] == "09:00"

    multi = TwogisPlacesAdapter.parse_item({
        "id": "12", "name": "Бар", "schedule": "Пн-Пт 09:00-13:00, 14:00-23:00",
    }, "бары")
    assert multi is not None
    assert multi.hours["mon"] == [["09:00", "13:00"], ["14:00", "23:00"]]
    # Both the lunch break and the window count survive the 2GIS re-encoding.
    stored_hours = multi.schedule["Mon"]["working_hours"]
    assert len(stored_hours) == 2
    assert normalize_schedule(multi.schedule)[0] == multi.hours

    round_the_clock = TwogisPlacesAdapter.parse_item({
        "id": "11", "name": "Аптека", "schedule": "круглосуточно",
    }, "аптеки")
    assert round_the_clock is not None
    assert round_the_clock.is_24_7 is True
    assert normalize_schedule(round_the_clock.schedule) == (None, True)


def test_parse_item_amenity_mapping_and_price_levels():
    from app.sources.twogis_places import parse_amenities, price_level_for

    assert parse_amenities({"attribute_groups": [
        {"attributes": {"Депозит": "500 Br", "Доставка": "есть"}}]}) == [
        "deposit", "delivery"]
    assert parse_amenities({"attributes": ["Веранда"]}) == ["terrace"]
    assert parse_amenities({}) is None
    assert price_level_for(None) is None
    assert price_level_for(24.99) == "low"
    assert price_level_for(25) == "medium"
    assert price_level_for(59.99) == "medium"
    assert price_level_for(60) == "high"


def test_parse_item_avg_check_ignores_noise():
    from app.sources.twogis_places import parse_avg_check

    assert parse_avg_check({"attributes": [
        {"name": "Средний чек", "value": "Уточняйте"}]}) is None
    assert parse_avg_check({"attributes": [
        {"name": "Средний чек", "value": "30 Br"}]}) == 30.0
    assert parse_avg_check({"attributes": [
        {"name": "Средний чек", "value": "12000000000"}]}) is None


def test_parse_item_name_fallback_and_empty():
    assert TwogisPlacesAdapter.parse_item({"id": "1", "name_ex": {"primary": " Нокиа "}}, "x").name == "Нокиа"
    assert TwogisPlacesAdapter.parse_item({"id": "1"}, "x") is None
    assert TwogisPlacesAdapter.parse_item({"nope": True}, "x") is None


def test_quota_guard_stops_at_cap_minus_reserve(conn):
    from app.core import db
    with db.get_conn(pg_url()) as c:
        assert try_consume(c, "twogis", "2026-10", cap=3, reserve=1) is True
        assert try_consume(c, "twogis", "2026-10", cap=3, reserve=1) is True
        assert used(c, "twogis", "2026-10") == 2
        # 2 >= 3-1 -> stop, no consume.
        assert try_consume(c, "twogis", "2026-10", cap=3, reserve=1) is False
        assert used(c, "twogis", "2026-10") == 2
        c.commit()


def test_upsert_venues_idempotent(conn):
    venue = VenueRow(source_id="7001", name="Кофейня", rubric="Кофейни",
                     address="Минск", latitude=53.9, longitude=27.5)
    stats = upsert_venues(conn, [venue])
    assert stats.rows_inserted == 1 and stats.parsed == 1
    stats = upsert_venues(conn, [venue])
    assert stats.rows_inserted == 0
    conn.commit()
    rows = conn.execute("SELECT name, latitude FROM collected_venues").fetchall()
    assert len(rows) == 1 and float(rows[0]["latitude"]) == 53.9


def test_upsert_venues_stores_enrichment(conn):
    venue = VenueRow(
        source_id="7002", name="Кафе", rubric="Кафе",
        schedule={"Mon": {"working_hours": [{"from": "09:00", "to": "22:00"}]}},
        hours={"mon": ["09:00", "22:00"]}, is_24_7=False,
        amenities=["wifi", "terrace"], avg_check=40.0,
        price_level="medium", district="Центральный")
    upsert_venues(conn, [venue])
    conn.commit()
    row = conn.execute(
        "SELECT amenities, avg_check, price_level, district, schedule"
        " FROM collected_venues WHERE source_id = '7002'").fetchone()
    assert row["amenities"] == ["wifi", "terrace"]
    assert float(row["avg_check"]) == 40.0
    assert row["price_level"] == "medium"
    assert row["district"] == "Центральный"
    assert row["schedule"]["Mon"]["working_hours"][0]["from"] == "09:00"


def test_venue_update_resets_embedded_at_only_when_changed(conn):
    venue = VenueRow(source_id="7003", name="Кафе", rubric="Кафе")
    upsert_venues(conn, [venue])
    conn.execute("UPDATE collected_venues SET embedded_at = now()")
    conn.commit()

    upsert_venues(conn, [VenueRow(source_id="7003", name="Кафе",
                                  rubric="Кафе")])
    conn.commit()
    unchanged = conn.execute(
        "SELECT embedded_at FROM collected_venues").fetchone()
    assert unchanged["embedded_at"] is not None

    upsert_venues(conn, [VenueRow(source_id="7003", name="Новое кафе",
                                  rubric="Кафе")])
    conn.commit()
    changed = conn.execute(
        "SELECT embedded_at FROM collected_venues").fetchone()
    assert changed["embedded_at"] is None


def test_twogis_collect_two_pages_then_quota(conn):
    import json as jsonlib

    from app.clients.http import PoliteClient
    from app.sources.base import CollectContext

    items = jsonlib.loads((FIXTURES / "twogis_items.json").read_text())["result"]["items"]

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/2.0/region/search" in url:
            return httpx.Response(200, json={"meta": {"code": 200},
                                             "result": {"items": [{"id": "32"}], "total": 1}})
        if "/2.0/catalog/rubric/search" in url:
            return httpx.Response(200, json={"meta": {"code": 200},
                                             "result": {"items": [{"id": "161"}], "total": 1}})
        page = int(request.url.params.get("page", "1"))
        if page >= 3:
            return httpx.Response(200, json={"meta": {"code": 200},
                                             "result": {"items": [], "total": 2}})
        return httpx.Response(200, json={"meta": {"code": 200},
                                         "result": {"items": items, "total": 2}})

    # NOTE: the adapter reads settings lazily (`from ..config import settings`
    # inside methods), so patch the config singleton for the test.
    import app.core.config as config_module
    saved = (config_module.settings.twogis_api_key,
             config_module.settings.twogis_monthly_cap,
             config_module.settings.twogis_reserve,
             config_module.settings.twogis_page_size)
    config_module.settings.twogis_api_key = "demo"
    config_module.settings.twogis_monthly_cap = 10000
    config_module.settings.twogis_reserve = 0
    config_module.settings.twogis_page_size = 1  # full pages -> paginate
    try:
        http = PoliteClient(user_agent="test/0.1", default_min_interval_s=0,
                            transport=httpx.MockTransport(handler))
        ctx = CollectContext(http=http, db_url=pg_url(), max_urls=2)
        stats = asyncio.run(TwogisPlacesAdapter(rubrics=["кафе"]).collect(ctx))
    finally:
        (config_module.settings.twogis_api_key,
         config_module.settings.twogis_monthly_cap,
         config_module.settings.twogis_reserve,
         config_module.settings.twogis_page_size) = saved
    assert stats.parsed == 2  # 2 pages x 1 item, upserted once
    assert stats.rows_inserted == 1
    rows = conn.execute("SELECT name FROM collected_venues").fetchall()
    assert len(rows) == 1


def test_twogis_collect_stops_on_quota(conn):

    from app.clients.http import PoliteClient
    from app.sources.base import CollectContext
    import app.core.config as config_module

    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"meta": {"code": 200},
                                         "result": {"items": [], "total": 0}})

    saved = (config_module.settings.twogis_api_key,
             config_module.settings.twogis_monthly_cap,
             config_module.settings.twogis_reserve)
    config_module.settings.twogis_api_key = "demo"
    config_module.settings.twogis_monthly_cap = 1
    config_module.settings.twogis_reserve = 1  # cap-reserve = 0: first call refused
    try:
        http = PoliteClient(user_agent="test/0.1", default_min_interval_s=0,
                            transport=httpx.MockTransport(handler))
        ctx = CollectContext(http=http, db_url=pg_url())
        with pytest.raises(QuotaExhausted):
            asyncio.run(TwogisPlacesAdapter(rubrics=["кафе"]).collect(ctx))
    finally:
        (config_module.settings.twogis_api_key,
         config_module.settings.twogis_monthly_cap,
         config_module.settings.twogis_reserve) = saved
    assert calls == []  # quota refused before any HTTP request


def test_twogis_items_request_has_no_locale_by_default(conn):
    """Regression: locale=ru_RU made 2GIS return an empty items list."""
    from app.clients.http import PoliteClient
    from app.sources.base import CollectContext
    import app.core.config as config_module
    import json as jsonlib

    items = jsonlib.loads((FIXTURES / "twogis_items.json").read_text())["result"]["items"]
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        if "/2.0/region/search" in str(request.url):
            return httpx.Response(200, json={"meta": {"code": 200},
                                             "result": {"items": [{"id": "32"}]}})
        if "/2.0/catalog/rubric/search" in str(request.url):
            return httpx.Response(200, json={"meta": {"code": 200},
                                             "result": {"items": [{"id": "161"}]}})
        return httpx.Response(200, json={"meta": {"code": 200},
                                         "result": {"items": items, "total": 1}})

    saved = (config_module.settings.twogis_api_key,
             config_module.settings.twogis_monthly_cap,
             config_module.settings.twogis_reserve)
    config_module.settings.twogis_api_key = "demo"
    config_module.settings.twogis_monthly_cap = 10000
    config_module.settings.twogis_reserve = 0
    try:
        http = PoliteClient(user_agent="test/0.1", default_min_interval_s=0,
                            transport=httpx.MockTransport(handler))
        ctx = CollectContext(http=http, db_url=pg_url(), max_urls=1)
        asyncio.run(TwogisPlacesAdapter(rubrics=["кафе"]).collect(ctx))
    finally:
        (config_module.settings.twogis_api_key,
         config_module.settings.twogis_monthly_cap,
         config_module.settings.twogis_reserve) = saved
    items_params = seen[-1]
    assert "locale" not in items_params
    assert items_params["page_size"] == "10"
