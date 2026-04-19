import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          MessageHandler, filters, ContextTypes, ConversationHandler)

TOKEN = "8609597914:AAHt8QdlrI-8lS8lrHtaohbo1_7GBP7j4qE"
GROUP_ID = -1003968130613
logging.basicConfig(level=logging.INFO)
CATEGORY, RATING, COMMENT = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("⭐ Baho berish", callback_data="feedback")],
          [InlineKeyboardButton("💡 Taklif yuborish", callback_data="suggestion")],
          [InlineKeyboardButton("😡 Shikoyat yuborish", callback_data="complaint")]]
    await update.message.reply_text("👋 Bo'limni tanlang:", reply_markup=InlineKeyboardMarkup(kb))
    return CATEGORY

async def category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["category"] = q.data
    if q.data == "feedback":
        kb = [[InlineKeyboardButton("⭐", callback_data="1"), InlineKeyboardButton("⭐⭐", callback_data="2"), InlineKeyboardButton("⭐⭐⭐", callback_data="3")],
              [InlineKeyboardButton("⭐⭐⭐⭐", callback_data="4"), InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="5")]]
        await q.edit_message_text("Bahoni tanlang:", reply_markup=InlineKeyboardMarkup(kb))
        return RATING
    await q.edit_message_text("💡 Taklifingizni yozing:" if q.data == "suggestion" else "😡 Shikoyatingizni yozing:")
    return COMMENT

async def rating_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["rating"] = q.data
    await q.edit_message_text(f"{'⭐'*int(q.data)} ({q.data}/5)\n\nIzoh yozing yoki /skip:")
    return COMMENT

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_to_group(update, context, None)
    await update.message.reply_text("✅ Rahmat! 🙏")
    return ConversationHandler.END

async def comment_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_to_group(update, context, update.message.text)
    await update.message.reply_text("✅ Qabul qilindi! Rahmat! 🙏")
    return ConversationHandler.END

async def send_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE, comment):
    user = update.effective_user
    cat = context.user_data.get("category", "feedback")
    rating = context.user_data.get("rating")
    icons = {"feedback": "⭐", "suggestion": "💡", "complaint": "😡"}
    names = {"feedback": "BAHO", "suggestion": "TAKLIF", "complaint": "SHIKOYAT"}
    text = f"{icons[cat]} *YANGI {names[cat]}*\n\n"
    text += f"👤 {user.full_name} (@{user.username or 'yoq'})\n🆔 `{user.id}`\n"
    if rating:
        text += f"⭐ {'⭐'*int(rating)} ({rating}/5)\n"
    if comment:
        text += f"\n💬 {comment}"
    await context.bot.send_message(chat_id=GROUP_ID, text=text, parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CATEGORY: [CallbackQueryHandler(category_chosen)],
            RATING: [CallbackQueryHandler(rating_chosen)],
            COMMENT: [CommandHandler("skip", skip),
                      MessageHandler(filters.TEXT & ~filters.COMMAND, comment_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    print("Bot ishga tushdi!")
    app.run_polling()
