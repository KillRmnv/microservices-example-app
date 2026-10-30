from app.filters import (
    CategoryFilter,
    CityFilter,
    FilterPipeline,
    MaxPriceFilter,
)
from app.models.search import FusedHit


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
