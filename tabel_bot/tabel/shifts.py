"""Smenalar va vaqt hisob-kitoblari."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from . import config

TZ = timezone(timedelta(hours=config.UTC_OFFSET_HOURS))
DAY_MINUTES = 24 * 60


def parse_hhmm(value: str) -> time:
    hours, minutes = value.strip().split(":")
    return time(int(hours), int(minutes))


def _minutes(moment: time) -> int:
    return moment.hour * 60 + moment.minute


@dataclass(frozen=True)
class Shift:
    key: str
    name: str
    start: time
    end: time
    checkin_from: time
    report_at: time
    emoji: str

    @property
    def duration(self) -> timedelta:
        minutes = (_minutes(self.end) - _minutes(self.start)) % DAY_MINUTES or DAY_MINUTES
        return timedelta(minutes=minutes)

    @property
    def hours(self) -> str:
        return f"{self.start:%H:%M}–{self.end:%H:%M}"

    def bounds(self, shift_date: date) -> tuple[datetime, datetime]:
        """Smenaning boshlanish va tugash vaqti (shift_date — smena boshlangan kun)."""
        start = datetime.combine(shift_date, self.start, TZ)
        return start, start + self.duration


def _load(raw: list[dict]) -> tuple[Shift, ...]:
    shifts = tuple(
        Shift(
            key=item["key"],
            name=item["name"],
            start=parse_hhmm(item["start"]),
            end=parse_hhmm(item["end"]),
            checkin_from=parse_hhmm(item["checkin_from"]),
            report_at=parse_hhmm(item["report_at"]),
            emoji=item.get("emoji", "🕒"),
        )
        for item in raw
    )
    if not shifts:
        raise ValueError("config.SHIFTS bo'sh")
    if len({s.key for s in shifts}) != len(shifts):
        raise ValueError("config.SHIFTS: smena kalitlari (key) takrorlanmasligi kerak")
    if len({s.checkin_from for s in shifts}) != len(shifts):
        raise ValueError("config.SHIFTS: checkin_from vaqtlari takrorlanmasligi kerak")
    windows = sorted(shifts, key=lambda s: _minutes(s.checkin_from))
    for index, shift in enumerate(windows):
        following = windows[(index + 1) % len(windows)]
        width = (_minutes(following.checkin_from) - _minutes(shift.checkin_from)) % DAY_MINUTES or DAY_MINUTES
        offset = (_minutes(shift.start) - _minutes(shift.checkin_from)) % DAY_MINUTES
        if offset >= width:
            raise ValueError(
                f"config.SHIFTS: {shift.name} boshlanishi ({shift.start:%H:%M}) "
                f"{shift.checkin_from:%H:%M}–{following.checkin_from:%H:%M} oralig'ida bo'lishi kerak"
            )
    return shifts


SHIFTS = _load(config.SHIFTS)
SHIFTS_BY_KEY = {shift.key: shift for shift in SHIFTS}
DAILY_REPORT_AT = parse_hhmm(config.DAILY_REPORT_AT)


def now() -> datetime:
    return datetime.now(TZ)


def to_local(moment: datetime) -> datetime:
    return moment.astimezone(TZ)


def floor_minute(moment: datetime) -> datetime:
    return moment.replace(second=0, microsecond=0)


def minutes_between(earlier: datetime, later: datetime) -> int:
    return int((later - earlier).total_seconds() // 60)


def detect_shift(moment: datetime) -> tuple[Shift, date]:
    """Kelish vaqtiga qarab smenani va smena boshlangan kunni aniqlaydi."""
    moment = to_local(moment)
    minute = moment.hour * 60 + moment.minute
    windows = sorted(SHIFTS, key=lambda s: _minutes(s.checkin_from))
    chosen = windows[-1]  # kun boshidagi eng erta oynadan oldin — kechagi oxirgi smena
    for shift in windows:
        if _minutes(shift.checkin_from) <= minute:
            chosen = shift
    opened = datetime.combine(moment.date(), chosen.checkin_from, TZ)
    if opened > moment:
        opened -= timedelta(days=1)
    start = datetime.combine(opened.date(), chosen.start, TZ)
    if start < opened:
        start += timedelta(days=1)
    return chosen, start.date()


def shift_date_near(shift: Shift, moment: datetime) -> date:
    """Boshlanishi berilgan vaqtga eng yaqin bo'lgan smena kuni (qo'lda tuzatishlar uchun)."""
    moment = to_local(moment)
    candidates = [moment.date() + timedelta(days=offset) for offset in (-1, 0, 1)]
    return min(candidates, key=lambda day: abs(shift.bounds(day)[0] - moment))


def work_day(moment: datetime) -> date:
    """Ish kuni: tungi smena davom etayotgan payt (eng erta kelish oynasigacha) oldingi kunga kiradi."""
    moment = to_local(moment)
    day_start = min(shift.checkin_from for shift in SHIFTS)
    return moment.date() - timedelta(days=1) if moment.time() < day_start else moment.date()


def latest_shift_date(shift: Shift, moment: datetime) -> date:
    """Berilgan vaqtgacha boshlangan eng oxirgi smena kuni."""
    moment = to_local(moment)
    day = moment.date()
    if datetime.combine(day, shift.start, TZ) > moment:
        day -= timedelta(days=1)
    return day


def late_minutes(check_in: datetime, start: datetime) -> int:
    return max(0, minutes_between(start, floor_minute(to_local(check_in))))


def early_minutes(check_out: datetime, end: datetime) -> int:
    return max(0, minutes_between(floor_minute(to_local(check_out)), end))


def is_late(late_min: int) -> bool:
    return late_min > config.LATE_GRACE_MINUTES


def is_early(early_min: int) -> bool:
    return early_min > config.EARLY_LEAVE_GRACE_MINUTES


def shift_of(visit) -> Shift:
    """Yozuvning smenasi; sozlamalardan olib tashlangan smena bo'lsa, yozuvdagi vaqtlardan tiklanadi."""
    shift = SHIFTS_BY_KEY.get(visit.shift_key)
    if shift is not None:
        return shift
    start, end = visit.start_at.timetz().replace(tzinfo=None), visit.end_at.timetz().replace(tzinfo=None)
    return Shift(visit.shift_key, visit.shift_key, start, end, start, start, "🕒")


def _normalize(text: str) -> str:
    text = text.strip().lower()
    for symbol in "'`ʻʼ‘’ -_":
        text = text.replace(symbol, "")
    return text.replace("smena", "")


_ALIASES = {"birinchi": "1", "ikkinchi": "2", "urta": "orta", "o": "orta"}


def parse_shift(text: str) -> Shift | None:
    """'1', '2', 'orta', "o'rta", '1-smena' kabi yozuvlarni smenaga aylantiradi."""
    wanted = _normalize(text)
    if not wanted:
        return None
    wanted = _ALIASES.get(wanted, wanted)
    for shift in SHIFTS:
        if wanted in (_normalize(shift.key), _normalize(shift.name)):
            return shift
    return None
