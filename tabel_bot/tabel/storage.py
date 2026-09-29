"""SQLite ombori: xodimlar, kelish-ketish yozuvlari va sozlamalar."""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    user_id     INTEGER PRIMARY KEY,
    full_name   TEXT NOT NULL,
    username    TEXT,
    custom_name TEXT,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS visits (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    chat_id      INTEGER NOT NULL,
    shift        TEXT NOT NULL,
    shift_date   TEXT NOT NULL,
    start_at     TEXT NOT NULL,
    end_at       TEXT NOT NULL,
    check_in     TEXT NOT NULL,
    in_msg_id    INTEGER,
    in_reply_id  INTEGER,
    late_min     INTEGER NOT NULL DEFAULT 0,
    check_out    TEXT,
    out_msg_id   INTEGER,
    out_reply_id INTEGER,
    early_min    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS visits_by_day ON visits (shift_date, shift);
CREATE INDEX IF NOT EXISTS visits_by_user ON visits (user_id, check_in);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_VISIT_SELECT = """
SELECT v.*, COALESCE(e.custom_name, e.full_name, CAST(v.user_id AS TEXT)) AS name
FROM visits v LEFT JOIN employees e ON e.user_id = v.user_id
"""


@dataclass
class Employee:
    user_id: int
    full_name: str
    username: str | None
    custom_name: str | None
    first_seen: datetime
    last_seen: datetime

    @property
    def name(self) -> str:
        return self.custom_name or self.full_name


@dataclass
class Visit:
    """Bitta smena: kelish videosi va (bo'lsa) ketish videosi."""

    user_id: int
    chat_id: int
    shift_key: str
    shift_date: date
    start_at: datetime
    end_at: datetime
    check_in: datetime
    in_msg_id: int | None
    late_min: int
    id: int | None = None
    in_reply_id: int | None = None
    check_out: datetime | None = None
    out_msg_id: int | None = None
    out_reply_id: int | None = None
    early_min: int = 0
    name: str = ""


def _iso(moment: datetime | None) -> str | None:
    return moment.replace(microsecond=0).isoformat() if moment else None


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _employee(row: sqlite3.Row) -> Employee:
    return Employee(
        user_id=row["user_id"],
        full_name=row["full_name"],
        username=row["username"],
        custom_name=row["custom_name"],
        first_seen=_dt(row["first_seen"]),
        last_seen=_dt(row["last_seen"]),
    )


def _visit(row: sqlite3.Row) -> Visit:
    return Visit(
        id=row["id"],
        user_id=row["user_id"],
        chat_id=row["chat_id"],
        shift_key=row["shift"],
        shift_date=date.fromisoformat(row["shift_date"]),
        start_at=_dt(row["start_at"]),
        end_at=_dt(row["end_at"]),
        check_in=_dt(row["check_in"]),
        in_msg_id=row["in_msg_id"],
        in_reply_id=row["in_reply_id"],
        late_min=row["late_min"],
        check_out=_dt(row["check_out"]),
        out_msg_id=row["out_msg_id"],
        out_reply_id=row["out_reply_id"],
        early_min=row["early_min"],
        name=row["name"],
    )


class Storage:
    def __init__(self, path: str) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # --- sozlamalar -------------------------------------------------------------

    def get_setting(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def group_id(self, default: int | None = None) -> int | None:
        """/ulash orqali ulangan guruh, bo'lmasa .env dagi GROUP_ID."""
        stored = self.get_setting("group_id")
        return int(stored) if stored else default

    def set_group_id(self, chat_id: int) -> None:
        self.set_setting("group_id", str(chat_id))

    def report_sent(self, key: str, day: date) -> bool:
        return self.get_setting(f"report:{key}:{day.isoformat()}") is not None

    def mark_report_sent(self, key: str, day: date) -> None:
        self.set_setting(f"report:{key}:{day.isoformat()}", "1")

    # --- xodimlar ---------------------------------------------------------------

    def upsert_employee(self, user_id: int, full_name: str, username: str | None, seen_at: datetime) -> Employee:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO employees (user_id, full_name, username, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    full_name = excluded.full_name,
                    username = excluded.username,
                    last_seen = MAX(employees.last_seen, excluded.last_seen)
                """,
                (user_id, full_name, username, _iso(seen_at), _iso(seen_at)),
            )
        return self.get_employee(user_id)

    def get_employee(self, user_id: int) -> Employee | None:
        row = self.conn.execute("SELECT * FROM employees WHERE user_id = ?", (user_id,)).fetchone()
        return _employee(row) if row else None

    def list_employees(self) -> list[Employee]:
        rows = self.conn.execute(
            "SELECT * FROM employees ORDER BY COALESCE(custom_name, full_name) COLLATE NOCASE"
        ).fetchall()
        return [_employee(row) for row in rows]

    def set_custom_name(self, user_id: int, name: str | None) -> None:
        with self.conn:
            self.conn.execute("UPDATE employees SET custom_name = ? WHERE user_id = ?", (name, user_id))

    # --- kelish-ketish yozuvlari ------------------------------------------------

    def add_visit(self, visit: Visit) -> Visit:
        with self.conn:
            cursor = self.conn.execute(
                """
                INSERT INTO visits (user_id, chat_id, shift, shift_date, start_at, end_at, check_in,
                                    in_msg_id, in_reply_id, late_min, check_out, out_msg_id, out_reply_id, early_min)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (visit.user_id, visit.chat_id, visit.shift_key, visit.shift_date.isoformat(), _iso(visit.start_at),
                 _iso(visit.end_at), _iso(visit.check_in), visit.in_msg_id, visit.in_reply_id, visit.late_min,
                 _iso(visit.check_out), visit.out_msg_id, visit.out_reply_id, visit.early_min),
            )
        return self.get_visit(cursor.lastrowid)

    def save_visit(self, visit: Visit) -> None:
        with self.conn:
            self.conn.execute(
                """
                UPDATE visits SET shift = ?, shift_date = ?, start_at = ?, end_at = ?, check_in = ?,
                                  in_msg_id = ?, in_reply_id = ?, late_min = ?, check_out = ?,
                                  out_msg_id = ?, out_reply_id = ?, early_min = ?
                WHERE id = ?
                """,
                (visit.shift_key, visit.shift_date.isoformat(), _iso(visit.start_at), _iso(visit.end_at),
                 _iso(visit.check_in), visit.in_msg_id, visit.in_reply_id, visit.late_min, _iso(visit.check_out),
                 visit.out_msg_id, visit.out_reply_id, visit.early_min, visit.id),
            )

    def delete_visit(self, visit_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM visits WHERE id = ?", (visit_id,))

    def set_reply_id(self, visit_id: int, role: str, message_id: int) -> None:
        column = "in_reply_id" if role == "in" else "out_reply_id"
        with self.conn:
            self.conn.execute(f"UPDATE visits SET {column} = ? WHERE id = ?", (message_id, visit_id))

    def get_visit(self, visit_id: int) -> Visit | None:
        row = self.conn.execute(_VISIT_SELECT + "WHERE v.id = ?", (visit_id,)).fetchone()
        return _visit(row) if row else None

    def last_visit(self, user_id: int) -> Visit | None:
        row = self.conn.execute(
            _VISIT_SELECT + "WHERE v.user_id = ? ORDER BY v.check_in DESC, v.id DESC LIMIT 1", (user_id,)
        ).fetchone()
        return _visit(row) if row else None

    def visit_before(self, user_id: int, moment: datetime) -> Visit | None:
        row = self.conn.execute(
            _VISIT_SELECT + "WHERE v.user_id = ? AND v.check_in < ? ORDER BY v.check_in DESC, v.id DESC LIMIT 1",
            (user_id, _iso(moment)),
        ).fetchone()
        return _visit(row) if row else None

    def find_by_message(self, chat_id: int, message_id: int) -> tuple[Visit, str] | None:
        """Video yoki botning javobi bo'yicha yozuvni topadi; rol: 'in' (kelish) yoki 'out' (ketish)."""
        row = self.conn.execute(
            _VISIT_SELECT + "WHERE v.chat_id = ? AND ? IN (v.in_msg_id, v.in_reply_id, v.out_msg_id, v.out_reply_id) "
            "ORDER BY v.id DESC LIMIT 1",
            (chat_id, message_id),
        ).fetchone()
        if row is None:
            return None
        visit = _visit(row)
        return visit, "in" if message_id in (visit.in_msg_id, visit.in_reply_id) else "out"

    def visits_on(self, shift_date: date, shift_key: str | None = None) -> list[Visit]:
        query, params = _VISIT_SELECT + "WHERE v.shift_date = ?", [shift_date.isoformat()]
        if shift_key is not None:
            query += " AND v.shift = ?"
            params.append(shift_key)
        rows = self.conn.execute(query + " ORDER BY v.check_in, v.id", params).fetchall()
        return [_visit(row) for row in rows]

    def visits_between(self, first: date, last: date) -> list[Visit]:
        rows = self.conn.execute(
            _VISIT_SELECT + "WHERE v.shift_date BETWEEN ? AND ? ORDER BY v.check_in, v.id",
            (first.isoformat(), last.isoformat()),
        ).fetchall()
        return [_visit(row) for row in rows]
