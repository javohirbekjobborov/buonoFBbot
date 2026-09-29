"""Telegram handlerlari: yumaloq videolar, rahbar buyruqlari va guruhni ulash."""

import logging
import time as clock
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import wraps

from telegram import (BotCommand, BotCommandScopeAllChatAdministrators, BotCommandScopeAllPrivateChats, Message,
                      Update)
from telegram.constants import ChatMemberStatus, ChatType
from telegram.error import TelegramError
from telegram.ext import Application, ChatMemberHandler, CommandHandler, ContextTypes, MessageHandler, filters

from . import attendance, reports, texts
from .config import Settings
from .sender import reply, send_long
from .shifts import now, parse_shift, shift_of, to_local, work_day
from .storage import Storage, Visit

log = logging.getLogger(__name__)

ADMIN_CACHE_SECONDS = 300
GROUP_TYPES = {ChatType.GROUP, ChatType.SUPERGROUP}
ADMIN_STATUSES = {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}

PRIVATE_COMMANDS = [
    BotCommand("bugun", "Bugungi hisobot"),
    BotCommand("kecha", "Kechagi to'liq hisobot"),
    BotCommand("hisobot", "Tanlangan kun hisoboti"),
    BotCommand("oylik", "Oylik statistika"),
    BotCommand("xodimlar", "Xodimlar ro'yxati"),
    BotCommand("id", "Chat va foydalanuvchi ID raqami"),
    BotCommand("help", "Yordam"),
]
GROUP_ADMIN_COMMANDS = [
    BotCommand("smena", "Smenani o'zgartirish (reply)"),
    BotCommand("keldi", "Videoni «keldi» deb belgilash (reply)"),
    BotCommand("ketdi", "Videoni «ketdi» deb belgilash (reply)"),
    BotCommand("ochir", "Yozuvni o'chirish (reply)"),
    BotCommand("ism", "Xodim ismini o'zgartirish (reply)"),
    BotCommand("bugun", "Bugungi hisobot"),
    BotCommand("ulash", "Guruhni Tabel guruhi sifatida ulash"),
]


def _db(context: ContextTypes.DEFAULT_TYPE) -> Storage:
    return context.bot_data["db"]


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.bot_data["settings"]


def group_id(context: ContextTypes.DEFAULT_TYPE) -> int | None:
    return _db(context).group_id(_settings(context).group_id)


# --- Huquqlar -----------------------------------------------------------------

