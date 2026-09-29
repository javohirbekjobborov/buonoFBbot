"""Bot yuboradigan matnlar. Xabarlarni o'zgartirish uchun shu faylni tahrirlang."""

import html
import random
from datetime import date, datetime, timedelta

from . import config
from .shifts import DAILY_REPORT_AT, SHIFTS, Shift, floor_minute, is_early, is_late, minutes_between

WEEKDAYS = ("Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba")
MONTHS = ("Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
          "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr")


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{esc(name)}</a>'


def duration(minutes: int) -> str:
    hours, mins = divmod(max(0, int(minutes)), 60)
    if hours and mins:
        return f"{hours} soat {mins} daqiqa"
    if hours:
        return f"{hours} soat"
    return f"{mins} daqiqa"


def hhmm(moment: datetime) -> str:
    return moment.strftime("%H:%M")


def day_str(day: date) -> str:
    return day.strftime("%d.%m.%Y")


def shift_label(shift: Shift) -> str:
    return f"{esc(shift.name)} ({shift.hours})"


# --- Guruhdagi javoblar (name — xodimni belgilovchi havola) --------------------

ON_TIME = (
    "👏 Ofarin, {name}! O'z vaqtida keldingiz, rahmat!",
    "💪 Barakalla, {name}! Bugun ham vaqtida — shunday davom eting!",
    "🌟 Tashakkur, {name}! Vaqtida kelganingiz uchun rahmat!",
    "✅ Zo'r, {name}! O'z vaqtida keldingiz. Ishingizga omad!",
)

LATE = (
    "⚠️ {name}, siz {late} kechikib keldingiz. Bu yaxshi emas, keyingi safar kechikmasdan keling!",
    "⏰ {name}, bugun {late} kechikdingiz. Bu yaxshi emas, keyingi safar vaqtida keling!",
    "⚠️ {name}, {late} kechikish qayd etildi. Bu yaxshi emas, keyingi safar kechikmasdan keling!",
)


def arrival(name: str, shift: Shift, visit) -> str:
    if is_late(visit.late_min):
        head = random.choice(LATE).format(name=name, late=duration(visit.late_min))
    else:
        head = random.choice(ON_TIME).format(name=name)
    return f"{head}\n🕒 {shift_label(shift)} · keldingiz: {hhmm(visit.check_in)}"


def departure(name: str, shift: Shift, visit) -> str:
    if is_early(visit.early_min):
        head = (f"⚠️ {name}, siz smenani {duration(visit.early_min)} erta tugatdingiz. "
                "Bu yaxshi emas, ish vaqti tugamasdan ketmang!")
    else:
        head = f"✅ {name}, smenangiz yakunlandi. Rahmat, yaxshi dam oling! 👋"
    worked = minutes_between(floor_minute(visit.check_in), floor_minute(visit.check_out))
    return (f"{head}\n🕒 {shift_label(shift)} · ketdingiz: {hhmm(visit.check_out)} · "
            f"ishladingiz: {duration(worked)}")


def already_arrived(name: str, visit) -> str:
    return (f"ℹ️ {name}, kelganingiz {hhmm(visit.check_in)}da qayd etilgan. "
            "Smena tugagach, ketayotganda yana video yuboring.")


def already_left(name: str, visit) -> str:
    return f"ℹ️ {name}, ketganingiz {hhmm(visit.check_out)}da qayd etilgan."


def forwarded(name: str) -> str:
    return f"⚠️ {name}, forward qilingan video qabul qilinmaydi. Iltimos, yangi yumaloq video yozib yuboring."


def regular_video(name: str) -> str:
    return (f"📹 {name}, bu oddiy video — tabelga yozilmadi. "
            "Kelish-ketishni qayd etish uchun <b>yumaloq video</b> yuboring.")


VIDEO_IN_PRIVATE = ("📹 Kelish-ketish videosini <b>Buono Tabel</b> guruhiga yuboring. "
                    "Bu yerga yuborilgan video hisobga olinmaydi.")


# --- Rahbar tuzatishlari ------------------------------------------------------

def visit_summary(visit, shift: Shift) -> str:
    came = f"keldi {hhmm(visit.check_in)}"
    came += f" ({duration(visit.late_min)} kechikish)" if is_late(visit.late_min) else " (vaqtida)"
    if visit.check_out is None:
        left = "ketish qayd etilmagan"
    else:
        left = f"ketdi {hhmm(visit.check_out)}"
        if is_early(visit.early_min):
            left += f" ({duration(visit.early_min)} erta)"
    return (f"👤 {esc(visit.name)} — {shift_label(shift)}, {day_str(visit.shift_date)}\n"
            f"🕒 {came} · {left}")


def shift_changed(summary: str) -> str:
    return f"✅ Smena o'zgartirildi.\n{summary}"


def marked_arrival(summary: str) -> str:
    return f"✅ «Keldi» deb belgilandi.\n{summary}"


def marked_departure(summary: str) -> str:
    return f"✅ «Ketdi» deb belgilandi.\n{summary}"


