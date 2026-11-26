import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.clients.collector import CollectorClient
from app.clients.vector import InMemoryStore, QdrantStore
from app.models.search import FusedHit, SearchPlan
from app.services.fusion import fuse_search, rrf_fuse
from app.services.search_service import HYBRID_ORIGIN, SearchService
from app.sparse import encode_sparse


def test_rrf_prefers_top_ranks():
    fused = dict(rrf_fuse([["a", "b", "c"], ["a", "b"]]))
    assert fused["a"] > fused["b"] > fused["c"]


def test_rrf_single_list_order_kept():
    assert [doc for doc, _ in rrf_fuse([["x", "y"]])] == ["x", "y"]


def test_fuse_search_origins():
    """Python fusion is the lexical-fallback path, kept for resilience."""
    hits = fuse_search([("a", {"title": "A"}), ("b", {"title": "B"})], ["b", "c"],
                       limit=3)
    by_id = {hit.id: hit for hit in hits}
    assert by_id["b"].origins == ["dense", "lexical"]
    assert by_id["a"].origins == ["dense"]
    assert by_id["c"].origins == ["lexical"]
    assert by_id["c"].payload == {}


class FakeEmbedder:
    dim = 3

    async def embed(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]


class BrokenEmbedder:
    dim = 3

    async def embed(self, texts):
        raise RuntimeError("llama down")


class FakeCollector(CollectorClient):
    def __init__(self, rows):
        self._rows = rows

    async def search_lexical(self, query, city, category, limit,
                             *, date_from=None, date_to=None):
        return self._rows[:limit]

    async def search_venues_lexical(self, query, city, rubric, limit):
        return self._rows[:limit]


class ExplodingCollector(FakeCollector):
    """Hybrid success must never touch the collector."""

    def __init__(self):
        super().__init__([])

    async def search_lexical(self, query, city, category, limit,
                             *, date_from=None, date_to=None):
        raise AssertionError("collector must not be called on hybrid hit")

    async def search_venues_lexical(self, query, city, rubric, limit):
        raise AssertionError("collector must not be called on hybrid hit")


def hybrid_store(*items):
    """items: (id, dense_vector, payload, sparse_text)."""
    return InMemoryStore(
        [(doc_id, vector, payload) for doc_id, vector, payload, _ in items],
        {doc_id: encode_sparse(text) for doc_id, _, _, text in items},
    )


def service(store, collector=None, embedder=None, *,
            hybrid_mode: str = "sparse") -> SearchService:
    return SearchService(embedder or FakeEmbedder(), store,
                         collector or FakeCollector([]),
                         hybrid_mode=hybrid_mode)


@pytest.mark.asyncio
async def test_hybrid_search_single_qdrant_call():
    store = hybrid_store(
        ("e1", [1.0, 0.0, 0.0], {"title": "Джазовый вечер"}, "джазовый вечер"),
        ("e2", [0.0, 1.0, 0.0], {"title": "Рок концерт"}, "рок концерт"),
    )
    hits = await service(store, ExplodingCollector()).events(
        SearchPlan(vector_query="джаз", limit=2))
    assert {hit.id for hit in hits} == {"e1", "e2"}
    assert all(hit.origins == [HYBRID_ORIGIN] for hit in hits)
    # Dense points at e1 (identical vector), sparse has no overlap either;
    # dense ranking decides.
    assert hits[0].id == "e1"


@pytest.mark.asyncio
async def test_hybrid_sparse_finds_token_match():
    store = hybrid_store(
        ("e1", [0.0, 1.0, 0.0], {"title": "Джазовый вечер"}, "джазовый вечер"),
        ("e2", [0.0, 1.0, 0.0], {"title": "Рок концерт"}, "рок концерт"),
    )
    hits = await service(store, ExplodingCollector()).events(
        SearchPlan(vector_query="джазовый", limit=2))
    assert hits[0].id == "e1"  # dense ties, sparse breaks it


@pytest.mark.asyncio
async def test_hybrid_survives_dense_outage_via_sparse():
    store = hybrid_store(
        ("e1", [0.0, 1.0, 0.0], {"title": "Джазовый вечер"}, "джазовый вечер"),
    )
    hits = await service(store, ExplodingCollector(),
                         embedder=BrokenEmbedder()).events(
        SearchPlan(vector_query="джазовый", limit=2))
    assert [hit.id for hit in hits] == ["e1"]
    assert hits[0].origins == [HYBRID_ORIGIN]


@pytest.mark.asyncio
async def test_hybrid_falls_back_to_lexical():
    class BrokenStore(InMemoryStore):
        async def hybrid_search(self, dense, sparse, limit, must=None,
                                must_not=None, text_query=None, weights=None):
            raise RuntimeError("qdrant down")

    collector = FakeCollector([{"id": "e9", "title": "Только лексика"}])
    hits = await service(BrokenStore(), collector).events(
        SearchPlan(vector_query="x", limit=3))
    assert [hit.id for hit in hits] == ["e9"]
    assert hits[0].origins == ["lexical"]


