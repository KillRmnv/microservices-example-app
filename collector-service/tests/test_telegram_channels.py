"""Channel config, adapter counters, preview and rescore tests."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import httpx

from app.core.config import Settings, settings
from app.clients.http import PoliteClient
from app.sources.base import CollectContext
from app.sources.telegram import (TelegramAdapter, detect_category,
                                  message_time, scan_price, scan_venue)
from app.services.telegram_service import TelegramService
from conftest import pg_url


def _page(channel: str, *posts: str, start_id: int = 100) -> str:
    wraps = []
    for offset, text in enumerate(posts):
        message_id = start_id + offset
        wraps.append(f"""
        <div class="tgme_widget_message_wrap">
          <div class="tgme_widget_message" data-post="{channel}/{message_id}">
            <div class="tgme_widget_message_text">{text}</div>
            <a class="tgme_widget_message_date" href="https://t.me/{channel}/{message_id}">
              <time datetime="2026-11-20T10:00:00+00:00"></time>
            </a>
          </div>
        </div>""")
    return "<html><body>" + "".join(wraps) + "</body></html>"


VALID = "Концерт «Тестовый» 25 декабря в 19:00\n📍 Клуб «Тестовый»\n💵 от 25 руб."
HOUSING = "Сдам квартиру на сутки, риэлтор, звоните"
JOBS = "Стажировка в IT: резюме и собеседование"
AD = "Розыгрыш сертификата! Подпишись и переходи по ссылке"


def test_channel_config_merge_and_per_channel_maps():
    configured = Settings(
        telegram_channels="Minsk_kuda,kuda_shodit_by",
        telegram_channels_extra="minsk_kuda,Minsk_kudaGo,deti_minsk",
        telegram_channel_pages="Minsk_kudaGo:2,deti_minsk:3",
        telegram_channel_rules="adpachinak:no_housing,"
                               "eventsforstudents:no_jobs,"
                               "merkzy_kokobay:strict_event,"
                               "paci_hub_minsk:no_companion_search",
        telegram_undated_ok="mafia_meets,minsk_detskiy,deti_minsk",
        telegram_channel_categories="minsk_detskiy:kids",
    )
    assert configured.telegram_channel_list() == [
        "Minsk_kuda", "kuda_shodit_by", "Minsk_kudaGo", "deti_minsk"]
    assert configured.telegram_pages_for("MINSK_KUDAGO") == 2
    assert configured.telegram_pages_for("deti_minsk") == 3
    assert configured.telegram_pages_for("unknown") is None
    assert configured.telegram_rule_flags("adpachinak") == {"no_housing"}
    assert configured.telegram_rule_flags("merkzy_kokobay") == {"strict_event"}
    assert "deti_minsk" in configured.telegram_undated_ok_set()
    assert configured.telegram_category_for("minsk_detskiy") == "kids"


def test_default_channel_list_covers_user_handles():
    configured = Settings()
    handles = {handle.casefold() for handle in configured.telegram_channel_list()}
    assert {"minsk_kuda", "kuda_shodit_by", "minsk_kudago", "adpachinak",
            "mafia_meets", "paci_hub_minsk", "eventsforstudents",
            "minsk_detskiy", "deti_minsk", "skyline_by",
            "cinemascopeby"} <= handles
    # Dead/private previews are not fetched at all: they only produced errors.
    assert not {"ominske", "cityminsk", "merkzy_kokobay"} & handles
    # Film channels: pages=2, film default, hard junk filtered out.
    for channel in ("skyline_by", "cinemascopeby"):
        assert configured.telegram_pages_for(channel) == 2
        assert configured.telegram_category_for(channel) == "film"
        assert configured.telegram_rule_flags(channel) == {
            "no_housing", "no_jobs", "no_ad"}
    # Probe gate: below 40% keep -> observe only.
    assert {"adpachinak", "mafia_meets"} <= configured.telegram_observe_set()


def test_posted_at_is_reference_for_relative_dates():
    message = {"id": 1, "posted_at": "2026-10-20T10:00:00+00:00",
               "text": "Завтра в 19:00 концерт в клубе «Тестовый»"}
    fallback = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
    reference = message_time(message, fallback)
    assert reference == datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)
    adapter = TelegramAdapter(channels=["x"])
    event = adapter.normalize("x", message, reference)
    assert event is not None
    # 21 Oct 19:00 Minsk == 16:00 UTC, not "tomorrow" relative to today.
    assert event.start_at == datetime(2026, 10, 21, 16, 0, tzinfo=timezone.utc)


def test_hashtag_and_keyword_categories_override_channel_default():
    assert detect_category("minsk_detskiy", "Событие без маркеров") == "kids"
    assert detect_category("minsk_detskiy", "Концерт 25.10") == "concert"
    assert detect_category("minsk_detskiy", "Спектакль #квиз") == "other"
    assert detect_category("minsk_detskiy", "#детям спектакль") == "kids"


def test_venue_and_price_fallback_without_emoji_sections():
    text = ("Джазовый вечер\n25 октября в 20:00\n"
            "Клуб «Тестовый», ул. Примерная, 1\nБилеты от 25 руб.")
    title = "Джазовый вечер"
    assert scan_venue(text, title) == "Клуб «Тестовый», ул. Примерная, 1"
    assert scan_price(text) == "Билеты от 25 руб."
    message = {"id": 7, "text": text, "posted_at": None}
    event = TelegramAdapter(channels=["x"]).normalize(
        "x", message, datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc))
    assert event.venue_name == "Клуб «Тестовый», ул. Примерная, 1"
    assert event.price_min == 25.0


def test_title_skips_cta_lines():
    message = {"id": 8, "text": "Жми по ссылке\nКонцерт 25 декабря в клубе"}
    event = TelegramAdapter(channels=["x"]).normalize(
        "x", message, datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc))
    assert event.title == "Концерт 25 декабря в клубе"


def test_collect_counts_reasons_and_stores_channel_stats(conn):
    html = _page("counters_test", HOUSING, JOBS, AD, VALID)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    http = PoliteClient(user_agent="test/0.1", default_min_interval_s=0,
                        transport=httpx.MockTransport(handler))
    ctx = CollectContext(http=http, db_url=pg_url())
    stats = asyncio.run(TelegramAdapter(
        channels=["counters_test"], max_pages=1).collect(ctx))
    assert (stats.parsed, stats.rows_inserted) == (1, 1)
    row = conn.execute(
        "SELECT value FROM collector_kv WHERE key = 'telegram:stats:counters_test'"
    ).fetchone()
    counters = json.loads(row["value"])
    assert counters["fetched"] == 4 and counters["kept"] == 1
    assert counters["dropped_housing"] == 1
    assert counters["dropped_jobs"] == 1
    assert counters["dropped_ad"] == 1
    assert counters["keep_ratio"] == 0.25


def test_observe_mode_classifies_but_does_not_write(conn, monkeypatch):
    monkeypatch.setattr(settings, "telegram_observe_channels", "observe_test")
    html = _page("observe_test", VALID)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    http = PoliteClient(user_agent="test/0.1", default_min_interval_s=0,
                        transport=httpx.MockTransport(handler))
    ctx = CollectContext(http=http, db_url=pg_url())
    stats = asyncio.run(TelegramAdapter(
        channels=["observe_test"], max_pages=1).collect(ctx))
    assert stats.parsed == 0
    assert conn.execute(
        "SELECT count(*) AS n FROM collected_events").fetchone()["n"] == 0
    counters = json.loads(conn.execute(
        "SELECT value FROM collector_kv"
        " WHERE key = 'telegram:stats:observe_test'").fetchone()["value"])
    assert counters["kept"] == 1


def test_preview_classifies_without_writing(conn):
    html = _page("preview_test", VALID, HOUSING)

    def handler(request: httpx.Request) -> httpx.Response:
        if "before=" in str(request.url):
            return httpx.Response(200, text="<html></html>")
        return httpx.Response(200, text=html)

    http = PoliteClient(user_agent="test/0.1", default_min_interval_s=0,
                        transport=httpx.MockTransport(handler))
    result = asyncio.run(TelegramService(http, pg_url()).preview(
        "preview_test", pages=2, limit=50))
    assert result["summary"] == {"total": 2, "kept": 1,
                                 "dropped_by_reason": {"housing": 1},
                                 "keep_ratio": 0.5}
    assert result["messages"][0]["keep"] is True
    assert result["messages"][1]["reason"] == "housing"
    assert result["observe"] is False
    assert conn.execute(
        "SELECT count(*) AS n FROM collected_events").fetchone()["n"] == 0


def _insert_event(conn, slug: str, title: str, source="telegram",
                  channel="adpachinak"):
    conn.execute(
        """INSERT INTO collected_events
               (source, source_id, source_url, title, description, raw)
           VALUES (%s, %s, %s, %s, %s, %s::jsonb)""",
        (source, slug, f"https://t.me/{channel}/{slug}", title,
         title, json.dumps({"channel": channel})))
    conn.commit()


def test_rescore_dry_run_then_delete_only_hard_junk(conn, database_url):
    _insert_event(conn, "housing", "Сдам квартиру на сутки, риэлтор")
    _insert_event(conn, "valid", "Концерт 25.12 в клубе «Тестовый»")
    _insert_event(conn, "ad", "Розыгрыш сертификата, подпишись")
    _insert_event(conn, "other-source", "Сдам квартиру", source="ticketpro")

    service = TelegramService(http=None, db_url=database_url)
    dry = service.rescore(dry_run=True)
    assert dry["scanned"] == 3
    assert dry["would_delete"] == 2 and dry["deleted"] == 0
    assert dry["by_reason"] == {"housing": 1, "ad": 1}
    assert conn.execute(
        "SELECT count(*) AS n FROM collected_events").fetchone()["n"] == 4
    assert conn.execute(
        "SELECT count(*) AS n FROM collector_kv"
        " WHERE key = 'telegram:rescore:audit'").fetchone()["n"] == 0

    applied = service.rescore(dry_run=False)
    assert applied["deleted"] == 2
    left = {row["source_id"] for row in conn.execute(
        "SELECT source_id FROM collected_events").fetchall()}
    assert left == {"valid", "other-source"}
    audit = json.loads(conn.execute(
        "SELECT value FROM collector_kv"
        " WHERE key = 'telegram:rescore:audit'").fetchone()["value"])
    assert {entry["reason"] for entry in audit["entries"]} == {"housing", "ad"}
