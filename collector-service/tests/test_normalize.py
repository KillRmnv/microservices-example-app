from datetime import datetime, timezone

from app.normalize import (
    RawEvent,
    is_minsk,
    normalize_jsonld,
    parse_age,
    parse_datetime,
    parse_price,
)
from app.parse import extract_json_ld_events
from app.store import fullness, merge_decision
from pathlib import Path

NOW = datetime(2026, 10, 23, tzinfo=timezone.utc)


def test_parse_datetime_naive_is_minsk():
    parsed = parse_datetime("2026-11-01T19:00:00")
    assert parsed is not None
    assert parsed.utcoffset().total_seconds() == 0
    assert parsed.hour == 16  # 19:00+03 -> 16:00Z


def test_parse_datetime_with_offset():
    assert parse_datetime("2026-11-01T19:00:00+0300").hour == 16
    assert parse_datetime("not-a-date") is None
    assert parse_datetime(None) is None


def test_parse_price_variants():
    assert parse_price("от 45 руб.") == (45.0, 45.0)
    assert parse_price("45 - 120 руб.") == (45.0, 120.0)
    assert parse_price("Уточняйте") == (None, None)
    assert parse_price("") == (None, None)
    assert parse_price(None) == (None, None)


def test_parse_age():
    assert parse_age("12+") == 12
    assert parse_age("Рок") is None


def test_is_minsk():
    assert is_minsk({"address": {"addressLocality": "Минск"}})
    assert not is_minsk({"address": {"addressLocality": "Брест"}})


def test_ticketpro_normalize_and_city_filter():
    from app.parse import extract_json_ld_events
    html = (Path(__file__).parent / "fixtures" / "ticketpro_listing.html").read_text()
    cards = extract_json_ld_events(html)
    minsk = normalize_jsonld("ticketpro", "id1", "http://x/1", "concert", cards[0], NOW)
    assert minsk is not None
    assert minsk.title == "Тестовый концерт"
    assert (minsk.price_min, minsk.price_max) == (45.0, 120.0)
    assert minsk.venue_name == "Дворец Республики"
    assert minsk.title and minsk.dedup_key
    brest = normalize_jsonld("ticketpro", "id2", "http://x/2", "concert", cards[1], NOW)
    assert brest is None  # non-Minsk filtered out


def test_relax_stale_start_but_future_end_kept():
    html = (Path(__file__).parent / "fixtures" / "relax_card.html").read_text()
    cards = extract_json_ld_events(html)
    event = normalize_jsonld("relax", "u1", "http://x/u1", "theatre", cards[0], NOW)
    assert event is not None
    assert event.start_at is not None and event.start_at.year == 2012
    assert (event.price_min, event.price_max) == (None, None)


def test_past_end_date_dropped():
    event = normalize_jsonld("relax", "u9", "http://x/u9", "theatre",
                             {"name": "Старое", "endDate": "2020-01-01",
                              "location": {"address": {"addressLocality": "Минск"}}}, NOW)
    assert event is None


def test_merge_decision_fullness_then_priority():
    assert merge_decision("relax", 2, "ticketpro", 5) is True
    assert merge_decision("ticketpro", 5, "relax", 2) is False
    assert merge_decision("relax", 3, "ticketpro", 3) is True  # tie -> priority
    assert merge_decision("ticketpro", 3, "relax", 3) is False


def test_fullness_counts():
    assert fullness(RawEvent(source="s", source_id="i", source_url="u", title="t")) == 0
    assert fullness(RawEvent(source="s", source_id="i", source_url="u", title="t",
                             description="d", price_min=10.0)) == 2