@pytest.mark.asyncio
async def test_multi_category_filter_uses_all_categories():
    store = hybrid_store(
        ("c", [1.0, 0.0, 0.0], {"title": "Концерт", "category": "concert"},
         "концерт"),
        ("t", [1.0, 0.0, 0.0], {"title": "Спектакль", "category": "theatre"},
         "спектакль"),
        ("s", [1.0, 0.0, 0.0], {"title": "Матч", "category": "sport"}, "матч"),
    )
    hits = await service(store, ExplodingCollector()).events(
        SearchPlan(vector_query="события", limit=5,
                   categories=["concert", "theatre"]))
    assert {hit.id for hit in hits} == {"c", "t"}


@pytest.mark.asyncio
async def test_price_filter_reads_qdrant_payload():
    store = hybrid_store(
        ("cheap", [1.0, 0.0, 0.0],
         {"title": "Дешево", "price_min": 20.0}, "дешево концерт"),
        ("pricey", [1.0, 0.0, 0.0],
         {"title": "Дорого", "price_min": 500.0}, "дорого концерт"),
    )
    hits = await service(store, ExplodingCollector()).events(
        SearchPlan(vector_query="концерт", limit=5, max_price_per_person=100.0))
    assert [hit.id for hit in hits] == ["cheap"]


@pytest.mark.asyncio
async def test_budget_overfetches_before_price_postfilter():
    """A cheap hit ranked below the top window must still be reachable."""
    store = hybrid_store(
        *[(f"p{i}", [1.0, 0.0, 0.0],
           {"title": f"Дорого {i}", "price_min": 500.0}, "")
          for i in range(5)],
        ("cheap", [0.0, 1.0, 0.0],
         {"title": "Дешево", "price_min": 20.0}, ""),
    )
    hits = await service(store, ExplodingCollector()).events(
        SearchPlan(vector_query="концерт", limit=2, max_price_per_person=100.0))
    assert [hit.id for hit in hits] == ["cheap"]


@pytest.mark.asyncio
async def test_unknown_price_passes_price_filter():
    store = hybrid_store(
        ("mystery", [1.0, 0.0, 0.0], {"title": "Без цены"}, "без цены"),
    )
    hits = await service(store, ExplodingCollector()).events(
        SearchPlan(vector_query="цены", limit=5, max_price_per_person=100.0))
    assert [hit.id for hit in hits] == ["mystery"]


@pytest.mark.asyncio
async def test_exclude_categories_filter():
    store = hybrid_store(
        ("a", [1.0, 0.0, 0.0],
         {"title": "Концерт", "category": "concert"}, "концерт"),
        ("b", [1.0, 0.0, 0.0],
         {"title": "Спорт", "category": "sport"}, "спорт"),
    )
    hits = await service(store, ExplodingCollector()).events(
        SearchPlan(vector_query="шоу", limit=5, exclude_categories=["sport"]))
    assert [hit.id for hit in hits] == ["a"]


@pytest.mark.asyncio
async def test_exclude_tags_drops_hits_by_search_text():
    store = hybrid_store(
        ("hookah", [1.0, 0.0, 0.0],
         {"title": "Вечеринка", "search_text": "вечеринка кальян музыка"},
         "вечеринка"),
        ("jazz", [1.0, 0.0, 0.0],
         {"title": "Джазовый вечер", "search_text": "джазовый вечер"},
         "джазовый вечер"),
    )
    hits = await service(store, ExplodingCollector()).events(
        SearchPlan(vector_query="вечер", limit=5, exclude_tags=["кальян"]))
    assert [hit.id for hit in hits] == ["jazz"]


