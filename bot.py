import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          MessageHandler, filters, ContextTypes, ConversationHandler)

TOKEN = "8609597914:AAEDg1sOrQ0EjSILTXJeBzl4JNv9fe-V7cE"
GROUP_ID = -1003968130613

logging.basicConfig(level=logging.INFO)
CATEGORY, RATING, COMMENT = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("⭐ Baho berish", callback_data="feedback")],
          [InlineKeyboardButton("💡 Taklif yuborish", callback_data="suggestion")],
          [InlineKeyboardButton("😡 Shikoyat yuborish", callback_data="complaint")]]
    await update.message.reply_text("👋 Xush kelibsiz! Bo'limni tanlang:",
                                    reply_markup=InlineKeyboardMarkup(kb))
    return CATEGORY

async def category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["category"] = q.data
    if q.data == "feedback":
        kb = [[InlineKeyboardButton("⭐", callback_data="1"),
               InlineKeyboardButton("⭐⭐", callback_data="2"),
               InlineKeyboardButton("⭐⭐⭐", callback_data="3")],
              [InlineKeyboardButton("⭐⭐⭐⭐", callback_data="4"),
               InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="5")]]
        await q.edit_message_text("Bahoni tanlang:", reply_markup=InlineKeyboardMarkup(kb))
        return RATING
    text = "💡 Taklifingizni yozing:" if q.data == "suggestion" else "😡 Shikoyatingizni yozing:"
    await q.edit_message_text(text)
    return COMMENT

async def rating_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["rating"] = q.data
    await q.edit_message_text(f"{'⭐'*int(q.data)} ({q.data}/5) baho!\n\nIzoh yozing yoki /skip:")
    return COMMENT

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_to_group(update, context, None)
    await update.message.reply_text("✅ Rahmat! 🙏\n/start — qayta boshlash")
    return ConversationHandler.END

async def comment_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_to_group(update, context, update.message.text)
    await update.message.reply_text("✅ Qabul qilindi! Rahmat! 🙏\n/start — qayta boshlash")
    return ConversationHandler.END

async def send_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE, comment):
    user = update.effective_user
    cat = context.user_data.get("category", "feedback")
    rating = context.user_data.get("rating")
    icons = {"feedback": "⭐", "suggestion": "💡", "complaint": "😡"}
    names = {"feedback": "BAHO", "suggestion": "TAKLIF", "complaint": "SHIKOYAT"}
    username = f"@{user.username}" if user.username else "yo'q"
    text = f"{icons[cat]} *YANGI {names[cat]}*\n\n"
    text += f"👤 {user.full_name} ({username})\n🆔 `{user.id}`\n"
    if rating:
        text += f"⭐ {'⭐'*int(rating)} ({rating}/5)\n"
    if comment:
        text += f"\n💬 {comment}"
    await context.bot.send_message(chat_id=GROUP_ID, text=text, parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi. /start")
    return ConversationHandler.END

async def run():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
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
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(run())
