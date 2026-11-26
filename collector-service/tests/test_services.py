"""Service-layer tests: collection wiring, embedding, ops."""
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone

import httpx
import pytest

from app.core.config import Settings
from app.errors import UnknownSource, UpstreamError
from app.clients.http import PoliteClient
from app.services import embed_service as embed_module
from app.services.collect_service import CollectService
from app.services.embed_service import (EmbedService, _event_payload, _event_text,
                                        _venue_text)
from app.services.ops_service import OpsService
from app.repositories import queries
from app.clients.vector import MemoryStore
from conftest import pg_url


def test_unknown_source_is_a_domain_error():
    # No connection is opened: the source lookup fails before any DB access.
    service = CollectService(
        PoliteClient(user_agent="test/0.1", default_min_interval_s=0),
        "postgresql://unused",
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
    assert points[0].payload["source"] == "ticketpro"
    row = queries.all_events_for_reindex(conn)[0]
    search_text = points[0].payload["search_text"]
    assert search_text and search_text == _event_text(row)
    assert "Джазовый вечер" in search_text and "Филармония" in search_text


def test_embed_venues_stores_search_text(database_url, conn):
    conn.execute(
        """INSERT INTO collected_venues (source, source_id, name, rubric, address)
           VALUES ('twogis', 'v1', 'Кофейня у Ратуши', 'кофейня',
                   'площадь Свободы 2')""")
    conn.commit()
    store = MemoryStore()

    async def run():
        service = EmbedService(database_url, FakeEmbedder(), MemoryStore(), store,
                               Settings())
        return await service.embed_venues()

    assert asyncio.run(run()) == (1, 0)
    points = asyncio.run(store.scroll_all())
    assert len(points) == 1
    row = queries.all_venues_for_reindex(conn)[0]
    search_text = points[0].payload["search_text"]
    assert search_text and search_text == _venue_text(row)
    assert "Кофейня у Ратуши" in search_text


def test_event_payload_carries_availability_and_venue(database_url, conn):
    venue_id = conn.execute(
        """INSERT INTO collected_venues
               (source, source_id, name, city, latitude, longitude,
                rating, review_count)
           VALUES ('twogis', 'v42', 'Филармония', 'Минск', 53.9, 27.5, 4.8, 120)
           RETURNING id""").fetchone()["id"]
    conn.execute(
        """INSERT INTO collected_events
               (source, source_id, source_url, title, venue_name, venue_id,
                address, start_at, status, availability, capacity, seats_left,
                age_limit, currency)
           VALUES ('ticketpro', 'e42', 'http://x/42', 'Концерт', 'Филармония',
                   %s, 'проспект Независимости, 1',
                   '2026-12-01T19:00:00+00:00', 'sold_out', 'sold_out',
                   500, 0, 12, 'BYN')""", (venue_id,))
    conn.commit()
    store = MemoryStore()

    async def run():
        service = EmbedService(database_url, FakeEmbedder(), store,
                               MemoryStore(), Settings())
        return await service.embed_events("ticketpro")

    assert asyncio.run(run()) == (1, 0)
    payload = asyncio.run(store.scroll_all())[0].payload
    assert payload["status"] == "sold_out"
    assert payload["address"] == "проспект Независимости, 1"
    assert payload["capacity"] == 500
    assert payload["seats_left"] == 0
    assert payload["age_limit"] == 12
    assert payload["currency"] == "BYN"
    assert payload["venue_id"] == str(venue_id)
    assert payload["lat"] == 53.9 and payload["lon"] == 27.5
    assert payload["venue_rating"] == 4.8
    assert payload["venue_review_count"] == 120
    # Freshness stamp for the assistant's seats_left/status TTL.
    assert payload["availability_at"].startswith("20")


def test_event_payload_availability_at_contract():
    row = {
        "id": "00000000-0000-0000-0000-000000000001",
        "title": "Концерт", "source": "ticketpro", "city": "Минск",
        "category": "concert", "venue_name": "Клуб", "description": "Джаз",
        "address": None, "start_at": None, "end_at": None,
        "price_min": None, "price_max": None, "booking_event_id": None,
        "status": None, "age_limit": None, "currency": None,
        "capacity": None, "seats_left": None, "venue_id": None,
        "venue_lat": None, "venue_lon": None, "venue_rating": None,
        "venue_review_count": None,
        "fetched_at": datetime(2026, 11, 26, 12, 30, tzinfo=timezone.utc),
    }
    payload = _event_payload(row)
    assert payload["availability_at"] == "2026-11-26T12:30:00+00:00"
    assert {"availability_at", "seats_left", "status", "capacity",
            "venue_id", "search_text"} <= set(payload)
    row["fetched_at"] = None
    assert _event_payload(row)["availability_at"] == ""


def test_venue_payload_carries_enrichment(database_url, conn):
    conn.execute(
        """INSERT INTO collected_venues
               (source, source_id, name, rubric, address, city, latitude,
                longitude, rating, review_count, schedule, amenities,
                avg_check, price_level, district)
           VALUES ('twogis', 'v43', 'Кофейня', 'Кофейни', 'ул. 1', 'Минск',
                   53.9, 27.5, 4.6, 55,
                   '{"Mon": {"working_hours": [{"from": "09:00", "to": "22:00"}]}}'::jsonb,
                   '["wifi", "terrace"]'::jsonb, 40.0, 'medium', 'Центральный')""")
    conn.commit()
    store = MemoryStore()

    async def run():
        service = EmbedService(database_url, FakeEmbedder(), MemoryStore(), store,
                               Settings())
        return await service.embed_venues()

    assert asyncio.run(run()) == (1, 0)
    payload = asyncio.run(store.scroll_all())[0].payload
    assert payload["lat"] == 53.9 and payload["lon"] == 27.5
    assert payload["rating"] == 4.6 and payload["review_count"] == 55
    assert payload["hours"] == {"mon": [["09:00", "22:00"]]}
    assert payload["is_24_7"] is False
    assert payload["amenities"] == ["wifi", "terrace"]
    assert payload["avg_check"] == 40.0
    assert payload["price_level"] == "medium"
    assert payload["district"] == "Центральный"


def test_venue_payload_defaults_for_unenriched_rows(database_url, conn):
    conn.execute(
        """INSERT INTO collected_venues (source, source_id, name, city)
           VALUES ('twogis', 'v44', 'Книжный', 'Минск')""")
    conn.commit()
    store = MemoryStore()

    async def run():
        service = EmbedService(database_url, FakeEmbedder(), MemoryStore(), store,
                               Settings())
        return await service.embed_venues()

    assert asyncio.run(run()) == (1, 0)
    payload = asyncio.run(store.scroll_all())[0].payload
    assert payload["hours"] is None
    assert payload["is_24_7"] is False
    assert payload["amenities"] == []
    assert payload["avg_check"] is None
    assert payload["price_level"] is None
    assert payload["district"] is None
    assert payload["atmosphere"] == []
    assert payload["lat"] is None and payload["rating"] is None


def test_venue_payload_carries_atmosphere_and_search_text(database_url, conn):
    conn.execute(
        """INSERT INTO collected_venues
               (source, source_id, name, rubric, address, city,
                atmosphere)
           VALUES ('twogis', 'v-atmo', 'Кофейня', 'Кафе', 'ул. 1', 'Минск',
                   '["cozy", "live_music"]'::jsonb)""")
    conn.commit()
    store = MemoryStore()

    async def run():
        service = EmbedService(database_url, FakeEmbedder(), MemoryStore(), store,
                               Settings())
        return await service.embed_venues()

    assert asyncio.run(run()) == (1, 0)
    payload = asyncio.run(store.scroll_all())[0].payload
    assert payload["atmosphere"] == ["cozy", "live_music"]
    row = queries.all_venues_for_reindex(conn)[0]
    assert payload["search_text"] == _venue_text(row)
    assert "уютно" in payload["search_text"]
    assert "живая музыка" in payload["search_text"]


def test_reindex_hybrid_patches_legacy_points(database_url, conn):
    from app.clients.vector import VectorPoint

    conn.execute(
        """INSERT INTO collected_events
               (source, source_id, source_url, title, venue_name, price_min)
           VALUES ('relax', 'r1', 'http://x/r1', 'Концерт у Немиги',
                   'Клуб', 40)""")
    conn.commit()
    row = queries.all_events_for_reindex(conn)[0]
    row_id = str(row["id"])
    patched: list = []

    class RecordingStore(MemoryStore):
        async def patch_points(self, points):
            patched.extend(points)
            await super().patch_points(points)

    store = RecordingStore()

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
    assert point.payload["source"] == "relax"
    assert point.payload["address"] == ""  # NULL address -> empty string
    # BM25 field reaches the patch call, not just the final point payload.
    assert patched and patched[0].payload["search_text"] == _event_text(row)
    assert patched[0].payload["search_text"]


def test_ops_service_health_and_metrics(database_url, conn):
    conn.execute(
        """INSERT INTO source_runs (source, status, started_at, finished_at,
                                    fetched, parsed, rows_inserted)
           VALUES ('ticketpro', 'ok', now(), now(), 1, 1, 5)""")
    conn.execute(
        """INSERT INTO collector_kv (key, value)
           VALUES ('telegram:stats:minsk_kuda',
                   '{"fetched": 10, "kept": 6, "keep_ratio": 0.6}')""")
    conn.commit()
    settings = Settings(ops_alert_window=2)
    service = OpsService(database_url, settings)
    health = service.collect_health()
    assert {entry["source"] for entry in health["sources"]} == {"ticketpro"}
    assert health["venue_link"] == {"linked": 0, "total": 0, "by_source": {}}
    assert health["telegram_channels"]["minsk_kuda"]["keep_ratio"] == 0.6
    assert health["payload_version"] == {
        "applied": None, "expected": embed_module.PAYLOAD_VERSION,
        "mismatch": True}
    assert 'collector_runs_total{source="ticketpro",status="ok"} 1' in service.metrics()


@contextmanager
def _lock_acquired(_db_url, key=None):
    yield True


@contextmanager
def _lock_busy(_db_url, key=None):
    yield False


def _fake_service() -> EmbedService:
    # No connection is opened until a method actually needs Postgres.
    return EmbedService("postgresql://unused", FakeEmbedder(), MemoryStore(),
                        MemoryStore(), Settings())


def test_payload_version_mismatch_reindexes_exactly_once(monkeypatch):
    calls, writes = [], []
    state = {"version": 1}
    monkeypatch.setattr(embed_module, "applied_payload_version",
                        lambda url: state["version"])

    def _store(url, version=embed_module.PAYLOAD_VERSION):
        writes.append(version)
        state["version"] = version

    monkeypatch.setattr(embed_module, "store_payload_version", _store)
    monkeypatch.setattr(embed_module, "payload_version_lock", _lock_acquired)
    service = _fake_service()

    async def reindex():
        calls.append(1)
        return {"events": {}, "venues": {}}

    service.reindex_hybrid = reindex
    first = asyncio.run(service.ensure_payload_version())
    second = asyncio.run(service.ensure_payload_version())

    assert first["reindexed"] is True and first["mismatch"] is False
    assert second == {"checked": False, "reason": "already_checked",
                      "applied": embed_module.PAYLOAD_VERSION,
                      "expected": embed_module.PAYLOAD_VERSION,
                      "mismatch": False}
    assert calls == [1]  # once per process, not per call
    assert writes == [embed_module.PAYLOAD_VERSION]


def test_payload_version_match_skips_reindex(monkeypatch):
    calls = []
    monkeypatch.setattr(embed_module, "applied_payload_version",
                        lambda url: embed_module.PAYLOAD_VERSION)
    monkeypatch.setattr(embed_module, "store_payload_version",
                        lambda *args, **kwargs: None)
    monkeypatch.setattr(embed_module, "payload_version_lock", _lock_acquired)
    service = _fake_service()

    async def reindex():  # pragma: no cover - must not run
        calls.append(1)

    service.reindex_hybrid = reindex
    result = asyncio.run(service.ensure_payload_version())

    assert result["reindexed"] is False and result["mismatch"] is False
    assert calls == []


def test_payload_version_reindex_failure_keeps_old_version(monkeypatch):
    writes = []
    monkeypatch.setattr(embed_module, "applied_payload_version", lambda url: 1)
    monkeypatch.setattr(embed_module, "store_payload_version",
                        lambda *args, **kwargs: writes.append(args))
    monkeypatch.setattr(embed_module, "payload_version_lock", _lock_acquired)
    service = _fake_service()

    async def boom():
        raise RuntimeError("qdrant down")

    service.reindex_hybrid = boom
    result = asyncio.run(service.ensure_payload_version())  # does not raise

    assert result["reindexed"] is False
    assert result["mismatch"] is True
    assert result["applied"] == 1
    assert "qdrant down" in result["error"]
    assert writes == []


def test_payload_version_skips_when_lock_is_held_elsewhere(monkeypatch):
    calls = []
    monkeypatch.setattr(embed_module, "applied_payload_version", lambda url: 1)
    monkeypatch.setattr(embed_module, "payload_version_lock", _lock_busy)
    service = _fake_service()

    async def reindex():  # pragma: no cover - must not run
        calls.append(1)

    service.reindex_hybrid = reindex
    result = asyncio.run(service.ensure_payload_version())

    assert result["reason"] == "locked" and result["reindexed"] is False
    assert calls == []


def test_reindex_hybrid_records_payload_version(monkeypatch):
    service = _fake_service()
    recorded = []
    monkeypatch.setattr(service, "record_payload_version",
                        lambda: recorded.append(embed_module.PAYLOAD_VERSION))

    async def fake_collection(store, name, fetch_rows, text_of, payload_of):
        return {"patched": 0}

    monkeypatch.setattr(service, "_reindex_collection", fake_collection)
    assert asyncio.run(service.reindex_hybrid()) == {
        "events": {"patched": 0}, "venues": {"patched": 0}}
    assert recorded == [embed_module.PAYLOAD_VERSION]



def test_event_payload_exposes_bycard_film_meta():
    from datetime import datetime, timezone

    from app.services.embed_service import _event_payload

    row = {
        "title": "Турбозавры. Суперфильм", "source": "ticketpro",
        "city": "Минск", "category": "film", "venue_name": "SKYLINE Cinema",
        "description": "Мультфильм", "address": None,
        "start_at": datetime(2026, 11, 26, tzinfo=timezone.utc),
        "end_at": None, "price_min": 8, "price_max": 18,
        "booking_event_id": None, "status": "scheduled", "age_limit": 6,
        "currency": "BYN", "capacity": None, "seats_left": None,
        "venue_id": None, "venue_lat": None, "venue_lon": None,
        "venue_rating": None, "venue_review_count": None,
        "fetched_at": None,
        "film_meta": {"genre": ["Мультфильм"], "duration": "PT75M",
                      "duration_minutes": 75, "description_present": True},
    }
    payload = _event_payload(row)
    assert payload["film_genre"] == ["Мультфильм"]
    assert payload["film_duration_min"] == 75
