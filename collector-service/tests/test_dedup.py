from datetime import datetime, timedelta, timezone

from app.models.dedup import compare, title_similarity
from app.models.catalog import RawEvent


def event(title: str, start=None, venue="Дворец спорта", category="concert"):
    return RawEvent(source="telegram", source_id=title, source_url="x",
                    title=title, start_at=start, venue_name=venue,
                    category=category, city="Минск")


def candidate(title: str, start=None, venue="Дворец спорта", category="concert"):
    return {"title": title, "start_at": start, "end_at": None,
            "venue_name": venue, "venue_id": None, "category": category}


def test_title_prefix_and_quotes_are_similar():
    assert title_similarity("Концерт «Кипелов»", "Кипелов") >= 0.9


def test_same_event_with_one_missing_date_is_kept_for_review():
    start = datetime(2026, 11, 27, 19, tzinfo=timezone.utc)
    decision = compare(
        event("ХХ Фестиваль духовной музыки", start=start,
              venue="Архикафедральный костёл"),
        candidate("ХХ Фестиваль духовной музыки",
                  venue="Архикафедральный костёл"))
    assert not decision.merge
    assert decision.reason == "undated"


def test_same_title_different_dates_stays_separate():
    first = datetime(2026, 12, 16, 16, tzinfo=timezone.utc)
    second = datetime(2026, 12, 28, 16, tzinfo=timezone.utc)
    decision = compare(event("Динамо-Минск vs Северсталь", start=first),
                       candidate("Динамо-Минск vs Северсталь", start=second))
    assert not decision.merge
    assert decision.reason == "time"


def test_different_venues_stays_separate():
    start = datetime(2026, 12, 16, 16, tzinfo=timezone.utc)
    decision = compare(event("Бесплатные кинопоказы", start=start,
                             venue="Дворец спорта"),
                       candidate("Бесплатные кинопоказы", start=start,
                                 venue="Культурное пространство Эхо"))
    assert not decision.merge


def test_category_conflict_stays_separate():
    start = datetime(2026, 12, 16, 16, tzinfo=timezone.utc)
    decision = compare(event("Событие", start=start, category="concert"),
                       candidate("Событие", start=start, category="theatre"))
    assert not decision.merge


def test_same_event_from_two_sources_merges():
    start = datetime(2026, 12, 16, 16, tzinfo=timezone.utc)
    decision = compare(
        event("Концерт «Кипелов»", start=start),
        candidate("Кипелов", start=start + timedelta(hours=1)))
    assert decision.merge


def _raw(source, source_id, title, start, venue="Дворец спорта"):
    return RawEvent(source=source, source_id=source_id,
                    source_url=f"https://example.com/{source_id}",
                    title=title, start_at=start, venue_name=venue,
                    category="concert", city="Минск")


def test_store_merges_cross_source_duplicate(conn):
    from app.repositories.store import upsert_events

    start = datetime(2026, 12, 16, 16, tzinfo=timezone.utc)
    first = _raw("ticketpro", "tp-1", "Концерт «Кипелов»", start)
    second = _raw("telegram", "tg-1", "Кипелов",
                  start + timedelta(hours=1))
    assert upsert_events(conn, [first]).rows_inserted == 1
    stats = upsert_events(conn, [second])
    assert stats.rows_inserted == 0
    assert stats.duplicates == 1
    rows = conn.execute("SELECT id, title FROM collected_events").fetchall()
    assert len(rows) == 1
    sources = conn.execute(
        "SELECT source FROM event_sources ORDER BY source").fetchall()
    assert [row["source"] for row in sources] == ["telegram", "ticketpro"]


def test_store_keeps_same_title_on_different_days(conn):
    from app.repositories.store import upsert_events

    first = _raw("ticketpro", "tp-2", "Динамо-Минск vs Северсталь",
                 datetime(2026, 12, 16, 16, tzinfo=timezone.utc))
    second = _raw("ticketpro", "tp-3", "Динамо-Минск vs Северсталь",
                  datetime(2026, 12, 28, 16, tzinfo=timezone.utc))
    upsert_events(conn, [first, second])
    rows = conn.execute("SELECT id FROM collected_events").fetchall()
    assert len(rows) == 2


def test_different_opponents_at_same_venue_do_not_merge():
    first = datetime(2026, 12, 4, 16, tzinfo=timezone.utc)
    second = datetime(2026, 12, 6, 14, tzinfo=timezone.utc)
    decision = compare(
        event("Динамо-Минск vs Динамо Москва", start=first,
              venue="Минск-Арена"),
        candidate("Динамо-Минск vs Сочи", start=second,
                  venue="Минск-Арена"))
    assert not decision.merge


def test_consecutive_shows_with_same_title_do_not_merge():
    first = datetime(2026, 11, 26, 17, tzinfo=timezone.utc)
    second = datetime(2026, 11, 27, 17, tzinfo=timezone.utc)
    decision = compare(event("Kai Angel", start=first),
                       candidate("Kai Angel", start=second))
    assert not decision.merge


def test_single_day_shows_on_consecutive_days_do_not_overlap():
    first = datetime(2026, 11, 26, 17, tzinfo=timezone.utc)
    second = datetime(2026, 11, 27, 17, tzinfo=timezone.utc)
    ev = event("Kai Angel", start=first)
    ev.end_at = first + timedelta(hours=1, minutes=40)
    cand = candidate("Kai Angel", start=second)
    cand["end_at"] = second + timedelta(hours=1, minutes=40)
    decision = compare(ev, cand)
    assert not decision.merge
