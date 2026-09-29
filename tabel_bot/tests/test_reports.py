from datetime import date

from conftest import at
from tabel import attendance, reports
from tabel.sender import split_text
from tabel.shifts import SHIFTS_BY_KEY

CHAT = -100500
DAY = date(2026, 9, 29)
_ids = iter(range(1, 10_000))


def video(db, user, name, day, clock):
    db.upsert_employee(user, name, None, at(day, clock))
    return attendance.register_video(db, user, CHAT, next(_ids), at(day, clock))


def fill_day(db):
    video(db, 1, "Ali", "29.09", "08:21")
    video(db, 2, "Sardor", "29.09", "08:47")      # 17 daqiqa kechikdi
    video(db, 3, "Aziz", "29.09", "08:30")
    video(db, 4, "Malika <3", "29.09", "08:29")   # ketish videosi yo'q
    video(db, 5, "Bobur", "29.09", "11:55")       # O'rta smena
    video(db, 6, "Jasur", "29.09", "18:40")       # 2-smena, 10 daqiqa kechikdi
    video(db, 1, "Ali", "29.09", "18:34")
    video(db, 2, "Sardor", "29.09", "18:30")
    video(db, 3, "Aziz", "29.09", "18:05")        # 25 daqiqa erta ketdi
    video(db, 5, "Bobur", "30.09", "00:02")
    video(db, 6, "Jasur", "30.09", "04:30")


def test_shift_report_lists_on_time_and_late(db):
    fill_day(db)
    text = reports.shift_report(db, SHIFTS_BY_KEY["1"], DAY, at("29.09", "10:00"))
    assert "Kelganlar: <b>4</b> kishi" in text
    assert "Vaqtida: <b>3</b>" in text and "Kechikkan: <b>1</b>" in text
    assert "Sardor — 08:47 (17 daqiqa)" in text
    assert "Malika &lt;3 — 08:29" in text
    assert "soat 10:00 holatiga" in text


def test_shift_report_when_nobody_came(db):
    text = reports.shift_report(db, SHIFTS_BY_KEY["orta"], DAY, at("29.09", "14:00"))
    assert "Hozircha hech kim kelmadi" in text


def test_day_report_covers_all_shifts(db):
    fill_day(db)
    text = reports.day_report(db, DAY, at("30.09", "07:30"))
    assert "Kunlik hisobot</b> — 29.09.2026, Seshanba" in text
    assert "Ishladi: <b>4</b> kishi" in text
    assert "• Sardor — 17 daqiqa (08:47)" in text
    assert "• Aziz — 25 daqiqa erta (18:05)" in text
    assert "Ketish videosi yuborilmagan (1)" in text and "• Malika &lt;3" in text
    assert "Jasur — 10 daqiqa (18:40)" in text
    assert "Bobur — 11:55 → 00:02" in text
    assert "Jami:</b> 6 kishi · ⏰ 2 ta kechikish · 🏃 1 ta erta ketish" in text


def test_day_report_marks_people_still_at_work(db):
    video(db, 1, "Ali", "29.09", "08:21")
    text = reports.day_report(db, DAY, at("29.09", "12:00"))
    assert "Ali — 08:21 → ishda" in text
    assert "Ketish videosi yuborilmagan" not in text


def test_day_report_without_records(db):
    text = reports.day_report(db, DAY, at("30.09", "07:30"))
    assert text.count("Hech kim qayd etilmagan.") == 3


def test_month_report_puts_most_late_first(db):
    fill_day(db)
    video(db, 6, "Jasur", "30.09", "19:50")        # yana 1 soat 20 daqiqa kechikdi
    text = reports.month_report(db, 2026, 9, at("30.09", "21:00"))
    assert "Oylik hisobot</b> — Sentabr 2026" in text
    assert text.index("Jasur") < text.index("Sardor") < text.index("Ali")
    assert "⏰ 2 marta kechikkan (jami 1 soat 30 daqiqa)" in text
    assert "✅ Kechikish va erta ketish yo'q" in text


def test_employees_report(db):
    fill_day(db)
    db.set_custom_name(4, "Malika Karimova")
    text = reports.employees_report(db)
    assert "Xodimlar</b> (6 kishi)" in text
    assert "Malika Karimova (Malika &lt;3)" in text


def test_split_text_keeps_lines_whole():
    text = "\n".join(f"{i}. Xodim ismi — 08:30 → 18:30" for i in range(400))
    parts = split_text(text, limit=1000)
    assert len(parts) > 1
    assert all(len(part) <= 1000 for part in parts)
    assert "\n".join(parts) == text
