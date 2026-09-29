"""Botni internetsiz, soxta Telegram serveri bilan boshidan oxirigacha tekshirish."""

import asyncio
import json
from datetime import date

import pytest
from telegram import Update
from telegram.request import BaseRequest

from conftest import at
from tabel.app import build_application
from tabel.config import Settings

GROUP = -1001234567890
OTHER_GROUP = -1009999999999
BOT = {"id": 999, "is_bot": True, "first_name": "Buono Tabel", "username": "buono_tabel_bot",
       "can_join_groups": True, "can_read_all_group_messages": False, "supports_inline_queries": False}
OWNER = {"id": 10, "is_bot": False, "first_name": "Rahbar"}
ALI = {"id": 1, "is_bot": False, "first_name": "Ali", "last_name": "Valiyev", "username": "ali"}
BOBUR = {"id": 2, "is_bot": False, "first_name": "Bobur"}
ADMIN_RIGHTS = dict(can_be_edited=False, is_anonymous=False, can_manage_chat=True, can_delete_messages=True,
                    can_manage_video_chats=True, can_restrict_members=True, can_promote_members=False,
                    can_change_info=True, can_invite_users=True, can_post_stories=False, can_edit_stories=False,
                    can_delete_stories=False)


class FakeTelegram(BaseRequest):
    def __init__(self):
        self.calls = []
        self.next_id = 50_000
        self.bot_is_admin = True

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    async def do_request(self, url, method, request_data=None, **timeouts):
        endpoint = url.rsplit("/", 1)[-1]
        params = request_data.parameters if request_data else {}
        self.calls.append((endpoint, params))
        return 200, json.dumps({"ok": True, "result": self._result(endpoint, params)}).encode()

    def _result(self, endpoint, params):
        if endpoint == "getMe":
            return BOT
        if endpoint == "sendMessage":
            self.next_id += 1
            chat_id = int(params["chat_id"])
            chat = {"id": chat_id, "type": "supergroup" if chat_id < 0 else "private"}
            return {"message_id": self.next_id, "date": 1_790_000_000, "chat": chat, "from": BOT,
                    "text": params["text"]}
        if endpoint == "getChatAdministrators":
            return [{"status": "creator", "user": OWNER, "is_anonymous": False}]
        if endpoint == "getChatMember":
            user_id = int(params["user_id"])
            if user_id == OWNER["id"]:
                return {"status": "creator", "user": OWNER, "is_anonymous": False}
            if user_id == BOT["id"] and self.bot_is_admin:
                return {"status": "administrator", "user": BOT, **ADMIN_RIGHTS}
            return {"status": "member", "user": {"id": user_id, "is_bot": False, "first_name": "X"}}
        return True

    def sent(self):
        return [params for endpoint, params in self.calls if endpoint == "sendMessage"]

    def last_text(self):
        return self.sent()[-1]["text"]


class Harness:
    def __init__(self, app, telegram):
        self.app = app
        self.telegram = telegram
        self.update_id = 0
        self.message_id = 100

    async def send(self, user, chat_id=GROUP, moment=None, reply_to=None, **content):
        self.update_id += 1
        self.message_id += 1
        chat = {"id": chat_id, "type": "private", "first_name": user["first_name"]} if chat_id > 0 else \
            {"id": chat_id, "type": "supergroup", "title": "Buono Tabel"}
        message = {"message_id": self.message_id, "date": int((moment or at("29.09", "12:00")).timestamp()),
                   "chat": chat, "from": user, **content}
        if reply_to is not None:
            message["reply_to_message"] = reply_to
        await self.app.process_update(Update.de_json({"update_id": self.update_id, "message": message},
                                                     self.app.bot))
        return message

    async def video(self, user, moment, **extra):
        note = {"file_id": "vid", "file_unique_id": "vid", "length": 384, "duration": 6}
        return await self.send(user, moment=moment, video_note=note, **extra)

    async def command(self, user, text, chat_id=GROUP, reply_to=None):
        name = text.split()[0]
        return await self.send(user, chat_id=chat_id, reply_to=reply_to, text=text,
                               entities=[{"type": "bot_command", "offset": 0, "length": len(name)}])

    def visits(self, day="29.09"):
        dd, mm = day.split(".")
        return self.app.bot_data["db"].visits_on(date(2026, int(mm), int(dd)))


@pytest.fixture
def bot(db):
    telegram = FakeTelegram()
    settings = Settings(token="123:TEST", group_id=None, admin_ids=frozenset(), report_chat_ids=(),
                        reports_to_group=True, db_path=":memory:")
    app = build_application(settings, db, request=telegram)
    asyncio.run(app.initialize())
    yield Harness(app, telegram)
    asyncio.run(app.shutdown())


