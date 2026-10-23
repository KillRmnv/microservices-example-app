import asyncio

import httpx
import pytest

from app.normalize import VenueRow
from app.quota import QuotaExhausted, try_consume, used
from app.sources.twogis_places import TwogisPlacesAdapter, normalize_point
from app.store import upsert_venues
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


def test_fix_minsk_coords_recovers_swapped():
    from app.sources.twogis_places import fix_minsk_coords
    assert fix_minsk_coords(53.9, 27.5) == (53.9, 27.5)
    assert fix_minsk_coords(27.5, 53.9) == (53.9, 27.5)  # swapped docs example
    assert fix_minsk_coords(None, 27.5) == (None, 27.5)


def test_parse_item_from_documented_shape():
    data = json.loads((FIXTURES / "twogis_items.json").read_text())
    venue = TwogisPlacesAdapter.parse_item(data["result"]["items"][0], "кафе")
    assert venue is not None
    assert venue.source_id == "70000001000000001"
    assert venue.name == "Тестовая кофейня"
    assert venue.rubric == "Кофейни"
    assert venue.address == "Минск, улица Тестовая, 1"
    assert (venue.lat, venue.lon) == (53.9056, 27.5539)
    assert venue.rating == 4.7
    assert venue.review_count == 32
    assert venue.schedule["Mon"]["working_hours"][0]["from"] == "09:00"


def test_parse_item_name_fallback_and_empty():
    assert TwogisPlacesAdapter.parse_item({"id": "1", "name_ex": {"primary": " Нокиа "}}, "x").name == "Нокиа"
    assert TwogisPlacesAdapter.parse_item({"id": "1"}, "x") is None
    assert TwogisPlacesAdapter.parse_item({"nope": True}, "x") is None


def test_quota_guard_stops_at_cap_minus_reserve(conn):
    from app import db
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
                     address="Минск", lat=53.9, lon=27.5)
    stats = upsert_venues(conn, [venue])
    assert stats.new_events == 1 and stats.parsed == 1
    stats = upsert_venues(conn, [venue])
    assert stats.new_events == 0
    conn.commit()
    rows = conn.execute("SELECT name, lat FROM collected_venues").fetchall()
    assert len(rows) == 1 and float(rows[0]["lat"]) == 53.9


def test_twogis_collect_two_pages_then_quota(conn):
    import json as jsonlib

    from app.http import PoliteClient
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
    import app.config as config_module
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
    assert stats.new_events == 1
    rows = conn.execute("SELECT name FROM collected_venues").fetchall()
    assert len(rows) == 1


def test_twogis_collect_stops_on_quota(conn):

    from app.http import PoliteClient
    from app.sources.base import CollectContext
    import app.config as config_module

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
