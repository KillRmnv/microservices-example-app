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
        "SELECT status, parse_errors FROM source_runs"
        " WHERE source = 'probe'").fetchone()
    assert row["status"] == "error" and row["parse_errors"] == 1


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


def test_ops_service_health_and_metrics(database_url, conn):
    conn.execute(
        """INSERT INTO source_runs (source, status, started_at, finished_at,
                                    fetched, parsed, new_events)
           VALUES ('ticketpro', 'ok', now(), now(), 1, 1, 5)""")
    conn.commit()
    settings = Settings(ops_alert_window=2)
    service = OpsService(database_url, settings)
    health = service.collect_health()
    assert {entry["source"] for entry in health["sources"]} == {"ticketpro"}
    assert 'collector_runs_total{source="ticketpro",status="ok"} 1' in service.metrics()
