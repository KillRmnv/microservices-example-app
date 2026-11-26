import httpx
import pytest

from app.core.config import Settings
from app.repositories import runs
from app.scheduler import advisory_lock
from app.services.ops_service import degraded_sources, post_alert, render_metrics


def test_schedule_map_parsing():
    settings = Settings(schedules="ticketpro:21600,relax:86400,bad,nope:abc")
    assert settings.schedule_map() == {"ticketpro": 21600, "relax": 86400}


def _seed_run(conn, source, status, rows_inserted, parse_errors=0):
    conn.execute(
        """INSERT INTO source_runs (source, status, started_at, finished_at,
                                    fetched, parsed, parse_errors, rows_inserted)
           VALUES (%s, %s, now(), now(), 1, 1, %s, %s)""",
        (source, status, parse_errors, rows_inserted),
    )
    conn.commit()


def test_source_health_flags_degraded(conn):
    _seed_run(conn, "good", "ok", 5)
    _seed_run(conn, "good", "ok", 3)
    _seed_run(conn, "dry", "ok", 0)
    _seed_run(conn, "dry", "ok", 0)
    _seed_run(conn, "broken", "error", 0)
    _seed_run(conn, "broken", "ok", 4)
    health = {entry["source"]: entry for entry in runs.health(conn, window=2)}
    assert health["good"]["degraded"] is False
    assert health["dry"]["degraded"] is True  # 0 new twice in a row
    assert health["broken"]["degraded"] is True  # last window has an error
    assert degraded_sources(list(health.values())) == ["broken", "dry"]


def test_advisory_lock_exclusive(conn):
    from app.core import db
    from tests.conftest import pg_url
    with advisory_lock(pg_url(), "collect:test") as first:
        assert first is True
        with db.get_conn(pg_url()) as other:
            # Same session would succeed; a second backend must fail.
            # Simulate by direct SQL on the other connection.
            locked = other.execute(
                "SELECT pg_try_advisory_lock(hashtext('collect:test')) AS locked"
            ).fetchone()["locked"]
            assert locked is False
    with advisory_lock(pg_url(), "collect:test") as again:
        assert again is True


@pytest.mark.asyncio
async def test_post_alert_posts_degraded_only():
    posted = []

    def handler(request: httpx.Request) -> httpx.Response:
        posted.append(request)
        return httpx.Response(200, text="ok")

    assert await post_alert("http://hook/x", [], transport=httpx.MockTransport(handler)) is False
    assert posted == []
    assert await post_alert("", ["dry"], transport=httpx.MockTransport(handler)) is False
    assert await post_alert("http://hook/x", ["dry", "broken"],
                            transport=httpx.MockTransport(handler)) is True
    import json
    body = json.loads(posted[0].read().decode())
    assert "dry" in body["text"] and "broken" in body["text"]


def test_collect_metrics_format(conn):
    _seed_run(conn, "ticketpro", "ok", 5, parse_errors=2)
    conn.execute(
        """INSERT INTO collected_events (source, source_id, source_url, title)
           VALUES ('ticketpro', 'x1', 'http://x/1', 'Концерт')""")
    conn.commit()
    text = render_metrics(runs.metrics(conn))
    assert 'collector_events_total{source="ticketpro"} 1' in text
    assert 'collector_runs_total{source="ticketpro",status="ok"} 1' in text
    assert 'collector_parse_errors_total{source="ticketpro"} 2' in text
    assert 'collector_last_run_unixtime{source="ticketpro"} ' in text
