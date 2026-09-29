"""Bot sozlamalari.

Token va ID raqamlar muhit o'zgaruvchilaridan (yoki .env faylidan) olinadi.
Smena vaqtlari va intizom qoidalari shu faylning o'zida turadi.
"""

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent

# Toshkent vaqti: UTC+5 (O'zbekistonda yozgi vaqtga o'tish yo'q)
UTC_OFFSET_HOURS = 5

# Smenalar.
#   start / end   — smena boshlanishi va tugashi
#   checkin_from  — shu vaqtdan boshlab yuborilgan "kelish" videosi shu smenaga yoziladi
#                   (keyingi smenaning checkin_from vaqtigacha). Standart holatda:
#                   04:30–11:00 → 1-smena, 11:00–16:30 → O'rta smena, 16:30–04:30 → 2-smena.
#                   Eng erta checkin_from (04:30) — ish kunining boshlanishi (/bugun, /kecha uchun)
#   report_at     — shu smena bo'yicha hisobot yuboriladigan vaqt
#   key           — /smena buyrug'ida ishlatiladigan qisqa nom
SHIFTS = [
    {"key": "1", "name": "1-smena", "start": "08:30", "end": "18:30",
     "checkin_from": "04:30", "report_at": "10:00", "emoji": "🌅"},
    {"key": "orta", "name": "O'rta smena", "start": "12:00", "end": "00:00",
     "checkin_from": "11:00", "report_at": "14:00", "emoji": "☀️"},
    {"key": "2", "name": "2-smena", "start": "18:30", "end": "04:30",
     "checkin_from": "16:30", "report_at": "20:00", "emoji": "🌙"},
]

# Kechagi barcha smenalar bo'yicha to'liq hisobot vaqti
DAILY_REPORT_AT = "07:30"

# Ruxsat etilgan kechikish: 08:30 dagi smenaga 08:35 da kelsa — vaqtida, 08:36 da — kechikdi
LATE_GRACE_MINUTES = 5

# Smena tugashidan shuncha daqiqa oldin ketish "erta ketish" hisoblanmaydi
EARLY_LEAVE_GRACE_MINUTES = 0

# Kelgandan keyin shu vaqt ichida yuborilgan yana bir video takroriy hisoblanadi (ketish emas)
DUPLICATE_WINDOW_MINUTES = 30

# Smena tugaganidan keyin shuncha soat o'tsa, ketish videosi yuborilmagan smena ochiq qoladi
# va xodimning keyingi videosi yangi "kelish" deb olinadi
MAX_OVERTIME_HOURS = 6

# Hisobot vaqtida bot o'chiq bo'lsa, shuncha daqiqa ichida yoqilganda hisobot baribir yuboriladi
REPORT_CATCHUP_MINUTES = 120


@dataclass(frozen=True)
class Settings:
    token: str
    group_id: int | None
    admin_ids: frozenset[int]
    report_chat_ids: tuple[int, ...]
    reports_to_group: bool
    db_path: str


def load_settings() -> Settings:
    _load_env_file(PROJECT_DIR / ".env")
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN topilmadi: uni .env fayliga yoki server sozlamalariga yozing.")
    group_ids = _int_list("GROUP_ID")
    return Settings(
        token=token,
        group_id=group_ids[0] if group_ids else None,
        admin_ids=frozenset(_int_list("ADMIN_IDS")),
        report_chat_ids=_int_list("REPORT_CHAT_IDS"),
        reports_to_group=os.environ.get("REPORTS_TO_GROUP", "1").strip().lower() not in {"0", "false", "no"},
        db_path=os.environ.get("DB_PATH", "").strip() or str(PROJECT_DIR / "tabel.db"),
    )


def _int_list(name: str) -> tuple[int, ...]:
    raw = os.environ.get(name, "")
    try:
        return tuple(int(part) for part in raw.replace(";", ",").split(",") if part.strip())
    except ValueError:
        raise SystemExit(f"{name} noto'g'ri: {raw!r}. Raqamlarni vergul bilan yozing, masalan: 123456789,987654321")


def _load_env_file(path: Path) -> None:
    """KEY=VALUE qatorlarini o'qiydi; serverda berilgan o'zgaruvchilar ustun turadi."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
