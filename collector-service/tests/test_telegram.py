from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.sources.telegram import (
    TelegramAdapter,
    extract_messages,
    first_meaningful_line,
    split_sections,
)
from app.text_ru import parse_ru_datetime
from conftest import pg_url

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)


def test_extract_messages():
    html = (FIXTURES / "telegram_preview.html").read_text()
    messages = extract_messages(html)
    assert [m["id"] for m in messages] == [1108, 1102]
    assert messages[0]["url"] == "https://t.me/minsk_kuda/1108"
    assert "Джазовый вечер" in messages[0]["text"]


def test_first_meaningful_line_skips_invisible_and_emoji():
    assert first_meaningful_line("​\n🌸\nДжазовый вечер", "fb") == "Джазовый вечер"
    assert first_meaningful_line("​​", "fb") == "fb"
    assert first_meaningful_line("  Обычный заголовок  ", "fb") == "Обычный заголовок"


def test_split_sections():
    sections = split_sections("Джазовый вечер\n⏰ 25 октября (сб), в 20:00\n📍 Клуб «Тестовый»\n💵 от 25 руб.")
    assert sections["date"] == "25 октября (сб), в 20:00"
    assert sections["place"] == "Клуб «Тестовый»"
    assert sections["price"] == "от 25 руб."
    assert split_sections("просто текст без секций") == {}


def test_parse_ru_datetime_day_month():
    parsed = parse_ru_datetime("25 октября (сб), в 20:00", NOW)
    assert parsed is not None
    assert (parsed.year, parsed.month, parsed.day) == (2026, 10, 25)
    assert (parsed.hour, parsed.minute) == (17, 0)  # 20:00+03 -> UTC


def test_parse_ru_datetime_past_returns_none():
    assert parse_ru_datetime("9 октября (пт), в 19:00", NOW) is None


def test_parse_ru_datetime_relative():
    parsed = parse_ru_datetime("завтра в 19:00", NOW)
    assert parsed is not None and (parsed.month, parsed.day) == (10, 24)
    assert parse_ru_datetime("без даты вообще", NOW) is None


def test_telegram_normalize():
    html = (FIXTURES / "telegram_preview.html").read_text()
    messages = extract_messages(html)
    adapter = TelegramAdapter(channels=["minsk_kuda"])
    event = adapter.normalize("minsk_kuda", messages[0], NOW)
    assert event is not None
    assert event.source_id == "minsk_kuda/1108"
    assert event.venue_name == "Клуб «Тестовый», ул. Примерная, 1"
    assert (event.price_min, event.price_max) == (25.0, 25.0)
    assert event.start_at is not None
    past = adapter.normalize("minsk_kuda", messages[1], NOW)
    assert past is not None and past.start_at is None  # 9 октября уже прошло
    assert past.price_min is None  # вход свободный


def test_telegram_collect_paginates(conn):
    from app.http import PoliteClient
    from app.sources.base import CollectContext

    page1 = (FIXTURES / "telegram_preview.html").read_text()
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        seen.append(url)
        if "before=" in url:
            return httpx.Response(200, text="<html><body></body></html>")
        return httpx.Response(200, text=page1)

    http = PoliteClient(user_agent="test/0.1", default_min_interval_s=0,
                        transport=httpx.MockTransport(handler))
    ctx = CollectContext(http=http, db_url=pg_url(), max_urls=None)
    import asyncio
    stats = asyncio.run(TelegramAdapter(channels=["minsk_kuda"], max_pages=5).collect(ctx))
    assert stats.parsed == 2
    assert stats.new_events == 2
    assert any("before=1101" in url for url in seen)  # min(1108, 1102) - 1
    rows = conn.execute("SELECT source_id FROM collected_events").fetchall()
    assert {row["source_id"] for row in rows} == {"minsk_kuda/1108", "minsk_kuda/1102"}
