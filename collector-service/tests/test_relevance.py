"""Deterministic Telegram relevance classifier tests."""
import json
from pathlib import Path

from app.parsing.relevance import ChannelRules, classify

FIXTURES = Path(__file__).parent / "fixtures"
POSTS = json.loads((FIXTURES / "telegram_relevance_posts.json").read_text())
RULES = ChannelRules()
UNDATED = ChannelRules(undated_ok=True)
STRICT = ChannelRules(strict_event=True)


def test_hard_junk_without_event_is_dropped():
    for key, reason in (("housing", "housing"), ("internship", "jobs"),
                        ("giveaway", "ad")):
        decision = classify(POSTS[key])
        assert decision.keep is False
        assert decision.reason == reason


def test_companion_search_dropped_without_full_event_context():
    decision = classify(POSTS["companion"])
    assert decision.keep is False and decision.reason == "companion"
    # Event + date + venue makes a companion post an event announcement.
    text = "Ищу компанию на концерт 25.10 в клубе «Тестовый»"
    assert classify(text).keep is True


def test_undated_event_needs_channel_opt_in_and_venue():
    assert classify(POSTS["undated_quiz"]).reason == "undated"
    decision = classify(POSTS["undated_quiz"], rules=UNDATED)
    assert decision.keep is True and decision.has_venue is True
    assert "undated_ok" in decision.signals
    no_venue = classify("Квиз без места", rules=UNDATED)
    assert no_venue.reason == "undated"


def test_discount_event_with_promo_is_kept():
    decision = classify(POSTS["discount_concert"])
    assert decision.keep is True
    assert decision.has_date and decision.has_venue
    assert "ad" in decision.signals and "event" in decision.signals


def test_digest_is_skipped():
    decision = classify(POSTS["digest"])
    assert decision.keep is False and decision.reason == "digest"
    assert "digest" in decision.signals


def test_strict_event_channel_rejects_undated_reviews():
    assert classify(POSTS["blog_review"], rules=STRICT).reason == "strict_event"
    assert classify("Концерт 25.10 в клубе «Тестовый»",
                    rules=STRICT).keep is True


def test_plain_non_event_text_is_dropped():
    assert classify("Купили новые стулья в офис").reason == "no_event"


def test_film_screening_words_count_as_event():
    text = ("Психотриллер «Веревка» — 1 октября в музее Азгура.\n"
            "Начало сеанса в 19:00\nБилеты от 15 руб.")
    decision = classify(text, "cinemascopeby")
    assert decision.keep is True and decision.has_date is True
    premiere = classify("Премьера фильма 5 декабря в кинотеатре SKYLINE")
    assert premiere.keep is True and "event" in premiere.signals


def test_resale_is_always_dropped():
    text = "Продам билет на концерт 25.10 в клубе «Тестовый»"
    decision = classify(text)
    assert decision.keep is False and decision.reason == "resale"


def test_channel_flags_override_event_context():
    housing_event = "Сдам квартиру после концерта 25.10 в клубе «Тестовый»"
    assert classify(housing_event).keep is True  # discount/announcement rule
    assert classify(housing_event,
                    rules=ChannelRules(no_housing=True)).reason == "housing"

    jobs_event = "Стажировка на фестивале 25.10 в парке"
    assert classify(jobs_event).keep is True
    assert classify(jobs_event,
                    rules=ChannelRules(no_jobs=True)).reason == "jobs"

    ad_event = "Розыгрыш билетов на концерт 25.10 в клубе «Тестовый»"
    assert classify(ad_event).keep is True
    assert classify(ad_event, rules=ChannelRules(no_ad=True)).reason == "ad"


def test_no_companion_flag_is_stricter_than_default():
    text = "Ищу компанию на концерт 25.10 в клубе «Тестовый»"
    assert classify(text).keep is True
    assert classify(text, rules=ChannelRules(
        no_companion_search=True)).reason == "companion"


def test_decision_exposes_signals_and_context():
    decision = classify("Концерт 25.10 в клубе, билеты от 20 руб.")
    assert decision.keep is True
    assert decision.has_date is True and decision.has_venue is True
    assert {"event", "date", "venue", "price"} <= set(decision.signals)
    assert decision.as_dict()["reason"] == "keep"
