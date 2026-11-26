"""2GIS schedule normalizer: nested windows, overnight spans, 24/7, text."""
from __future__ import annotations

import json

from app.parsing.schedule import normalize_schedule, schedule_for_storage


def test_dict_shape_from_documented_fixture():
    hours, is_24_7 = normalize_schedule(
        {"Mon": {"working_hours": [{"from": "09:00", "to": "22:00"}]}})
    assert hours == {"mon": [["09:00", "22:00"]]}
    assert is_24_7 is False


def test_dict_shape_keeps_a_lunch_break():
    hours, _ = normalize_schedule({
        "Sat": {"working_hours": [{"from": "10:00", "to": "14:00"},
                                  {"from": "15:00", "to": "20:00"}]},
    })
    assert hours == {"sat": [["10:00", "14:00"], ["15:00", "20:00"]]}


def test_dict_shape_keeps_an_overnight_span():
    hours, is_24_7 = normalize_schedule({
        "Fri": {"working_hours": [{"from": "18:00", "to": "02:00"}]},
        "Sat": {"working_hours": [{"from": "18:00", "to": "02:00"}]},
    })
    assert hours == {"fri": [["18:00", "02:00"]],
                     "sat": [["18:00", "02:00"]]}
    assert is_24_7 is False


def test_dict_shape_days_are_ordered_and_24_7_flag_wins():
    hours, is_24_7 = normalize_schedule({
        "Sun": {"working_hours": [{"from": "12:00", "to": "18:00"}]},
        "Mon": {"is_24_7": True},
    })
    assert hours == {"sun": [["12:00", "18:00"]]}
    assert is_24_7 is True


def test_dict_shape_all_day_span_implies_24_7():
    week = {day: {"working_hours": [{"from": "00:00", "to": "24:00"}]}
            for day in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")}
    hours, is_24_7 = normalize_schedule(week)
    assert len(hours) == 7
    assert hours["mon"] == [["00:00", "23:59"]]  # 24:00 clamped, not dropped
    assert is_24_7 is True


def test_closed_day_is_absent_never_an_empty_list():
    hours, _ = normalize_schedule({
        "Mon": {"is_closed": True},
        "Tue": {"working_hours": []},
        "Wed": {"working_hours": [{"from": "10:00", "to": ""}]},
        "Thu": {"working_hours": [{"from": "10:00", "to": "18:00"}]},
    })
    assert hours == {"thu": [["10:00", "18:00"]]}
    assert all(windows for windows in hours.values())


def test_string_range_shape():
    assert normalize_schedule("Пн-Вс 09:00-23:00") == (
        {day: [["09:00", "23:00"]] for day in
         ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}, False)
    hours, _ = normalize_schedule("Пн-Пт 9:00-18:00, Сб-Вс 10:00-16:00")
    assert hours["mon"] == [["09:00", "18:00"]]
    assert hours["fri"] == [["09:00", "18:00"]]
    assert hours["sat"] == [["10:00", "16:00"]]
    assert hours["sun"] == [["10:00", "16:00"]]


def test_string_overnight_bar():
    hours, _ = normalize_schedule("Пт-Сб 18:00-02:00")
    assert hours["fri"] == [["18:00", "02:00"]]
    assert hours["sat"] == [["18:00", "02:00"]]
    assert "mon" not in hours


def test_string_multi_window_shares_its_day_group():
    hours, _ = normalize_schedule("Пн-Пт 09:00-13:00, 14:00-23:00")
    assert hours["mon"] == [["09:00", "13:00"], ["14:00", "23:00"]]
    assert hours["fri"] == [["09:00", "13:00"], ["14:00", "23:00"]]
    assert "sat" not in hours


def test_string_without_days_applies_to_the_week():
    hours, _ = normalize_schedule("09:00–22:00")
    assert len(hours) == 7 and hours["wed"] == [["09:00", "22:00"]]


def test_string_24_7_and_json_shapes():
    assert normalize_schedule("круглосуточно") == (None, True)
    assert normalize_schedule("24/7") == (None, True)
    encoded = json.dumps({"Fri": {"working_hours": [
        {"from": "11:00", "to": "01:00"}]}})  # overnight survives the encoding
    assert normalize_schedule(encoded) == ({"fri": [["11:00", "01:00"]]}, False)


def test_string_encoded_json_round_trip():
    schedule = {"Mon": {"working_hours": [{"from": "18:00", "to": "02:00"}]},
                "Tue": {"working_hours": [{"from": "09:00", "to": "13:00"},
                                          {"from": "14:00", "to": "23:00"}]}}
    hours, _ = normalize_schedule(schedule)
    assert normalize_schedule(json.dumps(hours)) == (hours, False)


def test_text_schedule_storage_round_trip():
    hours, is_24_7 = normalize_schedule("Пн-Пт 09:00-13:00, 14:00-23:00")
    stored = schedule_for_storage("Пн-Пт 09:00-13:00, 14:00-23:00",
                                  hours, is_24_7)
    assert stored["Mon"]["working_hours"] == [
        {"from": "09:00", "to": "13:00"}, {"from": "14:00", "to": "23:00"}]
    assert normalize_schedule(stored) == (hours, is_24_7)


def test_24_7_storage_round_trip():
    stored = schedule_for_storage("круглосуточно", None, True)
    assert stored == {"is_24_7": True}
    assert normalize_schedule(stored) == (None, True)


def test_invalid_times_are_dropped_not_mispaired():
    hours, _ = normalize_schedule({
        "Mon": {"working_hours": [{"from": "25:00", "to": "02:00"},
                                  {"from": "09:30", "to": "09:30"},
                                  {"from": "10:00", "to": "12:00"}]},
    })
    assert hours == {"mon": [["10:00", "12:00"]]}


def test_unusable_values_do_not_raise():
    for value in (None, 42, [], {}, "", "нет данных", "{not json"):
        assert normalize_schedule(value) == (None, False)
