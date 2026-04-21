import logging
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          MessageHandler, filters, ContextTypes, ConversationHandler)

TOKEN = "8609597914:AAHt8QdlrI-8lS8lrHtaohbo1_7GBP7j4qE"
GROUP_ID = -1003968130613
STATS_FILE = "stats.json"

logging.basicConfig(level=logging.INFO)
CATEGORY, RATING, COMMENT = range(3)

def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    return {
        "ratings": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
        "suggestion": 0,
        "complaint": 0,
        "month": datetime.now().month
    }

def save_stats(stats):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f)

def add_stat(category, rating=None):
    stats = load_stats()
    if category == "feedback" and rating:
        stats["ratings"][str(rating)] = stats["ratings"].get(str(rating), 0) + 1
    elif category == "suggestion":
        stats["suggestion"] = stats.get("suggestion", 0) + 1
    elif category == "complaint":
        stats["complaint"] = stats.get("complaint", 0) + 1
    save_stats(stats)

def ortga_tugma(callback):
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Ortga", callback_data=callback)]])

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

    if query.data == "feedback":
        kb = [
            [InlineKeyboardButton("⭐", callback_data="1"),
             InlineKeyboardButton("⭐⭐", callback_data="2"),
             InlineKeyboardButton("⭐⭐⭐", callback_data="3")],
            [InlineKeyboardButton("⭐⭐⭐⭐", callback_data="4"),
             InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="5")],
            [InlineKeyboardButton("⬅️ Ortga", callback_data="back_to_start")],
        ]
        await query.edit_message_text("🌟 Bahoni tanlang:", reply_markup=InlineKeyboardMarkup(kb))
        return RATING

    text = "💡 Taklifingizni yozing:" if query.data == "suggestion" else "😡 Shikoyatingizni yozing:"
    await query.edit_message_text(
        text + "\n\n_(Matn yoki rasm yuborishingiz mumkin)_",
        reply_markup=ortga_tugma("back_to_start"),
        parse_mode="Markdown"
    )
    return COMMENT

async def rating_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["rating"] = query.data
    await query.edit_message_text(
        f"{'⭐' * int(query.data)} ({query.data}/5) baho!\n\n"
        f"Izoh yozing, rasm yuboring yoki /skip:\n"
        f"_(Matn yoki rasm yuborishingiz mumkin)_",
        reply_markup=ortga_tugma("back_to_rating"),
        parse_mode="Markdown"
    )
    return COMMENT

async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_rating":
        kb = [
            [InlineKeyboardButton("⭐", callback_data="1"),
             InlineKeyboardButton("⭐⭐", callback_data="2"),
             InlineKeyboardButton("⭐⭐⭐", callback_data="3")],
            [InlineKeyboardButton("⭐⭐⭐⭐", callback_data="4"),
             InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="5")],
            [InlineKeyboardButton("⬅️ Ortga", callback_data="back_to_start")],
        ]
        await query.edit_message_text("🌟 Bahoni tanlang:", reply_markup=InlineKeyboardMarkup(kb))
        return RATING

    if query.data == "back_to_start":
        context.user_data.clear()
        kb = [
            [InlineKeyboardButton("⭐ Baho berish", callback_data="feedback")],
            [InlineKeyboardButton("💡 Taklif yuborish", callback_data="suggestion")],
            [InlineKeyboardButton("😡 Shikoyat yuborish", callback_data="complaint")],
        ]
        await query.edit_message_text("👋 Xush kelibsiz! Bo'limni tanlang:", reply_markup=InlineKeyboardMarkup(kb))
        return CATEGORY

async def comment_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_to_group(update, context, text=update.message.text, photo=None)
    await update.message.reply_text("✅ Qabul qilindi! Rahmat! 🙏\n/start — qayta boshlash")
    return ConversationHandler.END

async def photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    caption = update.message.caption or None
    await send_to_group(update, context, text=caption, photo=photo.file_id)
    await update.message.reply_text("✅ Qabul qilindi! Rahmat! 🙏\n/start — qayta boshlash")
    return ConversationHandler.END

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_to_group(update, context, text=None, photo=None)
    await update.message.reply_text("✅ Rahmat! 🙏\n/start — qayta boshlash")
    return ConversationHandler.END

async def send_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE, text, photo):
    user = update.effective_user
    cat = context.user_data.get("category", "feedback")
    rating = context.user_data.get("rating")
    icons = {"feedback": "⭐", "suggestion": "💡", "complaint": "😡"}
    names = {"feedback": "BAHO", "suggestion": "TAKLIF", "complaint": "SHIKOYAT"}
    username = f"@{user.username}" if user.username else "yo'q"

    msg = f"{icons[cat]} *YANGI {names[cat]}*\n\n"
    msg += f"👤 {user.full_name} ({username})\n🆔 `{user.id}`\n"
    if rating:
        msg += f"⭐ {'⭐' * int(rating)} ({rating}/5)\n"
    if text:
        msg += f"\n💬 {text}"

    add_stat(cat, rating)

    if photo:
        await context.bot.send_photo(
            chat_id=GROUP_ID,
            photo=photo,
            caption=msg,
            parse_mode="Markdown"
        )
    else:
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=msg,
            parse_mode="Markdown"
        )

async def send_monthly_report(context: ContextTypes.DEFAULT_TYPE):
    stats = load_stats()
    now = datetime.now()

    months_uz = {
        1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
        5: "May", 6: "Iyun", 7: "Iyul", 8: "Avgust",
        9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr"
    }
    month_name = f"{months_uz[now.month]} {now.year}"
    ratings = stats.get("ratings", {})
    total_ratings = sum(ratings.values())

    # O'rtacha baho hisoblash
    total_score = sum(int(k) * v for k, v in ratings.items())
    avg = round(total_score / total_ratings, 1) if total_ratings > 0 else 0

    report = f"📊 *OYLIK HISOBOT — {month_name}*\n\n"
    report += f"⭐ *Baholar: {total_ratings} ta*\n"
    for i in range(1, 6):
        count = ratings.get(str(i), 0)
        bar = "▓" * count if count <= 20 else "▓" * 20 + f"(+{count-20})"
        report += f"  {'⭐'*i} — {count} ta {bar}\n"
    report += f"  📈 O'rtacha baho: *{avg}/5*\n\n"
    report += f"💡 *Takliflar: {stats.get('suggestion', 0)} ta*\n"
    report += f"😡 *Shikoyatlar: {stats.get('complaint', 0)} ta*\n\n"
    total = total_ratings + stats.get('suggestion', 0) + stats.get('complaint', 0)
    report += f"📌 *Jami: {total} ta*"

    await context.bot.send_message(
        chat_id=GROUP_ID,
        text=report,
        parse_mode="Markdown"
    )

    save_stats({
        "ratings": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
        "suggestion": 0,
        "complaint": 0,
        "month": now.month
    })

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

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CATEGORY: [CallbackQueryHandler(category_chosen)],
            RATING: [
                CallbackQueryHandler(rating_chosen, pattern="^[1-5]$"),
                CallbackQueryHandler(category_chosen, pattern="^back_to_start$"),
            ],
            COMMENT: [
                CommandHandler("skip", skip),
                CallbackQueryHandler(back_handler, pattern="^back_to_"),
                MessageHandler(filters.PHOTO, photo_received),
                MessageHandler(filters.TEXT & ~filters.COMMAND, comment_received),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    print("Bot ishga tushdi!")
    app.run_polling()
