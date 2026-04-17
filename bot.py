import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ===== SOZLAMALAR =====
TOKEN = "8609597914:AAEDg1sOrQ0EjSILTXJeBzl4JNv9fe-V7cE"
GROUP_ID = -1003968130613
# ======================

logging.basicConfig(level=logging.INFO)

RATING, COMMENT, CATEGORY = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⭐ Baho berish", callback_data="feedback")],
        [InlineKeyboardButton("📝 Taklif yuborish", callback_data="suggestion")],
        [InlineKeyboardButton("😡 Shikoyat yuborish", callback_data="complaint")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Xush kelibsiz!\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=reply_markup
    )
    return CATEGORY

async def category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    category = query.data
    context.user_data['category'] = category
    
    if category == "feedback":
        keyboard = [
            [InlineKeyboardButton("⭐", callback_data="1"),
             InlineKeyboardButton("⭐⭐", callback_data="2"),
             InlineKeyboardButton("⭐⭐⭐", callback_data="3")],
            [InlineKeyboardButton("⭐⭐⭐⭐", callback_data="4"),
             InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="5")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🌟 Xizmatimizni baholang:\n\n1 ⭐ - Juda yomon\n5 ⭐⭐⭐⭐⭐ - Ajoyib",
            reply_markup=reply_markup
        )
        return RATING
    else:
        if category == "suggestion":
            text = "💡 Taklifingizni yozing:"
        else:
            text = "😡 Shikoyatingizni batafsil yozing:"
        await query.edit_message_text(text)
        return COMMENT

async def rating_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    rating = query.data
    context.user_data['rating'] = rating
    stars = "⭐" * int(rating)
    
    await query.edit_message_text(
        f"Siz {stars} ({rating}/5) baho berdingiz!\n\n"
        f"📝 Izoh qoldirmoqchimisiz? (Ixtiyoriy)\n"
        f"Izoхsiz davom etish uchun /skip yuboring"
    )
    return COMMENT

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_to_group(update, context, comment=None)
    await update.message.reply_text(
        "✅ Bahoyingiz qabul qilindi! Rahmat! 🙏\n\nYangi fikr bildirish uchun /start bosing"
    )
    return ConversationHandler.END

async def comment_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comment = update.message.text
    await send_to_group(update, context, comment=comment)
    
    category = context.user_data.get('category', 'feedback')
    if category == "feedback":
        msg = "✅ Bahoyingiz va izohingiz qabul qilindi! Rahmat! 🙏"
    elif category == "suggestion":
        msg = "✅ Taklifingiz qabul qilindi! Rahmat! 🙏"
    else:
        msg = "✅ Shikoyatingiz qabul qilindi. Ko'rib chiqamiz! 🙏"
    
    await update.message.reply_text(msg + "\n\nYangi fikr bildirish uchun /start bosing")
    return ConversationHandler.END

async def send_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE, comment):
    user = update.effective_user
    category = context.user_data.get('category', 'feedback')
    rating = context.user_data.get('rating', None)
    
    if category == "feedback":
        emoji = "⭐"
        cat_text = "BAHO"
    elif category == "suggestion":
        emoji = "💡"
        cat_text = "TAKLIF"
    else:
        emoji = "😡"
        cat_text = "SHIKOYAT"
    
    username = f"@{user.username}" if user.username else "username yo'q"
    full_name = user.full_name or "Ism yo'q"
    
    message = f"{emoji} *YANGI {cat_text}*\n\n"
    message += f"👤 Mijoz: {full_name} ({username})\n"
    message += f"🆔 ID: `{user.id}`\n"
    
    if rating:
        stars = "⭐" * int(rating)
        message += f"⭐ Baho: {stars} ({rating}/5)\n"
    
    if comment:
        message += f"\n💬 Izoh:\n{comment}"
    
    await context.bot.send_message(
        chat_id=GROUP_ID,
        text=message,
        parse_mode='Markdown'
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi. Qaytadan boshlash uchun /start bosing")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
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
    
    app.add_handler(conv_handler)
    print("✅ Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
