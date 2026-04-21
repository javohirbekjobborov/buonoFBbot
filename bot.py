import logging
import json
import os
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          MessageHandler, filters, ContextTypes, ConversationHandler)

TOKEN = "8609597914:AAHt8QdlrI-8lS8lrHtaohbo1_7GBP7j4qE"
GROUP_ID = -1003968130613
STATS_FILE = "stats.json"
TZ = timezone(timedelta(hours=5))  # UTC+5

logging.basicConfig(level=logging.INFO)

CATEGORY, KASSIR, TAOM, TOZALIK, COMMENT, RATING_COMMENT = range(6)

MONTHS_UZ = {
    1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
    5: "May", 6: "Iyun", 7: "Iyul", 8: "Avgust",
    9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr"
}

def get_smena():
    now = datetime.now(TZ)
    hour = now.hour
    if 9 <= hour < 18 or (hour == 18 and now.minute < 30):
        return "1-smena (09:00-18:30)"
    return "2-smena (18:30-04:00)"

def empty_smena_stats():
    return {
        "kassir": {"1":0,"2":0,"3":0,"4":0,"5":0},
        "taom":   {"1":0,"2":0,"3":0,"4":0,"5":0},
        "tozalik":{"1":0,"2":0,"3":0,"4":0,"5":0},
        "suggestion": 0,
        "complaint": 0,
    }

def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    return {"smena1": empty_smena_stats(), "smena2": empty_smena_stats()}

def save_stats(stats):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f)

def add_stat(category, smena_key, kassir=None, taom=None, tozalik=None):
    stats = load_stats()
    s = stats[smena_key]
    if category == "feedback":
        if kassir: s["kassir"][str(kassir)] = s["kassir"].get(str(kassir), 0) + 1
        if taom:   s["taom"][str(taom)]     = s["taom"].get(str(taom), 0) + 1
        if tozalik:s["tozalik"][str(tozalik)]= s["tozalik"].get(str(tozalik), 0) + 1
    elif category == "suggestion":
        s["suggestion"] = s.get("suggestion", 0) + 1
    elif category == "complaint":
        s["complaint"] = s.get("complaint", 0) + 1
    save_stats(stats)

def ortga_tugma(callback):
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Ortga", callback_data=callback)]])

