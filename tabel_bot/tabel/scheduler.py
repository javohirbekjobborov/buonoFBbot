"""Avtomatik hisobotlar: har 30 soniyada tekshiriladi, vaqti kelgan hisobot bir marta yuboriladi.

Yuborilgan hisobot bazada belgilanadi, shuning uchun bot qayta ishga tushsa ham takrorlanmaydi,
hisobot vaqtida bot o'chiq bo'lgan bo'lsa esa REPORT_CATCHUP_MINUTES ichida baribir yuboriladi.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Callable

from telegram.ext import ContextTypes

from . import config, reports
from .sender import send_long
from .shifts import DAILY_REPORT_AT, SHIFTS, TZ, Shift, latest_shift_date, now
from .storage import Storage

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 5


@dataclass(frozen=True)
class ScheduledReport:
    key: str
    at: time
    build: Callable[[Storage, datetime, datetime], str]  # (db, rejalashtirilgan vaqt, hozir)


def _daily(db: Storage, due: datetime, moment: datetime) -> str:
    return reports.day_report(db, due.date() - timedelta(days=1), moment)


def _for_shift(shift: Shift) -> Callable[[Storage, datetime, datetime], str]:
    def build(db: Storage, due: datetime, moment: datetime) -> str:
        return reports.shift_report(db, shift, latest_shift_date(shift, due), moment)
    return build


def schedule() -> list[ScheduledReport]:
    jobs = [ScheduledReport("daily", DAILY_REPORT_AT, _daily)]
    jobs += [ScheduledReport(f"shift:{shift.key}", shift.report_at, _for_shift(shift)) for shift in SHIFTS]
    return jobs


def due_reports(db: Storage, moment: datetime) -> list[tuple[ScheduledReport, datetime]]:
    window = timedelta(minutes=config.REPORT_CATCHUP_MINUTES)
    result = []
    for job in schedule():
        for day in (moment.date() - timedelta(days=1), moment.date()):
            due = datetime.combine(day, job.at, TZ)
            if due <= moment < due + window and not db.report_sent(job.key, day):
                result.append((job, due))
    return result


def recipients(db: Storage, settings: config.Settings) -> list[int]:
    chat_ids = []
    group = db.group_id(settings.group_id)
    if settings.reports_to_group and group is not None:
        chat_ids.append(group)
    chat_ids += [chat_id for chat_id in settings.report_chat_ids if chat_id not in chat_ids]
    return chat_ids


async def report_tick(context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Storage = context.bot_data["db"]
    settings: config.Settings = context.bot_data["settings"]
    failures: dict = context.bot_data.setdefault("report_failures", {})
    moment = now()
    for job, due in due_reports(db, moment):
        chat_ids = recipients(db, settings)
        if not chat_ids:
            log.warning("%s hisoboti yuborilmadi: guruh ulanmagan va REPORT_CHAT_IDS bo'sh", job.key)
            db.mark_report_sent(job.key, due.date())
            continue
        text = job.build(db, due, moment)
        delivered = [await send_long(context.bot, chat_id, text) for chat_id in chat_ids]
        key = (job.key, due.date())
        if any(delivered):
            log.info("%s hisoboti yuborildi (%s)", job.key, due.date())
        elif failures.get(key, 0) + 1 < MAX_ATTEMPTS:
            failures[key] = failures.get(key, 0) + 1
            continue
        else:
            log.error("%s hisobotini %d urinishda ham yuborib bo'lmadi", job.key, MAX_ATTEMPTS)
        db.mark_report_sent(job.key, due.date())
        failures.pop(key, None)
