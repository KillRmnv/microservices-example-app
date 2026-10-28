"""Controller wiring tests: fixed paths must not be captured by {source}."""
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.http import PoliteClient
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
    assert denied.json()["code"] == "validation_error"

    reindexed = client.post("/embed/reindex-hybrid?confirm=true")
    assert reindexed.status_code == 200
    assert reindexed.json()["events"]["patched"] == 0
