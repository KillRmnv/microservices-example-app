"""Unit tests for emoji / Telegram-decoration cleanup (no database needed)."""
from __future__ import annotations

from app.text import clean_text, strip_emoji


def test_strip_emoji_removes_pictographs_and_dingbats():
    text = "Привет 🌸 мир 🎉 ✅ ❌ ➡️ ⭐ ❤️"
    cleaned = strip_emoji(text)
    for symbol in ("🌸", "🎉", "✅", "❌", "➡", "⭐", "❤"):
        assert symbol not in cleaned
    assert "Привет" in cleaned and "мир" in cleaned


def test_strip_emoji_removes_emoji_variant_arrows():
    assert strip_emoji("↔️") == ""
    assert strip_emoji("Смотри ➡️ дальше") == "Смотри  дальше"


def test_strip_emoji_removes_flags_and_skin_tone_modifiers():
    assert "🇧🇾" not in strip_emoji("🇧🇾 Минск")
    assert "🏳️‍🌈" not in strip_emoji("🏳️‍🌈")
    assert strip_emoji("👍🏽") == ""
    assert strip_emoji("👨‍👩‍👧") == ""


def test_strip_emoji_removes_variation_selectors_and_zero_width():
    assert strip_emoji("❤️") == ""                 # FE0F variation selector
    assert strip_emoji("Мин\u200bск\ufeff") == "Минск"  # ZWSP + BOM
    assert strip_emoji("а\u200dб\u2060в") == "абв"      # ZWJ + word joiner
    assert strip_emoji("1️⃣") == "1"                # keycap sequence


def test_clean_text_strips_telegram_decoration():
    raw = (
        "🔥 КОНЦЕРТ 🔥\n"
        "────────────\n"
        "**Джазовый вечер**\n"
        "_Клуб «Тестовый»_\n\n"
        "📍 ул. Примерная, 1\n"
        "💵 от 25 руб.\n"
        "||секрет||\n\n\n"
        "Ссылка: https://t.me/example/1"
    )
    assert clean_text(raw) == (
        "КОНЦЕРТ\n"
        "Джазовый вечер\n"
        "Клуб «Тестовый»\n\n"
        "ул. Примерная, 1\n"
        "от 25 руб.\n"
        "секрет\n\n"
        "Ссылка: https://t.me/example/1"
    )


def test_clean_text_keeps_russian_text_punctuation_and_urls():
    url = "https://example.com/a_b__c?x=1"
    assert clean_text(f"Смотри {url} — билеты.") == f"Смотри {url} — билеты."
    assert clean_text("[билеты](https://tickets.example/event?id=1)") == (
        "билеты (https://tickets.example/event?id=1)")
    assert clean_text("t.me/channel/123") == "t.me/channel/123"


def test_clean_text_preserves_paragraphs_and_collapses_spaces():
    text = "Первая строка\n\n\nВторая   строка\tс пробелами"
    assert clean_text(text) == "Первая строка\n\nВторая строка с пробелами"
    assert clean_text("a   b\nc") == "a b\nc"


def test_clean_text_drops_symbol_only_lines_but_keeps_punctuation():
    assert clean_text("Заголовок\n••••\n***\nТекст") == "Заголовок\nТекст"
    assert clean_text("Цена — 25 руб.") == "Цена — 25 руб."


def test_clean_text_empty_values():
    assert clean_text(None) is None
    assert clean_text("") is None
    assert clean_text("   \n\t\n") is None
    assert clean_text("🌸🎉") is None


def test_clean_text_is_idempotent():
    raw = "🎉 **Событие** 🎉\n\n\n📍 Минск"
    once = clean_text(raw)
    assert once is not None
    assert clean_text(once) == once


def test_raw_event_cleans_title_and_description():
    from app.models.catalog import RawEvent

    event = RawEvent(
        source="telegram",
        source_id="1",
        source_url="https://t.me/example/1",
        title="🎉 Джазовый вечер 🎉",
        description="Текст описания 🔥\n\n────────\nПродолжение",
    )
    assert event.title == "Джазовый вечер"
    assert event.description == "Текст описания\n\nПродолжение"
