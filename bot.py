import os
import sys
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

from services import services
from checker import run_checker, validate_combo, main_menu_keyboard, keywords_keyboard

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ TOKEN set nahi hai!")
    sys.exit(1)

print("✅ Token loaded! Bot starting...")

user_data = {}
SELECT_CATEGORY, UPLOAD_COMBO, ENTER_THREADS = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {"selected_services": set(), "speed_mode": "Medium"}
    context.user_data['selected_services'] = user_data[user_id]["selected_services"]
    await update.message.reply_text("🔥 <b>Hotmail Checker</b>\n\nMain Menu:", parse_mode='HTML', reply_markup=main_menu_keyboard())
    return SELECT_CATEGORY

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {"selected_services": set(), "speed_mode": "Medium"}
    selected = user_data[user_id]["selected_services"]

    if data == "start_checking":
        if not selected:
            await query.edit_message_text("❌ Pehle Keywords select karo!", reply_markup=main_menu_keyboard())
            return SELECT_CATEGORY
        await query.edit_message_text("📤 Send your combo file (.txt)")
        return UPLOAD_COMBO

    elif data == "menu_keywords":
        context.user_data["current_page"] = 0
        await query.edit_message_text("🔑 Keywords - Page 1/5\nSelect services:", reply_markup=keywords_keyboard(selected, 0))

    # ... (baaki button logic same as before)

    elif data == "done_keywords":
        await query.edit_message_text("✅ Keywords saved! Back to Main Menu", reply_markup=main_menu_keyboard())
        return SELECT_CATEGORY

    elif data == "back_to_main":
        await query.edit_message_text("🔥 Hotmail Checker Main Menu", reply_markup=main_menu_keyboard())

    elif data == "menu_speed":
        keyboard = [
            [InlineKeyboardButton("🐢 Slow", callback_data="speed_Slow")],
            [InlineKeyboardButton("⚡ Medium (Recommended)", callback_data="speed_Medium")],
            [InlineKeyboardButton("🚀 Fast", callback_data="speed_Fast")],
            [InlineKeyboardButton("🔥 Turbo", callback_data="speed_Turbo")],
            [InlineKeyboardButton("🧠 Deep Scan", callback_data="speed_Deep Scan")],
            [InlineKeyboardButton("💎 VIP+ Ultra", callback_data="speed_VIP+ Ultra")]
        ]
        await query.edit_message_text("⚡ Choose Speed Mode:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("speed_"):
        mode = data[6:]
        user_data[user_id]["speed_mode"] = mode
        await query.edit_message_text(f"✅ Speed set to {mode}!", reply_markup=main_menu_keyboard())
        return SELECT_CATEGORY

    else:
        await query.edit_message_text("🔥 Coming soon... More features added soon!", reply_markup=main_menu_keyboard())

    return SELECT_CATEGORY

async def receive_combo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document:
        file = await update.message.document.get_file()
        await file.download_to_drive("combo.txt")
        valid_count = validate_combo("combo.txt")
        context.user_data['combo_file'] = "combo.txt"
        await update.message.reply_text(f"✅ Combo received! {valid_count} valid lines.\n\nSend threads number (20-500 recommended, default 200):")
        return ENTER_THREADS
    await update.message.reply_text("Please send combo as .txt file!")
    return UPLOAD_COMBO

async def receive_threads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        threads = int(update.message.text.strip())
        if not 1 <= threads <= 1000:
            threads = 200  # default 200 threads
        context.user_data['threads'] = threads
        await update.message.reply_text(f"🚀 Added to Queue! Position #1\nScanning will start automatically with {threads} threads...")

        threading.Thread(target=run_checker, args=(context.bot, update.effective_chat.id, threads, services), daemon=True).start()
        return ConversationHandler.END
    except:
        await update.message.reply_text("❌ Valid number (1-1000) bhejo. Default 200 use kar raha hoon.")
        context.user_data['threads'] = 200
        threading.Thread(target=run_checker, args=(context.bot, update.effective_chat.id, 200, services), daemon=True).start()
        return ConversationHandler.END

def main():
    if not os.path.exists("Accounts"):
        os.makedirs("Accounts")
    
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_CATEGORY: [CallbackQueryHandler(button_handler)],
            UPLOAD_COMBO: [MessageHandler(filters.Document.ALL, receive_combo)],
            ENTER_THREADS: [MessageHandler(filters.TEXT, receive_threads)],
        },
        fallbacks=[],
    )
    
    app.add_handler(conv_handler)
    print("🤖 KAKASHI Hotmail Checker is running... Send /start")
    app.run_polling()

if __name__ == "__main__":
    main()