class RecordingStore(InMemoryStore):
    """Captures the backend call; returns nothing so the fallback runs."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[dict] = []

    async def hybrid_search(self, dense, sparse, limit, must=None,
                            must_not=None, text_query=None, weights=None):
        self.calls.append({"limit": limit, "must": must,
                           "must_not": must_not, "text_query": text_query,
                           "weights": weights, "dense": dense,
                           "sparse": sparse})
        return []


@pytest.mark.asyncio
async def test_must_not_and_overfetch_reach_the_store():
    store = RecordingStore()
    collector = FakeCollector([{"id": "e9", "title": "Только лексика"}])
    hits = await service(store, collector).events(
        SearchPlan(vector_query="шоу", limit=4, exclude_categories=["sport"],
                   exclude_tags=["кальян"]))
    call = store.calls[0]
    assert call["must_not"] == {"category": ["sport"]}
    # Negative filters widen the window so post-filtering cannot starve it.
    assert call["limit"] == 12
    # The lexical fallback still applies the Python post-filters.
    assert [hit.id for hit in hits] == ["e9"]


@pytest.mark.asyncio
async def test_no_negative_filters_keeps_the_normal_window():
    store = RecordingStore()
    await service(store, FakeCollector([])).events(
        SearchPlan(vector_query="шоу", limit=4))
    call = store.calls[0]
    assert call["must_not"] is None
    assert call["limit"] == 8


@pytest.mark.asyncio
async def test_city_filter_pushed_to_qdrant():
    store = hybrid_store(
        ("here", [1.0, 0.0, 0.0],
         {"title": "Дома", "city": "Минск"}, "дома"),
        ("away", [1.0, 0.0, 0.0],
         {"title": "В гостях", "city": "Брест"}, "гостях"),
    )
    hits = await service(store, ExplodingCollector()).events(
        SearchPlan(vector_query="дома", limit=5, city="Минск"))
    assert [hit.id for hit in hits] == ["here"]


@pytest.mark.asyncio
async def test_date_filter_drops_other_days_and_undated_events():
    from datetime import datetime, timezone

    store = hybrid_store(
        ("today", [1.0, 0.0, 0.0],
         {"title": "Сегодня", "start_at": "2026-10-31T18:00:00+00:00"},
         "сегодня концерт"),
        ("january", [1.0, 0.0, 0.0],
         {"title": "Январь", "start_at": "2027-01-24T18:00:00+00:00"},
         "январь концерт"),
        ("undated", [1.0, 0.0, 0.0], {"title": "Без даты"},
         "без даты концерт"),
    )
    hits = await service(store, ExplodingCollector()).events(SearchPlan(
        vector_query="концерт", limit=5,
        date_from=datetime(2026, 10, 31, tzinfo=timezone.utc),
        date_to=datetime(2026, 11, 1, tzinfo=timezone.utc)))
    assert [hit.id for hit in hits] == ["today"]


@pytest.mark.asyncio
async def test_date_filter_keeps_multiday_event_overlapping_the_day():
    from datetime import datetime, timezone

    store = hybrid_store(
        ("dolphinarium", [1.0, 0.0, 0.0],
         {"title": "Дельфинарий",
          "start_at": "2026-10-29T09:00:00+00:00",
          "end_at": "2026-11-28T21:00:00+00:00"},
         "дельфинарий животные"),
        ("past", [1.0, 0.0, 0.0],
         {"title": "Прошлое",
          "start_at": "2026-10-01T09:00:00+00:00",
          "end_at": "2026-10-02T21:00:00+00:00"},
         "прошлое животные"),
    )
    hits = await service(store, ExplodingCollector()).events(SearchPlan(
        vector_query="животные", limit=5,
        date_from=datetime(2026, 11, 4, tzinfo=timezone.utc),
        date_to=datetime(2026, 11, 5, tzinfo=timezone.utc)))
    assert [hit.id for hit in hits] == ["dolphinarium"]


@pytest.mark.asyncio
async def test_collector_client_uses_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/events/search"
        assert request.url.params["q"] == "джаз"
        assert request.url.params["date_from"] == "2026-10-31T00:00:00+03:00"
        assert request.url.params["date_to"] == "2026-11-01T00:00:00+03:00"
        return httpx.Response(200, json={"events": [{"id": "e1", "title": "Джаз"}]})

    client = CollectorClient("http://collector:8080",
                             transport=httpx.MockTransport(handler))
    rows = await client.search_lexical(
        "джаз", None, None, 5,
        date_from="2026-10-31T00:00:00+03:00",
        date_to="2026-11-01T00:00:00+03:00")
    assert rows == [{"id": "e1", "title": "Джаз"}]


@pytest.mark.asyncio
async def test_collector_outage_raises_domain_error():
    from app.errors import UpstreamError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    client = CollectorClient("http://collector:8080",
                             transport=httpx.MockTransport(handler))
    with pytest.raises(UpstreamError):
        await client.search_lexical("x", None, None, 5)


@pytest.mark.asyncio
async def test_hybrid_search_venues():
    store = hybrid_store(
        ("v1", [1.0, 0.0, 0.0],
         {"name": "Кофейня", "rubric": "Кофейни"}, "кофейня"),
        ("v2", [0.0, 1.0, 0.0],
         {"name": "Театр", "rubric": "Театры"}, "театр"),
    )
    hits = await service(store, ExplodingCollector()).venues(
        SearchPlan(vector_query="кофейня", limit=2))
    assert hits[0].id == "v1"
    assert all(hit.origins == [HYBRID_ORIGIN] for hit in hits)


@pytest.mark.asyncio
async def test_venue_rubric_miss_retries_without_the_rubric():
    """Live 2GIS has no "Бары" rubric; the text match must still answer."""
    store = hybrid_store(
        ("v1", [1.0, 0.0, 0.0],
         {"name": "Бар «Культура»", "search_text": "бар коктейли",
          "rubric": "Кафе", "city": "Минск"}, "бар коктейли"),
    )
    hits = await service(store, FakeCollector([])).venues(
        SearchPlan(vector_query="бар", city="Минск", rubric="Бары", limit=3))
    assert [hit.id for hit in hits] == ["v1"]


@pytest.mark.asyncio
async def test_venue_rubric_none_does_not_retry():
    store = hybrid_store(
        ("v1", [1.0, 0.0, 0.0],
         {"name": "Бар «Культура»", "rubric": "Кафе", "city": "Минск"},
         "бар коктейли"),
    )
    hits = await service(store, FakeCollector([])).venues(
        SearchPlan(vector_query="бар", city="Минск", limit=3))
    assert [hit.id for hit in hits] == ["v1"]


class SlowEmbedder:
    dim = 3

    async def embed(self, texts):
        await asyncio.sleep(5)
        return [[1.0, 0.0, 0.0] for _ in texts]


@pytest.mark.asyncio
async def test_slow_embedder_does_not_stall_query():
    store = hybrid_store(
        ("e1", [0.0, 1.0, 0.0], {"title": "Джазовый вечер"}, "джазовый вечер"),
    )
    svc = SearchService(SlowEmbedder(), store, ExplodingCollector(),
                        query_timeout_s=0.01)
    hits = await svc.events(SearchPlan(vector_query="джазовый", limit=2))
    # Sparse alone still answers; the query never waits on the model server.
    assert [hit.id for hit in hits] == ["e1"]


@pytest.mark.asyncio
async def test_empty_vector_index_falls_back_to_lexical():
    collector = FakeCollector([{"id": "e9", "title": "Только в Postgres"}])
    hits = await service(InMemoryStore(), collector).events(
        SearchPlan(vector_query="x", limit=3))
    assert [hit.id for hit in hits] == ["e9"]
    assert hits[0].origins == ["lexical"]


@pytest.mark.asyncio
async def test_date_filter_respects_evening_time_window():
    from datetime import datetime, timezone

    store = hybrid_store(
        ("morning", [1.0, 0.0, 0.0],
         {"title": "Утренний концерт",
          "start_at": "2026-11-27T10:00:00+00:00"}, "концерт"),
        ("evening", [1.0, 0.0, 0.0],
         {"title": "Вечерний концерт",
          "start_at": "2026-11-27T19:00:00+00:00"}, "концерт"),
    )
    hits = await service(store, ExplodingCollector()).events(SearchPlan(
        vector_query="концерт", limit=5,
        date_from=datetime(2026, 11, 27, 18, 0, tzinfo=timezone.utc),
        date_to=datetime(2026, 11, 27, 23, 59, tzinfo=timezone.utc)))
    assert [hit.id for hit in hits] == ["evening"]


# --- BM25 / hybrid_mode -------------------------------------------------

@pytest.mark.asyncio
async def test_default_mode_is_sparse_and_sends_no_text_query():
    store = RecordingStore()
    await service(store, FakeCollector([])).events(
        SearchPlan(vector_query="джаз", limit=2))
    assert store.calls[0]["text_query"] is None


@pytest.mark.asyncio
async def test_bm25_mode_passes_text_query_to_the_store():
    store = RecordingStore()
    await service(store, FakeCollector([]), hybrid_mode="bm25").events(
        SearchPlan(vector_query="джазовый вечер", limit=2))
    assert store.calls[0]["text_query"] == "джазовый вечер"


@pytest.mark.asyncio
async def test_inmemory_text_scoring_ranks_term_overlap():
    """BM25 stand-in: payload search_text overlap decides the text ranking."""
    store = InMemoryStore([
        ("e1", [0.0, 1.0, 0.0],
         {"title": "Джазовый вечер", "search_text": "джазовый вечер музыка"}),
        ("e2", [0.0, 1.0, 0.0],
         {"title": "Рок концерт", "search_text": "рок концерт"}),
    ])
    hits = await store.hybrid_search(None, None, 5, text_query="джазовый")
    assert [hit.id for hit in hits] == ["e1"]


@pytest.mark.asyncio
async def test_bm25_only_query_without_dense_or_sparse():
    store = InMemoryStore([
        ("e1", [0.0, 0.0, 0.0], {"search_text": "джазовый вечер"}),
        ("e2", [0.0, 0.0, 0.0], {"search_text": "рок концерт"}),
    ])
    hits = await store.hybrid_search(None, None, 5, text_query="джазовый")
    assert [hit.id for hit in hits] == ["e1"]


@pytest.mark.asyncio
async def test_bm25_failure_retries_dense_and_sparse():
    class TextBrokenStore(InMemoryStore):
        def __init__(self) -> None:
            super().__init__([
                ("e1", [1.0, 0.0, 0.0], {"title": "Джаз", "search_text": "джаз"}),
            ], {"e1": encode_sparse("джаз")})
            self.calls: list[dict] = []

        async def hybrid_search(self, dense, sparse, limit, must=None,
                                must_not=None, text_query=None, weights=None):
            self.calls.append({"text_query": text_query})
            if text_query is not None:
                raise RuntimeError("missing search_text index")
            return await super().hybrid_search(dense, sparse, limit, must,
                                               must_not, weights=weights)

    store = TextBrokenStore()
    hits = await service(store, ExplodingCollector(), hybrid_mode="bm25").events(
        SearchPlan(vector_query="джаз", limit=2))
    assert [hit.id for hit in hits] == ["e1"]
    assert [call["text_query"] for call in store.calls] == ["джаз", None]


@pytest.mark.asyncio
async def test_lexical_mode_skips_the_vector_store():
    class ExplodingStore(InMemoryStore):
        async def hybrid_search(self, *args, **kwargs):
            raise AssertionError("store must not be called in lexical mode")

    collector = FakeCollector([{"id": "e9", "title": "Только лексика"}])
    hits = await service(ExplodingStore(), collector,
                         hybrid_mode="lexical").events(
        SearchPlan(vector_query="джаз", limit=3))
    assert [hit.id for hit in hits] == ["e9"]
    assert hits[0].origins == ["lexical"]


def test_unknown_hybrid_mode_is_rejected():
    with pytest.raises(ValueError):
        SearchService(FakeEmbedder(), InMemoryStore(), FakeCollector([]),
                      hybrid_mode="bm42")


# --- hard constraints: party / status / age / rating / hours ------------


def fresh_stamp(hours: int = 1) -> str:
    """Collector fetch timestamp inside the availability TTL."""
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def stale_stamp(hours: int = 72) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


@pytest.mark.asyncio
async def test_party_size_drops_hits_with_too_few_seats():
    fresh = fresh_stamp()
    store = hybrid_store(
        ("small", [1.0, 0.0, 0.0],
         {"title": "Малый зал", "seats_left": 2,
          "availability_at": fresh}, "малый зал"),
        ("big", [1.0, 0.0, 0.0],
         {"title": "Большой зал", "seats_left": 20,
          "availability_at": fresh}, "большой зал"),
        ("unknown", [1.0, 0.0, 0.0], {"title": "Без данных"}, "без данных"),
    )
    hits = await service(store, ExplodingCollector()).events(
        SearchPlan(vector_query="зал", limit=5, party_size=6))
    assert {hit.id for hit in hits} == {"big", "unknown"}


@pytest.mark.asyncio
async def test_party_size_ignores_stale_scraped_inventory():
    """Stale `seats_left` is unknown: a party query must not hide the event."""
    store = hybrid_store(
        ("stale", [1.0, 0.0, 0.0],
         {"title": "Старый зал", "seats_left": 1,
          "availability_at": stale_stamp()}, "старый зал"),
        ("legacy", [1.0, 0.0, 0.0],
         {"title": "Без метки", "seats_left": 1}, "без метки"),
    )
    hits = await service(store, ExplodingCollector()).events(
        SearchPlan(vector_query="зал", limit=5, party_size=6))
    assert {hit.id for hit in hits} == {"stale", "legacy"}


@pytest.mark.asyncio
async def test_sold_out_and_cancelled_status_filtering():
    store = hybrid_store(
        ("cancelled", [1.0, 0.0, 0.0],
         {"title": "Отменён", "status": "cancelled"}, "отменён"),
        ("sold", [1.0, 0.0, 0.0],
         {"title": "Распродан", "status": "sold_out",
          "availability_at": fresh_stamp()}, "распродан"),
        ("ok", [1.0, 0.0, 0.0],
         {"title": "Идёт", "status": "available"}, "идёт"),
    )
    no_party = await service(store, ExplodingCollector()).events(
        SearchPlan(vector_query="концерт", limit=5))
    ids = {hit.id for hit in no_party}
    assert "cancelled" not in ids
    assert {"sold", "ok"} <= ids

    with_party = await service(store, ExplodingCollector()).events(
        SearchPlan(vector_query="концерт", limit=5, party_size=2))
    assert {hit.id for hit in with_party} == {"ok"}


@pytest.mark.asyncio
async def test_stale_sold_out_is_not_hidden():
    store = hybrid_store(
        ("stale", [1.0, 0.0, 0.0],
         {"title": "Распродан давно", "status": "sold_out",
          "availability_at": stale_stamp()}, "распродан"),
    )
    hits = await service(store, ExplodingCollector()).events(
        SearchPlan(vector_query="концерт", limit=5, party_size=2))
    assert [hit.id for hit in hits] == ["stale"]


@pytest.mark.asyncio
async def test_age_max_drops_adult_only_events():
    store = hybrid_store(
        ("kids", [1.0, 0.0, 0.0],
         {"title": "Детский", "age_limit": 6}, "детский"),
        ("adult", [1.0, 0.0, 0.0],
         {"title": "18+", "age_limit": 18}, "взрослый"),
    )
    hits = await service(store, ExplodingCollector()).events(
        SearchPlan(vector_query="шоу", limit=5, age_max=12))
    assert [hit.id for hit in hits] == ["kids"]


@pytest.mark.asyncio
async def test_rating_is_only_a_tie_break():
    # A much better fused score must win despite a lower rating.
    store = hybrid_store(
        ("first", [1.0, 0.0, 0.0],
         {"title": "Первый", "venue_rating": 3.0}, "первый"),
        ("second", [0.0, 1.0, 0.0],
         {"title": "Второй", "venue_rating": 5.0}, "второй"),
    )
    hits = await service(store, ExplodingCollector()).events(
        SearchPlan(vector_query="первый", limit=5))
    assert [hit.id for hit in hits] == ["first", "second"]


@pytest.mark.asyncio
async def test_equal_scores_break_on_rating_and_unrated_stays_last():
    store = hybrid_store(
        ("unrated", [1.0, 0.0, 0.0], {"title": "А"}, "а"),
        ("rated", [1.0, 0.0, 0.0],
         {"title": "Б", "rating": 4.8}, "б"),
    )
    hits = await service(store, ExplodingCollector()).venues(
        SearchPlan(vector_query="место", limit=5))
    assert [hit.id for hit in hits] == ["rated", "unrated"]


@pytest.mark.asyncio
async def test_venue_hours_filter_drops_closed_venues():
    from datetime import datetime, timezone

    start = datetime(2026, 11, 25, 18, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 25, 23, 59, tzinfo=timezone.utc)
    key = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[start.weekday()]
    store = hybrid_store(
        ("open", [1.0, 0.0, 0.0],
         {"name": "Открыт", "hours": {key: ["10:00", "23:00"]}}, "место"),
        ("closed", [1.0, 0.0, 0.0],
         {"name": "Закрыт", "hours": {key: ["10:00", "17:00"]}}, "место"),
    )
    hits = await service(store, ExplodingCollector()).venues(SearchPlan(
        vector_query="место", limit=5, date_from=start, date_to=end,
        timezone="UTC"))
    assert [hit.id for hit in hits] == ["open"]


@pytest.mark.asyncio
async def test_rain_excludes_terrace_venues_by_amenity():
    store = hybrid_store(
        ("terrace", [1.0, 0.0, 0.0],
         {"name": "На террасе", "amenities": ["terrace", "wifi"]}, "бар"),
        ("inside", [1.0, 0.0, 0.0],
         {"name": "В помещении", "amenities": ["wifi"]}, "бар"),
    )
    hits = await service(store, ExplodingCollector()).venues(SearchPlan(
        vector_query="бар", limit=5, exclude_tags=["terrace"]))
    assert [hit.id for hit in hits] == ["inside"]


@pytest.mark.asyncio
async def test_rain_amenity_exclusion_falls_back_to_text():
    """Live 2GIS has no attribute groups: `amenities` is empty there."""
    store = hybrid_store(
        ("text", [1.0, 0.0, 0.0], {"name": "Летняя веранда"}, "бар"),
        ("inside", [1.0, 0.0, 0.0], {"name": "Бар в подвале"}, "бар"),
        ("structured", [1.0, 0.0, 0.0],
         {"name": "Бар", "amenities": ["wifi"],
          "description": "есть веранда"}, "бар"),
    )
    hits = await service(store, ExplodingCollector()).venues(SearchPlan(
        vector_query="бар", limit=5,
        exclude_amenities=["terrace", "веранда"]))
    # The text-only venue is caught; a venue with structured amenities is
    # judged by that list only, so its description mention is kept.
    assert {hit.id for hit in hits} == {"inside", "structured"}


@pytest.mark.asyncio
async def test_venue_budget_reads_avg_check_and_price_level():
    store = hybrid_store(
        ("cheap", [1.0, 0.0, 0.0],
         {"name": "Дешево", "avg_check": 20}, "кафе"),
        ("pricey", [1.0, 0.0, 0.0],
         {"name": "Дорого", "avg_check": 200}, "кафе"),
        ("level", [1.0, 0.0, 0.0],
         {"name": "Средне", "price_level": "medium"}, "кафе"),
        ("unknown", [1.0, 0.0, 0.0], {"name": "Без цены"}, "кафе"),
    )
    hits = await service(store, ExplodingCollector()).venues(SearchPlan(
        vector_query="кафе", limit=5, max_price_per_person=70))
    assert {hit.id for hit in hits} == {"cheap", "level", "unknown"}


# --- retrieval signals: themes, group relevance -------------------------


def test_lexical_query_appends_themes():
    assert SearchService._lexical_query(
        SearchPlan(vector_query="концерт", limit=1,
                   themes=["джаз", "саксофон"])) == "концерт джаз саксофон"
    # Themes alone are a valid lexical query when the model left it empty.
    assert SearchService._lexical_query(
        SearchPlan(vector_query="", limit=1, themes=["выставки"])) == "выставки"
    # No themes: the vector query is passed through unchanged.
    assert SearchService._lexical_query(
        SearchPlan(vector_query="джаз", limit=1)) == "джаз"


@pytest.mark.asyncio
async def test_themes_reach_the_bm25_text_query():
    store = RecordingStore()
    await service(store, FakeCollector([]), hybrid_mode="bm25").events(
        SearchPlan(vector_query="концерт", limit=2,
                   themes=["джаз", "саксофон"]))
    assert store.calls[0]["text_query"] == "концерт джаз саксофон"


@pytest.mark.asyncio
async def test_themes_reach_the_sparse_query_without_a_vector_query():
    """Themes restore lexical recall instead of forcing a dense-only search."""
    store = hybrid_store(
        ("jazz", [0.0, 1.0, 0.0], {"title": "Джазовый вечер"}, "джазовый вечер"),
        ("rock", [0.0, 1.0, 0.0], {"title": "Рок концерт"}, "рок концерт"),
    )
    hits = await service(store, ExplodingCollector()).events(
        SearchPlan(vector_query="", limit=2, themes=["джазовый"]))
    assert [hit.id for hit in hits] == ["jazz"]


def test_group_query_enriches_the_venue_query_from_six_people():
    svc = service(InMemoryStore(), FakeCollector([]))
    plan = svc._group_plan(SearchPlan(vector_query="бар", limit=5, party_size=8))
    assert plan.vector_query.startswith("бар ")
    assert "большая компания" in plan.vector_query
    # Party under the threshold: the query is untouched.
    assert svc._group_plan(
        SearchPlan(vector_query="бар", limit=5, party_size=2)
    ).vector_query == "бар"
    # Empty base query: the group terms are the fallback query.
    fallback = svc._group_plan(SearchPlan(vector_query="", limit=5,
                                          party_size=6))
    assert fallback.vector_query.startswith("большая компания")


@pytest.mark.asyncio
async def test_group_amenity_breaks_a_venue_tie_without_filtering():
    store = hybrid_store(
        ("plain", [1.0, 0.0, 0.0],
         {"name": "Бар", "rating": 4.0}, "бар"),
        ("group", [1.0, 0.0, 0.0],
         {"name": "Банкет-холл", "rating": 4.0,
          "amenities": ["banquet", "wifi"]}, "бар"),
    )
    svc = service(store, ExplodingCollector())
    big = await svc.venues(SearchPlan(vector_query="бар", limit=5, party_size=8))
    assert [hit.id for hit in big] == ["group", "plain"]
    # Never a hard filter: both venues still answer a group query.
    assert {hit.id for hit in big} == {"plain", "group"}
    # Below the threshold the boost is inert and the fused order stands.
    small = await svc.venues(SearchPlan(vector_query="бар", limit=5,
                                        party_size=2))
    assert [hit.id for hit in small] == ["plain", "group"]


# --- weighted RRF / freshness / reranker --------------------------------


class FakeQdrantClient:
    """Stands in for AsyncQdrantClient; one canned ranking per call."""

    def __init__(self, rankings):
        self._rankings = list(rankings)
        self.calls: list[dict] = []

    async def query_points(self, collection, **kwargs):
        from types import SimpleNamespace

        self.calls.append(kwargs)
        ids = self._rankings.pop(0) if self._rankings else []
        return SimpleNamespace(points=[
            SimpleNamespace(id=doc_id, score=1.0, payload={"id": doc_id})
            for doc_id in ids])


def qdrant_store(rankings) -> tuple[QdrantStore, FakeQdrantClient]:
    store = QdrantStore("http://localhost:6333", "events")
    fake = FakeQdrantClient(rankings)
    store._client = fake
    return store, fake


@pytest.mark.asyncio
async def test_equal_weights_keep_one_server_side_fusion_call():
    from qdrant_client import models

    store, fake = qdrant_store([["a", "b"]])
    hits = await store.hybrid_search([1.0, 0.0], encode_sparse("джаз"), 5,
                                     text_query="джаз")
    assert [hit.id for hit in hits] == ["a", "b"]
    assert len(fake.calls) == 1
    assert isinstance(fake.calls[0]["query"], models.FusionQuery)
    assert fake.calls[0]["prefetch"]


@pytest.mark.asyncio
async def test_unequal_weights_fuse_client_side_and_decide_order():
    store, fake = qdrant_store([["a", "b"], ["b", "a"]])
    hits = await store.hybrid_search(
        [1.0, 0.0], encode_sparse("джаз"), 5,
        weights={"dense": 5, "sparse": 1})
    assert len(fake.calls) == 2
    assert all("prefetch" not in call for call in fake.calls)
    assert [hit.id for hit in hits] == ["a", "b"]

    store, _ = qdrant_store([["a", "b"], ["b", "a"]])
    flipped = await store.hybrid_search(
        [1.0, 0.0], encode_sparse("джаз"), 5,
        weights={"dense": 1, "sparse": 5})
    assert [hit.id for hit in flipped] == ["b", "a"]


@pytest.mark.asyncio
async def test_inmemory_store_honours_the_same_weights():
    store = InMemoryStore(
        [("a", [1.0, 0.0, 0.0], {"search_text": "джаз"}),
         ("b", [0.0, 1.0, 0.0], {"search_text": "джаз джаз джаз"})],
        {"a": encode_sparse("джаз"), "b": encode_sparse("джаз джаз джаз")},
    )
    query = encode_sparse("джаз")
    dense_first = await store.hybrid_search(
        [1.0, 0.0, 0.0], query, 5, weights={"dense": 5, "sparse": 1})
    assert [hit.id for hit in dense_first] == ["a", "b"]
    sparse_first = await store.hybrid_search(
        [1.0, 0.0, 0.0], query, 5, weights={"dense": 1, "sparse": 5})
    assert [hit.id for hit in sparse_first] == ["b", "a"]


@pytest.mark.asyncio
async def test_freshness_boost_changes_the_order_only_when_enabled():
    now = datetime.now(timezone.utc)
    store = hybrid_store(
        ("later", [1.0, 0.0, 0.0],
         {"title": "Позже", "start_at": (now + timedelta(days=25)).isoformat()},
         "концерт"),
        ("soon", [1.0, 0.0, 0.0],
         {"title": "Скоро", "start_at": (now + timedelta(days=1)).isoformat()},
         "концерт"),
    )
    plan = SearchPlan(vector_query="концерт", limit=5)
    # Default boost 0.0: the fused tie keeps the retriever order.
    default_hits = await service(store, ExplodingCollector()).events(plan)
    assert [hit.id for hit in default_hits] == ["later", "soon"]

    boosted = SearchService(FakeEmbedder(), store, ExplodingCollector(),
                            freshness_boost=0.01)
    boosted_hits = await boosted.events(plan)
    assert [hit.id for hit in boosted_hits] == ["soon", "later"]


class ExplodingReranker:
    async def rerank(self, query, hits):
        raise AssertionError("reranker must not run while disabled")


class ReverseReranker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    async def rerank(self, query, hits):
        self.calls.append((query, [hit.id for hit in hits]))
        return list(reversed(hits))


@pytest.mark.asyncio
async def test_reranker_off_does_not_call_the_hook():
    store = hybrid_store(
        ("e1", [1.0, 0.0, 0.0], {"title": "Первый"}, "концерт"),
        ("e2", [1.0, 0.0, 0.0], {"title": "Второй"}, "концерт"),
    )
    svc = SearchService(FakeEmbedder(), store, ExplodingCollector(),
                        reranker=ExplodingReranker(), rerank_enabled=False)
    hits = await svc.events(SearchPlan(vector_query="концерт", limit=5))
    assert {hit.id for hit in hits} == {"e1", "e2"}


@pytest.mark.asyncio
async def test_enabled_reranker_reorders_the_candidates():
    store = hybrid_store(
        ("e1", [1.0, 0.0, 0.0], {"title": "Первый"}, "концерт"),
        ("e2", [1.0, 0.0, 0.0], {"title": "Второй"}, "концерт"),
    )
    reranker = ReverseReranker()
    svc = SearchService(FakeEmbedder(), store, ExplodingCollector(),
                        rerank_enabled=True, reranker=reranker)
    hits = await svc.events(SearchPlan(vector_query="концерт", limit=5))
    assert reranker.calls == [("концерт", ["e1", "e2"])]
    # Equal fused scores: the stable sort keeps the reranker's order.
    assert [hit.id for hit in hits] == ["e2", "e1"]


# --- "ещё" pagination / undated posts / atmosphere ----------------------


@pytest.mark.asyncio
async def test_exclude_ids_drops_shown_hits_and_booking_ids():
    store = hybrid_store(
        ("shown", [1.0, 0.0, 0.0], {"title": "Показан"}, "показан"),
        ("fresh", [1.0, 0.0, 0.0], {"title": "Новый"}, "новый"),
        ("uuid-booked", [1.0, 0.0, 0.0],
         {"title": "Бронь", "booking_event_id": 7}, "бронь"),
    )
    hits = await service(store, ExplodingCollector()).events(SearchPlan(
        vector_query="событие", limit=5, exclude_ids=["shown", "7"]))
    # Point ids and booking ids both address a shown card.
    assert [hit.id for hit in hits] == ["fresh"]


@pytest.mark.asyncio
async def test_exclude_ids_widens_the_candidate_window():
    store = RecordingStore()
    await service(store, FakeCollector([])).events(
        SearchPlan(vector_query="шоу", limit=4, exclude_ids=["x"]))
    assert store.calls[0]["limit"] == 12


@pytest.mark.asyncio
async def test_undated_hits_are_allowed_and_rank_after_dated_ones():
    store = hybrid_store(
        ("undated", [1.0, 0.0, 0.0], {"title": "Анонс"}, "анонс"),
        ("dated", [1.0, 0.0, 0.0],
         {"title": "Премьера", "start_at": "2026-12-05T19:00:00+00:00"},
         "премьера"),
        ("past", [1.0, 0.0, 0.0],
         {"title": "Прошлое", "start_at": "2026-11-01T19:00:00+00:00"},
         "прошлое"),
    )
    hits = await service(store, ExplodingCollector()).events(SearchPlan(
        vector_query="фильм", limit=5, include_undated=True,
        date_from=datetime(2026, 11, 25, tzinfo=timezone.utc)))
    # Undated passes, past dated does not, and dated ranks first.
    assert [hit.id for hit in hits] == ["dated", "undated"]


@pytest.mark.asyncio
async def test_date_filter_without_undated_mode_drops_undated():
    store = hybrid_store(
        ("undated", [1.0, 0.0, 0.0], {"title": "Анонс"}, "анонс"),
        ("dated", [1.0, 0.0, 0.0],
         {"title": "Премьера", "start_at": "2026-12-05T19:00:00+00:00"},
         "премьера"),
    )
    hits = await service(store, ExplodingCollector()).events(SearchPlan(
        vector_query="фильм", limit=5,
        date_from=datetime(2026, 11, 25, tzinfo=timezone.utc)))
    assert [hit.id for hit in hits] == ["dated"]


def test_exclude_tags_reads_the_atmosphere_payload():
    from app.filters.specs import ExcludeTagsFilter

    hit = FusedHit(id="venue", score=1.0,
                   payload={"name": "Бар", "atmosphere": ["громко", "толпа"]})
    assert ExcludeTagsFilter(["громко"]).matches(hit) is False
    assert ExcludeTagsFilter(["толпа"]).matches(hit) is False
    assert ExcludeTagsFilter(["кальян"]).matches(hit) is True


@pytest.mark.asyncio
async def test_exclude_ids_also_applies_to_venues():
    store = hybrid_store(
        ("v1", [1.0, 0.0, 0.0], {"name": "Кафе 1"}, "кафе"),
        ("v2", [1.0, 0.0, 0.0], {"name": "Кафе 2"}, "кафе"),
    )
    hits = await service(store, ExplodingCollector()).venues(SearchPlan(
        vector_query="кафе", limit=5, exclude_ids=["v1"]))
    assert [hit.id for hit in hits] == ["v2"]
