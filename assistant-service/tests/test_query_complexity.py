from app.core.config import Settings
from app.services.query_complexity import classify


def test_simple_request_is_not_complex():
    result = classify("джаз завтра", Settings())
    assert result.complex is False
    assert result.reasons == ["date"]


def test_multi_constraint_request_is_complex():
    result = classify("тихий джаз в субботу до 50 рублей на двоих без фастфуда",
                      Settings())
    assert result.complex is True
    assert "date" in result.reasons
    assert "budget" in result.reasons
    assert "party" in result.reasons
    assert "negation" in result.reasons


def test_long_request_is_complex_by_length():
    result = classify("x" * 140, Settings())
    assert result.complex is True
    assert "long" in result.reasons


def test_two_categories_are_a_complexity_signal():
    result = classify("концерт или спектакль", Settings())
    assert "multi_category" in result.reasons
    # A single signal alone stays on the fast lane.
    assert result.complex is False


def test_thresholds_are_configurable():
    settings = Settings(llm_complex_min_chars=1000, llm_complex_min_signals=99)
    result = classify("тихий джаз в субботу до 50 рублей на двоих", settings)
    assert result.complex is False
