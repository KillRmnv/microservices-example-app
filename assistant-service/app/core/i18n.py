"""Message catalogs (ru/en) for user-facing assistant strings.

Only presentation lives here; source data such as venue titles is never
translated. Formatting uses ``str.format`` with named parameters so catalog
entries stay reviewable.
"""
from __future__ import annotations

from typing import Any

DEFAULT_LOCALE = "ru"

CATALOG: dict[str, dict[str, str]] = {
    "ru": {
        "filters_locked": "Условия поиска зафиксированы.",
        "search_empty": (
            "По этим условиям ничего не нашлось. "
            "Смягчите фильтры или уточните дату."),
        "search_results": "Вот что нашлось:",
        "clarify_date": (
            "На какую дату и время ищем?{hint} "
            "Например: «в субботу вечером»."),
        "clarify_booking": (
            "Бронирование через ассистента появится позже. "
            "Пока оформите билет на странице события."),
        "weather_unavailable": "Прогноз недоступен.",
        "weather_rain": (
            "{date}: дождь вероятен ({probability}%), макс. {temp}°. "
            "Уличное лучше перенести в помещение."),
        "weather_dry": (
            "{date}: без дождя ({probability}%), макс. {temp}°. "
            "Для прогулки подходит."),
        "card_untitled": "Без названия",
        "card_scraped": "Внешняя афиша — наличие уточняйте у источника",
        "price_unknown": "цена уточняется",
        "price_range": "{price_min:g}–{price_max:g} {currency}",
        "price_from": "от {price_min:g} {currency}",
        "currency_byn": "руб.",
        "availability_available": "места есть",
        "availability_few_left": "осталось мало",
        "availability_sold_out": "распродано",
        "availability_unknown": "наличие неизвестно",
        "geo_center": "центр: {city}",
    },
    "en": {
        "filters_locked": "Search conditions are locked in.",
        "search_empty": (
            "Nothing matched these filters. "
            "Try loosening them or picking another date."),
        "search_results": "Here is what we found:",
        "clarify_date": (
            "Which date and time should we look for?{hint} "
            "For example: “Saturday evening”."),
        "clarify_booking": (
            "Booking through the assistant is not available yet. "
            "Please buy a ticket on the event page."),
        "weather_unavailable": "Forecast is unavailable.",
        "weather_rain": (
            "{date}: rain is likely ({probability}%), high {temp}°C. "
            "Consider an indoor activity."),
        "weather_dry": (
            "{date}: no rain ({probability}%), high {temp}°C. "
            "Good for a walk."),
        "card_untitled": "Untitled",
        "card_scraped": "External listing — check availability with the source",
        "price_unknown": "price on request",
        "price_range": "{price_min:g}–{price_max:g} {currency}",
        "price_from": "from {price_min:g} {currency}",
        "currency_byn": "BYN",
        "availability_available": "tickets available",
        "availability_few_left": "few left",
        "availability_sold_out": "sold out",
        "availability_unknown": "availability unknown",
        "geo_center": "center of {city}",
    },
}

# Currency display suffix per locale; unknown codes fall back to the ISO code.
CURRENCY_SUFFIX: dict[str, dict[str, str]] = {
    "ru": {"BYN": "currency_byn"},
    "en": {"BYN": "currency_byn"},
}


def resolve_locale(language: str | None) -> str:
    """Map an arbitrary language tag to a supported catalog (default ru)."""
    if not language:
        return DEFAULT_LOCALE
    base = language.strip().lower().split("-", 1)[0].split("_", 1)[0]
    return base if base in CATALOG else DEFAULT_LOCALE


def t(key: str, language: str | None = None, **params: Any) -> str:
    locale = resolve_locale(language)
    template = CATALOG[locale].get(key) or CATALOG[DEFAULT_LOCALE].get(key) or key
    return template.format(**params)


def currency_label(currency: str | None, language: str | None = None) -> str:
    code = (currency or "").upper()
    key = CURRENCY_SUFFIX.get(resolve_locale(language), {}).get(code)
    return t(key, language) if key else (code or "")


def format_price(price_min: float | None, price_max: float | None,
                 currency: str | None = None,
                 language: str | None = None) -> str:
    """Human price text; unknown prices degrade to "price on request"."""
    if price_min is None:
        return t("price_unknown", language)
    suffix = currency_label(currency, language)
    if price_max is not None and price_max != price_min:
        return t("price_range", language, price_min=price_min,
                 price_max=price_max, currency=suffix)
    return t("price_from", language, price_min=price_min, currency=suffix)
