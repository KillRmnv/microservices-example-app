from app.filters import (
    AgeMaxFilter,
    AmenityExcludeFilter,
    CategoryFilter,
    CityFilter,
    DateRangeFilter,
    ExcludeCategoriesFilter,
    ExcludeTagsFilter,
    ExcludeVenueCategoriesFilter,
    FilterPipeline,
    MaxPriceFilter,
    MinRatingFilter,
    PartyFilter,
    StatusFilter,
    VenueBudgetFilter,
    VenueHoursFilter,
)
from app.models.search import FusedHit, PayloadDateRange


def make_hit(doc_id="e1", **payload) -> FusedHit:
    return FusedHit(id=doc_id, score=1.0, payload=payload)


def fresh_stamp(hours: int = 1) -> str:
    """Collector timestamp inside the availability TTL."""
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def stale_stamp(hours: int = 72) -> str:
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def test_pipeline_merges_backend_filters():
    pipeline = FilterPipeline([CityFilter("Минск"), CategoryFilter("concert")])
    assert pipeline.qdrant_must() == {"city": "Минск", "category": ["concert"]}
    assert pipeline.lexical_params() == {"city": "Минск", "categories": ["concert"]}


def test_category_filter_accepts_multiple_categories():
    pipeline = FilterPipeline([CategoryFilter(["concert", "theatre"])])
    assert pipeline.matches(make_hit("e1", category="theatre"))
    assert not pipeline.matches(make_hit("e2", category="sport"))


def test_pipeline_applies_specs_in_one_pass():
    pipeline = FilterPipeline([
        CityFilter("Минск"),
        MaxPriceFilter(100, {"e1": 50, "e2": 500}),
    ])
    hits = [make_hit("e1", city="Минск"), make_hit("e2", city="Минск"),
            make_hit("e3", city="Гомель")]
    assert [hit.id for hit in pipeline.apply(hits)] == ["e1"]


def test_missing_payload_value_does_not_reject():
    pipeline = FilterPipeline([CityFilter("Минск")])
    assert pipeline.matches(make_hit("e1"))
    assert not pipeline.matches(make_hit("e2", city="Гомель"))


def test_date_range_filter_without_end_is_a_future_floor():
    from datetime import datetime, timezone

    floor = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
    spec = DateRangeFilter(floor)
    # No upper bound: only "has not finished before the floor" is pushed.
    assert spec.qdrant_must() == {
        "end_at": PayloadDateRange(gte=floor.isoformat())}
    assert spec.lexical_params() == {"date_from": floor.isoformat()}

    running = make_hit("running", start_at="2026-10-29T09:00:00+00:00",
                       end_at="2026-11-28T21:00:00+00:00")
    finished = make_hit("finished", start_at="2026-11-01T09:00:00+00:00",
                        end_at="2026-11-02T21:00:00+00:00")
    assert spec.matches(running)
    assert not spec.matches(finished)
    assert not spec.matches(make_hit("undated"))


def test_date_range_filter_with_end_keeps_the_upper_bound():
    from datetime import datetime, timezone

    start = datetime(2026, 10, 31, tzinfo=timezone.utc)
    end = datetime(2026, 11, 1, tzinfo=timezone.utc)
    spec = DateRangeFilter(start, end)
    assert spec.qdrant_must() == {
        "end_at": PayloadDateRange(gte=start.isoformat()),
        "start_at": PayloadDateRange(lt=end.isoformat()),
    }
    assert spec.lexical_params() == {"date_from": start.isoformat(),
                                     "date_to": end.isoformat()}
    assert spec.matches(make_hit("today",
                                 start_at="2026-10-31T18:00:00+00:00"))
    assert not spec.matches(make_hit("january",
                                     start_at="2027-01-24T18:00:00+00:00"))


def test_exclude_categories_pushes_must_not_to_the_backend():
    spec = ExcludeCategoriesFilter(["sport", "kids"])
    assert spec.qdrant_must_not() == {"category": ["sport", "kids"]}
    pipeline = FilterPipeline([spec])
    assert pipeline.must_not() == {"category": ["sport", "kids"]}
    # The post-filter is case-insensitive and still runs in Python.
    assert not pipeline.matches(make_hit("s", category="Sport"))
    assert pipeline.matches(make_hit("c", category="concert"))


def test_exclude_tags_post_filters_free_text():
    pipeline = FilterPipeline([ExcludeTagsFilter(["кальян"])])
    assert not pipeline.matches(
        make_hit("a", search_text="вечеринка с кальяном"))
    assert not pipeline.matches(make_hit("b", title="Кальянная вечеринка"))
    assert not pipeline.matches(make_hit("c", venue="Кальян-бар"))
    assert pipeline.matches(make_hit("d", title="Джазовый вечер"))


