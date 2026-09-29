"""Hisobotlar: smena hisoboti, kunlik va oylik hisobot, xodimlar ro'yxati."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .shifts import SHIFTS, Shift, is_early, is_late, shift_of
from .storage import Storage, Visit
from .texts import MONTHS, WEEKDAYS, day_str, duration, esc, hhmm


def shift_report(db: Storage, shift: Shift, shift_date: date, moment: datetime) -> str:
    """Smena boshlangandan keyingi holat: kim vaqtida, kim kechikib keldi va necha kishi keldi."""
    visits = db.visits_on(shift_date, shift.key)
    on_time = [v for v in visits if not is_late(v.late_min)]
    late = [v for v in visits if is_late(v.late_min)]
    lines = [
        f"📊 <b>{esc(shift.name)} hisoboti</b> — {day_str(shift_date)}",
        f"🕒 Smena: {shift.hours} · soat {hhmm(moment)} holatiga",
        "",
    ]
    if not visits:
        lines.append("😕 Hozircha hech kim kelmadi.")
        return "\n".join(lines)
    lines.append(f"👥 Kelganlar: <b>{len(visits)}</b> kishi")
    lines.append(f"✅ Vaqtida: <b>{len(on_time)}</b> · ⏰ Kechikkan: <b>{len(late)}</b>")
    if on_time:
        lines += ["", "✅ <b>Vaqtida kelganlar:</b>"]
        lines += [f"{i}. {esc(v.name)} — {hhmm(v.check_in)}" for i, v in enumerate(on_time, 1)]
    if late:
        lines += ["", "⏰ <b>Kechikib kelganlar:</b>"]
        lines += [f"{i}. {esc(v.name)} — {hhmm(v.check_in)} ({duration(v.late_min)})"
                  for i, v in enumerate(late, 1)]
    return "\n".join(lines)


def day_report(db: Storage, day: date, moment: datetime) -> str:
    """Kun bo'yicha barcha smenalar: kim ishladi, kim kechikdi, kim erta ketdi."""
    visits = db.visits_on(day)
    groups = [(shift, [v for v in visits if v.shift_key == shift.key]) for shift in SHIFTS]
    for key in sorted({v.shift_key for v in visits} - {shift.key for shift in SHIFTS}):
        extra = [v for v in visits if v.shift_key == key]
        groups.append((shift_of(extra[0]), extra))

    lines = [f"🗓 <b>Kunlik hisobot</b> — {day_str(day)}, {WEEKDAYS[day.weekday()]}"]
    for shift, items in groups:
        lines += ["", *_shift_block(shift, items, moment)]
    if visits:
        people = len({v.user_id for v in visits})
        late = sum(1 for v in visits if is_late(v.late_min))
        early = sum(1 for v in visits if _left_early(v))
        missing = sum(1 for v in visits if _missing_out(v, moment))
        total = f"📈 <b>Jami:</b> {people} kishi · ⏰ {late} ta kechikish · 🏃 {early} ta erta ketish"
        if missing:
            total += f" · ❓ {missing} ta ketish videosi yo'q"
        lines += ["", total]
    return "\n".join(lines)


def _shift_block(shift: Shift, visits: list[Visit], moment: datetime) -> list[str]:
    lines = [f"{shift.emoji} <b>{esc(shift.name)}</b> ({shift.hours})"]
    if not visits:
        return lines + ["Hech kim qayd etilmagan."]
    lines.append(f"👥 Ishladi: <b>{len(visits)}</b> kishi")
    for i, v in enumerate(visits, 1):
        marks = (" ⏰" if is_late(v.late_min) else "") + (" 🏃" if _left_early(v) else "")
        lines.append(f"{i}. {esc(v.name)} — {hhmm(v.check_in)} → {_out_label(v, moment)}{marks}")

    late = [v for v in visits if is_late(v.late_min)]
    if late:
        lines.append(f"⏰ Kechikkanlar ({len(late)}):")
        lines += [f"   • {esc(v.name)} — {duration(v.late_min)} ({hhmm(v.check_in)})" for v in late]
    else:
        lines.append("⏰ Kechikkanlar: yo'q ✅")

    early = [v for v in visits if _left_early(v)]
    if early:
        lines.append(f"🏃 Erta ketganlar ({len(early)}):")
        lines += [f"   • {esc(v.name)} — {duration(v.early_min)} erta ({hhmm(v.check_out)})" for v in early]
    else:
        lines.append("🏃 Erta ketganlar: yo'q ✅")

    missing = [v for v in visits if _missing_out(v, moment)]
    if missing:
        lines.append(f"❓ Ketish videosi yuborilmagan ({len(missing)}):")
        lines += [f"   • {esc(v.name)}" for v in missing]
    return lines


