from app.filters import (
    CategoryFilter,
    CityFilter,
    DateRangeFilter,
    ExcludeCategoriesFilter,
    ExcludeTagsFilter,
    FilterPipeline,
    MaxPriceFilter,
)
from app.models.search import FusedHit, PayloadDateRange


def make_hit(doc_id="e1", **payload) -> FusedHit:
    return FusedHit(id=doc_id, score=1.0, payload=payload)


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
