"""Qdrant payload index schema (BM25 text index) without a live server."""
import asyncio
from types import SimpleNamespace

from qdrant_client import models

from app.clients.vector import PAYLOAD_INDEXES, QdrantStore


class FakeIndexClient:
    """Captures create_payload_index calls; talks to no server."""

    def __init__(self) -> None:
        self.calls: dict[str, object] = {}

    async def create_payload_index(self, collection, field_name, field_schema):
        self.calls[field_name] = (collection, field_schema)


def fake_store(client, collection: str = "events") -> QdrantStore:
    store = object.__new__(QdrantStore)
    store._client = client
    store._models = models
    store._collection = collection
    return store


def test_search_text_is_a_text_payload_index():
    assert PAYLOAD_INDEXES["search_text"] == "text"


def test_availability_and_enrichment_payload_indexes():
    expected = {
        "status": "keyword",
        "age_limit": "integer",
        "capacity": "integer",
        "seats_left": "integer",
        "lat": "float",
        "lon": "float",
        "venue_rating": "float",
        "rating": "float",
        "amenities": "keyword",
        "avg_check": "float",
        "is_24_7": "bool",
        "atmosphere": "keyword",
    }
    assert {key: PAYLOAD_INDEXES[key] for key in expected} == expected


def test_new_payload_index_schema_types():
    client = FakeIndexClient()

    asyncio.run(fake_store(client)._ensure_payload_indexes())

    assert client.calls["status"][1] == models.PayloadSchemaType.KEYWORD
    assert client.calls["age_limit"][1] == models.PayloadSchemaType.INTEGER
    assert client.calls["capacity"][1] == models.PayloadSchemaType.INTEGER
    assert client.calls["seats_left"][1] == models.PayloadSchemaType.INTEGER
    # Flat lat/lon floats: a GeoIndex needs {"lon","lat"} objects.
    assert client.calls["lat"][1] == models.PayloadSchemaType.FLOAT
    assert client.calls["lon"][1] == models.PayloadSchemaType.FLOAT
    assert client.calls["venue_rating"][1] == models.PayloadSchemaType.FLOAT
    assert client.calls["amenities"][1] == models.PayloadSchemaType.KEYWORD
    assert client.calls["avg_check"][1] == models.PayloadSchemaType.FLOAT
    assert client.calls["is_24_7"][1] == models.PayloadSchemaType.BOOL
    assert client.calls["atmosphere"][1] == models.PayloadSchemaType.KEYWORD


def test_payload_index_schema_builds_bm25_text_params():
    client = FakeIndexClient()

    asyncio.run(fake_store(client)._ensure_payload_indexes())

    collection, schema = client.calls["search_text"]
    assert collection == "events"
    assert isinstance(schema, models.TextIndexParams)
    assert schema.type == models.TextIndexType.TEXT
    assert schema.tokenizer == models.TokenizerType.WORD
    assert schema.lowercase is True
    assert schema.scoring is True
    assert schema.stemmer.type == models.Snowball.SNOWBALL
    assert schema.stemmer.language == models.SnowballLanguage.RUSSIAN
    assert models.Language.RUSSIAN in schema.stopwords.languages
    # Keyword/float indexes keep their old schema types.
    assert client.calls["city"][1] == models.PayloadSchemaType.KEYWORD
    assert client.calls["price_min"][1] == models.PayloadSchemaType.FLOAT


def test_dense_only_legacy_branch_creates_payload_indexes():
    """Legacy collections (no sparse config, data inside) still get indexes."""

    class LegacyClient(FakeIndexClient):
        async def get_collection(self, collection):
            return SimpleNamespace(
                config=SimpleNamespace(
                    params=SimpleNamespace(sparse_vectors=None)))

        async def count(self, collection):
            return SimpleNamespace(count=42)

        async def delete_collection(self, collection):  # pragma: no cover
            raise AssertionError("non-empty legacy collection must survive")

    client = LegacyClient()

    asyncio.run(fake_store(client).ensure(dim=1024))

    assert "search_text" in client.calls
    assert "city" in client.calls
