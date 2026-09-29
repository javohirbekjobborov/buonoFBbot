import asyncio
from types import SimpleNamespace

from telegram.error import NetworkError

from conftest import at
from tabel import scheduler
from tabel.config import Settings

GROUP = -100500


def settings(**overrides):
    values = dict(token="x", group_id=GROUP, admin_ids=frozenset(), report_chat_ids=(),
                  reports_to_group=True, db_path=":memory:")
    values.update(overrides)
    return Settings(**values)


def due_keys(db, day, clock):
    return [job.key for job, _ in scheduler.due_reports(db, at(day, clock))]


def test_reports_are_due_at_their_times(db):
    assert due_keys(db, "29.09", "07:29") == []
    assert due_keys(db, "29.09", "07:30") == ["daily"]
    assert due_keys(db, "29.09", "10:00") == ["shift:1"]
    assert due_keys(db, "29.09", "14:00") == ["shift:orta"]
    assert due_keys(db, "29.09", "20:00") == ["shift:2"]


def test_sent_report_is_not_repeated_and_missed_report_is_caught_up(db):
    db.mark_report_sent("daily", at("29.09", "07:30").date())
    assert due_keys(db, "29.09", "07:31") == []
    assert due_keys(db, "29.09", "11:59") == ["shift:1"]   # bot 10:00 da o'chiq bo'lgan
    assert due_keys(db, "29.09", "12:00") == []            # 2 soatdan keyin — kech


def test_recipients(db):
    assert scheduler.recipients(db, settings(group_id=None)) == []
    assert scheduler.recipients(db, settings()) == [GROUP]
    assert scheduler.recipients(db, settings(report_chat_ids=(7, GROUP))) == [GROUP, 7]
    assert scheduler.recipients(db, settings(reports_to_group=False, report_chat_ids=(7,))) == [7]
    db.set_group_id(-100777)
    assert scheduler.recipients(db, settings()) == [-100777]


class FakeBot:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    async def send_message(self, chat_id, text, **kwargs):
        if self.fail:
            raise NetworkError("offline")
        self.sent.append((chat_id, text))


def run_tick(db, bot, moment, monkeypatch, **overrides):
    monkeypatch.setattr(scheduler, "now", lambda: moment)
    context = SimpleNamespace(bot=bot, bot_data={"db": db, "settings": settings(**overrides)})
    asyncio.run(scheduler.report_tick(context))
    return context


def test_tick_sends_daily_report_once(db, monkeypatch):
    bot = FakeBot()
    run_tick(db, bot, at("29.09", "07:30", 10), monkeypatch)
    assert len(bot.sent) == 1
    chat_id, text = bot.sent[0]
    assert chat_id == GROUP and "Kunlik hisobot</b> — 28.09.2026" in text
    run_tick(db, bot, at("29.09", "07:31"), monkeypatch)
    assert len(bot.sent) == 1


def test_tick_retries_when_telegram_is_unreachable(db, monkeypatch):
    offline = FakeBot(fail=True)
    context = run_tick(db, offline, at("29.09", "10:00"), monkeypatch)
    assert not db.report_sent("shift:1", at("29.09", "10:00").date())
    online = FakeBot()
    monkeypatch.setattr(scheduler, "now", lambda: at("29.09", "10:01"))
    context.bot = online
    asyncio.run(scheduler.report_tick(context))
    assert len(online.sent) == 1 and "1-smena hisoboti" in online.sent[0][1]
    assert db.report_sent("shift:1", at("29.09", "10:00").date())