def test_full_day_in_the_group(bot):
    async def scenario():
        # Guruh ulanmaguncha videolar hisobga olinmaydi
        await bot.video(ALI, at("29.09", "08:20"))
        assert bot.visits() == [] and bot.telegram.sent() == []

        # Oddiy a'zo guruhni ulay olmaydi, guruh egasi ulaydi
        await bot.command(BOBUR, "/ulash")
        assert "faqat rahbarlar" in bot.telegram.last_text()
        await bot.command(OWNER, "/ulash")
        assert "Tabel guruhi</b> sifatida ulandi" in bot.telegram.last_text()
        assert "admin</b> qiling" not in bot.telegram.last_text()

        # Ali 08:36 da keldi — kechikdi, Bobur 08:35 da — vaqtida
        ali_in = await bot.video(ALI, at("29.09", "08:36"))
        reply = bot.telegram.sent()[-1]
        assert 'href="tg://user?id=1">Ali Valiyev</a>' in reply["text"]
        assert "6 daqiqa" in reply["text"] and "Bu yaxshi emas" in reply["text"]
        assert reply["reply_parameters"]["message_id"] == ali_in["message_id"]
        assert reply["reply_parameters"]["allow_sending_without_reply"] is True
        assert reply["parse_mode"] == "HTML"
        await bot.video(BOBUR, at("29.09", "08:35", 59))
        assert "kechik" not in bot.telegram.last_text()
        assert "1-smena (08:30–18:30)" in bot.telegram.last_text()

        # Takroriy video, forward qilingan video va boshqa guruhdagi video
        await bot.video(ALI, at("29.09", "08:40"))
        assert "kelganingiz 08:36da qayd etilgan" in bot.telegram.last_text()
        await bot.video(BOBUR, at("29.09", "09:00"),
                        forward_origin={"type": "user", "date": 1_790_000_000, "sender_user": BOBUR})
        assert "forward qilingan video qabul qilinmaydi" in bot.telegram.last_text()
        count = len(bot.telegram.sent())
        await bot.send(ALI, chat_id=OTHER_GROUP, video_note={"file_id": "v", "file_unique_id": "v", "length": 1,
                                                             "duration": 1})
        assert len(bot.telegram.sent()) == count

        # Ketish: Ali 18:31 da (vaqtida), Bobur 18:05 da (erta)
        await bot.video(ALI, at("29.09", "18:31"))
        assert "smenangiz yakunlandi" in bot.telegram.last_text()
        await bot.video(BOBUR, at("29.09", "18:05"))
        assert "25 daqiqa erta" in bot.telegram.last_text()

        visits = {v.user_id: v for v in bot.visits()}
        assert visits[1].late_min == 6 and visits[1].check_out == at("29.09", "18:31")
        assert visits[2].late_min == 5 and visits[2].early_min == 25

    asyncio.run(scenario())


def test_admin_corrections_and_reports(bot):
    async def scenario():
        await bot.command(OWNER, "/ulash")
        # Ali 11:10 da keldi — bot O'rta smena deb oldi, aslida 1-smenada edi
        await bot.video(ALI, at("29.09", "11:10"))
        bot_reply = bot.telegram.sent()[-1]
        assert "O'rta smena" in bot_reply["text"]
        reply_message = {"message_id": bot.telegram.next_id, "date": 1_790_000_000,
                         "chat": {"id": GROUP, "type": "supergroup"}, "from": BOT, "text": bot_reply["text"]}

        await bot.command(BOBUR, "/smena 1", reply_to=reply_message)
        assert "faqat rahbarlar" in bot.telegram.last_text()
        await bot.command(OWNER, "/smena 1", reply_to=reply_message)
        assert "Smena o'zgartirildi" in bot.telegram.last_text()
        assert "2 soat 40 daqiqa kechikish" in bot.telegram.last_text()
        assert bot.visits()[0].shift_key == "1"

        await bot.command(OWNER, "/smena", reply_to=reply_message)
        assert "/smena 1" in bot.telegram.last_text()
        await bot.command(OWNER, "/ochir")
        assert "reply" in bot.telegram.last_text()

        # Ism o'zgartirish va o'chirish
        await bot.command(OWNER, "/ism Valiyev Ali", reply_to=reply_message)
        assert "Valiyev Ali" in bot.telegram.last_text()
        await bot.command(OWNER, "/ochir", reply_to=reply_message)
        assert "Yozuv o'chirildi: Valiyev Ali" in bot.telegram.last_text()
        assert bot.visits() == []

        # Rahbar shaxsiy chatda hisobot so'raydi, oddiy xodim — yo'q
        await bot.command(OWNER, "/kecha", chat_id=OWNER["id"])
        assert "Kunlik hisobot" in bot.telegram.last_text()
        await bot.command(OWNER, "/hisobot 29.09.2026", chat_id=OWNER["id"])
        assert "29.09.2026, Seshanba" in bot.telegram.last_text()
        await bot.command(OWNER, "/oylik 09.2026", chat_id=OWNER["id"])
        assert "Sentabr 2026" in bot.telegram.last_text()
        await bot.command(OWNER, "/xodimlar", chat_id=OWNER["id"])
        assert "Valiyev Ali (Ali Valiyev, @ali)" in bot.telegram.last_text()
        await bot.command(OWNER, "/start", chat_id=OWNER["id"])
        assert "Rahbar buyruqlari" in bot.telegram.last_text()

        await bot.command(BOBUR, "/bugun", chat_id=BOBUR["id"])
        assert "faqat rahbarlar" in bot.telegram.last_text()
        await bot.command(BOBUR, "/start", chat_id=BOBUR["id"])
        assert "yumaloq video yuboring" in bot.telegram.last_text()

    asyncio.run(scenario())


