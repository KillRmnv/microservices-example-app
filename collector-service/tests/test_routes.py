"""Controller wiring tests: fixed paths must not be captured by {source}."""
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.clients.http import PoliteClient
from app.main import create_app
from app.services.collect_service import CollectService
from app.services.ops_service import OpsService


class FakeEmbed:
    async def embed_events(self, source="all", limit=None, cap=None):
        return 0, 0

    async def embed_venues(self, limit=None):
        return 0, 0

    async def reindex_hybrid(self):
        return {"events": {"patched": 0, "stored": 0, "rows": 0},
                "venues": {"patched": 0, "stored": 0, "rows": 0}}

    async def delete_events(self, ids):
        return len(ids)


class FakeTelegram:
    async def preview(self, channel, pages=2, limit=50):
        return {"channel": channel, "pages": pages, "observe": False,
                "messages": [],
                "summary": {"total": 0, "kept": 0,
                            "dropped_by_reason": {}, "keep_ratio": 0.0}}

    def rescore(self, dry_run=True):
        return {"dry_run": dry_run, "scanned": 0, "would_delete": 0,
                "deleted": 0, "by_reason": {}, "samples": [],
                "other_dropped": {}, "deleted_ids": []}


class FakeAtmosphere:
    def enrich(self, limit=200, force=False):
        return {"venues": 0, "tagged": 0, "updated": 0, "unchanged": 0,
                "limit": limit, "force": force}


class FakeTicketpro:
    async def enrich(self, limit=10):
        return {"fetched": 0, "updated": 0, "skipped": 0, "failed": 0,
                "limit": limit}


class FakeFilmMetadata:
    async def enrich(self, limit=10, dry_run=True):
        return {"dry_run": dry_run, "limit": limit, "fetched": 0}


def test_fixed_paths_are_not_swallowed_by_path_params(database_url):
    app = create_app()
    app.state.db_url = database_url
    app.state.collect = CollectService(
        PoliteClient(user_agent="test/0.1", default_min_interval_s=0),
        database_url,
    )
    app.state.ops = OpsService(database_url, Settings())
    app.state.embed = FakeEmbed()
    client = TestClient(app)

    health = client.get("/collect/health")
    assert health.status_code == 200
    assert "sources" in health.json()

    venues = client.post("/embed/venues")
    assert venues.status_code == 200
    assert venues.json()["embedded"] == 0

    denied = client.post("/embed/reindex-hybrid")
    assert denied.status_code == 400
    assert denied.json()["code"] == "reindex_confirmation_required"

    reindexed = client.post("/embed/reindex-hybrid?confirm=true")
    assert reindexed.status_code == 200
    assert reindexed.json()["events"]["patched"] == 0


def test_enrichment_paths_are_not_swallowed_by_source_catch_all():
    app = create_app()
    app.state.atmosphere = FakeAtmosphere()
    app.state.ticketpro_details = FakeTicketpro()
    app.state.film_metadata = FakeFilmMetadata()
    client = TestClient(app)

    atmosphere = client.post("/collect/atmosphere?limit=5&force=true")
    assert atmosphere.status_code == 200
    assert atmosphere.json() == {"venues": 0, "tagged": 0, "updated": 0,
                                 "unchanged": 0, "limit": 5, "force": True}

    details = client.post("/collect/ticketpro_details?limit=3")
    assert details.status_code == 200
    assert details.json()["limit"] == 3
    assert details.json()["updated"] == 0

    film = client.post("/collect/film_metadata?limit=10")
    assert film.status_code == 200
    assert film.json()["dry_run"] is True


def test_telegram_preview_and_rescore_paths():
    app = create_app()
    app.state.telegram = FakeTelegram()
    app.state.embed = FakeEmbed()
    client = TestClient(app)

    preview = client.post("/collect/telegram_preview?channel=minsk_kuda")
    assert preview.status_code == 200
    assert preview.json()["summary"]["total"] == 0

    rescore = client.post("/collect/telegram_rescore?dry_run=true")
    assert rescore.status_code == 200
    assert rescore.json()["dry_run"] is True
    assert "deleted_ids" not in rescore.json()
