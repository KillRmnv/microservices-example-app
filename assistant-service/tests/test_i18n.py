from app.core import i18n


def test_price_formats_by_locale():
    assert i18n.format_price(None, None, "BYN", "ru") == "цена уточняется"
    assert i18n.format_price(25, 60, "BYN", "ru") == "25–60 руб."
    assert i18n.format_price(25, 25, "BYN", "ru") == "от 25 руб."
    assert i18n.format_price(None, None, "BYN", "en") == "price on request"
    assert i18n.format_price(25, 60, "BYN", "en") == "25–60 BYN"


def test_unknown_currency_falls_back_to_code():
    assert i18n.format_price(10, None, "EUR", "ru") == "от 10 EUR"


def test_locale_resolution():
    assert i18n.resolve_locale("en-US") == "en"
    assert i18n.resolve_locale("ru_RU") == "ru"
    assert i18n.resolve_locale("de") == "ru"
    assert i18n.resolve_locale(None) == "ru"


def test_missing_key_degrades_to_key():
    assert i18n.t("does.not.exist", "ru") == "does.not.exist"