async def is_admin(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """Rahbar: ADMIN_IDS dagi foydalanuvchi yoki Tabel guruhining admini."""
    if user_id in _settings(context).admin_ids:
        return True
    chat_id = group_id(context)
    if chat_id is None:
        return False
    cache = context.bot_data.setdefault("admin_cache", {})
    cached = cache.get(chat_id)
    if cached is None or clock.monotonic() - cached[0] > ADMIN_CACHE_SECONDS:
        try:
            members = await context.bot.get_chat_administrators(chat_id)
        except TelegramError as exc:
            log.warning("Guruh adminlarini olib bo'lmadi: %s", exc)
            return cached is not None and user_id in cached[1]
        cached = (clock.monotonic(), {member.user.id for member in members})
        cache[chat_id] = cached
    return user_id in cached[1]


async def _is_chat_admin(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
    except TelegramError:
        return False
    return member.status in ADMIN_STATUSES


def _is_anonymous_admin(message: Message) -> bool:
    """Guruh nomidan (anonim admin sifatida) yozilgan xabar — buni faqat guruh adminlari qila oladi."""
    return message.sender_chat is not None and message.sender_chat.id == message.chat_id


async def _from_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.effective_message
    if _is_anonymous_admin(message):
        return message.chat_id == group_id(context)
    user = update.effective_user
    return user is not None and await is_admin(context, user.id)


def admin_only(handler):
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _from_admin(update, context):
            await reply(update.effective_message, texts.NOT_ADMIN)
            return
        await handler(update, context)
    return wrapper


def _is_employee_message(message: Message) -> bool:
    user = message.from_user
    return user is not None and not user.is_bot and message.sender_chat is None


# --- Yumaloq video ------------------------------------------------------------

async def on_video_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message.chat.type == ChatType.PRIVATE:
        await reply(message, texts.VIDEO_IN_PRIVATE)
        return
    if message.chat_id != group_id(context) or not _is_employee_message(message):
        return
    db = _db(context)
    user = message.from_user
    moment = to_local(message.date)
    employee = db.upsert_employee(user.id, user.full_name, user.username, moment)
    who = texts.mention(user.id, employee.name)
    if message.forward_origin is not None:
        await reply(message, texts.forwarded(who))
        return

    result = attendance.register_video(db, user.id, message.chat_id, message.message_id, moment)
    visit, shift = result.visit, shift_of(result.visit)
    if result.kind == attendance.ARRIVED:
        text = texts.arrival(who, shift, visit)
    elif result.kind == attendance.LEFT:
        text = texts.departure(who, shift, visit)
    elif result.kind == attendance.ALREADY_ARRIVED:
        text = texts.already_arrived(who, visit)
    else:
        text = texts.already_left(who, visit)
    sent = await reply(message, text)
    if sent is not None and result.kind in (attendance.ARRIVED, attendance.LEFT):
        db.set_reply_id(visit.id, "in" if result.kind == attendance.ARRIVED else "out", sent.message_id)
    log.info("%s: %s (%s, %s)", employee.name, result.kind, shift.name, moment.strftime("%d.%m %H:%M"))


async def on_regular_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Oddiy video tabelga yozilmaydi — xodim buni bilishi kerak."""
    message = update.effective_message
    if message.chat_id != group_id(context) or not _is_employee_message(message):
        return
    user = message.from_user
    if await is_admin(context, user.id):
        return
    employee = _db(context).get_employee(user.id)
    await reply(message, texts.regular_video(texts.mention(user.id, employee.name if employee else user.full_name)))


# --- Umumiy buyruqlar ---------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if await _from_admin(update, context):
        await reply(message, texts.admin_help())
    elif message.chat.type == ChatType.PRIVATE:
        await reply(message, texts.employee_help())


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    lines = [f"💬 Chat ID: <code>{message.chat_id}</code>"]
    if update.effective_user is not None:
        lines.append(f"👤 Sizning ID: <code>{update.effective_user.id}</code>")
    await reply(message, "\n".join(lines))


async def cmd_bind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    if message.chat.type not in GROUP_TYPES:
        await reply(message, texts.BIND_IN_GROUP)
        return
    if _is_anonymous_admin(message):
        allowed = group_id(context) in (None, message.chat_id)
    else:
        allowed = user is not None and await _can_bind(context, message.chat_id, user.id)
    if not allowed:
        await reply(message, texts.NOT_ADMIN)
        return
    _db(context).set_group_id(message.chat_id)
    context.bot_data.pop("admin_cache", None)
    log.info("Tabel guruhi ulandi: %s (%s)", message.chat.title, message.chat_id)
    text = texts.BOUND
    if not context.bot.can_read_all_group_messages and not await _is_chat_admin(context, message.chat_id,
                                                                                 context.bot.id):
        text += "\n\n" + texts.BOT_NOT_ADMIN
    await reply(message, text)


async def _can_bind(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    if user_id in _settings(context).admin_ids:
        return True
    if not await _is_chat_admin(context, chat_id, user_id):
        return False
    current = group_id(context)
    return current is None or current == chat_id or await is_admin(context, user_id)


# --- Hisobotlar ---------------------------------------------------------------

def parse_day(text: str, today: date) -> date | None:
    """'28.09.2026', '28.09', '2026-09-28' ko'rinishidagi sanani o'qiydi."""
    parts = text.strip().replace("/", ".").replace("-", ".").split(".")
    try:
        if len(parts) == 3 and len(parts[0]) == 4:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        if len(parts) == 3:
            year = int(parts[2])
            return date(year + 2000 if year < 100 else year, int(parts[1]), int(parts[0]))
        if len(parts) == 2:
            return date(today.year, int(parts[1]), int(parts[0]))
    except ValueError:
        return None
    return None


def parse_month(text: str, today: date) -> tuple[int, int] | None:
    """'09.2026', '9', '2026-09' ko'rinishidagi oyni o'qiydi."""
    parts = text.strip().replace("/", ".").replace("-", ".").split(".")
    try:
        if len(parts) == 2 and len(parts[0]) == 4:
            year, month = int(parts[0]), int(parts[1])
        elif len(parts) == 2:
            month, year = int(parts[0]), int(parts[1])
        elif len(parts) == 1:
            month, year = int(parts[0]), today.year
        else:
            return None
    except ValueError:
        return None
    if year < 100:
        year += 2000
    return (year, month) if 1 <= month <= 12 and 2000 <= year <= 2100 else None


async def _send_report(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    await send_long(context.bot, update.effective_chat.id, text)


@admin_only
async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    moment = now()
    await _send_report(update, context, reports.day_report(_db(context), work_day(moment), moment))


@admin_only
async def cmd_yesterday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    moment = now()
    day = work_day(moment) - timedelta(days=1)
    await _send_report(update, context, reports.day_report(_db(context), day, moment))


@admin_only
async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    moment = now()
    day = parse_day(" ".join(context.args), moment.date()) if context.args else None
    if day is None:
        await reply(update.effective_message, texts.HISOBOT_USAGE)
        return
    await _send_report(update, context, reports.day_report(_db(context), day, moment))


@admin_only
async def cmd_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    moment = now()
    period = parse_month(" ".join(context.args), moment.date()) if context.args else (moment.year, moment.month)
    if period is None:
        await reply(update.effective_message, texts.OYLIK_USAGE)
        return
    await _send_report(update, context, reports.month_report(_db(context), *period, moment))


@admin_only
async def cmd_employees(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_report(update, context, reports.employees_report(_db(context)))


# --- Tuzatishlar (guruhda, videoga yoki botning javobiga reply qilib) ---------

@dataclass
class _Target:
    user_id: int
    message_id: int
    moment: datetime
    visit: Visit | None = None
    role: str | None = None


async def _target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> _Target | None:
    """Reply qilingan xabar qaysi video va qaysi yozuvga tegishli ekanini aniqlaydi."""
    message = update.effective_message
    if message.chat_id != group_id(context):
        await reply(message, texts.GROUP_ONLY)
        return None
    replied = message.reply_to_message
    if replied is None:
        await reply(message, texts.NEED_REPLY)
        return None
    db = _db(context)
    found = db.find_by_message(message.chat_id, replied.message_id)
    if found is not None:
        visit, role = found
        if role == "in":
            return _Target(visit.user_id, visit.in_msg_id, visit.check_in, visit, role)
        return _Target(visit.user_id, visit.out_msg_id, visit.check_out, visit, role)
    if replied.video_note is not None and _is_employee_message(replied):
        author = replied.from_user
        moment = to_local(replied.date)
        db.upsert_employee(author.id, author.full_name, author.username, moment)
        return _Target(author.id, replied.message_id, moment)
    await reply(message, texts.NOT_FOUND)
    return None


@admin_only
async def cmd_set_shift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    shift = parse_shift(" ".join(context.args)) if context.args else None
    if shift is None:
        await reply(message, texts.SMENA_USAGE)
        return
    target = await _target(update, context)
    if target is None:
        return
    if target.visit is None:
        await reply(message, texts.NOT_FOUND)
        return
    attendance.change_shift(_db(context), target.visit, shift)
    await reply(message, texts.shift_changed(texts.visit_summary(target.visit, shift)))


@admin_only
async def cmd_mark_arrival(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    shift = None
    if context.args:
        shift = parse_shift(" ".join(context.args))
        if shift is None:
            await reply(message, texts.SMENA_USAGE)
            return
    target = await _target(update, context)
    if target is None:
        return
    visit = attendance.mark_arrival(_db(context), target.user_id, message.chat_id, target.message_id,
                                    target.moment, shift)
    await reply(message, texts.marked_arrival(texts.visit_summary(visit, shift_of(visit))))


@admin_only
async def cmd_mark_departure(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    target = await _target(update, context)
    if target is None:
        return
    visit = attendance.mark_departure(_db(context), target.user_id, message.chat_id, target.message_id,
                                      target.moment)
    if visit is None:
        await reply(message, texts.NO_PREVIOUS_ARRIVAL)
        return
    await reply(message, texts.marked_departure(texts.visit_summary(visit, shift_of(visit))))


@admin_only
async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    target = await _target(update, context)
    if target is None:
        return
    visit = target.visit
    if visit is None:
        await reply(message, texts.NOT_FOUND)
        return
    shift = shift_of(visit)
    if target.role == "in":
        attendance.remove_visit(_db(context), visit)
        await reply(message, texts.deleted(visit, shift))
    else:
        attendance.reopen_visit(_db(context), visit)
        await reply(message, texts.reopened(texts.visit_summary(visit, shift)))


@admin_only
async def cmd_rename(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    new_name = " ".join(context.args).strip()[:64]
    if not new_name:
        await reply(message, texts.ISM_USAGE)
        return
    if message.chat_id != group_id(context):
        await reply(message, texts.GROUP_ONLY)
        return
    db = _db(context)
    replied = message.reply_to_message
    employee = None
    if replied is not None:
        found = db.find_by_message(message.chat_id, replied.message_id)
        if found is not None:
            employee = db.get_employee(found[0].user_id)
        elif _is_employee_message(replied):
            author = replied.from_user
            employee = db.upsert_employee(author.id, author.full_name, author.username, to_local(replied.date))
    if employee is None:
        await reply(message, texts.ISM_USAGE)
        return
    db.set_custom_name(employee.user_id, new_name)
    await reply(message, texts.renamed(employee.name, new_name))


# --- Guruh hodisalari ---------------------------------------------------------

async def on_migrate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guruh supergroupga aylanganda uning ID si o'zgaradi — yangisini eslab qolamiz."""
    message = update.effective_message
    current = group_id(context)
    if message.migrate_to_chat_id and message.chat_id == current:
        new_id = message.migrate_to_chat_id
    elif message.migrate_from_chat_id and message.migrate_from_chat_id == current:
        new_id = message.chat_id
    else:
        return
    _db(context).set_group_id(new_id)
    context.bot_data.pop("admin_cache", None)
    log.info("Tabel guruhi yangi ID ga o'tdi: %s -> %s", current, new_id)


async def on_bot_added(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    change = update.my_chat_member
    if change.chat.type not in GROUP_TYPES or group_id(context) is not None:
        return
    joined = change.old_chat_member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED)
    if joined and change.new_chat_member.status not in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
        try:
            await context.bot.send_message(change.chat.id, texts.ADDED_TO_GROUP)
        except TelegramError as exc:
            log.warning("Guruhga salom yuborilmadi: %s", exc)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Xatolik yuz berdi", exc_info=context.error)


async def post_init(app: Application) -> None:
    try:
        await app.bot.set_my_commands(PRIVATE_COMMANDS, scope=BotCommandScopeAllPrivateChats())
        await app.bot.set_my_commands(GROUP_ADMIN_COMMANDS, scope=BotCommandScopeAllChatAdministrators())
    except TelegramError as exc:
        log.warning("Buyruqlar menyusini o'rnatib bo'lmadi: %s", exc)


def register(app: Application) -> None:
    new_messages = filters.UpdateType.MESSAGE
    app.add_handler(MessageHandler(filters.VIDEO_NOTE & new_messages, on_video_note))
    app.add_handler(MessageHandler(filters.VIDEO & filters.ChatType.GROUPS & new_messages, on_regular_video))
    app.add_handler(MessageHandler(filters.StatusUpdate.MIGRATE, on_migrate))
    commands = [
        (("start", "help", "yordam"), cmd_start),
        (("id",), cmd_id),
        (("ulash",), cmd_bind),
        (("bugun",), cmd_today),
        (("kecha",), cmd_yesterday),
        (("hisobot",), cmd_report),
        (("oylik",), cmd_month),
        (("xodimlar",), cmd_employees),
        (("smena",), cmd_set_shift),
        (("keldi",), cmd_mark_arrival),
        (("ketdi",), cmd_mark_departure),
        (("ochir",), cmd_delete),
        (("ism",), cmd_rename),
    ]
    for names, callback in commands:
        app.add_handler(CommandHandler(names, callback, filters=new_messages))
    app.add_handler(ChatMemberHandler(on_bot_added, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_error_handler(on_error)
