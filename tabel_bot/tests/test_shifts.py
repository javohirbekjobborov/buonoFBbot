from datetime import date, datetime, timezone

import pytest

from conftest import at
from tabel.shifts import (SHIFTS_BY_KEY, TZ, detect_shift, early_minutes, is_early, is_late, late_minutes,
                          latest_shift_date, parse_shift, shift_date_near, work_day)

DAY = date(2026, 9, 29)
PREV = date(2026, 9, 28)


@pytest.mark.parametrize("clock, key, day", [
    ("04:30", "1", DAY),
    ("08:30", "1", DAY),
    ("10:59", "1", DAY),
    ("11:00", "orta", DAY),
    ("12:10", "orta", DAY),
    ("16:29", "orta", DAY),
    ("16:30", "2", DAY),
    ("17:20", "2", DAY),
    ("18:36", "2", DAY),
    ("23:59", "2", DAY),
    ("00:00", "2", PREV),
    ("02:15", "2", PREV),
    ("04:29", "2", PREV),
])
def test_detect_shift_by_arrival_time(clock, key, day):
    shift, shift_date = detect_shift(at("29.09", clock))
    assert (shift.key, shift_date) == (key, day)


def test_five_minutes_of_lateness_are_allowed():
    start, _ = SHIFTS_BY_KEY["1"].bounds(DAY)
    assert late_minutes(at("29.09", "08:20"), start) == 0
    assert late_minutes(at("29.09", "08:35", second=59), start) == 5
    assert not is_late(late_minutes(at("29.09", "08:35", second=59), start))
    assert late_minutes(at("29.09", "08:36"), start) == 6
    assert is_late(late_minutes(at("29.09", "08:36"), start))


def test_telegram_utc_time_is_converted_to_tashkent():
    utc = datetime(2026, 9, 29, 3, 36, tzinfo=timezone.utc)  # 08:36 Toshkent
    shift, shift_date = detect_shift(utc)
    start, _ = shift.bounds(shift_date)
    assert shift.key == "1"
    assert late_minutes(utc, start) == 6


def test_shift_bounds_cross_midnight():
    assert SHIFTS_BY_KEY["2"].bounds(DAY) == (datetime(2026, 9, 29, 18, 30, tzinfo=TZ),
                                              datetime(2026, 9, 30, 4, 30, tzinfo=TZ))
    assert SHIFTS_BY_KEY["orta"].bounds(DAY)[1] == datetime(2026, 9, 30, 0, 0, tzinfo=TZ)
    assert SHIFTS_BY_KEY["1"].duration.total_seconds() == 10 * 3600


def test_early_leave_minutes():
    _, end = SHIFTS_BY_KEY["1"].bounds(DAY)
    assert early_minutes(at("29.09", "18:05"), end) == 25
    assert is_early(early_minutes(at("29.09", "18:29", second=59), end))
    assert early_minutes(at("29.09", "18:30"), end) == 0
    assert early_minutes(at("29.09", "19:10"), end) == 0


@pytest.mark.parametrize("text, key", [
    ("1", "1"), ("1-smena", "1"), ("birinchi", "1"), ("2", "2"), ("2-smena", "2"),
    ("orta", "orta"), ("o'rta", "orta"), ("Oʻrta smena", "orta"), ("urta", "orta"),
])
def test_parse_shift(text, key):
    assert parse_shift(text).key == key


def test_parse_shift_rejects_unknown_values():
    assert parse_shift("") is None
    assert parse_shift("5") is None


def test_shift_date_helpers():
    assert shift_date_near(SHIFTS_BY_KEY["2"], at("30.09", "01:00")) == DAY
    assert shift_date_near(SHIFTS_BY_KEY["orta"], at("29.09", "11:40")) == DAY
    assert latest_shift_date(SHIFTS_BY_KEY["2"], at("29.09", "20:00")) == DAY
    assert latest_shift_date(SHIFTS_BY_KEY["2"], at("30.09", "02:00")) == DAY
    assert latest_shift_date(SHIFTS_BY_KEY["1"], at("29.09", "10:00")) == DAY


def test_work_day_includes_the_night_shift():
    assert work_day(at("30.09", "02:00")) == DAY
    assert work_day(at("30.09", "04:29")) == DAY
    assert work_day(at("30.09", "04:30")) == date(2026, 9, 30)
    assert work_day(at("29.09", "23:00")) == DAY