def deleted(visit, shift: Shift) -> str:
    return (f"🗑 Yozuv o'chirildi: {esc(visit.name)} — {shift_label(shift)}, "
            f"{day_str(visit.shift_date)}, keldi {hhmm(visit.check_in)}.")


def reopened(summary: str) -> str:
    return f"🗑 Ketish belgisi o'chirildi, smena yana ochiq.\n{summary}"


def renamed(old: str, new: str) -> str:
    return f"✏️ Ism o'zgartirildi: {esc(old)} → <b>{esc(new)}</b>"


NOT_ADMIN = "⛔ Bu buyruq faqat rahbarlar uchun."
NEED_REPLY = "↩️ Bu buyruqni xodimning yumaloq videosiga yoki botning javobiga <i>reply</i> qilib yozing."
NOT_FOUND = "🤷 Bu xabar bo'yicha yozuv topilmadi. Xodimning yumaloq videosiga yoki botning javobiga reply qiling."
NO_PREVIOUS_ARRIVAL = "🤷 Bu xodimning oxirgi 24 soat ichidagi «keldi» yozuvi topilmadi."
GROUP_ONLY = "👥 Bu buyruq Buono Tabel guruhida ishlaydi."
SMENA_USAGE = "Smenani yozing, masalan: <code>/smena 1</code>, <code>/smena 2</code> yoki <code>/smena orta</code>"
ISM_USAGE = "Xodimning xabariga reply qilib yozing, masalan: <code>/ism Aliyev Vali</code>"
HISOBOT_USAGE = "Sanani yozing, masalan: <code>/hisobot 28.09.2026</code>"
OYLIK_USAGE = "Oyni yozing, masalan: <code>/oylik 09.2026</code>"


# --- Sozlash ------------------------------------------------------------------

BIND_IN_GROUP = "👥 /ulash buyrug'ini Buono Tabel guruhining o'zida yozing."
BOUND = "✅ Shu guruh <b>Tabel guruhi</b> sifatida ulandi. Endi xodimlarning yumaloq videolarini kuzatib boraman."
BOT_NOT_ADMIN = ("⚠️ Videolarni ko'rishim uchun meni guruhda <b>admin</b> qiling "
                 "(yoki @BotFather → /setprivacy → Disable).")
ADDED_TO_GROUP = ("👋 Salom! Men Buono Tabel nazorat botiman.\n"
                  "Ishni boshlash uchun: 1) meni guruhda admin qiling; 2) rahbar guruhda /ulash buyrug'ini yuborsin.")


def _shift_lines() -> str:
    return "\n".join(f"{shift.emoji} {shift_label(shift)}" for shift in SHIFTS)


def schedule_line() -> str:
    parts = [f"{DAILY_REPORT_AT:%H:%M} — kechagi kun"]
    parts += [f"{shift.report_at:%H:%M} — {esc(shift.name)}" for shift in sorted(SHIFTS, key=lambda s: s.report_at)]
    return ", ".join(parts)


def employee_help() -> str:
    first = SHIFTS[0]
    allowed = datetime.combine(date.today(), first.start) + timedelta(minutes=config.LATE_GRACE_MINUTES)
    return (
        "👋 Salom! Men <b>Buono Tabel</b> nazorat botiman.\n\n"
        "📹 Ishga kelganingizda va smena tugab ketayotganingizda <b>Buono Tabel</b> guruhiga "
        "yumaloq video yuboring — kelgan va ketgan vaqtingizni qayd etaman.\n\n"
        f"🕒 Smenalar:\n{_shift_lines()}\n\n"
        f"⏰ Kechikishga ruxsat: {config.LATE_GRACE_MINUTES} daqiqa. Masalan, {first.start:%H:%M}da "
        f"boshlanadigan smenaga {allowed:%H:%M}gacha kelsangiz — vaqtida hisoblanasiz."
    )


def admin_help() -> str:
    return (
        "🛠 <b>Rahbar buyruqlari</b>\n\n"
        "📊 <b>Hisobotlar</b> (shu yerda yoki guruhda):\n"
        "/bugun — bugungi holat\n"
        "/kecha — kechagi to'liq hisobot\n"
        "/hisobot 28.09.2026 — tanlangan kun hisoboti\n"
        "/oylik — oylik statistika (/oylik 09.2026)\n"
        "/xodimlar — xodimlar ro'yxati\n\n"
        "✏️ <b>Tuzatishlar</b> (guruhda xodim videosiga yoki botning javobiga <i>reply</i> qilib):\n"
        "/smena 1 | 2 | orta — smenani o'zgartirish\n"
        "/keldi — videoni «keldi» deb belgilash\n"
        "/ketdi — videoni «ketdi» deb belgilash\n"
        "/ochir — yozuvni o'chirish\n"
        "/ism Ism Familiya — xodim ismini o'zgartirish\n\n"
        "⚙️ <b>Sozlash</b>:\n"
        "/ulash — guruhni Tabel guruhi sifatida ulash (guruhda yoziladi)\n"
        "/id — chat va foydalanuvchi ID raqami\n\n"
        f"🕒 Smenalar:\n{_shift_lines()}\n\n"
        f"⏰ Avtomatik hisobotlar: {schedule_line()}"
    )