def test_exclude_tags_normalises_underscores():
    pipeline = FilterPipeline([ExcludeTagsFilter(["loud_music"])])
    assert not pipeline.matches(make_hit("a", description="Loud Music night"))
    assert pipeline.matches(make_hit("b", description="тихий вечер"))


def test_exclude_tags_matches_russian_inflections():
    # "кальяна" is longer than the stem, so its prefix matches "кальян"...
    assert not FilterPipeline([ExcludeTagsFilter(["кальяна"])]).matches(
        make_hit("a", search_text="кальян и напитки"))
    # ...and the short tag still matches the inflected haystack.
    assert not FilterPipeline([ExcludeTagsFilter(["кальян"])]).matches(
        make_hit("b", search_text="подача кальяна"))


def test_exclude_tags_is_post_filter_only():
    spec = ExcludeTagsFilter(["кальян"])
    assert spec.qdrant_must() == {}
    assert spec.qdrant_must_not() == {}
    assert spec.lexical_params() == {}


# --- party / status / age / rating -------------------------------------


def test_party_filter_unknown_data_passes_and_short_zones_fail():
    fresh = fresh_stamp()
    # Both unknown: never hide a hit for missing inventory data.
    assert PartyFilter(4).matches(make_hit("unknown"))
    # Payload drives the pipeline instance while `availability_at` is fresh.
    assert not PartyFilter(4).matches(
        make_hit("short", seats_left=2, availability_at=fresh))
    assert PartyFilter(4).matches(
        make_hit("roomy", seats_left=6, availability_at=fresh))
    assert PartyFilter(4).matches(
        make_hit("capacity", capacity=10, availability_at=fresh))
    assert not PartyFilter(4).matches(
        make_hit("small-room", capacity=2, availability_at=fresh))
    # 0/None means "any party": no constraint.
    assert PartyFilter(0).matches(make_hit("any", seats_left=1))
    # Explicit constructor values win over the payload (live availability).
    assert not PartyFilter(4, seats_left=2).matches(make_hit("x"))
    assert PartyFilter(4, capacity=10).matches(make_hit("y"))


def test_party_filter_stale_or_missing_availability_is_unknown():
    # Legacy points without `availability_at`: inventory is not trusted.
    assert PartyFilter(4).matches(make_hit("legacy", seats_left=1))
    # Stale fetch: the numbers may be gone, so the hit is not hidden.
    assert PartyFilter(4).matches(
        make_hit("stale", seats_left=1, availability_at=stale_stamp()))
    # A custom TTL tightens the trust window without touching the defaults.
    assert not PartyFilter(4, availability_ttl_h=100).matches(
        make_hit("old", seats_left=1, availability_at=stale_stamp(72)))
    # Explicit live values are trusted regardless of the payload stamp.
    assert not PartyFilter(4, seats_left=1).matches(
        make_hit("live", seats_left=10, availability_at=stale_stamp()))


def test_status_filter_drops_cancelled_always_and_sold_out_with_a_party():
    fresh = fresh_stamp()
    assert not StatusFilter().matches(make_hit("c", status="cancelled"))
    assert not StatusFilter(4).matches(make_hit("c", status="Cancelled"))
    assert StatusFilter().matches(make_hit("s", status="sold_out"))
    assert not StatusFilter(4).matches(
        make_hit("s", status="sold_out", availability_at=fresh))
    assert StatusFilter(4).matches(make_hit("ok", status="available"))


def test_status_filter_stale_sold_out_is_not_hidden():
    # Stale or absent stamps: `sold_out` may no longer hold, do not hide.
    assert StatusFilter(4).matches(make_hit("stale", status="sold_out",
                                            availability_at=stale_stamp()))
    assert StatusFilter(4).matches(make_hit("legacy", status="sold_out"))
    # Cancellation is editorial, not scraped inventory: always dropped.
    assert not StatusFilter(4).matches(make_hit(
        "cancelled", status="cancelled", availability_at=stale_stamp()))


def test_age_max_filter_drops_adult_only_hits():
    spec = AgeMaxFilter(12)
    assert spec.matches(make_hit("kids", age_limit=6))
    assert spec.matches(make_hit("teen", age_limit=12))
    assert not spec.matches(make_hit("adult", age_limit=16))
    assert spec.matches(make_hit("unknown"))  # missing data passes
    assert AgeMaxFilter(None).matches(make_hit("any", age_limit=18))


