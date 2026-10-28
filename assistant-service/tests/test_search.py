import httpx
import pytest

from app.clients.collector import CollectorClient
from app.clients.vector import InMemoryStore
from app.models.search import SearchPlan
from app.services.fusion import fuse_search, rrf_fuse
from app.services.search_service import SearchService


def test_rrf_prefers_top_ranks():
    fused = dict(rrf_fuse([["a", "b", "c"], ["a", "b"]]))
    assert fused["a"] > fused["b"] > fused["c"]


def test_rrf_single_list_order_kept():
    assert [doc for doc, _ in rrf_fuse([["x", "y"]])] == ["x", "y"]


def test_fuse_search_origins():
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


class FakeCollector(CollectorClient):
    def __init__(self, rows):
        self._rows = rows

    async def search_lexical(self, query, city, category, limit):
        return self._rows[:limit]

    async def search_venues_lexical(self, query, city, rubric, limit):
        return self._rows[:limit]


def service(store, collector) -> SearchService:
    return SearchService(FakeEmbedder(), store, collector)


@pytest.mark.asyncio
async def test_hybrid_search_merges_both_origins():
    store = InMemoryStore([
        ("e1", [1.0, 0.0, 0.0], {"title": "Джаз"}),
        ("e2", [0.0, 1.0, 0.0], {"title": "Рок"}),
    ])
    collector = FakeCollector([
        {"id": "e2", "title": "Рок", "category": "concert"},
        {"id": "e3", "title": "Театр", "category": "theatre"},
    ])
    hits = await service(store, collector).events(
        SearchPlan(vector_query="джаз", limit=3))
    by_id = {hit.id: hit for hit in hits}
    assert set(by_id) == {"e1", "e2", "e3"}
    assert by_id["e2"].origins == ["dense", "lexical"]
    assert by_id["e3"].payload["title"] == "Театр"  # backfilled from lexical row


@pytest.mark.asyncio
async def test_hybrid_search_survives_dense_outage():
    class BrokenStore(InMemoryStore):
        async def search(self, vector, limit, must=None):
            raise RuntimeError("qdrant down")

    collector = FakeCollector([{"id": "e9", "title": "Только лексика"}])
    hits = await service(BrokenStore(), collector).events(
        SearchPlan(vector_query="x", limit=3))
    assert [hit.id for hit in hits] == ["e9"]
    assert hits[0].origins == ["lexical"]


@pytest.mark.asyncio
async def test_price_filter_is_a_specification():
    collector = FakeCollector([
        {"id": "cheap", "title": "Дешево", "price_min": 20.0},
        {"id": "pricey", "title": "Дорого", "price_min": 500.0},
    ])
    hits = await service(InMemoryStore(), collector).events(
        SearchPlan(vector_query="x", limit=5, max_price_per_person=100.0))
    assert [hit.id for hit in hits] == ["cheap"]


@pytest.mark.asyncio
async def test_exclude_categories_filter():
    collector = FakeCollector([
        {"id": "a", "title": "Концерт", "category": "concert"},
        {"id": "b", "title": "Спорт", "category": "sport"},
    ])
    hits = await service(InMemoryStore(), collector).events(
        SearchPlan(vector_query="x", limit=5, exclude_categories=["sport"]))
    assert [hit.id for hit in hits] == ["a"]


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
async def test_hybrid_search_venues_merges():
    store = InMemoryStore([
        ("v1", [1.0, 0.0, 0.0], {"name": "Кофейня", "rubric": "Кофейни"}),
        ("v2", [0.0, 1.0, 0.0], {"name": "Театр", "rubric": "Театры"}),
    ])
    collector = FakeCollector([
        {"id": "v2", "name": "Театр", "rubric": "Театры", "address": "ул. X"},
        {"id": "v3", "name": "Бар", "rubric": "Бары", "address": "ул. Y"},
    ])
    hits = await service(store, collector).venues(
        SearchPlan(vector_query="кофе", limit=3))
    by_id = {hit.id: hit for hit in hits}
    assert set(by_id) == {"v1", "v2", "v3"}
    assert by_id["v2"].origins == ["dense", "lexical"]
    assert by_id["v3"].payload["address"] == "ул. Y"