def _left_early(visit: Visit) -> bool:
    return visit.check_out is not None and is_early(visit.early_min)


def _missing_out(visit: Visit, moment: datetime) -> bool:
    return visit.check_out is None and moment >= visit.end_at


def _out_label(visit: Visit, moment: datetime) -> str:
    if visit.check_out is not None:
        return hhmm(visit.check_out)
    return "ishda" if moment < visit.end_at else "❓"


@dataclass
class _Stats:
    name: str
    shifts: int = 0
    late: int = 0
    late_minutes: int = 0
    early: int = 0
    early_minutes: int = 0
    missing: int = 0


def month_report(db: Storage, year: int, month: int, moment: datetime) -> str:
    """Oy bo'yicha har bir xodim: nechta smena, necha marta kechikkan va erta ketgan."""
    first = date(year, month, 1)
    last = (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    visits = db.visits_between(first, last)
    header = f"📅 <b>Oylik hisobot</b> — {MONTHS[month - 1]} {year}"
    if not visits:
        return f"{header}\n\nBu oy uchun yozuvlar yo'q."

    stats: dict[int, _Stats] = {}
    for v in visits:
        item = stats.setdefault(v.user_id, _Stats(v.name))
        item.shifts += 1
        if is_late(v.late_min):
            item.late += 1
            item.late_minutes += v.late_min
        if _left_early(v):
            item.early += 1
            item.early_minutes += v.early_min
        if _missing_out(v, moment):
            item.missing += 1

    ordered = sorted(stats.values(), key=lambda s: (-s.late_minutes, -s.late, -s.early_minutes, s.name.lower()))
    lines = [header, f"👥 Xodimlar: {len(stats)} · smenalar: {len(visits)}", ""]
    for i, item in enumerate(ordered, 1):
        lines.append(f"{i}. <b>{esc(item.name)}</b> — {item.shifts} smena")
        details = []
        if item.late:
            details.append(f"⏰ {item.late} marta kechikkan (jami {duration(item.late_minutes)})")
        if item.early:
            details.append(f"🏃 {item.early} marta erta ketgan (jami {duration(item.early_minutes)})")
        if item.missing:
            details.append(f"❓ {item.missing} marta ketish videosi yo'q")
        lines += [f"    {line}" for line in details or ["✅ Kechikish va erta ketish yo'q"]]
    return "\n".join(lines)


def employees_report(db: Storage) -> str:
    employees = db.list_employees()
    if not employees:
        return "👥 Hozircha xodimlar yo'q. Xodim guruhga birinchi yumaloq video yuborganda ro'yxatga qo'shiladi."
    lines = [f"👥 <b>Xodimlar</b> ({len(employees)} kishi)", ""]
    for i, employee in enumerate(employees, 1):
        extra = []
        if employee.custom_name:
            extra.append(esc(employee.full_name))
        if employee.username:
            extra.append(f"@{esc(employee.username)}")
        suffix = f" ({', '.join(extra)})" if extra else ""
        lines.append(f"{i}. {esc(employee.name)}{suffix} — oxirgi video: {employee.last_seen:%d.%m.%Y %H:%M}")
    return "\n".join(lines)
