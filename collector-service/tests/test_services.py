"""Service-layer tests: collection wiring, embedding, ops."""
import asyncio

import httpx
import pytest

from app.core.config import Settings
from app.errors import UnknownSource, UpstreamError
from app.http import PoliteClient
from app.services.collect_service import CollectService
from app.services.embed_service import EmbedService
from app.services.ops_service import OpsService
from app.vector import MemoryStore
from conftest import pg_url


def test_unknown_source_is_a_domain_error():
    service = CollectService(
        PoliteClient(user_agent="test/0.1", default_min_interval_s=0),
        pg_url(),
    )
    with pytest.raises(UnknownSource):
        asyncio.run(service.collect("nope"))


def test_probe_records_a_source_run(conn):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>ok</html>")

    http = PoliteClient(user_agent="test/0.1", default_min_interval_s=0,
                        transport=httpx.MockTransport(handler))
    service = CollectService(http, pg_url())
    result = asyncio.run(service.probe("probe", "https://example.com/"))
    assert result["status_code"] == 200
    row = conn.execute(
        "SELECT status, fetched, parsed FROM source_runs"
        " WHERE source = 'probe'").fetchone()
    assert row == {"status": "ok", "fetched": 1, "parsed": 1}


def test_probe_failure_is_recorded_then_mapped(conn):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    http = PoliteClient(user_agent="test/0.1", default_min_interval_s=0,
                        max_attempts=1, backoff_base_s=0,
                        transport=httpx.MockTransport(handler))
    service = CollectService(http, pg_url())
    with pytest.raises(UpstreamError):
        asyncio.run(service.probe("probe", "https://example.com/"))
    row = conn.execute(
        "SELECT status, parse_errors, fetch_errors FROM source_runs"
        " WHERE source = 'probe'").fetchone()
    assert row["status"] == "error" and row["fetch_errors"] == 1
    assert row["parse_errors"] == 0


class FakeEmbedder:
    dim = 3

    async def embed(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]


def test_embed_events_marks_rows(database_url, conn):
    conn.execute(
        """INSERT INTO collected_events (source, source_id, source_url, title)
           VALUES ('ticketpro', 'e1', 'http://x/1', 'Концерт'),
                  ('ticketpro', 'e2', 'http://x/2', 'Спектакль')""")
    conn.commit()
    store = MemoryStore()
    settings = Settings()

    async def run():
        service = EmbedService(database_url, FakeEmbedder(), store, MemoryStore(),
                               settings)
        return await service.embed_events("ticketpro")

    embedded, pending = asyncio.run(run())
    assert embedded == 2 and pending == 0
    assert asyncio.run(store.count()) == 2
    left = conn.execute(
        "SELECT count(*) AS n FROM collected_events WHERE embedded_at IS NULL"
    ).fetchone()["n"]
    assert left == 0


def test_embed_events_stores_sparse_and_price_payload(database_url, conn):
    conn.execute(
        """INSERT INTO collected_events
               (source, source_id, source_url, title, venue_name, description,
                price_min, price_max)
           VALUES ('ticketpro', 'e9', 'http://x/9', 'Джазовый вечер',
                   'Филармония', 'Тихий джаз', 25, 60)""")
    conn.commit()
    store = MemoryStore()

    async def run():
        service = EmbedService(database_url, FakeEmbedder(), store,
                               MemoryStore(), Settings())
        return await service.embed_events("ticketpro")

    assert asyncio.run(run()) == (1, 0)
    points = asyncio.run(store.scroll_all())
    assert len(points) == 1
    assert points[0].sparse  # sparse indexed alongside dense
    assert points[0].payload["price_min"] == 25.0
    assert points[0].payload["price_max"] == 60.0


def test_reindex_hybrid_patches_legacy_points(database_url, conn):
    from app.vector import VectorPoint

    conn.execute(
        """INSERT INTO collected_events
               (source, source_id, source_url, title, venue_name, price_min)
           VALUES ('relax', 'r1', 'http://x/r1', 'Концерт у Немиги',
                   'Клуб', 40)""")
    conn.commit()
    row_id = str(conn.execute(
        "SELECT id FROM collected_events WHERE source_id = 'r1'").fetchone()["id"])
    store = MemoryStore()

    async def run():
        # Legacy dense-only point, as created before hybrid search.
        await store.upsert([VectorPoint(id=row_id, vector=[1.0, 0.0, 0.0],
                                        payload={"title": "Концерт у Немиги"})])
        service = EmbedService(database_url, FakeEmbedder(), store,
                               MemoryStore(), Settings())
        return await service.reindex_hybrid()

    result = asyncio.run(run())
    assert result["events"]["patched"] == 1
    assert result["events"]["rows"] == 1
    (point,) = asyncio.run(store.scroll_all())
    assert point.vector == [1.0, 0.0, 0.0]  # dense preserved
    assert point.sparse  # sparse merged from Postgres text
    assert point.payload["price_min"] == 40.0


def test_ops_service_health_and_metrics(database_url, conn):
    conn.execute(
        """INSERT INTO source_runs (source, status, started_at, finished_at,
                                    fetched, parsed, rows_inserted)
           VALUES ('ticketpro', 'ok', now(), now(), 1, 1, 5)""")
    conn.commit()
    settings = Settings(ops_alert_window=2)
    service = OpsService(database_url, settings)
    health = service.collect_health()
    assert {entry["source"] for entry in health["sources"]} == {"ticketpro"}
    assert 'collector_runs_total{source="ticketpro",status="ok"} 1' in service.metrics()
