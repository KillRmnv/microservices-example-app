import asyncio

import httpx
import pytest

from app.clients.collector import CollectorClient
from app.clients.vector import InMemoryStore
from app.models.search import SearchPlan
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

    async def search_lexical(self, query, city, category, limit):
        return self._rows[:limit]

    async def search_venues_lexical(self, query, city, rubric, limit):
        return self._rows[:limit]


class ExplodingCollector(FakeCollector):
    """Hybrid success must never touch the collector."""

    def __init__(self):
        super().__init__([])

    async def search_lexical(self, query, city, category, limit):
        raise AssertionError("collector must not be called on hybrid hit")

    async def search_venues_lexical(self, query, city, rubric, limit):
        raise AssertionError("collector must not be called on hybrid hit")


def hybrid_store(*items):
    """items: (id, dense_vector, payload, sparse_text)."""
    return InMemoryStore(
        [(doc_id, vector, payload) for doc_id, vector, payload, _ in items],
        {doc_id: encode_sparse(text) for doc_id, _, _, text in items},
    )


def service(store, collector=None, embedder=None) -> SearchService:
    return SearchService(embedder or FakeEmbedder(), store,
                         collector or FakeCollector([]))


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
        async def hybrid_search(self, dense, sparse, limit, must=None):
            raise RuntimeError("qdrant down")

    collector = FakeCollector([{"id": "e9", "title": "Только лексика"}])
    hits = await service(BrokenStore(), collector).events(
        SearchPlan(vector_query="x", limit=3))
    assert [hit.id for hit in hits] == ["e9"]
    assert hits[0].origins == ["lexical"]


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
async def test_collector_client_uses_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/events/search"
        assert request.url.params["q"] == "джаз"
        return httpx.Response(200, json={"events": [{"id": "e1", "title": "Джаз"}]})

    client = CollectorClient("http://collector:8080",
                             transport=httpx.MockTransport(handler))
    rows = await client.search_lexical("джаз", None, None, 5)
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