def baho_kb(back_cb):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐", callback_data="1"),
         InlineKeyboardButton("⭐⭐", callback_data="2"),
         InlineKeyboardButton("⭐⭐⭐", callback_data="3")],
        [InlineKeyboardButton("⭐⭐⭐⭐", callback_data="4"),
         InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="5")],
        [InlineKeyboardButton("⬅️ Ortga", callback_data=back_cb)],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kb = [
        [InlineKeyboardButton("⭐ Baho berish", callback_data="feedback")],
        [InlineKeyboardButton("💡 Taklif yuborish", callback_data="suggestion")],
        [InlineKeyboardButton("😡 Shikoyat yuborish", callback_data="complaint")],
    ]
    await update.message.reply_text(
        "👋 Xush kelibsiz! Bo'limni tanlang:",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return CATEGORY

async def category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_start":
        context.user_data.clear()
        kb = [
            [InlineKeyboardButton("⭐ Baho berish", callback_data="feedback")],
            [InlineKeyboardButton("💡 Taklif yuborish", callback_data="suggestion")],
            [InlineKeyboardButton("😡 Shikoyat yuborish", callback_data="complaint")],
        ]
        await query.edit_message_text("👋 Xush kelibsiz! Bo'limni tanlang:", reply_markup=InlineKeyboardMarkup(kb))
        return CATEGORY

    context.user_data["category"] = query.data
    context.user_data["smena"] = get_smena()

    if query.data == "feedback":
        await query.edit_message_text(
            "⭐ *1/3 — Kassir muomalasini baholang:*",
            reply_markup=baho_kb("back_to_start"),
            parse_mode="Markdown"
        )
        return KASSIR

    text = "💡 Taklifingizni yozing:" if query.data == "suggestion" else "😡 Shikoyatingizni yozing:"
    await query.edit_message_text(
        text + "\n\n_(Matn yoki rasm yuborishingiz mumkin)_",
        reply_markup=ortga_tugma("back_to_start"),
        parse_mode="Markdown"
    )
    return COMMENT

async def kassir_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "back_to_start":
        return await category_chosen(update, context)
    context.user_data["kassir"] = int(query.data)
    await query.edit_message_text(
        "🍔 *2/3 — Taom mazasini baholang:*",
        reply_markup=baho_kb("back_to_kassir"),
        parse_mode="Markdown"
    )
    return TAOM

async def taom_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "back_to_kassir":
        await query.edit_message_text(
            "⭐ *1/3 — Kassir muomalasini baholang:*",
            reply_markup=baho_kb("back_to_start"),
            parse_mode="Markdown"
        )
        return KASSIR
    context.user_data["taom"] = int(query.data)
    await query.edit_message_text(
        "🧹 *3/3 — Tozalikni baholang:*",
        reply_markup=baho_kb("back_to_taom"),
        parse_mode="Markdown"
    )
    return TOZALIK

async def tozalik_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "back_to_taom":
        await query.edit_message_text(
            "🍔 *2/3 — Taom mazasini baholang:*",
            reply_markup=baho_kb("back_to_kassir"),
            parse_mode="Markdown"
        )
        return TAOM
    context.user_data["tozalik"] = int(query.data)
    await query.edit_message_text(
        "💬 Izoh yozing, rasm yuboring yoki /skip:\n_(ixtiyoriy)_",
        reply_markup=ortga_tugma("back_to_tozalik"),
        parse_mode="Markdown"
    )
    return RATING_COMMENT

async def rating_comment_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_to_group(update, context, text=update.message.text, photo=None)
    await update.message.reply_text("✅ Bahoyingiz qabul qilindi! Rahmat! 🙏\n/start — qayta boshlash")
    return ConversationHandler.END

async def rating_photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    await send_to_group(update, context, text=update.message.caption, photo=photo.file_id)
    await update.message.reply_text("✅ Bahoyingiz qabul qilindi! Rahmat! 🙏\n/start — qayta boshlash")
    return ConversationHandler.END

async def rating_back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "back_to_tozalik":
        await query.edit_message_text(
            "🧹 *3/3 — Tozalikni baholang:*",
            reply_markup=baho_kb("back_to_taom"),
            parse_mode="Markdown"
        )
        return TOZALIK

async def comment_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_to_group(update, context, text=update.message.text, photo=None)
    await update.message.reply_text("✅ Qabul qilindi! Rahmat! 🙏\n/start — qayta boshlash")
    return ConversationHandler.END

async def photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    await send_to_group(update, context, text=update.message.caption, photo=photo.file_id)
    await update.message.reply_text("✅ Qabul qilindi! Rahmat! 🙏\n/start — qayta boshlash")
    return ConversationHandler.END

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_to_group(update, context, text=None, photo=None)
    await update.message.reply_text("✅ Rahmat! 🙏\n/start — qayta boshlash")
    return ConversationHandler.END

async def send_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE, text, photo):
    user = update.effective_user
    cat = context.user_data.get("category", "feedback")
    smena = context.user_data.get("smena", get_smena())
    smena_key = "smena1" if "1-smena" in smena else "smena2"
    username = f"@{user.username}" if user.username else "yo'q"
    icons = {"feedback": "⭐", "suggestion": "💡", "complaint": "😡"}
    names = {"feedback": "BAHO", "suggestion": "TAKLIF", "complaint": "SHIKOYAT"}

    msg = f"{icons[cat]} *YANGI {names[cat]}*\n"
    msg += f"🕐 {smena}\n\n"
    msg += f"👤 {user.full_name} ({username})\n🆔 `{user.id}`\n"

    if cat == "feedback":
        kassir  = context.user_data.get("kassir")
        taom    = context.user_data.get("taom")
        tozalik = context.user_data.get("tozalik")
        msg += f"\n⭐ Kassir muomalasi: {'⭐'*kassir} ({kassir}/5)\n"
        msg += f"🍔 Taom mazasi: {'⭐'*taom} ({taom}/5)\n"
        msg += f"🧹 Tozalik: {'⭐'*tozalik} ({tozalik}/5)\n"
        add_stat("feedback", smena_key, kassir=kassir, taom=taom, tozalik=tozalik)
    else:
        add_stat(cat, smena_key)

    if text:
        msg += f"\n💬 {text}"

    if photo:
        await context.bot.send_photo(chat_id=GROUP_ID, photo=photo, caption=msg, parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode="Markdown")