def test_min_rating_filter_uses_the_right_payload_key():
    venues = MinRatingFilter(4.0, key="rating")
    assert venues.matches(make_hit("good", rating=4.5))
    assert not venues.matches(make_hit("meh", rating=3.2))
    assert venues.matches(make_hit("unrated"))
    events = MinRatingFilter(4.0, key="venue_rating")
    assert events.matches(make_hit("e", venue_rating=4.8))
    assert not events.matches(make_hit("e2", venue_rating=3.0))
    # The event key is `venue_rating`: a bare `rating` field is unknown there
    # and unknown ratings pass.
    assert events.matches(make_hit("e3", rating=3.0))


# --- venue hours / budget / categories ---------------------------------


def _day_key(moment):
    return ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[moment.weekday()]


def test_venue_hours_filter_needs_overlap_with_the_requested_window():
    from datetime import datetime, timezone

    start = datetime(2026, 11, 25, 18, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 25, 23, 59, tzinfo=timezone.utc)
    key = _day_key(start)
    spec = VenueHoursFilter(start, end, "UTC")
    assert spec.matches(make_hit("open", hours={key: ["11:00", "23:00"]}))
    assert not spec.matches(make_hit("early", hours={key: ["11:00", "17:00"]}))
    # Unknown / missing hours are not a closed venue.
    assert spec.matches(make_hit("unknown"))
    assert spec.matches(make_hit("always", is_24_7=True))
    assert spec.matches(make_hit("whole-day", hours={key: "24 hours"}))


def test_venue_hours_filter_handles_overnight_closes():
    from datetime import datetime, timezone

    start = datetime(2026, 11, 25, 23, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 25, 23, 30, tzinfo=timezone.utc)
    key = _day_key(start)
    spec = VenueHoursFilter(start, end, "UTC")
    assert spec.matches(make_hit("night", hours={key: ["20:00", "02:00"]}))


def test_venue_budget_filter_uses_avg_check_then_price_level():
    levels = {"low": 25, "medium": 60, "high": 150}
    spec = VenueBudgetFilter(70, levels)
    assert spec.matches(make_hit("avg", avg_check=50))
    assert not spec.matches(make_hit("pricey", avg_check=90))
    assert spec.matches(make_hit("medium", price_level="medium"))
    assert not spec.matches(make_hit("high", price_level="high"))
    assert spec.matches(make_hit("unknown"))
    # avg_check wins over the coarse level when both are present.
    assert not VenueBudgetFilter(40, levels).matches(
        make_hit("mixed", avg_check=90, price_level="low"))


def test_exclude_venue_categories_maps_event_categories_to_rubrics():
    from app.filters import ExcludeVenueCategoriesFilter

    spec = ExcludeVenueCategoriesFilter(["theatre", "film", "sport"])
    assert not spec.matches(make_hit("t", rubric="Театры"))
    assert not spec.matches(make_hit("t2", rubric="театр"))
    assert not spec.matches(make_hit("f", rubric="Кинотеатры"))
    assert spec.matches(make_hit("c", rubric="Кафе"))
    assert spec.matches(make_hit("unknown-rubric"))
    # "sport" has no venue rubric mapping and is ignored.
    assert ExcludeVenueCategoriesFilter(["sport"]).matches(
        make_hit("x", rubric="Фитнес-клубы"))


def test_venue_hours_filter_handles_a_lunch_break():
    from datetime import datetime, timedelta, timezone

    start = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 25, 13, 0, tzinfo=timezone.utc)
    key = _day_key(start)
    hours = {key: [["09:00", "13:00"], ["14:00", "23:00"]]}
    assert VenueHoursFilter(start, end, "UTC").matches(
        make_hit("lunch-open", hours=hours))
    # 13:30-14:00 falls into the break between the two pairs.
    gap_start = datetime(2026, 11, 25, 13, 30, tzinfo=timezone.utc)
    assert not VenueHoursFilter(gap_start, gap_start + timedelta(minutes=30),
                                "UTC").matches(make_hit("lunch-gap", hours=hours))


def test_venue_hours_filter_handles_a_nested_overnight_close():
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 11, 23, 23, 0, tzinfo=timezone.utc)
    key = _day_key(base)
    next_key = _day_key(base + timedelta(days=1))
    # The collector emits every day; 18:00-02:00 runs into the next day.
    hours = {key: [["18:00", "02:00"]], next_key: [["18:00", "02:00"]]}
    assert VenueHoursFilter(base, base + timedelta(minutes=30), "UTC").matches(
        make_hit("late", hours=hours))
    # 01:00 next day is covered by the previous day's overnight interval.
    small_hours = datetime(2026, 11, 24, 1, 0, tzinfo=timezone.utc)
    assert VenueHoursFilter(small_hours,
                            small_hours + timedelta(minutes=30),
                            "UTC").matches(make_hit("spillover", hours=hours))
    # 03:00 next day is after the close.
    closed = datetime(2026, 11, 24, 3, 0, tzinfo=timezone.utc)
    assert not VenueHoursFilter(closed, closed + timedelta(minutes=30),
                                "UTC").matches(make_hit("closed", hours=hours))


