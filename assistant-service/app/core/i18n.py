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
        "search_more_empty": "Больше вариантов нет — уточните фильтры",
        "search_empty_cinemas": "Событий с датой нет — вот кинотеатры",
        "search_empty_theatres": "Событий с датой нет — вот театры",
        "search_empty_exhibitions": "Событий с датой нет — вот выставки",
        "filters_sep": " · ",
        "filters_item": "{label}: {value}",
        "filters_default_suffix": "(по умолчанию)",
        "filters_label_section": "Раздел",
        "filters_label_date": "Когда",
        "filters_label_city": "Где",
        "filters_label_type": "Тип",
        "filters_label_themes": "Темы",
        "filters_label_company": "Компания",
        "filters_label_budget": "Бюджет",
        "filters_label_amenities": "Удобства",
        "filters_label_rating": "Рейтинг",
        "filters_label_age": "Возраст",
        "filters_label_exclusions": "Исключения",
        "filters_label_event_count": "Событий в плане",
        "filters_section_events": "события",
        "filters_section_venues": "места",
        "filters_section_both": "события и места",
        "filters_date_default": "ближайшие",
        "filters_date_any": "любая",
        "filters_city_any": "любой",
        "filters_city_none": "не указан",
        "filters_type_any": "любые",
        "filters_none": "нет",
        "filters_company_none": "не указана",
        "filters_company_any": "любая",
        "filters_company_value": "{party} чел.",
        "filters_budget_none": "без ограничений",
        "filters_budget_per_person": "до {amount} {currency} на человека",
        "filters_budget_total": "до {amount} {currency} на всех",
        "filters_rating_any": "любой",
        "filters_rating_value": "от {rating:g}",
        "filters_age_any": "любой",
        "filters_age_value": "до {age} лет",
        "filters_list_sep": ", ",
        "category_concert": "концерты",
        "category_theatre": "театр",
        "category_exhibition": "выставки",
        "category_film": "кино",
        "category_sport": "спорт",
        "category_kids": "для детей",
        "category_other": "другое",
        "search_results": "Вот что нашлось:",
        "venue_results": "Вот какие места нашлись:",
        "venue_empty": "Подходящих мест не нашлось. Уточните район или запрос.",
        "assistant_capabilities": (
            "Я помогаю с досугом в Минске: ищу события и места (бары, кафе, "
            "рестораны), учитываю дату, бюджет и компанию, показываю погоду, "
            "собираю план вечера и держу бронь. Спросите, например: «джаз "
            "завтра», «где выпить пива с друзьями» или «план на субботу»."),
        "clarify_date": (
            "На какую дату и время ищем?{hint} "
            "Например: «в субботу вечером»."),
        "clarify_missing": (
            "Уточните, пожалуйста: {missing}. "
            "Для любого варианта можно ответить «не важно»."),
        "clarify_booking": (
            "Бронирование через ассистента появится позже. "
            "Пока оформите билет на странице события."),
        "slot_datetime": "дата",
        "slot_city": "город",
        "slot_budget": "бюджет",
        "slot_party": "количество человек",
        "weather_unavailable": "Прогноз недоступен.",
        "weather_rain": (
            "{date}: дождь вероятен ({probability}%), макс. {temp}°. "
            "Уличное лучше перенести в помещение."),
        "weather_light_rain": (
            "{date}: возможен небольшой дождь ({probability}%), макс. {temp}°. "
            "Возьмите зонт, план можно не менять."),
        "weather_dry": (
            "{date}: без дождя ({probability}%), макс. {temp}°. "
            "Для прогулки подходит."),
        "card_untitled": "Без названия",
        "card_scraped": "наличие уточняйте у источника",
        "card_undated": "дата уточняется",
        "price_unknown": "цена уточняется",
        "price_range": "{price_min:g}–{price_max:g} {currency}",
        "price_from": "от {price_min:g} {currency}",
        "currency_byn": "руб.",
        "availability_available": "места есть",
        "availability_few_left": "осталось мало",
        "availability_sold_out": "распродано",
        "availability_unknown": "наличие неизвестно",
        "card_no_seats": "на {party} человек нет мест",
        "card_hours": "до {close}",
        "card_hours_24_7": "круглосуточно",
        "card_film_run_until": "прокат до {date}",
        "card_film_next_session": "ближайший сеанс {time}",
        "card_film_next_session_cinema": "ближайший сеанс {time} · {cinema}",
        "card_film_duration": "{minutes} мин",
        "card_address": "{address}",
        "venue_closed": "закрыто",
        "meta_rating": "★{rating} · {count} отзывов",
        "weather_adjusted_rain": (
            "{date}: дождь ({probability}%), уличные и террасные варианты "
            "исключены."),
        "geo_center": "центр: {city}",
    },
    "en": {
        "filters_locked": "Search conditions are locked in.",
        "search_empty": (
            "Nothing matched these filters. "
            "Try loosening them or picking another date."),
        "search_more_empty": "No more options — refine the filters",
        "search_empty_cinemas": "No dated events — here are cinemas",
        "search_empty_theatres": "No dated events — here are theatres",
        "search_empty_exhibitions": "No dated events — here are exhibitions",
        "filters_sep": " · ",
        "filters_item": "{label}: {value}",
        "filters_default_suffix": "(default)",
        "filters_label_section": "Section",
        "filters_label_date": "When",
        "filters_label_city": "Where",
        "filters_label_type": "Type",
        "filters_label_themes": "Themes",
        "filters_label_company": "Party",
        "filters_label_budget": "Budget",
        "filters_label_amenities": "Amenities",
        "filters_label_rating": "Rating",
        "filters_label_age": "Age",
        "filters_label_exclusions": "Exclusions",
        "filters_label_event_count": "Events in the plan",
        "filters_section_events": "events",
        "filters_section_venues": "places",
        "filters_section_both": "events and places",
        "filters_date_default": "nearest",
        "filters_date_any": "any",
        "filters_city_any": "any",
        "filters_city_none": "not set",
        "filters_type_any": "any",
        "filters_none": "none",
        "filters_company_none": "not specified",
        "filters_company_any": "any",
        "filters_company_value": "{party} people",
        "filters_budget_none": "no limit",
        "filters_budget_per_person": "up to {amount} {currency} per person",
        "filters_budget_total": "up to {amount} {currency} total",
        "filters_rating_any": "any",
        "filters_rating_value": "from {rating:g}",
        "filters_age_any": "any",
        "filters_age_value": "up to {age}",
        "filters_list_sep": ", ",
        "category_concert": "concerts",
        "category_theatre": "theatre",
        "category_exhibition": "exhibitions",
        "category_film": "cinema",
        "category_sport": "sport",
        "category_kids": "for kids",
        "category_other": "other",
        "search_results": "Here is what we found:",
        "venue_results": "Here are the places we found:",
        "venue_empty": "No matching places. Try another district or query.",
        "assistant_capabilities": (
            "I help with leisure in Minsk: events, venues (bars, cafes, "
            "restaurants), dates, budgets, weather, evening plans and holds. "
            "Try: \"jazz tomorrow\" or \"where to drink beer with friends\"."),
        "clarify_date": (
            "Which date and time should we look for?{hint} "
            "For example: “Saturday evening”."),
        "clarify_missing": (
            "Please specify: {missing}. "
            "For any option you can answer “doesn't matter”."),
        "clarify_booking": (
            "Booking through the assistant is not available yet. "
            "Please buy a ticket on the event page."),
        "slot_datetime": "date",
        "slot_city": "city",
        "slot_budget": "budget",
        "slot_party": "number of people",
        "weather_unavailable": "Forecast is unavailable.",
        "weather_rain": (
            "{date}: rain is likely ({probability}%), high {temp}°C. "
            "Consider an indoor activity."),
        "weather_light_rain": (
            "{date}: light rain possible ({probability}%), high {temp}°C. "
            "Take an umbrella; the plan can stay as is."),
        "weather_dry": (
            "{date}: no rain ({probability}%), high {temp}°C. "
            "Good for a walk."),
        "card_untitled": "Untitled",
        "card_scraped": "check availability with the source",
        "card_undated": "date to be confirmed",
        "price_unknown": "price on request",
        "price_range": "{price_min:g}–{price_max:g} {currency}",
        "price_from": "from {price_min:g} {currency}",
        "currency_byn": "BYN",
        "availability_available": "tickets available",
        "availability_few_left": "few left",
        "availability_sold_out": "sold out",
        "availability_unknown": "availability unknown",
        "card_no_seats": "no seats for {party} people",
        "card_hours": "until {close}",
        "card_hours_24_7": "open 24/7",
        "card_film_run_until": "in cinemas until {date}",
        "card_film_next_session": "next show {time}",
        "card_film_next_session_cinema": "next show {time} · {cinema}",
        "card_film_duration": "{minutes} min",
        "card_address": "{address}",
        "venue_closed": "closed",
        "meta_rating": "★{rating} · {count} reviews",
        "weather_adjusted_rain": (
            "{date}: rain ({probability}%), outdoor and terrace options are "
            "excluded."),
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