def build_report(stats, title):
    def avg(d):
        total = sum(d.values())
        if total == 0: return 0, 0
        score = sum(int(k)*v for k,v in d.items())
        return round(score/total, 1), total

    s1 = stats.get("smena1", empty_smena_stats())
    s2 = stats.get("smena2", empty_smena_stats())

    def smena_block(s, name):
        ka, kt = avg(s["kassir"])
        ta, tt = avg(s["taom"])
        to_, tot = avg(s["tozalik"])
        total_ratings = kt
        block = f"🔷 *{name}*\n"
        block += f"⭐ *Baholar: {total_ratings} ta*\n"
        block += f"  Kassir: {ka}/5 ({kt} ta)\n"
        for i in range(1,6):
            block += f"    {'⭐'*i} — {s['kassir'].get(str(i),0)} ta\n"
        block += f"  Taom: {ta}/5 ({tt} ta)\n"
        for i in range(1,6):
            block += f"    {'⭐'*i} — {s['taom'].get(str(i),0)} ta\n"
        block += f"  Tozalik: {to_}/5 ({tot} ta)\n"
        for i in range(1,6):
            block += f"    {'⭐'*i} — {s['tozalik'].get(str(i),0)} ta\n"
        block += f"💡 Takliflar: {s.get('suggestion',0)} ta\n"
        block += f"😡 Shikoyatlar: {s.get('complaint',0)} ta\n"
        return block

    report = f"📊 *{title}*\n\n"
    report += smena_block(s1, "1-smena (09:00–18:30)")
    report += "\n"
    report += smena_block(s2, "2-smena (18:30–04:00)")
    return report

async def send_monthly_report(context: ContextTypes.DEFAULT_TYPE):
    stats = load_stats()
    now = datetime.now(TZ)
    title = f"OYLIK HISOBOT — {MONTHS_UZ[now.month]} {now.year}"
    report = build_report(stats, title)
    await context.bot.send_message(chat_id=GROUP_ID, text=report, parse_mode="Markdown")
    save_stats({"smena1": empty_smena_stats(), "smena2": empty_smena_stats()})

async def statistika(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = load_stats()
    now = datetime.now(TZ)
    title = f"STATISTIKA — {MONTHS_UZ[now.month]} {now.year} (hozirgi)"
    report = build_report(stats, title)
    await update.message.reply_text(report, parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi. /start")
    return ConversationHandler.END

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()

    app.job_queue.run_monthly(
        send_monthly_report,
        when=datetime.strptime("09:00", "%H:%M").time(),
        day=1
    )

    app.add_handler(CommandHandler("statistika", statistika))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CATEGORY: [CallbackQueryHandler(category_chosen)],
            KASSIR: [CallbackQueryHandler(kassir_chosen)],
            TAOM:   [CallbackQueryHandler(taom_chosen)],
            TOZALIK:[CallbackQueryHandler(tozalik_chosen)],
            RATING_COMMENT: [
                CommandHandler("skip", skip),
                CallbackQueryHandler(rating_back_handler, pattern="^back_to_tozalik$"),
                MessageHandler(filters.PHOTO, rating_photo_received),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rating_comment_received),
            ],
            COMMENT: [
                CommandHandler("skip", skip),
                CallbackQueryHandler(lambda u,c: category_chosen(u,c), pattern="^back_to_start$"),
                MessageHandler(filters.PHOTO, photo_received),
                MessageHandler(filters.TEXT & ~filters.COMMAND, comment_received),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    print("Bot ishga tushdi!")
    app.run_polling()