def test_keldi_and_ketdi_fix_misread_videos(bot):
    async def scenario():
        await bot.command(OWNER, "/ulash")
        await bot.video(ALI, at("29.09", "08:30"))
        accidental = await bot.video(ALI, at("29.09", "09:30"))   # tasodifan — ketish deb olindi
        assert "erta tugatdingiz" in bot.telegram.last_text()
        real_exit = await bot.video(ALI, at("29.09", "18:30"))   # yangi kelish deb olindi
        assert "2-smena" in bot.telegram.last_text()

        await bot.command(OWNER, "/ketdi", reply_to=real_exit)
        assert "«Ketdi» deb belgilandi" in bot.telegram.last_text()
        visits = bot.visits()
        assert len(visits) == 1
        assert visits[0].check_out == at("29.09", "18:30") and visits[0].early_min == 0

        await bot.command(OWNER, "/keldi", reply_to=accidental)
        assert "«Keldi» deb belgilandi" in bot.telegram.last_text()
        assert len(bot.visits()) == 2

    asyncio.run(scenario())


def test_video_in_private_chat_and_regular_video(bot):
    async def scenario():
        await bot.command(OWNER, "/ulash")
        await bot.send(ALI, chat_id=ALI["id"],
                       video_note={"file_id": "v", "file_unique_id": "v", "length": 1, "duration": 1})
        assert "guruhiga yuboring" in bot.telegram.last_text()
        await bot.send(ALI, video={"file_id": "v", "file_unique_id": "v", "width": 1, "height": 1, "duration": 1})
        assert "oddiy video" in bot.telegram.last_text()
        count = len(bot.telegram.sent())
        await bot.send(OWNER, video={"file_id": "v", "file_unique_id": "v", "width": 1, "height": 1, "duration": 1})
        assert len(bot.telegram.sent()) == count

    asyncio.run(scenario())


def test_edited_video_message_is_ignored(bot):
    async def scenario():
        await bot.command(OWNER, "/ulash")
        count = len(bot.telegram.sent())
        edited = {"message_id": 7, "date": int(at("29.09", "08:30").timestamp()), "edit_date": 1_790_000_100,
                  "chat": {"id": GROUP, "type": "supergroup"}, "from": ALI,
                  "video_note": {"file_id": "v", "file_unique_id": "v", "length": 1, "duration": 1}}
        await bot.app.process_update(Update.de_json({"update_id": 999, "edited_message": edited}, bot.app.bot))
        assert len(bot.telegram.sent()) == count and bot.visits() == []

    asyncio.run(scenario())


def test_bind_warns_when_bot_cannot_see_videos(bot):
    async def scenario():
        bot.telegram.bot_is_admin = False
        await bot.command(OWNER, "/ulash")
        assert "Tabel guruhi</b> sifatida ulandi" in bot.telegram.last_text()
        assert "admin</b> qiling" in bot.telegram.last_text()

    asyncio.run(scenario())


def test_anonymous_group_admin_can_bind_and_request_reports(bot):
    anonymous = {"id": 1087968824, "is_bot": True, "first_name": "Group", "username": "GroupAnonymousBot"}
    as_group = {"id": GROUP, "type": "supergroup", "title": "Buono Tabel"}

    async def scenario():
        await bot.send(anonymous, text="/ulash", sender_chat=as_group,
                       entities=[{"type": "bot_command", "offset": 0, "length": 6}])
        assert "Tabel guruhi</b> sifatida ulandi" in bot.telegram.last_text()
        await bot.send(anonymous, text="/bugun", sender_chat=as_group,
                       entities=[{"type": "bot_command", "offset": 0, "length": 6}])
        assert "Kunlik hisobot" in bot.telegram.last_text()
        # Anonim adminning videosi xodim videosi hisoblanmaydi
        await bot.send(anonymous, sender_chat=as_group,
                       video_note={"file_id": "v", "file_unique_id": "v", "length": 1, "duration": 1})
        assert bot.visits() == []

    asyncio.run(scenario())


def test_group_migration_keeps_binding(bot):
    async def scenario():
        await bot.command(OWNER, "/ulash")
        await bot.send(OWNER, migrate_to_chat_id=OTHER_GROUP)
        assert bot.app.bot_data["db"].group_id() == OTHER_GROUP

    asyncio.run(scenario())
