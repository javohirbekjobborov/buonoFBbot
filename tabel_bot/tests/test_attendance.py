from datetime import date

from conftest import at
from tabel import attendance
from tabel.attendance import ALREADY_ARRIVED, ALREADY_LEFT, ARRIVED, LEFT
from tabel.shifts import SHIFTS_BY_KEY, is_late

CHAT = -100500
ALI = 1
_ids = iter(range(1, 10_000))


def video(db, day, clock, user=ALI, second=0):
    message_id = next(_ids)
    result = attendance.register_video(db, user, CHAT, message_id, at(day, clock, second))
    return result, message_id


def test_on_time_arrival_and_departure(db):
    came, _ = video(db, "29.09", "08:28")
    assert came.kind == ARRIVED
    assert (came.visit.shift_key, came.visit.shift_date, came.visit.late_min) == ("1", date(2026, 9, 29), 0)

    left, _ = video(db, "29.09", "18:31")
    assert left.kind == LEFT
    assert left.visit.id == came.visit.id
    assert left.visit.early_min == 0
    assert db.last_visit(ALI).check_out == at("29.09", "18:31")


def test_late_arrival_after_grace_period(db):
    ok, _ = video(db, "29.09", "08:35", user=2)
    late, _ = video(db, "29.09", "08:36", user=3)
    assert not is_late(ok.visit.late_min)
    assert late.visit.late_min == 6 and is_late(late.visit.late_min)


def test_repeated_videos_are_not_counted_twice(db):
    video(db, "29.09", "08:30")
    again, _ = video(db, "29.09", "08:45")
    assert again.kind == ALREADY_ARRIVED
    video(db, "29.09", "18:30")
    again, _ = video(db, "29.09", "18:40")
    assert again.kind == ALREADY_LEFT
    assert len(db.visits_on(date(2026, 9, 29))) == 1


def test_early_departure(db):
    video(db, "29.09", "08:30")
    left, _ = video(db, "29.09", "18:05")
    assert left.kind == LEFT and left.visit.early_min == 25


def test_night_shift_crosses_midnight(db):
    came, _ = video(db, "29.09", "18:29")
    assert (came.visit.shift_key, came.visit.shift_date) == ("2", date(2026, 9, 29))
    left, _ = video(db, "30.09", "04:31")
    assert left.kind == LEFT and left.visit.early_min == 0
    assert [v.shift_key for v in db.visits_on(date(2026, 9, 29))] == ["2"]


def test_middle_shift_departure_at_midnight(db):
    came, _ = video(db, "29.09", "11:57")
    assert came.visit.shift_key == "orta"
    left, _ = video(db, "30.09", "00:00")
    assert left.kind == LEFT and left.visit.early_min == 0


def test_overtime_departure_is_accepted(db):
    video(db, "29.09", "08:30")
    left, _ = video(db, "29.09", "23:00")
    assert left.kind == LEFT and left.visit.early_min == 0


def test_forgotten_departure_does_not_swallow_next_arrival(db):
    first, _ = video(db, "29.09", "08:30")
    nxt, _ = video(db, "30.09", "08:25")
    assert nxt.kind == ARRIVED and nxt.visit.id != first.visit.id
    assert db.get_visit(first.visit.id).check_out is None


def test_change_shift_recalculates_lateness(db):
    came, _ = video(db, "29.09", "12:05")
    assert came.visit.shift_key == "orta" and not is_late(came.visit.late_min)
    attendance.change_shift(db, came.visit, SHIFTS_BY_KEY["1"])
    visit = db.get_visit(came.visit.id)
    assert visit.shift_key == "1" and visit.late_min == 215


def test_mark_departure_fixes_video_taken_as_new_arrival(db):
    came, _ = video(db, "29.09", "08:30")
    video(db, "29.09", "09:30")                     # tasodifiy video — ketish deb olindi
    wrong, msg_id = video(db, "29.09", "18:30")      # haqiqiy ketish — yangi kelish deb olindi
    assert wrong.kind == ARRIVED

    fixed = attendance.mark_departure(db, ALI, CHAT, msg_id, at("29.09", "18:30"))
    assert fixed.id == came.visit.id
    assert fixed.check_out == at("29.09", "18:30") and fixed.early_min == 0
    assert db.get_visit(wrong.visit.id) is None


def test_mark_departure_on_repeated_video(db):
    came, _ = video(db, "29.09", "08:30")
    dup, msg_id = video(db, "29.09", "08:50")
    assert dup.kind == ALREADY_ARRIVED
    fixed = attendance.mark_departure(db, ALI, CHAT, msg_id, at("29.09", "08:50"))
    assert fixed.id == came.visit.id and fixed.early_min == 580


def test_mark_departure_without_recent_arrival(db):
    assert attendance.mark_departure(db, ALI, CHAT, 999, at("29.09", "18:30")) is None
    video(db, "27.09", "08:30")
    assert attendance.mark_departure(db, ALI, CHAT, 998, at("29.09", "18:30")) is None


def test_mark_arrival_turns_departure_into_new_shift(db):
    first, _ = video(db, "29.09", "08:30")
    left, msg_id = video(db, "29.09", "18:30")
    assert left.kind == LEFT

    second = attendance.mark_arrival(db, ALI, CHAT, msg_id, at("29.09", "18:30"))
    assert second.id != first.visit.id and second.shift_key == "2"
    assert db.get_visit(first.visit.id).check_out is None


def test_mark_arrival_with_explicit_shift(db):
    dup_source, _ = video(db, "29.09", "08:30")
    dup, msg_id = video(db, "29.09", "08:40")
    assert dup.kind == ALREADY_ARRIVED
    visit = attendance.mark_arrival(db, ALI, CHAT, msg_id, at("29.09", "08:40"), SHIFTS_BY_KEY["orta"])
    assert visit.shift_key == "orta" and visit.late_min == 0
    assert visit.id != dup_source.visit.id


def test_remove_and_reopen(db):
    came, _ = video(db, "29.09", "08:30")
    video(db, "29.09", "18:30")
    attendance.reopen_visit(db, db.get_visit(came.visit.id))
    assert db.get_visit(came.visit.id).check_out is None
    attendance.remove_visit(db, db.get_visit(came.visit.id))
    assert db.visits_on(date(2026, 9, 29)) == []


def test_find_by_message_roles(db):
    came, in_id = video(db, "29.09", "08:30")
    db.set_reply_id(came.visit.id, "in", 5000)
    _, out_id = video(db, "29.09", "18:30")
    assert db.find_by_message(CHAT, in_id)[1] == "in"
    assert db.find_by_message(CHAT, 5000)[1] == "in"
    assert db.find_by_message(CHAT, out_id)[1] == "out"
    assert db.find_by_message(CHAT, 424242) is None
    assert db.find_by_message(-1, in_id) is None
