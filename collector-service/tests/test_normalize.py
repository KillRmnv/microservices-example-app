from datetime import datetime, timezone

from app.parsing.normalize import (
    RawEvent,
    is_target_city,
    normalize_jsonld,
    normalize_next_event,
    parse_age,
    parse_datetime,
    parse_price,
)
from app.parsing.html import extract_json_ld_events
from app.repositories.store import fullness, merge_decision
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
    # Years/phones glued into one huge number are noise, not a price.
    assert parse_price("12000000000") == (None, None)
    assert parse_price("45 - 12000000000") == (45.0, 45.0)


def test_parse_age():
    assert parse_age("12+") == 12
    assert parse_age("Рок") is None
    assert parse_age("99+") is None


def test_is_target_city():
    assert is_target_city({"address": {"addressLocality": "Минск"}})
    assert not is_target_city({"address": {"addressLocality": "Брест"}})


def test_ticketpro_normalize_and_city_filter():
    from app.parsing.html import extract_json_ld_events
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


def test_ticketpro_next_event_builds_encoded_cover_url():
    event = normalize_next_event(
        "ticketpro", "49667", "https://ticketpro.by/x", "sport",
        {
            "title": "Динамо-Минск",
            "startTime": "2026-12-02T19:00:00",
            "venue": {"city": {"name": "Минск"}, "title": "Минск-Арена"},
            "coverS3Key": "event/620х900 (10)_image_1.png",
        },
        NOW,
    )
    assert event is not None
    assert event.image_url == (
        "https://cdn.ticketpro.by/event/620%D1%85900%20%2810%29_image_1.png")


def test_jsonld_image_object_and_relative_url():
    event = normalize_jsonld(
        "ticketpro", "id9", "https://ticketpro.by/event/x", "concert",
        {
            "name": "Концерт",
            "url": "https://ticketpro.by/event/x",
            "location": {"address": {"addressLocality": "Минск"}},
            "image": {"@type": "ImageObject", "url": "/media/poster.png"},
        },
        NOW,
    )
    assert event is not None
    assert event.image_url == "https://ticketpro.by/media/poster.png"


def _jsonld(**overrides):
    data = {
        "name": "Концерт",
        "startDate": "2026-12-01T19:00:00+03:00",
        "location": {"address": {"addressLocality": "Минск"}},
        "offers": {"price": "45-90", "priceCurrency": "BYN"},
    }
    data.update(overrides)
    return normalize_jsonld("ticketpro", "id", "http://x/1", "concert",
                            data, NOW)


def test_parse_availability_tokens():
    from app.parsing.normalize import parse_availability

    assert parse_availability("https://schema.org/InStock") == "in_stock"
    assert parse_availability("InStock") == "in_stock"
    assert parse_availability("LimitedAvailability") == "limited"
    assert parse_availability("https://schema.org/SoldOut") == "sold_out"
    assert parse_availability("OutOfStock") == "sold_out"
    assert parse_availability("PreOrder") == "unknown"
    assert parse_availability("SomethingNew") == "unknown"
    assert parse_availability(None) is None
    assert parse_availability("") is None


def test_parse_capacity_bounds():
    from app.parsing.normalize import parse_capacity

    assert parse_capacity("500") == 500
    assert parse_capacity("12.7") == 12
    assert parse_capacity(0) == 0
    assert parse_capacity(-1) is None
    assert parse_capacity(10_000_001) is None
    assert parse_capacity("abc") is None
    assert parse_capacity(True) is None
    assert parse_capacity(None) is None


def test_sold_out_offer_sets_status_and_capacity():
    event = _jsonld(
        offers={"price": "45", "availability": "https://schema.org/SoldOut"},
        maximumAttendeeCapacity=500,
        remainingAttendeeCapacity=0,
    )
    assert event is not None
    assert event.availability == "sold_out"
    assert event.status == "sold_out"
    assert (event.capacity, event.seats_left) == (500, 0)


def test_cancelled_and_postponed_event_status():
    cancelled = _jsonld(eventStatus="https://schema.org/EventCancelled")
    assert cancelled is not None and cancelled.status == "cancelled"
    assert cancelled.availability is None
    postponed = _jsonld(eventStatus="https://schema.org/EventPostponed")
    assert postponed is not None and postponed.status == "scheduled"


def test_inconsistent_capacity_keeps_capacity_only():
    event = _jsonld(maximumAttendeeCapacity=100,
                    remainingAttendeeCapacity=500)
    assert event is not None
    assert event.capacity == 100
    assert event.seats_left is None


def test_absent_availability_fields_keep_defaults():
    event = _jsonld()
    assert event is not None
    assert event.availability is None
    assert event.capacity is None
    assert event.seats_left is None
    assert event.status == "scheduled"


def test_in_stock_offer_stays_scheduled():
    event = _jsonld(offers={"price": "45",
                            "availability": "https://schema.org/InStock"})
    assert event is not None
    assert event.availability == "in_stock"
    assert event.status == "scheduled"
