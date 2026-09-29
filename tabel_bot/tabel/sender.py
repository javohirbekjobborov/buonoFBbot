"""Xabar yuborish: uzun matnni bo'laklash va Telegram cheklovida (flood) qayta urinish."""

import asyncio
import logging
from datetime import timedelta

from telegram import Bot, Message
from telegram.error import RetryAfter, TelegramError

log = logging.getLogger(__name__)

# Telegram chegarasi 4096 belgi; emoji va teglar uchun zaxira qoldiriladi
MAX_MESSAGE_LENGTH = 3500


def split_text(text: str, limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    parts: list[str] = []
    current = ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit and current:
            parts.append(current)
            current = line
        else:
            current = candidate
    if current:
        parts.append(current)
    return [part[i:i + limit] for part in parts for i in range(0, len(part), limit)]


async def _with_retry(call, **kwargs):
    for _ in range(3):
        try:
            return await call(**kwargs)
        except RetryAfter as exc:
            delay = exc.retry_after
            if isinstance(delay, timedelta):
                delay = delay.total_seconds()
            await asyncio.sleep(float(delay) + 1)
    return await call(**kwargs)


async def reply(message: Message, text: str) -> Message | None:
    """Xabarga reply qilib javob beradi. Yuborib bo'lmasa — logga yozadi va None qaytaradi."""
    try:
        return await _with_retry(message.reply_text, text=text, do_quote=True)
    except TelegramError as exc:
        log.warning("Javob yuborilmadi (chat %s): %s", message.chat_id, exc)
        return None


async def send_long(bot: Bot, chat_id: int, text: str) -> bool:
    try:
        for part in split_text(text):
            await _with_retry(bot.send_message, chat_id=chat_id, text=part)
    except TelegramError as exc:
        log.warning("Xabar yuborilmadi (chat %s): %s", chat_id, exc)
        return False
    return True
