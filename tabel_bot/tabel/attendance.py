"""Kelish-ketish mantig'i: yangi videoni qayd etish va rahbar tuzatishlari."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from . import config
from .shifts import Shift, detect_shift, early_minutes, late_minutes, shift_date_near, to_local
from .storage import Storage, Visit

ARRIVED = "arrived"
LEFT = "left"
ALREADY_ARRIVED = "already_arrived"
ALREADY_LEFT = "already_left"

DUPLICATE_WINDOW = timedelta(minutes=config.DUPLICATE_WINDOW_MINUTES)
MAX_OVERTIME = timedelta(hours=config.MAX_OVERTIME_HOURS)
# /ketdi bilan faqat shu vaqt ichidagi "kelish"ni yopish mumkin
MAX_VISIT_SPAN = timedelta(hours=24)


@dataclass
class Result:
    kind: str
    visit: Visit


def register_video(db: Storage, user_id: int, chat_id: int, message_id: int, moment: datetime) -> Result:
    """Xodimning yumaloq videosi: ochiq smenasi bo'lsa — ketish, aks holda — kelish."""
    moment = to_local(moment)
    last = db.last_visit(user_id)
    if last is not None:
        if last.check_out is None:
            if moment - last.check_in < DUPLICATE_WINDOW:
                return Result(ALREADY_ARRIVED, last)
            if moment <= last.end_at + MAX_OVERTIME:
                _close(last, moment, message_id)
                db.save_visit(last)
                return Result(LEFT, last)
        elif moment - last.check_out < DUPLICATE_WINDOW:
            return Result(ALREADY_LEFT, last)
    return Result(ARRIVED, db.add_visit(_open(user_id, chat_id, message_id, moment)))


def change_shift(db: Storage, visit: Visit, shift: Shift) -> None:
    day = shift_date_near(shift, visit.check_in)
    visit.shift_key, visit.shift_date = shift.key, day
    visit.start_at, visit.end_at = shift.bounds(day)
    visit.late_min = late_minutes(visit.check_in, visit.start_at)
    if visit.check_out is not None:
        visit.early_min = early_minutes(visit.check_out, visit.end_at)
    db.save_visit(visit)


def remove_visit(db: Storage, visit: Visit) -> None:
    db.delete_visit(visit.id)


def reopen_visit(db: Storage, visit: Visit) -> None:
    """Ketish belgisini olib tashlaydi — smena yana ochiq holatga qaytadi."""
    visit.check_out = visit.out_msg_id = visit.out_reply_id = None
    visit.early_min = 0
    db.save_visit(visit)


def mark_arrival(db: Storage, user_id: int, chat_id: int, message_id: int, moment: datetime,
                 shift: Shift | None = None) -> Visit:
    """Videoni "keldi" deb belgilaydi (masalan, bot uni takroriy yoki ketish deb olgan bo'lsa)."""
    moment = to_local(moment)
    found = db.find_by_message(chat_id, message_id)
    if found is not None:
        visit, role = found
        if role == "in":
            if shift is not None:
                change_shift(db, visit, shift)
            return visit
        reopen_visit(db, visit)
    return db.add_visit(_open(user_id, chat_id, message_id, moment, shift))


def mark_departure(db: Storage, user_id: int, chat_id: int, message_id: int, moment: datetime) -> Visit | None:
    """Videoni oldingi "kelish"ning ketishi deb belgilaydi. Oldingi kelish topilmasa — None."""
    moment = to_local(moment)
    found = db.find_by_message(chat_id, message_id)
    if found is not None and found[1] == "out":
        return found[0]
    target = db.visit_before(user_id, moment)
    if target is None or moment - target.check_in > MAX_VISIT_SPAN:
        return None
    if found is not None:
        db.delete_visit(found[0].id)
    _close(target, moment, message_id)
    db.save_visit(target)
    return target


def _open(user_id: int, chat_id: int, message_id: int, moment: datetime, shift: Shift | None = None) -> Visit:
    if shift is None:
        shift, day = detect_shift(moment)
    else:
        day = shift_date_near(shift, moment)
    start, end = shift.bounds(day)
    return Visit(
        user_id=user_id,
        chat_id=chat_id,
        shift_key=shift.key,
        shift_date=day,
        start_at=start,
        end_at=end,
        check_in=moment,
        in_msg_id=message_id,
        late_min=late_minutes(moment, start),
    )


def _close(visit: Visit, moment: datetime, message_id: int) -> None:
    visit.check_out = moment
    visit.out_msg_id = message_id
    visit.out_reply_id = None
    visit.early_min = early_minutes(moment, visit.end_at)
