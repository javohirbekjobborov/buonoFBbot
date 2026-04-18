import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

TOKEN = "8609597914:AAEDg1sOrQ0EjSILTXJeBzl4JNv9fe-V7cE"
GROUP_ID = -1003968130613

logging.basicConfig(level=logging.INFO)

RATING, COMMENT, CATEGORY = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⭐ Baho berish", callback_data="feedback")],
        [InlineKeyboardButton("💡 Taklif yuborish", callback_data="suggestion")],
        [InlineKeyboardButton("😡 Shikoyat yuborish", callback_data="complaint")],
    ]
    await update.message.reply_text(
        "👋 Xush kelibsiz!\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CATEGORY

async def category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['category'] = query.data

    if query.data == "feedback":
        keyboard = [
            [InlineKeyboardButton("⭐", callback_data="1"),
             InlineKeyboardButton("⭐⭐", callback_data="2"),
             InlineKeyboardButton("⭐⭐⭐", callback_data="3")],
            [InlineKeyboardButton("⭐⭐⭐⭐", callback_data="4"),
             InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="5")],
        ]
        await query.edit_message_text(
            "🌟 Xizmatimizni baholang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return RATING
    else:
        text = "💡 Taklifingizni yozing:" if query.data == "suggestion" else "😡 Shikoyatingizni yozing:"
        await query.edit_message_text(text)
        return COMMENT

async def rating_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['rating'] = query.data
    stars = "⭐" * int(query.data)
    await query.edit_message_text(
        f"Siz {stars} ({query.data}/5) baho berdingiz!\n\n"
        f"📝 Izoh qoldirmoqchimisiz? (ixtiyoriy)\n"
        f"Izoхsiz davom etish uchun /skip yuboring"
    )
    return COMMENT

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_to_group(update, context, comment=None)
    await update.message.reply_text("✅ Bahoyingiz qabul qilindi! Rahmat! 🙏\n\n/start — qayta boshlash")
    return ConversationHandler.END

async def comment_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_to_group(update, context, comment=update.message.text)
    category = context.user_data.get('category', 'feedback')
    msgs = {
        "feedback": "✅ Bahoyingiz va izohingiz qabul qilindi! Rahmat! 🙏",
        "suggestion": "✅ Taklifingiz qabul qilindi! Rahmat! 🙏",
        "complaint": "✅ Shikoyatingiz qabul qilindi. Ko'rib chiqamiz! 🙏"
    }
    await update.message.reply_text(msgs.get(category, "✅ Qabul qilindi!") + "\n\n/start — qayta boshlash")
    return ConversationHandler.END

async def send_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE, comment):
    user = update.effective_user
    category = context.user_data.get('category', 'feedback')
    rating = context.user_data.get('rating', None)

    icons = {"feedback": "⭐", "suggestion": "💡", "complaint": "😡"}
    names = {"feedback": "BAHO", "suggestion": "TAKLIF", "complaint": "SHIKOYAT"}

    username = f"@{user.username}" if user.username else "username yo'q"
    msg = f"{icons[category]} *YANGI {names[category]}*\n\n"
    msg += f"👤 Mijoz: {user.full_name} ({username})\n"
    msg += f"🆔 ID: `{user.id}`\n"

    if rating:
        msg += f"⭐ Baho: {'⭐' * int(rating)} ({rating}/5)\n"
    if comment:
        msg += f"\n💬 Izoh:\n{comment}"

    await context.bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode='Markdown')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi. /start — qayta boshlash")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CATEGORY: [CallbackQueryHandler(category_chosen)],
            RATING: [CallbackQueryHandler(rating_chosen)],
            COMMENT: [
                CommandHandler("skip", skip),
                MessageHandler(filters.TEXT & ~filters.COMMAND, comment_received)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv)
    print("✅ Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
