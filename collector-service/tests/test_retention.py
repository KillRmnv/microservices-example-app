from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.services.retention_service import RetentionService


def _insert(conn, slug, start_at, last_seen, source="telegram"):
    row = conn.execute(
        """INSERT INTO collected_events
               (source, source_id, source_url, title, start_at, last_seen_at)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (source, slug, f"https://example.com/{slug}", slug,
         start_at, last_seen)).fetchone()
    conn.commit()
    return str(row["id"])


def test_retention_removes_past_and_undated_but_keeps_future(database_url, conn):
    now = datetime.now(timezone.utc)
    old_past = _insert(conn, "old-past", now - timedelta(days=40), now)
    undated = _insert(conn, "undated", None, now - timedelta(days=60))
    future = _insert(conn, "future", now + timedelta(days=10), now)
    booking = _insert(conn, "booking-old", now - timedelta(days=40), now,
                      source="booking")

    settings = Settings(event_retention_days=30, stale_event_days=45,
                        cleanup_batch=100)
    removed = RetentionService(database_url, settings).purge()

    assert set(removed) == {old_past, undated}
    remaining = {str(row["id"]) for row in conn.execute(
        "SELECT id FROM collected_events").fetchall()}
    assert future not in removed and booking not in removed
    assert future in remaining and booking in remaining