def test_venue_hours_filter_treats_unknown_schedules_as_open():
    from datetime import datetime, timedelta, timezone

    start = datetime(2026, 11, 25, 18, 0, tzinfo=timezone.utc)
    spec = VenueHoursFilter(start, start + timedelta(hours=1), "UTC")
    key = _day_key(start)
    other_key = next(day for day in ("mon", "tue", "wed", "thu", "fri", "sat",
                                     "sun") if day != key)
    # None/[] per day is "unknown", never "closed".
    assert spec.matches(make_hit("none", hours={key: None}))
    assert spec.matches(make_hit("empty", hours={key: []}))
    assert spec.matches(make_hit("missing-day", hours={other_key: [
        ["10:00", "23:00"]]}))
    assert spec.matches(make_hit("no-hours", hours={}))
    assert spec.matches(make_hit("no-payload"))


def test_day_intervals_accepts_nested_pairs_and_the_legacy_flat_pair():
    from datetime import time

    from app.filters.specs import day_intervals

    assert day_intervals([["09:00", "13:00"], ["14:00", "23:00"]]) == [
        (time(9, 0), time(13, 0)), (time(14, 0), time(23, 0))]
    assert day_intervals([["18:00", "02:00"]]) == [(time(18, 0), time(2, 0))]
    # Legacy flat pair: one interval, unchanged behaviour.
    assert day_intervals(["09:00", "22:00"]) == [(time(9, 0), time(22, 0))]
    assert day_intervals([]) == []


def test_exclude_tags_reads_venue_amenities():
    assert not FilterPipeline([ExcludeTagsFilter(["terrace"])]).matches(
        make_hit("v", amenities=["terrace", "wifi"]))
    assert not FilterPipeline([ExcludeTagsFilter(["веранда"])]).matches(
        make_hit("v2", amenities=["веранда"]))
    assert FilterPipeline([ExcludeTagsFilter(["terrace"])]).matches(
        make_hit("v3", amenities=["wifi"]))


def test_amenity_exclude_prefers_structured_amenities():
    spec = AmenityExcludeFilter(["terrace"])
    assert not spec.matches(make_hit("v", amenities=["terrace", "wifi"]))
    # Structured amenities exist and no terrace among them: text is ignored,
    # so a description that mentions a terrace is not a false positive.
    assert spec.matches(make_hit("v2", amenities=["wifi"],
                                 description="уютная терраса",
                                 search_text="кафе терраса"))
    # Underscores/dashes normalise the same way as the tag filter.
    assert not AmenityExcludeFilter(["long_tables"]).matches(
        make_hit("lt", amenities=["long-tables"]))
    assert AmenityExcludeFilter([]).matches(make_hit("any",
                                                     amenities=["terrace"]))


def test_amenity_exclude_falls_back_to_text_without_amenities():
    """Live 2GIS has no attribute groups, so `amenities` is empty."""
    spec = AmenityExcludeFilter(["terrace", "веранда", "терраса"])
    assert not spec.matches(make_hit("missing", name="Летняя веранда"))
    assert not spec.matches(make_hit("empty", amenities=[],
                                     description="столики на террасе"))
    assert not spec.matches(make_hit("search-text", search_text="кафе веранда"))
    assert spec.matches(make_hit("indoor", amenities=[], description="зал внутри"))
    assert spec.matches(make_hit("nothing"))


def test_date_range_filter_allow_undated_keeps_the_future_floor():
    from datetime import datetime, timezone

    floor = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
    spec = DateRangeFilter(floor, allow_undated=True)
    # Undated points cannot satisfy a pushed range; Python decides.
    assert spec.qdrant_must() == {}
    assert spec.lexical_params() == {}

    future = make_hit("future", start_at="2026-12-05T19:00:00+00:00")
    past = make_hit("past", start_at="2026-11-01T19:00:00+00:00")
    assert spec.matches(future)
    assert spec.matches(make_hit("undated"))
    assert not spec.matches(past)

    strict = DateRangeFilter(floor)
    assert not strict.matches(make_hit("undated"))
    assert not strict.matches(past)
