from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.sources.telegram import (
    TelegramAdapter,
    extract_messages,
    first_meaningful_line,
    scan_venue,
    split_sections,
)
from app.parsing.text_ru import parse_ru_datetime
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


def test_parse_ru_datetime_invalid_day_is_none():
    # "31 февраля" is malformed, not an event: must not raise (a channel run
    # used to die with "day is out of range for month").
    assert parse_ru_datetime("31 февраля в 19:00", NOW) is None
    assert parse_ru_datetime("31 апреля, 20:00", NOW) is None


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
    from app.clients.http import PoliteClient
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
    assert stats.rows_inserted == 2
    assert any("before=1101" in url for url in seen)  # min(1108, 1102) - 1
    rows = conn.execute("SELECT source_id FROM collected_events").fetchall()
    assert {row["source_id"] for row in rows} == {"minsk_kuda/1108", "minsk_kuda/1102"}


def test_telegram_extracts_photo_background():
    html = """
    <div class="tgme_widget_message_wrap">
      <div class="tgme_widget_message" data-post="minsk_kuda/2000">
        <a class="tgme_widget_message_photo_wrap"
           style="background-image:url('https://cdn4.telesco.pe/file/poster.jpg')"></a>
        <div class="tgme_widget_message_text">Джазовый вечер\n⏰ 25 октября, в 20:00</div>
        <time datetime="2026-10-20T12:00:00+00:00"></time>
        <a class="tgme_widget_message_date" href="https://t.me/minsk_kuda/2000"></a>
      </div>
    </div>
    """
    messages = extract_messages(html)
    assert messages[0]["image"] == "https://cdn4.telesco.pe/file/poster.jpg"
    event = TelegramAdapter(channels=["minsk_kuda"]).normalize(
        "minsk_kuda", messages[0], NOW)
    assert event is not None
    assert event.image_url == "https://cdn4.telesco.pe/file/poster.jpg"


def test_telegram_extracts_video_thumb_when_no_photo():
    html = """
    <div class="tgme_widget_message_wrap">
      <div class="tgme_widget_message" data-post="minsk_kuda/2001">
        <i class="tgme_widget_message_video_thumb"
           style="background-image:url('https://cdn4.telesco.pe/file/thumb.jpg')"></i>
        <div class="tgme_widget_message_text">Событие</div>
      </div>
    </div>
    """
    assert extract_messages(html)[0]["image"] == (
        "https://cdn4.telesco.pe/file/thumb.jpg")


def test_venue_section_is_trimmed_to_the_first_line():
    message = {
        "id": 9,
        "text": (
            "Кино и анимация в Гастросквере\n"
            "25 декабря в 12:00\n"
            "📍 Гастросквер «Манифест», ул. Кульман, 1/8\n"
            "вход свободный\n"
            "Для детей: мультфильм и шоу\n"
            "#киноминск #бесплатно\n"
            "Телефон: +375 17 000-00-00"),
        "posted_at": None,
    }
    event = TelegramAdapter(channels=["x"]).normalize(
        "x", message, datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc))
    assert event is not None
    assert event.venue_name == "Гастросквер «Манифест», ул. Кульман, 1/8"


def test_scan_venue_skips_hashtags_and_links():
    assert scan_venue("#киноминск\nПодробнее: https://t.me/x") is None


def test_link_preview_image_is_extracted():
    html = """
    <div class="tgme_widget_message_wrap">
      <div class="tgme_widget_message text_not_supported_wrap js-widget_message"
           data-post="minsk_detskiy/1876">
        <div class="tgme_widget_message_text">Выставка «Кот и осень»</div>
        <a class="tgme_widget_message_link_preview" href="https://example.com">
          <img src="https://cdn4.telesco.pe/file/link-preview.jpg" />
        </a>
        <a class="tgme_widget_message_date" href="https://t.me/minsk_detskiy/1876">
          <time datetime="2026-11-20T10:00:00+00:00"></time>
        </a>
      </div>
    </div>
    """
    messages = extract_messages(html)
    assert messages[0]["image"] == "https://cdn4.telesco.pe/file/link-preview.jpg"


def test_link_preview_background_image_is_extracted():
    html = """
    <div class="tgme_widget_message_wrap">
      <div class="tgme_widget_message" data-post="ch/2">
        <div class="tgme_widget_message_text">Событие</div>
        <a class="tgme_widget_message_link_preview">
          <div class="tgme_widget_message_link_preview_image"
               style="background-image:url('https://cdn4.telesco.pe/file/bg.jpg')"></div>
        </a>
      </div>
    </div>
    """
    assert extract_messages(html)[0]["image"] == "https://cdn4.telesco.pe/file/bg.jpg"


def test_text_not_supported_image_and_photo_priority():
    text_only = """
    <div class="tgme_widget_message_wrap">
      <div class="tgme_widget_message text_not_supported_wrap" data-post="ch/3">
        <img src="https://cdn4.telesco.pe/file/fallback.jpg" />
        <div class="tgme_widget_message_text">Пост</div>
      </div>
    </div>
    """
    assert extract_messages(text_only)[0]["image"] == "https://cdn4.telesco.pe/file/fallback.jpg"
    photo_and_preview = """
    <div class="tgme_widget_message_wrap">
      <div class="tgme_widget_message" data-post="ch/4">
        <a class="tgme_widget_message_photo_wrap"
           style="background-image:url('https://cdn4.telesco.pe/file/photo.jpg')"></a>
        <a class="tgme_widget_message_link_preview"><img src="https://x/preview.jpg" /></a>
        <div class="tgme_widget_message_text">Пост</div>
      </div>
    </div>
    """
    assert extract_messages(photo_and_preview)[0]["image"].endswith("photo.jpg")
