"""Botni yig'ish va ishga tushirish."""

import logging

from telegram import LinkPreviewOptions, Update
from telegram.constants import ParseMode
from telegram.ext import Application, Defaults
from telegram.request import BaseRequest

from . import config, handlers, scheduler
from .shifts import TZ
from .storage import Storage

log = logging.getLogger(__name__)

REPORT_CHECK_SECONDS = 30


def build_application(settings: config.Settings, db: Storage, request: BaseRequest | None = None) -> Application:
    defaults = Defaults(
        parse_mode=ParseMode.HTML,
        tzinfo=TZ,
        allow_sending_without_reply=True,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
    builder = Application.builder().token(settings.token).defaults(defaults).post_init(handlers.post_init)
    if request is not None:
        builder = builder.request(request).get_updates_request(request)
    app = builder.build()
    app.bot_data["db"] = db
    app.bot_data["settings"] = settings
    handlers.register(app)
    app.job_queue.run_repeating(scheduler.report_tick, interval=REPORT_CHECK_SECONDS, first=5, name="reports")
    return app


def main() -> None:
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    settings = config.load_settings()
    db = Storage(settings.db_path)
    app = build_application(settings, db)
    log.info("Buono Tabel boti ishga tushdi. Baza: %s", settings.db_path)
    app.run_polling(allowed_updates=[Update.MESSAGE, Update.MY_CHAT_MEMBER])
