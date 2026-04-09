import os
import sys
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

from services import services
from checker import HotmailChecker

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ TOKEN set nahi hai! Railway Variables mein TOKEN daal do.")
    sys.exit(1)

print("✅ Token loaded! Bot starting...")

# ================== CATEGORIES FOR KEYWORDS ==================
CATEGORIES = {
    "Gaming": ["Steam", "Xbox", "PlayStation", "Epic Games", "Rockstar", "EA Sports", "Ubisoft", "Blizzard", "Riot Games", "Valorant", "Genshin Impact", "PUBG", "Free Fire", "Mobile Legends", "Call of Duty", "Fortnite", "Roblox", "Minecraft", "Supercell", "Nintendo"],
    "Streaming": ["Netflix", "Spotify", "Twitch", "YouTube", "Disney+", "Hulu", "Amazon Prime"],
    "Shopping": ["Amazon", "eBay", "Shopify", "Etsy", "AliExpress"],
    "Payment & Finance": ["PayPal", "Binance", "Coinbase"],
    "Social Media": ["Facebook", "Instagram", "TikTok", "Twitter"],
    "Messaging": ["WhatsApp", "Telegram", "Discord"]
}

user_data = {}
SELECT_CATEGORY, UPLOAD_COMBO = range(2)   # Threads step remove kiya

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🚀 Start Checking", callback_data="start_checking")],
        [InlineKeyboardButton("🔑 Keywords", callback_data="menu_keywords"), InlineKeyboardButton("⚡ Speed", callback_data="menu_speed")],
        [InlineKeyboardButton("📊 Stats Menu", callback_data="menu_stats"), InlineKeyboardButton("🎯 My Hits", callback_data="menu_hits")],
        [InlineKeyboardButton("👤 My Profile", callback_data="menu_profile"), InlineKeyboardButton("🏆 Leaderboard", callback_data="menu_leaderboard")],
        [InlineKeyboardButton("🌍 Global", callback_data="menu_global")],
        [InlineKeyboardButton("📈 Live Stats", callback_data="menu_livestats"), InlineKeyboardButton("📋 Queue (0)", callback_data="menu_queue")],
        [InlineKeyboardButton("🔴 Live Activity", callback_data="menu_activity")],
        [InlineKeyboardButton("🎁 Loot Box", callback_data="menu_loot"), InlineKeyboardButton("🔄 Referral", callback_data="menu_referral")],
        [InlineKeyboardButton("🛒 Market", callback_data="menu_market")],
        [InlineKeyboardButton("🌐 Language", callback_data="menu_language"), InlineKeyboardButton("🛠 Tools", callback_data="menu_tools")],
        [InlineKeyboardButton("💎 Buy VIP", callback_data="menu_vip")]
    ]
    return InlineKeyboardMarkup(keyboard)

def keywords_keyboard(selected, page=0, per_page=10):
    all_services = []
    for cat_services in CATEGORIES.values():
        all_services.extend(cat_services)
    all_services = sorted(set(all_services))
    start = page * per_page
    end = start + per_page
    current_page = all_services[start:end]

    keyboard = []
    for srv in current_page:
        status = "✅" if srv in selected else "⬜"
        keyboard.append([InlineKeyboardButton(f"{status} {srv}", callback_data=f"svc_{srv}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"page_{page-1}"))
    if end < len(all_services):
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))
    if nav:
        keyboard.append(nav)

    keyboard.append([
        InlineKeyboardButton("✅ Select All", callback_data="select_all_keywords"),
        InlineKeyboardButton("❌ Deselect All", callback_data="deselect_all_keywords")
    ])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
    keyboard.append([InlineKeyboardButton("✅ Done", callback_data="done_keywords")])

    return InlineKeyboardMarkup(keyboard)

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

    elif data.startswith("page_"):
        page = int(data[5:])
        context.user_data["current_page"] = page
        await query.edit_message_text(f"🔑 Keywords - Page {page+1}/5\nSelect services:", reply_markup=keywords_keyboard(selected, page))

    elif data.startswith("svc_"):
        service = data[4:]
        if service in selected:
            selected.remove(service)
        else:
            selected.add(service)
        page = context.user_data.get("current_page", 0)
        await query.edit_message_text(f"🔑 Keywords - Page {page+1}/5\nSelect services:", reply_markup=keywords_keyboard(selected, page))

    elif data == "select_all_keywords":
        for cat in CATEGORIES.values():
            selected.update(cat)
        page = context.user_data.get("current_page", 0)
        await query.edit_message_text(f"🔑 Keywords - Page {page+1}/5\nSelect services:", reply_markup=keywords_keyboard(selected, page))

    elif data == "deselect_all_keywords":
        selected.clear()
        page = context.user_data.get("current_page", 0)
        await query.edit_message_text(f"🔑 Keywords - Page {page+1}/5\nSelect services:", reply_markup=keywords_keyboard(selected, page))

    elif data == "done_keywords":
        await query.edit_message_text("✅ Keywords saved! Back to Main Menu", reply_markup=main_menu_keyboard())
        return SELECT_CATEGORY

    elif data == "back_to_main":
        await query.edit_message_text("🔥 Hotmail Checker Main Menu", reply_markup=main_menu_keyboard())

    else:
        await query.edit_message_text("🔥 Coming soon... More features added soon!", reply_markup=main_menu_keyboard())

    return SELECT_CATEGORY

def validate_combo(file_path):
    valid = []
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if ":" in line and "@" in line.split(":", 1)[0]:
                valid.append(line)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(valid) + "\n")
    return len(valid)

async def receive_combo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document:
        file = await update.message.document.get_file()
        await file.download_to_drive("combo.txt")
        valid_count = validate_combo("combo.txt")
        context.user_data['combo_file'] = "combo.txt"
        
        await update.message.reply_text(f"✅ Combo received! {valid_count} valid lines.\n\nChecking will start automatically with **200 threads**...")
        
        # Default 200 threads - user ko select nahi karna padega
        threading.Thread(
            target=run_checker, 
            args=(context.bot, update.effective_chat.id, 200, services), 
            daemon=True
        ).start()
        
        return ConversationHandler.END
    
    await update.message.reply_text("Please send combo as .txt file!")
    return UPLOAD_COMBO

def run_checker(bot, chat_id, threads, services):
    checker = HotmailChecker(bot, chat_id, services)
    checker.run(threads=threads)

def main():
    if not os.path.exists("Accounts"):
        os.makedirs("Accounts")
    
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_CATEGORY: [CallbackQueryHandler(button_handler)],
            UPLOAD_COMBO: [MessageHandler(filters.Document.ALL, receive_combo)],
        },
        fallbacks=[],
    )
    
    app.add_handler(conv_handler)
    print("🤖 KAKASHI Hotmail Checker is running... Send /start")
    app.run_polling()

if __name__ == "__main__":
    main()